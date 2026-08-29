"""ToolBus invoke pipeline, draft-commit, observations, and cutover meta-tests."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from ai_team.tools.bus import (
    ToolSpec,
    get_bus,
    observation_to_agent_text,
    reset_bus,
)
from ai_team.tools.draft import commit_draft, stage_draft
from ai_team.tools.kinds import SUMMARY_MAX_CHARS, ToolObservation, ToolRequest

pytestmark = pytest.mark.eval_unit


@pytest.fixture
def bus_ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ws = tmp_path / "workspace"
    out = tmp_path / "output"
    ws.mkdir()
    out.mkdir()
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
    from ai_team.config.settings import reload_settings

    reload_settings()
    reset_bus()
    yield ws
    reset_bus()


def _echo_handler(args: dict, request: ToolRequest) -> ToolObservation:
    _ = request
    return ToolObservation(
        ok=True,
        code="ok",
        summary=str(args.get("msg") or ""),
        tool="echo",
        kind="read",
        risk_class="low",
    )


def test_not_found() -> None:
    bus = reset_bus(empty=True)
    obs = bus.invoke(ToolRequest(tool="nope", args={}))
    assert obs.code == "not_found"
    assert obs.ok is False


def test_schema_invalid() -> None:
    from pydantic import BaseModel, Field

    class NeedMsg(BaseModel):
        msg: str = Field(...)

    bus = reset_bus(empty=True)
    bus.register(
        ToolSpec(
            name="echo",
            kind="read",
            risk_class="low",
            args_schema=NeedMsg,
            handler=_echo_handler,
        )
    )
    obs = bus.invoke(ToolRequest(tool="echo", args={}))
    assert obs.code == "schema_invalid"
    assert obs.ok is False


def test_permission_denied() -> None:
    from pydantic import BaseModel

    class Empty(BaseModel):
        pass

    bus = reset_bus(empty=True)
    bus.register(
        ToolSpec(
            name="echo",
            kind="read",
            risk_class="low",
            args_schema=Empty,
            handler=_echo_handler,
            allow_roles=["architect"],
        )
    )
    obs = bus.invoke(ToolRequest(tool="echo", args={}, agent_role="qa_engineer"))
    assert obs.code == "permission_denied"


def test_ok_and_summary_cap() -> None:
    from pydantic import BaseModel, Field

    class NeedMsg(BaseModel):
        msg: str = Field(...)

    def huge2(args: dict, request: ToolRequest) -> ToolObservation:
        _ = request
        _ = args
        return ToolObservation(
            ok=True,
            code="ok",
            summary="y" * (SUMMARY_MAX_CHARS + 50),
            tool="echo",
            kind="read",
            risk_class="low",
        )

    bus = reset_bus(empty=True)
    bus.register(
        ToolSpec(
            name="echo2",
            kind="read",
            risk_class="low",
            args_schema=NeedMsg,
            handler=huge2,
        )
    )
    obs = bus.invoke(ToolRequest(tool="echo2", args={"msg": "hi"}))
    assert obs.ok is True
    assert len(obs.summary) <= SUMMARY_MAX_CHARS
    assert obs.detail.get("summary_truncated") is True
    assert "summary://truncated" in obs.artifact_refs
    text = observation_to_agent_text(obs)
    assert len(text) <= SUMMARY_MAX_CHARS


def test_builtin_registry_names(bus_ws: Path) -> None:
    _ = bus_ws
    names = get_bus().registered_names()
    for expected in (
        "read_file",
        "write_file",
        "delete_file",
        "execute_shell",
        "commit_write",
        "list_directory",
    ):
        assert expected in names


def test_audit_spans_parseable(bus_ws: Path, tmp_path: Path) -> None:
    from evals.trace.parsers import parse_audit_jsonl

    bus = get_bus()
    bus.invoke(ToolRequest(tool="list_directory", args={"path": "."}))
    audit = bus_ws / "logs" / "audit.jsonl"
    assert audit.is_file()
    spans, warnings = parse_audit_jsonl(audit)
    drop = [w for w in warnings if "unrecognized" in w]
    assert drop == []
    types = {s.type for s in spans}
    assert "tool_use" in types
    assert "tool_result" in types


def test_public_wrappers_call_invoke() -> None:
    from ai_team.tools import code_tools, file_tools

    assert "_invoke" in inspect.getsource(file_tools.write_file)
    assert "invoke" in inspect.getsource(file_tools.write_file)
    assert "_invoke" in inspect.getsource(file_tools.delete_file)
    assert "get_bus" in inspect.getsource(code_tools.execute_shell)
    assert "invoke" in inspect.getsource(code_tools.execute_shell)


@pytest.mark.bus_draft
class TestDraftCommit:
    def test_write_file_does_not_touch_live(self, bus_ws: Path) -> None:
        from ai_team.tools.bus import get_bus

        live = bus_ws / "src" / "app.py"
        obs = get_bus().invoke(
            ToolRequest(
                tool="write_file",
                args={"path": "src/app.py", "content": "print(1)\n"},
                phase="development",
            )
        )
        assert obs.code == "drafted"
        assert not live.exists()
        draft_id = str(obs.detail.get("draft_id") or "")
        committed = get_bus().invoke(ToolRequest(tool="commit_write", args={"draft_id": draft_id}))
        assert committed.ok is True
        assert live.is_file()
        assert live.read_text(encoding="utf-8") == "print(1)\n"

    def test_commit_path_traversal_rejected(self, bus_ws: Path) -> None:
        rec = stage_draft(bus_ws, "src/ok.py", "x")
        manifest = bus_ws / ".harness" / "drafts" / f"{rec.draft_id}.manifest.json"
        text = manifest.read_text(encoding="utf-8").replace("src/ok.py", "../escape.py")
        manifest.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid draft path|escapes"):
            commit_draft(bus_ws, rec.draft_id)

    def test_irreversible_gated_without_policy(self, bus_ws: Path) -> None:
        (bus_ws / "gone.txt").write_text("x", encoding="utf-8")
        obs = get_bus().invoke(
            ToolRequest(tool="delete_file", args={"path": "gone.txt", "confirm": True})
        )
        assert obs.code == "gated"
        assert (bus_ws / "gone.txt").is_file()

    def test_irreversible_executes_with_policy(self, bus_ws: Path) -> None:
        (bus_ws / "gone.txt").write_text("x", encoding="utf-8")
        obs = get_bus().invoke(
            ToolRequest(
                tool="delete_file",
                args={"path": "gone.txt", "confirm": True},
                allow_irreversible=True,
            )
        )
        assert obs.ok is True
        assert not (bus_ws / "gone.txt").exists()

    def test_lockfile_write_is_irreversible(self, bus_ws: Path) -> None:
        obs = get_bus().invoke(
            ToolRequest(
                tool="write_file",
                args={"path": "requirements.txt", "content": "flask==0\n"},
            )
        )
        assert obs.code == "gated"

    def test_salvage_auto_commits(self, bus_ws: Path) -> None:
        from ai_team.harness.fm001 import salvage_write

        obs = salvage_write("src/salvage.py", "x = 1\n", phase="development")
        assert obs.ok is True
        assert (bus_ws / "src" / "salvage.py").is_file()
