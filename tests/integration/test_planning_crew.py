"""Integration tests for the Planning Crew (mock or real LLM).

Crew structure (hierarchical process, manager, task dependencies) is covered by
unit tests in tests/unit/tasks/test_planning_tasks.py. Here we test kickoff().
Set AI_TEAM_USE_REAL_LLM=1 to run against real Ollama; default is mocked.
"""

from unittest.mock import MagicMock, patch

import pytest
from crewai.crew import CrewOutput
from crewai.utilities.converter import ConverterError
from pydantic import ValidationError

from ai_team.config.settings import get_settings
from ai_team.crews.planning_crew import kickoff


@pytest.mark.real_llm
class TestPlanningCrewKickoff:
    """Test kickoff with mocked or real crew execution."""

    @pytest.fixture
    def mock_crew_output(self) -> CrewOutput:
        """Minimal CrewOutput for assertions."""
        return CrewOutput(
            raw="Mock planning output",
            tasks_output=[],
        )

    def test_kickoff_with_mocked_crew_kickoff_returns_mock_output(
        self,
        mock_crew_output: CrewOutput,
        use_real_llm: bool,
    ) -> None:
        """With mock: returns mock CrewOutput. With real LLM: returns valid result."""
        if use_real_llm:
            if not get_settings().validate_ollama_connection():
                pytest.skip("Ollama unreachable; run with mock or start Ollama")
            try:
                result = kickoff("A simple CLI tool.", verbose=False)
            except (ConverterError, ValidationError) as e:
                pytest.skip(
                    f"Real LLM output could not be parsed (try a larger model): {e!s}"
                )
            assert result is not None
            assert hasattr(result, "raw")
            assert hasattr(result, "tasks_output")
            return

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
