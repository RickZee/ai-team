"""Integration tests for the Planning Crew (with mocked LLM / kickoff).

Crew structure (hierarchical process, manager, task dependencies) is covered by
unit tests in tests/unit/tasks/test_planning_tasks.py. Here we test kickoff()
with mocked crew execution to avoid real LLM calls.
"""

from unittest.mock import MagicMock, patch

import pytest
from crewai.crew import CrewOutput

from ai_team.crews.planning_crew import kickoff


class TestPlanningCrewKickoff:
    """Test kickoff with mocked crew execution (no real LLM)."""

    @pytest.fixture
    def mock_crew_output(self) -> CrewOutput:
        """Minimal CrewOutput for assertions."""
        return CrewOutput(
            raw="Mock planning output",
            tasks_output=[],
        )

    def test_kickoff_with_mocked_crew_kickoff_returns_mock_output(
        self, mock_crew_output: CrewOutput
    ) -> None:
        """When crew.kickoff is patched, kickoff() returns the mock CrewOutput."""
        with patch(
            "ai_team.crews.planning_crew.create_planning_crew",
        ) as mock_create:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_crew_output
            mock_create.return_value = mock_crew
            result = kickoff("A simple CLI tool.", verbose=False)
            mock_create.assert_called_once()
            mock_crew.kickoff.assert_called_once_with(inputs={"project_description": "A simple CLI tool."})
            assert result is mock_crew_output
            assert result.raw == "Mock planning output"
