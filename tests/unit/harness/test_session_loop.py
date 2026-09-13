"""Session loop termination, dirty_exit → FM-012, regression demotion (R8 / R9)."""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

from ai_team.harness.acceptance import write_initial
from ai_team.harness.session_loop import (
    SessionRecord,
    load_session_records,
    run_sessions,
    sessions_enabled,
)
from ai_team.models.requirements import (
    AcceptanceCriterion,
    MoSCoW,
    RequirementsDocument,
    UserStory,
)

from evals.checks.registry import get_check
from evals.trace.builder import TraceBuilder
from evals.trace.parsers import parse_sessions_jsonl


def _init_git(ws: Path) -> None:
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.t"], cwd=ws, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=ws, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=ws, check=False, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=ws, check=False, capture_output=True)


def _acceptance(ws: Path) -> None:
    req = RequirementsDocument(
        project_name="todo",
        user_stories=[
            UserStory(
                as_a="user",
                i_want="list",
                so_that="see",
                acceptance_criteria=[AcceptanceCriterion(description="GET /todos 200")],
                priority=MoSCoW.MUST,
            ),
            UserStory(
                as_a="user",
                i_want="create",
                so_that="add",
                acceptance_criteria=[AcceptanceCriterion(description="POST /todos 201")],
                priority=MoSCoW.SHOULD,
            ),
        ],
    )
    write_initial(ws, req, "run-sess")


class _Stub:
    def __init__(self, results: list[dict]) -> None:
        self.results = list(results)
        self.calls = 0

    def run_session(self, workspace: Path, **kwargs: object) -> dict:
        del workspace, kwargs
        idx = min(self.calls, len(self.results) - 1)
        self.calls += 1
        return dict(self.results[idx])


def test_sessions_off_by_default() -> None:
    assert sessions_enabled(None) is False
    assert sessions_enabled(1) is False
    assert sessions_enabled(3) is True


def test_three_sessions_and_max_sessions(tmp_path: Path) -> None:
    _acceptance(tmp_path)
    _init_git(tmp_path)
    backend = _Stub([{"items_passed": ["x"], "cost_usd": 0.1, "skip_commit": True}] * 5)
    records = run_sessions(tmp_path, backend=backend, max_sessions=3, total_budget_usd=10.0)
    assert len(records) == 3
    assert backend.calls == 3


def test_terminates_on_spend(tmp_path: Path) -> None:
    _acceptance(tmp_path)
    _init_git(tmp_path)
    backend = _Stub([{"budget_exhausted": True, "cost_usd": 5.0, "skip_commit": True}])
    records = run_sessions(tmp_path, backend=backend, max_sessions=5, total_budget_usd=4.0)
    assert records[0].status == "budget_exhausted"


def test_terminates_on_no_progress(tmp_path: Path) -> None:
    _acceptance(tmp_path)
    _init_git(tmp_path)
    backend = _Stub([{"items_passed": [], "cost_usd": 0.0, "skip_commit": True}] * 5)
    records = run_sessions(
        tmp_path,
        backend=backend,
        max_sessions=5,
        total_budget_usd=10.0,
        no_progress_sessions=2,
    )
    assert len(records) == 2


def test_dirty_exit_fires_fm012(tmp_path: Path) -> None:
    _acceptance(tmp_path)
    _init_git(tmp_path)
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    (src / "uncommitted.py").write_text("x = 1\n", encoding="utf-8")

    class _Dirty:
        def run_session(self, workspace: Path, **kwargs: object) -> dict:
            del kwargs
            (workspace / "src" / "uncommitted.py").write_text("x = 2\n", encoding="utf-8")
            return {"skip_commit": True, "items_passed": ["z"]}

    records = run_sessions(tmp_path, backend=_Dirty(), max_sessions=2, total_budget_usd=5.0)
    assert records[0].status == "dirty_exit"
    trace = TraceBuilder(backend="claude-agent-sdk", tier="A").from_workspace(
        tmp_path, scenario_id="todo-api-beginner"
    )
    result = get_check("CHK-draft-commit").run(trace)
    assert result.outcome == "fail"
    assert result.failure_mode_id == "FM-012"


def test_regression_demotes_and_prioritizes(tmp_path: Path) -> None:
    _acceptance(tmp_path)
    from ai_team.harness.acceptance import VerifierIdentity, load, mark_passing

    ev = tmp_path / "docs" / "evidence.txt"
    ev.parent.mkdir(exist_ok=True)
    ev.write_text("ok", encoding="utf-8")
    doc = load(tmp_path)
    identity = VerifierIdentity(agent_role="qa_engineer", session_id="s0")
    mark_passing(
        tmp_path,
        doc.items[0].id,
        evidence=["docs/evidence.txt"],
        verified_by="test",
        identity=identity,
    )
    _init_git(tmp_path)

    class _Ok:
        def run_session(self, workspace: Path, **kwargs: object) -> dict:
            del workspace, kwargs
            return {"items_passed": [], "skip_commit": True}

    def verify(_ws: Path, _item_id: str) -> bool:
        return False

    records = run_sessions(
        tmp_path,
        backend=_Ok(),
        max_sessions=2,
        total_budget_usd=5.0,
        verify=verify,
        rng=random.Random(0),
    )
    assert any(r.items_demoted for r in records)
    after = load(tmp_path)
    assert any(i.demotions for i in after.items)


def test_sessions_jsonl_round_trip_and_absent(tmp_path: Path) -> None:
    spans, warnings = parse_sessions_jsonl(tmp_path / "logs" / "sessions.jsonl")
    assert spans == []
    assert warnings == []
    rec = SessionRecord(
        session_id="s",
        index=0,
        started_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        ended_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        status="ok",
    )
    from ai_team.harness.session_loop import append_session_record

    append_session_record(tmp_path, rec)
    loaded = load_session_records(tmp_path)
    assert loaded[0].session_id == "s"
    spans, _ = parse_sessions_jsonl(tmp_path / "logs" / "sessions.jsonl")
    assert any(s.type == "session_start" for s in spans)
    assert any(s.type == "session_end" for s in spans)
