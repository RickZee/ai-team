"""Smoke tests for Claude Agent SDK backend wiring."""

from __future__ import annotations

from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend
from ai_team.backends.registry import get_backend
from ai_team.core.team_profile import TeamProfile


class TestClaudeAgentBackend:
    def test_get_backend_returns_instance(self) -> None:
        b = get_backend("claude-agent-sdk")
        assert isinstance(b, ClaudeAgentBackend)
        assert b.name == "claude-agent-sdk"


class TestResultsBundleWrite:
    """SDK runs previously wrote no output/runs/<id>/ bundle at all — results
    lived only in the workspace and vanished from the registry (2026-07-03
    comparison finding #4)."""

    def _profile(self) -> TeamProfile:
        return TeamProfile(name="smoke", agents=["architect"], phases=["development"])

    def test_write_results_bundle_creates_registry_entry(self, tmp_path, monkeypatch) -> None:
        import json

        from ai_team.config.settings import reload_settings

        out_root = tmp_path / "out"
        ws = tmp_path / "ws" / "run-xyz"
        ws.mkdir(parents=True)
        monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out_root))
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
        reload_settings()

        backend = ClaudeAgentBackend()
        raw = {
            "cost_usd": 0.7,
            "session_id": "sess-1",
            "test_results": {"passed": 5, "failed": 0, "total": 5},
            "generated_files": ["src/calc.py"],
        }
        backend._write_results_bundle(ws, self._profile(), raw, success=True)

        run_json = json.loads(
            (out_root / "runs" / "run-xyz" / "run.json").read_text(encoding="utf-8")
        )
        assert run_json["backend"] == "claude-agent-sdk"
        assert run_json["completed_at"] is not None
        assert run_json["extra"]["final_status"] == "complete"
        state = json.loads(
            (out_root / "runs" / "run-xyz" / "state.json").read_text(encoding="utf-8")
        )
        assert state["current_phase"] == "complete"
        assert state["test_results"]["passed"] == 5
        costs = (out_root / "runs" / "run-xyz" / "logs" / "costs.jsonl").read_text(encoding="utf-8")
        assert '"spent_usd": 0.7' in costs

    def test_write_results_bundle_failure_does_not_raise(self, tmp_path, monkeypatch) -> None:
        """Adversarial: unwritable output root must not break the run itself."""
        from ai_team.config.settings import reload_settings

        ws = tmp_path / "ws" / "run-abc"
        ws.mkdir(parents=True)
        monkeypatch.setenv("PROJECT_OUTPUT_DIR", "/dev/null/nope")
        monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
        reload_settings()

        backend = ClaudeAgentBackend()
        backend._write_results_bundle(ws, self._profile(), {}, success=False)
