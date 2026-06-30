"""Tests for the runtime self-improvement loop in the Claude SDK recovery path.

The loop's contract: when an orchestrator run finishes cleanly but the running
app fails a runtime smoke test, feed the failure back and retry; stop as soon as
the smoke passes (or attempts run out). This is what stops a green unit suite
over a 500-ing app from being reported as success.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from ai_team.backends.claude_agent_sdk_backend import recovery
from ai_team.core.team_profile import TeamProfile


class _FakeResult:
    """Minimal stand-in for claude_agent_sdk.ResultMessage."""

    def __init__(self, *, is_error: bool = False, stop_reason: str = "end_turn") -> None:
        self.is_error = is_error
        self.stop_reason = stop_reason
        self.errors: list[str] = []
        self.total_cost_usd = 0.01
        self.usage = {}
        self.session_id = "sid"


class _Smoke:
    def __init__(self, *, ran: bool, success: bool, message: str = "") -> None:
        self.ran = ran
        self.success = success
        self.message = message
        self.probes: list = []
        self.logs = ""


def _profile() -> TeamProfile:
    return TeamProfile(
        name="full",
        agents=["backend_developer", "qa_engineer"],
        phases=["development", "testing"],
        metadata={},
    )


def _patch_iter(results: list[_FakeResult]):
    """Patch iter_orchestrator_messages to yield one ResultMessage per call."""
    calls = {"n": 0}

    async def _fake_iter(description, profile, workspace, **kwargs):  # noqa: ANN001
        idx = min(calls["n"], len(results) - 1)
        calls["n"] += 1
        yield results[idx]

    return _fake_iter, calls


@pytest.mark.asyncio
async def test_smoke_failure_then_pass_retries_then_succeeds(tmp_path: Path) -> None:
    fake_iter, calls = _patch_iter([_FakeResult(), _FakeResult()])
    # First smoke fails (app 500s), second passes (defect fixed).
    smokes = iter(
        [
            _Smoke(ran=True, success=False, message="GET /health -> 500"),
            _Smoke(ran=True, success=True, message="ok"),
        ]
    )

    with (
        patch.object(recovery, "iter_orchestrator_messages", fake_iter),
        patch.object(recovery, "ResultMessage", _FakeResult),
        patch("ai_team.tools.smoke_tools.run_app_smoke", lambda ws: next(smokes)),
    ):
        last, logs = await recovery.run_orchestrator_with_recovery(
            "build a flask app",
            _profile(),
            tmp_path,
            recovery_max_attempts=3,
        )

    assert last is not None and not last.is_error
    assert calls["n"] == 2  # retried exactly once after the smoke failure
    assert any("runtime smoke failed" in line for line in logs)
    assert any("success" in line for line in logs)


@pytest.mark.asyncio
async def test_smoke_pass_first_try_no_retry(tmp_path: Path) -> None:
    fake_iter, calls = _patch_iter([_FakeResult()])

    with (
        patch.object(recovery, "iter_orchestrator_messages", fake_iter),
        patch.object(recovery, "ResultMessage", _FakeResult),
        patch(
            "ai_team.tools.smoke_tools.run_app_smoke",
            lambda ws: _Smoke(ran=True, success=True, message="ok"),
        ),
    ):
        last, logs = await recovery.run_orchestrator_with_recovery(
            "build a flask app",
            _profile(),
            tmp_path,
            recovery_max_attempts=3,
        )

    assert last is not None and not last.is_error
    assert calls["n"] == 1  # no retry needed
    assert any("attempt 1: success" in line for line in logs)


@pytest.mark.asyncio
async def test_smoke_skipped_counts_as_pass(tmp_path: Path) -> None:
    # No bootable entrypoint -> smoke skipped -> treated as success, no retry.
    fake_iter, calls = _patch_iter([_FakeResult()])

    with (
        patch.object(recovery, "iter_orchestrator_messages", fake_iter),
        patch.object(recovery, "ResultMessage", _FakeResult),
        patch(
            "ai_team.tools.smoke_tools.run_app_smoke",
            lambda ws: _Smoke(ran=False, success=False, message="no entrypoint"),
        ),
    ):
        last, logs = await recovery.run_orchestrator_with_recovery(
            "build a library", _profile(), tmp_path, recovery_max_attempts=3
        )

    assert calls["n"] == 1
    assert any("attempt 1: success" in line for line in logs)


@pytest.mark.asyncio
async def test_smoke_failing_to_the_end_returns_last_result(tmp_path: Path) -> None:
    fake_iter, calls = _patch_iter([_FakeResult(), _FakeResult()])

    with (
        patch.object(recovery, "iter_orchestrator_messages", fake_iter),
        patch.object(recovery, "ResultMessage", _FakeResult),
        patch(
            "ai_team.tools.smoke_tools.run_app_smoke",
            lambda ws: _Smoke(ran=True, success=False, message="still 500"),
        ),
    ):
        last, logs = await recovery.run_orchestrator_with_recovery(
            "build a flask app", _profile(), tmp_path, recovery_max_attempts=2
        )

    assert calls["n"] == 2  # used the full budget
    assert last is not None
    assert any("still failing at final attempt" in line for line in logs)
