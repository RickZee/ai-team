"""Replay-mode tests for the batch runner.

These validate the harness end-to-end — parse recorded rows, compute confidence
intervals, render verdicts — with zero API cost. This is the mechanism that lets a
contributor prove a change to the stats or verdict logic works without spending a cent,
which is what makes the n>=5 contribution bar in CONTRIBUTING actually clearable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from run_smoke_batch import _run_replay, render_report  # noqa: E402

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "smoke_batch"
_EXAMPLE = _FIXTURE_DIR / "example_mixed_model_n5.json"


def test_example_fixture_exists_and_is_a_bundle() -> None:
    bundle = json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    assert "runs" in bundle and "backends" in bundle
    assert bundle["runs"], "fixture must contain recorded rows"


def test_replay_by_bare_name_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    code = _run_replay("example_mixed_model_n5")
    assert code == 0
    out = capsys.readouterr().out
    assert "REPLAY (no live runs, $0)" in out


def test_replay_renders_confidence_intervals(capsys: pytest.CaptureFixture[str]) -> None:
    _run_replay(str(_EXAMPLE))
    out = capsys.readouterr().out
    # The whole point: the CI/verdict pipeline runs on recorded data.
    assert "Green 95% CI" in out
    assert "no significant difference at this n" in out


def test_replay_flags_mixed_model_as_confounded(capsys: pytest.CaptureFixture[str]) -> None:
    _run_replay(str(_EXAMPLE))
    out = capsys.readouterr().out
    assert "MIXED-MODEL (confounded)" in out


def test_missing_fixture_returns_error_code(capsys: pytest.CaptureFixture[str]) -> None:
    code = _run_replay("does-not-exist-anywhere")
    assert code == 2
    assert "not found" in capsys.readouterr().out


def test_non_bundle_json_is_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "not_a_bundle.json"
    bad.write_text('{"hello": "world"}', encoding="utf-8")
    code = _run_replay(str(bad))
    assert code == 2
    assert "not a batch bundle" in capsys.readouterr().out


def test_render_report_is_pure_over_run_mechanism(capsys: pytest.CaptureFixture[str]) -> None:
    # render_report should work on any well-formed bundle, live or recorded.
    bundle = {
        "backends": ["a", "b"],
        "same_model": True,
        "is_canary": False,
        "demo": "demos/02_todo_app",
        "team": "smoke-claude",
        "n_per_backend": 3,
        "generated_at_utc": "2026-07-10T00:00:00+00:00",
        "runs": [
            {"backend": "a", "tests_ok": True, "wall_seconds": 100.0, "spent_usd": 0.5},
            {"backend": "a", "tests_ok": True, "wall_seconds": 110.0, "spent_usd": 0.5},
            {"backend": "a", "tests_ok": True, "wall_seconds": 120.0, "spent_usd": 0.5},
            {"backend": "b", "tests_ok": False, "wall_seconds": 90.0, "spent_usd": 0.4},
            {"backend": "b", "tests_ok": False, "wall_seconds": 95.0, "spent_usd": 0.4},
            {"backend": "b", "tests_ok": False, "wall_seconds": 92.0, "spent_usd": 0.4},
        ],
    }
    render_report(bundle)
    out = capsys.readouterr().out
    assert "SAME-MODEL" in out
    # 3/3 vs 0/3 still overlaps at n=3 — the rule must not over-claim.
    assert "no significant difference" in out
