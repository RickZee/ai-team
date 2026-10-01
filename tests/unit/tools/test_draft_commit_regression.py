"""Regression: agent writes stayed drafts forever (2026-08-28 → 2026-09-16).

Draft-then-commit was on by default, but no backend gave agents ``commit_write`` and
nothing else promoted drafts. LangGraph and CrewAI runs rewrote the same files, pytest
collected nothing, and live runs looped past 15 minutes. The unit suite never saw it
because its autouse fixture turns drafts *off*; every test here opts back in.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_team.tools.bus import get_bus, reset_bus
from ai_team.tools.draft import commit_pending_drafts, list_drafts, stage_draft
from ai_team.tools.kinds import ToolRequest

pytestmark = [pytest.mark.eval_unit, pytest.mark.bus_draft]


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from ai_team.config.settings import reload_settings

    root = tmp_path / "workspace"
    root.mkdir()
    (tmp_path / "output").mkdir()
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(root))
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("AI_TEAM_DRAFT_WRITES", "1")
    reload_settings()
    reset_bus()
    yield root
    reset_bus()
    monkeypatch.delenv("PROJECT_WORKSPACE_DIR")
    monkeypatch.delenv("PROJECT_OUTPUT_DIR")
    reload_settings()


def _agent_write(path: str, content: str) -> None:
    obs = get_bus().invoke(ToolRequest(tool="write_file", args={"path": path, "content": content}))
    assert obs.code == "drafted", obs


class TestCommitPendingDrafts:
    def test_agent_write_is_invisible_until_the_harness_commits(self, ws: Path) -> None:
        _agent_write("calc.py", "def add(a, b):\n    return a + b\n")
        assert not (ws / "calc.py").exists()

        res = commit_pending_drafts(phase="development")

        assert res.ok and res.committed == ["calc.py"]
        assert (ws / "calc.py").read_text(encoding="utf-8").startswith("def add")
        assert list_drafts(ws) == []

    def test_newest_draft_of_a_path_wins(self, ws: Path) -> None:
        _agent_write("calc.py", "v1\n")
        time.sleep(0.01)
        _agent_write("calc.py", "v2\n")

        res = commit_pending_drafts(phase="development")

        assert res.committed == ["calc.py"]
        assert (ws / "calc.py").read_text(encoding="utf-8") == "v2\n"
        assert list_drafts(ws) == []

    def test_commit_is_audited_as_a_harness_commit_write(self, ws: Path) -> None:
        _agent_write("tests/test_calc.py", "def test_x():\n    assert True\n")
        with patch.object(get_bus(), "_audit", wraps=get_bus()._audit) as audit:
            commit_pending_drafts(phase="testing")
        calls = [c for c in audit.call_args_list if c.args[0] == "tool_result"]
        req = calls[-1].args[1]
        assert req.tool == "commit_write"
        assert req.agent_role == "_harness"
        assert req.phase == "testing"

    def test_nothing_pending_is_a_no_op(self, ws: Path) -> None:
        res = commit_pending_drafts(phase="testing")
        assert res.ok and res.committed == [] and res.rejected == []

    def test_agents_cannot_target_the_draft_area(self, ws: Path) -> None:
        with pytest.raises(ValueError, match="harness area"):
            stage_draft(ws, ".harness/drafts/abc", "x")


class TestFileWriterTellsTheTruth:
    def test_file_writer_says_staged(self, ws: Path) -> None:
        from ai_team.tools.developer_tools import FileWriterTool

        out = FileWriterTool()._run(path="calc.py", content="x = 1\n")
        assert out.startswith("OK (staged")
        assert not (ws / "calc.py").exists()


class TestLangGraphTestingPhaseSeesAgentFiles:
    def test_tests_written_by_qa_are_on_disk_before_the_gate(self, ws: Path) -> None:
        """The exact live failure: QA drafts a test, the gate collects nothing."""
        from langchain_core.messages import AIMessage

        from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr

        def _qa_turn(*_a: object, **_k: object) -> dict[str, object]:
            _agent_write("tests/test_calc.py", "def test_ok():\n    assert 1 + 1 == 2\n")
            return {"messages": [AIMessage(content="Wrote tests/test_calc.py")]}

        seen: dict[str, bool] = {}

        def _gate() -> dict[str, object]:
            seen["test_on_disk"] = (ws / "tests" / "test_calc.py").is_file()
            return {"passed": True}

        sub = MagicMock()
        sub.invoke.side_effect = _qa_turn
        with (
            patch.object(sr, "_cached_testing", return_value=sub),
            patch.object(sr, "_extract_profile_from_state", return_value=([], {})),
            patch.object(sr, "_run_real_quality_gate", side_effect=_gate),
        ):
            out = sr.testing_subgraph_node(
                {"project_description": "x" * 20, "generated_files": [], "messages": []}, {}
            )

        assert seen == {"test_on_disk": True}
        assert out["test_results"] == {"passed": True}
        assert sub.invoke.call_count == 1  # no "you wrote nothing" re-prompt

    def test_guardrail_terminal_phase_does_not_commit(self, ws: Path) -> None:
        from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr

        def _bad_turn(*_a: object, **_k: object) -> dict[str, object]:
            _agent_write("tests/test_calc.py", "import os\n")
            return {"messages": [], "guardrail_terminal": True, "guardrail_checks": []}

        sub = MagicMock()
        sub.invoke.side_effect = _bad_turn
        with (
            patch.object(sr, "_cached_testing", return_value=sub),
            patch.object(sr, "_extract_profile_from_state", return_value=([], {})),
        ):
            out = sr.testing_subgraph_node(
                {"project_description": "x" * 20, "generated_files": [], "messages": []}, {}
            )

        assert out["errors"][0]["type"] == "GuardrailError"
        assert not (ws / "tests" / "test_calc.py").exists()

    def test_inventory_ignores_the_draft_area(self, ws: Path) -> None:
        from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr

        _agent_write("calc.py", "x = 1\n")
        assert all(".harness" not in f["path"] for f in sr._snapshot_workspace_files())


class TestCrewAITestingCrewCommits:
    def test_persisted_test_files_reach_disk(self, ws: Path) -> None:
        from ai_team.backends.crewai_backend.crews import testing_crew as tc
        from ai_team.models.development import CodeFile

        files = [
            CodeFile(
                path="tests/test_calc.py",
                content="def test_ok():\n    assert True\n",
                language="python",
                description="calc tests",
            )
        ]
        assert tc._persist_test_files_from_code_files(files) == 1
        assert (ws / "tests" / "test_calc.py").is_file()
