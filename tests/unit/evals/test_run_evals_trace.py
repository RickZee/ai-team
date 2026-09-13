"""Trace emission path in run_evals — mocked subprocess, no live API calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.cost import BudgetLedger
from evals.run_evals import SuiteContext, _emit_trace, _find_workspace
from evals.store import TraceStore

pytestmark = pytest.mark.eval_unit

_MINI = Path(__file__).resolve().parents[2] / "fixtures" / "mini_workspace"


def test_emit_trace_from_mini_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = TraceStore(root=tmp_path / "traces")
    ctx = SuiteContext(
        tier="B",
        k=1,
        budget=BudgetLedger(ceiling_usd=5.0),
        store=store,
        pricing_version="2026-08-16",
        yes=True,
        no_judge=True,
        verbose=False,
    )
    monkeypatch.setattr(
        "evals.run_evals._find_workspace",
        lambda backend, log_path: _MINI,
    )
    trace_id = _emit_trace(
        backend="claude-agent-sdk",
        scenario="smoke-test",
        ctx=ctx,
        wall_time_s=1.5,
        killed=False,
        exit_code=0,
        log_path=None,
    )
    assert trace_id is not None
    path = store.root / f"{trace_id}.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "complete"
    assert data["scenario_id"] == "smoke-test"
    assert data["backend"] == "claude-agent-sdk"
    assert ctx.budget.spent_usd >= 0.0


def test_emit_trace_killed_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = TraceStore(root=tmp_path / "traces")
    ctx = SuiteContext(
        tier="B",
        k=1,
        budget=BudgetLedger(ceiling_usd=5.0),
        store=store,
        pricing_version="2026-08-16",
        yes=True,
        no_judge=True,
        verbose=False,
    )
    monkeypatch.setattr(
        "evals.run_evals._find_workspace",
        lambda backend, log_path: _MINI,
    )
    trace_id = _emit_trace(
        backend="crewai",
        scenario="smoke-test",
        ctx=ctx,
        wall_time_s=90.0,
        killed=True,
        exit_code=1,
        log_path=None,
    )
    assert trace_id is not None
    data = json.loads((store.root / f"{trace_id}.json").read_text(encoding="utf-8"))
    assert data["status"] == "killed"


def test_find_workspace_from_log(tmp_path: Path) -> None:
    ws = tmp_path / "workspace" / "run1"
    (ws / "logs").mkdir(parents=True)
    (ws / "logs" / "phases.jsonl").write_text("{}\n", encoding="utf-8")
    log_path = tmp_path / "eval_crewai.log"
    log_path.write_text(f"workspace at {ws}\n", encoding="utf-8")
    found = _find_workspace("crewai", log_path)
    assert found is not None
    assert found == ws


def test_workspace_path_re_has_no_root_allowlist() -> None:
    """R17.4: paths outside /Users|/home|/tmp|/var|/private must still match."""
    from evals.run_evals import _WORKSPACE_PATH_RE

    match = _WORKSPACE_PATH_RE.search("cwd=/opt/hostedtoolcache/workspace/run-x")
    assert match is not None
    assert match.group(1).startswith("/opt/")


def test_find_workspace_outside_legacy_root_allowlist(tmp_path: Path) -> None:
    """R17.4: a path that is not under /Users|/home|/tmp|/var|/private still resolves."""
    ws = tmp_path / "opt" / "eval-root" / "workspace" / "run-x"
    (ws / "logs").mkdir(parents=True)
    log_path = tmp_path / "eval.log"
    log_path.write_text(f"cwd={ws}\n", encoding="utf-8")
    found = _find_workspace("langgraph", log_path)
    assert found == ws


def test_find_workspace_returns_none_when_log_has_no_path(tmp_path: Path) -> None:
    """R17.4: no match → None, never the newest sibling under ./workspace/."""
    decoy = tmp_path / "workspace" / "someone-elses-run"
    (decoy / "logs").mkdir(parents=True)
    log_path = tmp_path / "eval.log"
    log_path.write_text("run finished with no workspace path\n", encoding="utf-8")
    assert _find_workspace("crewai", log_path) is None


def test_ladder_cli_dry_run_spends_nothing() -> None:
    from evals.cli import main

    assert (
        main(
            [
                "ladder",
                "run",
                "--scenario",
                "todo-api-beginner",
                "--arms",
                "solo,ai_team",
                "-n",
                "1",
            ]
        )
        == 0
    )


def test_cli_flags_parsed() -> None:
    from evals.run_evals import main

    with pytest.raises(SystemExit) as exc:
        # No live mode: help / no action exits 0 when nothing selected —
        # exercise argparse for new flags via compare projection gate without CI.
        main(
            [
                "--tier",
                "B",
                "--k",
                "2",
                "--budget-usd",
                "0.01",
                "--no-judge",
                "--scenario",
                "smoke-test",
            ]
        )
    assert exc.value.code == 0


def test_cli_budget_projection_blocks_without_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from evals.run_evals import main

    monkeypatch.delenv("CI", raising=False)
    # Projection for smoke-test × 1 backend × k=1 ≈ $0.04 > 50% of $0.05.
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--backend",
                "crewai",
                "--tier",
                "B",
                "--k",
                "1",
                "--budget-usd",
                "0.05",
                "--no-judge",
                "--scenario",
                "smoke-test",
            ]
        )
    assert exc.value.code == 2
