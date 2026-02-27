"""Unit tests for run_ai_team: recursion limit is set for flow execution and restored after."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from ai_team.flows.main_flow import FLOW_RECURSION_LIMIT, run_ai_team


class TestRunAiTeamRecursionLimit:
    """run_ai_team raises recursion limit during kickoff and restores it after."""

    def test_recursion_limit_restored_after_success(self) -> None:
        """After successful kickoff, original recursion limit is restored."""
        old_limit = sys.getrecursionlimit()
        try:
            with patch("ai_team.flows.main_flow.AITeamFlow") as mock_flow_class:
                mock_flow = MagicMock()
                mock_flow.kickoff.return_value = None
                mock_flow.state.model_dump.return_value = {"current_phase": "complete"}
                mock_flow_class.return_value = mock_flow
                run_ai_team("A small API", skip_estimate=True)
            assert sys.getrecursionlimit() == old_limit
        finally:
            sys.setrecursionlimit(old_limit)

    def test_recursion_limit_restored_after_exception(self) -> None:
        """After kickoff raises, recursion limit is still restored in finally."""
        old_limit = sys.getrecursionlimit()
        try:
            with patch("ai_team.flows.main_flow.AITeamFlow") as mock_flow_class:
                mock_flow = MagicMock()
                mock_flow.kickoff.side_effect = RuntimeError("simulated failure")
                mock_flow_class.return_value = mock_flow
                with pytest.raises(RuntimeError, match="simulated failure"):
                    run_ai_team("A small API", skip_estimate=True)
            assert sys.getrecursionlimit() == old_limit
        finally:
            sys.setrecursionlimit(old_limit)

    def test_recursion_limit_raised_during_run(self) -> None:
        """During kickoff, recursion limit is FLOW_RECURSION_LIMIT."""
        limits_seen: list[int] = []

        def capture_limit_and_raise() -> None:
            limits_seen.append(sys.getrecursionlimit())
            raise ValueError("stop")

        old_limit = sys.getrecursionlimit()
        try:
            with patch("ai_team.flows.main_flow.AITeamFlow") as mock_flow_class:
                mock_flow = MagicMock()
                mock_flow.kickoff.side_effect = capture_limit_and_raise
                mock_flow_class.return_value = mock_flow
                with pytest.raises(ValueError, match="stop"):
                    run_ai_team("A small API", skip_estimate=True)
            assert limits_seen == [FLOW_RECURSION_LIMIT]
            assert sys.getrecursionlimit() == old_limit
        finally:
            sys.setrecursionlimit(old_limit)
