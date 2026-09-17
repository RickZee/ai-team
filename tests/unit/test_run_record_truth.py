"""
Regression: a run record must not report a number that isn't true.

Three findings from the 2026-09-17 live runs
(`course/testing/runs/2026-09-17-stranger`, `-stranger-2`):

* **F22** — an empty `OPENROUTER_API_KEY` in the shell beats `.env` (deliberately: that is
  how the $0 placeholder run guarantees it cannot spend). When it was still around for a
  paid run, the failure surfaced ~3 s in as litellm's "Missing credentials ... set the
  OPENAI_API_KEY environment variable" — a variable this project does not use.
* **R8** — CrewAI's token tracker reported `$0.0247`; `logs/costs.jsonl` recorded
  `spent_usd: 0.000236`, because crews run under subprocess isolation and the spend guard
  only counts what passes through this process.
* **R9** — the Claude SDK writes its bundle after the orchestrator returns, so a 217-second
  run recorded `started_at` and `completed_at` 6 ms apart.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ai_team.core.spend_guard import current_spend, reconcile_spend, reset_spend_guard

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_demo():
    """Import scripts/run_demo.py, which is not an installed module."""
    if "run_demo" in sys.modules:
        return sys.modules["run_demo"]
    spec = importlib.util.spec_from_file_location("run_demo", REPO_ROOT / "scripts" / "run_demo.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_demo"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestApiKeyPreflight:
    def test_empty_key_names_the_right_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        msg = _run_demo()._missing_api_key("langgraph", "full")
        assert msg is not None
        assert "OPENROUTER_API_KEY" in msg
        assert "unset OPENROUTER_API_KEY" in msg
        assert "OPENAI_API_KEY" not in msg

    def test_a_key_in_the_environment_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        assert _run_demo()._missing_api_key("langgraph", "full") is None

    def test_placeholder_mode_never_needs_a_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The $0 dry run must stay runnable with the key blanked on purpose."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        assert _run_demo()._missing_api_key("langgraph", "placeholder") is None

    def test_claude_backend_is_asked_for_its_own_variable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        msg = _run_demo()._missing_api_key("claude-agent-sdk", "full")
        assert msg is not None
        assert "ANTHROPIC_API_KEY" in msg


class TestSpendReconciliation:
    def test_a_backend_total_replaces_the_guard_total(self) -> None:
        reset_spend_guard(1.0, run_id="run-a")
        from ai_team.core.spend_guard import record_usage

        record_usage(0.000236, total_tokens=10)
        assert current_spend()["spent_usd"] == pytest.approx(0.000236)

        reconcile_spend(0.0247, source="crewai_token_tracker", run_id="run-a")
        snap = current_spend(run_id="run-a")
        assert snap["spent_usd"] == pytest.approx(0.0247)
        assert snap["observed_usd"] == pytest.approx(0.000236)
        assert snap["source"] == "crewai_token_tracker"

    def test_an_unreconciled_run_says_where_its_number_came_from(self) -> None:
        reset_spend_guard(1.0, run_id="run-b")
        snap = current_spend(run_id="run-b")
        assert snap["source"] == "spend_guard"
        assert "observed_usd" not in snap

    def test_reconciling_does_not_move_the_ceiling(self) -> None:
        """A total that arrives after the run cannot stop it, so it must not pretend to."""
        from ai_team.core.spend_guard import record_usage

        reset_spend_guard(1.0, run_id="run-c")
        reconcile_spend(5.0, source="crewai_token_tracker", run_id="run-c")
        record_usage(0.01)  # would raise if the ceiling had been recomputed against $5
        assert current_spend(run_id="run-c")["spent_usd"] == pytest.approx(5.0)

    def test_a_negative_total_is_ignored(self) -> None:
        reset_spend_guard(1.0, run_id="run-d")
        reconcile_spend(-1.0, source="bogus", run_id="run-d")
        assert current_spend(run_id="run-d")["spent_usd"] == pytest.approx(0.0)


class TestRunStartedAt:
    def test_bundle_metadata_honours_an_explicit_start(self, tmp_path: Path) -> None:
        from ai_team.core.results.writer import ResultsBundle

        started = datetime.now(UTC) - timedelta(seconds=217)
        b = ResultsBundle("run-e", workspace_dir=tmp_path / "ws")
        meta = b.default_run_metadata(
            backend="claude-agent-sdk", team_profile="prototype", env=None, started_at=started
        )
        assert meta.started_at == started

    def test_claude_backend_passes_a_start_time_through(self) -> None:
        """The bundle is written after the run, so the signature must carry the start."""
        import inspect

        from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend

        sig = inspect.signature(ClaudeAgentBackend._write_results_bundle)
        assert "started_at" in sig.parameters
