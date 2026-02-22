"""Unit tests for planning tasks: config, guardrails, and task factory."""

import json
from unittest.mock import MagicMock, patch

import pytest

from ai_team.tasks.planning_tasks import (
    architecture_guardrail,
    create_planning_tasks,
    planning_tasks_config,
    requirements_guardrail,
)


class TestPlanningTasksConfig:
    """Test loading planning task definitions from YAML."""

    def test_loads_planning_section(self) -> None:
        config = planning_tasks_config()
        assert "requirements_gathering" in config
        assert "architecture_design" in config

    def test_requirements_gathering_has_expected_keys(self) -> None:
        config = planning_tasks_config()
        rg = config["requirements_gathering"]
        assert rg["agent"] == "product_owner"
        assert "description" in rg
        assert "expected_output" in rg
        assert rg["output_pydantic"] == "RequirementsDocument"
        assert "guardrail" in rg
        assert rg.get("context") == []
        assert "timeout_seconds" in rg

    def test_architecture_design_has_context(self) -> None:
        config = planning_tasks_config()
        ad = config["architecture_design"]
        assert ad["agent"] == "architect"
        assert ad.get("context") == ["requirements_gathering"]
        assert ad["output_pydantic"] == "ArchitectureDocument"


class TestRequirementsGuardrail:
    """Test guardrail: at least 3 user stories with acceptance criteria."""

    def test_fails_no_json(self) -> None:
        passed, _ = requirements_guardrail("plain text output")
        assert passed is False

    def test_fails_too_few_stories(self) -> None:
        doc = {
            "project_name": "P",
            "description": "D",
            "user_stories": [
                {"as_a": "u", "i_want": "x", "so_that": "y", "acceptance_criteria": [{"description": "AC1", "testable": True}], "priority": "Must have"},
                {"as_a": "u", "i_want": "x", "so_that": "y", "acceptance_criteria": [{"description": "AC2", "testable": True}], "priority": "Must have"},
            ],
        }
        passed, _ = requirements_guardrail(json.dumps(doc))
        assert passed is False

    def test_fails_story_without_acceptance_criteria(self) -> None:
        doc = {
            "project_name": "P",
            "description": "D",
            "user_stories": [
                {"as_a": "u", "i_want": "x", "so_that": "y", "acceptance_criteria": [{"description": "AC", "testable": True}], "priority": "Must have"},
                {"as_a": "u", "i_want": "x", "so_that": "y", "acceptance_criteria": [{"description": "AC", "testable": True}], "priority": "Must have"},
                {"as_a": "u", "i_want": "x", "so_that": "y", "acceptance_criteria": [], "priority": "Must have"},
            ],
        }
        passed, _ = requirements_guardrail(json.dumps(doc))
        assert passed is False

    def test_passes_three_stories_with_criteria(self) -> None:
        doc = {
            "project_name": "P",
            "description": "D",
            "user_stories": [
                {"as_a": "u", "i_want": "a", "so_that": "b", "acceptance_criteria": [{"description": "AC1", "testable": True}], "priority": "Must have"},
                {"as_a": "u", "i_want": "c", "so_that": "d", "acceptance_criteria": [{"description": "AC2", "testable": True}], "priority": "Should have"},
                {"as_a": "u", "i_want": "e", "so_that": "f", "acceptance_criteria": [{"description": "AC3", "testable": True}], "priority": "Could have"},
            ],
        }
        passed, _ = requirements_guardrail(json.dumps(doc))
        assert passed is True

    def test_accepts_result_with_raw_attribute(self) -> None:
        doc = {
            "project_name": "P",
            "description": "D",
            "user_stories": [
                {"as_a": "u", "i_want": "a", "so_that": "b", "acceptance_criteria": [{"description": "AC1", "testable": True}], "priority": "Must have"},
                {"as_a": "u", "i_want": "c", "so_that": "d", "acceptance_criteria": [{"description": "AC2", "testable": True}], "priority": "Should have"},
                {"as_a": "u", "i_want": "e", "so_that": "f", "acceptance_criteria": [{"description": "AC3", "testable": True}], "priority": "Could have"},
            ],
        }
        result = MagicMock()
        result.raw = json.dumps(doc)
        passed, _ = requirements_guardrail(result)
        assert passed is True

    def test_passes_json_embedded_in_prose(self) -> None:
        """Guardrail extracts first top-level {...} when output is prose + JSON."""
        doc = {
            "project_name": "Todo API",
            "description": "REST API for a todo list",
            "user_stories": [
                {"as_a": "user", "i_want": "list items", "so_that": "I can track work", "acceptance_criteria": [{"description": "AC1", "testable": True}], "priority": "Must have"},
                {"as_a": "user", "i_want": "add items", "so_that": "I can add tasks", "acceptance_criteria": [{"description": "AC2", "testable": True}], "priority": "Must have"},
                {"as_a": "user", "i_want": "delete items", "so_that": "I can remove tasks", "acceptance_criteria": [{"description": "AC3", "testable": True}], "priority": "Should have"},
            ],
        }
        wrapped = "Here are the requirements.\n\n" + json.dumps(doc) + "\n\nWe also need NFRs later."
        passed, _ = requirements_guardrail(wrapped)
        assert passed is True


class TestArchitectureGuardrail:
    """Test guardrail: architecture structural completeness."""

    def test_fails_no_json(self) -> None:
        passed, _ = architecture_guardrail("not json")
        assert passed is False

    def test_fails_invalid_structure(self) -> None:
        passed, _ = architecture_guardrail(json.dumps({"system_overview": "x"}))
        assert passed is False  # missing required list fields

    def test_passes_minimal_valid_architecture(self) -> None:
        doc = {
            "system_overview": "A minimal system with one component and one ADR for testing.",
            "components": [{"name": "API", "responsibilities": "Serves requests"}],
            "technology_stack": [{"name": "Python", "category": "backend", "justification": "Simple"}],
            "interface_contracts": [],
            "adrs": [{"title": "T", "status": "Accepted", "context": "C", "decision": "D", "consequences": "E"}],
            "ascii_diagram": "  [API] --> [Client]  ",
        }
        passed, _ = architecture_guardrail(json.dumps(doc))
        assert passed is True

    def test_passes_json_embedded_in_prose(self) -> None:
        """Guardrail extracts first top-level {...} when output is prose + JSON."""
        doc = {
            "system_overview": "A minimal system for testing fallback extraction.",
            "components": [{"name": "API", "responsibilities": "Serves requests"}],
            "technology_stack": [{"name": "Python", "category": "backend", "justification": "Simple"}],
            "interface_contracts": [],
            "adrs": [{"title": "T", "status": "Accepted", "context": "C", "decision": "D", "consequences": "E"}],
            "ascii_diagram": "  [API] --> [Client]  ",  # long enough for guardrail
        }
        wrapped = "Here is the architecture.\n\n" + json.dumps(doc) + "\n\nExplanation: we chose Python."
        passed, _ = architecture_guardrail(wrapped)
        assert passed is True


class TestCreatePlanningTasks:
    """Test task factory creates CrewAI Task objects with context and guardrails."""

    def test_creates_two_tasks(self) -> None:
        agents = {"product_owner": MagicMock(), "architect": MagicMock()}
        with patch("ai_team.tasks.planning_tasks.Task") as MockTask:
            mock_t1, mock_t2 = MagicMock(), MagicMock()
            MockTask.side_effect = [mock_t1, mock_t2]
            tasks, timeouts = create_planning_tasks(agents)
        assert len(tasks) == 2
        assert len(timeouts) == 2
        assert "requirements_gathering" in timeouts
        assert "architecture_design" in timeouts
        assert MockTask.call_count == 2

    def test_architecture_task_has_context(self) -> None:
        agents = {"product_owner": MagicMock(), "architect": MagicMock()}
        with patch("ai_team.tasks.planning_tasks.Task") as MockTask:
            mock_req, mock_arch = MagicMock(), MagicMock()
            MockTask.side_effect = [mock_req, mock_arch]
            tasks, _ = create_planning_tasks(agents)
        assert tasks[0] is mock_req
        assert tasks[1] is mock_arch
        # Second call must have context=[first task]
        call_kw = MockTask.call_args_list[1][1]
        assert call_kw["context"] == [mock_req]

    def test_missing_agent_raises(self) -> None:
        agents = {"product_owner": MagicMock()}
        with patch("ai_team.tasks.planning_tasks.Task") as MockTask:
            MockTask.return_value = MagicMock()
            with pytest.raises(ValueError, match="architect"):
                create_planning_tasks(agents)
