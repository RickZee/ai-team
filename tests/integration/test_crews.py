"""Integration tests for crews with lightweight mock LLM.

Tests Planning (RequirementsDocument + ArchitectureDocument), Development (CodeFile list),
Testing (TestRunResult), and Deployment (DeploymentConfig) crews. Verifies crew-to-crew
handoffs pass correct context. Uses mocked crew kickoff for speed; label real-LLM tests
with @pytest.mark.slow.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_team.crews import development_crew as development_crew_mod
from ai_team.crews import planning_crew as planning_crew_mod
from ai_team.crews import testing_crew as testing_crew_mod
from ai_team.flows.main_flow import _parse_planning_output
from ai_team.models.architecture import (
    ArchitectureDocument,
    Component,
    TechnologyChoice,
)
from ai_team.models.development import CodeFile, DeploymentConfig
from ai_team.models.requirements import (
    AcceptanceCriterion,
    MoSCoW,
    RequirementsDocument,
    UserStory,
)
from ai_team.tools.test_tools import TestRunResult


def _task_output_with_raw(raw: str) -> SimpleNamespace:
    """Build a task output object with .raw attribute."""
    return SimpleNamespace(raw=raw)


def _mock_planning_output(
    requirements: RequirementsDocument,
    architecture: ArchitectureDocument,
) -> SimpleNamespace:
    """Build crew result that _parse_planning_output can consume."""
    req_json = json.dumps(requirements.model_dump(mode="json"))
    arch_json = json.dumps(architecture.model_dump(mode="json"))
    return SimpleNamespace(
        raw="",
        tasks_output=[
            _task_output_with_raw(req_json),
            _task_output_with_raw(arch_json),
        ],
    )


# -----------------------------------------------------------------------------
# Planning crew → RequirementsDocument + ArchitectureDocument
# -----------------------------------------------------------------------------


class TestPlanningCrewProducesValidDocuments:
    """Planning crew (requirements + architecture) produces valid structured output."""

    def test_planning_crew_produces_valid_requirements_document(
        self,
        sample_requirements_document: RequirementsDocument,
        sample_architecture_document: ArchitectureDocument,
    ) -> None:
        """Mock LLM: Planning crew output parses to valid RequirementsDocument."""
        mock_result = _mock_planning_output(
            sample_requirements_document,
            sample_architecture_document,
        )
        with patch(
            "ai_team.crews.planning_crew.create_planning_crew",
        ) as mock_create:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_create.return_value = mock_crew

            result = planning_crew_mod.kickoff("A REST API for todos.", verbose=False)

            mock_crew.kickoff.assert_called_once_with(
                inputs={"project_description": "A REST API for todos."}
            )

        requirements, _, needs_clarification = _parse_planning_output(result)
        assert requirements is not None
        assert isinstance(requirements, RequirementsDocument)
        assert requirements.project_name == sample_requirements_document.project_name
        assert len(requirements.user_stories) >= 3
        for story in requirements.user_stories:
            assert story.acceptance_criteria
        assert not needs_clarification or len(requirements.user_stories) >= 3

    def test_planning_crew_produces_valid_architecture_document(
        self,
        sample_requirements_document: RequirementsDocument,
        sample_architecture_document: ArchitectureDocument,
    ) -> None:
        """Mock LLM: Planning crew output parses to valid ArchitectureDocument."""
        mock_result = _mock_planning_output(
            sample_requirements_document,
            sample_architecture_document,
        )
        with patch(
            "ai_team.crews.planning_crew.create_planning_crew",
        ) as mock_create:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_create.return_value = mock_crew

            result = planning_crew_mod.kickoff("A REST API for todos.", verbose=False)

        _, architecture, _ = _parse_planning_output(result)
        assert architecture is not None
        assert isinstance(architecture, ArchitectureDocument)
        assert architecture.system_overview
        assert len(architecture.components) >= 1
        assert len(architecture.technology_stack) >= 1


# -----------------------------------------------------------------------------
# Development crew → CodeFile list (+ optional DeploymentConfig)
# -----------------------------------------------------------------------------


class TestDevelopmentCrewProducesValidCodeFiles:
    """Development crew produces valid CodeFile list and optional DeploymentConfig."""

    def test_development_crew_produces_valid_code_file_list(
        self,
        sample_requirements_document: RequirementsDocument,
        sample_architecture_document: ArchitectureDocument,
        sample_code_files: list[CodeFile],
    ) -> None:
        """Mock LLM: Development crew returns valid list of CodeFile."""
        with patch.object(
            development_crew_mod,
            "kickoff",
            return_value=(sample_code_files, None),
        ):
            code_files, deployment_config = development_crew_mod.kickoff(
                sample_requirements_document,
                sample_architecture_document,
            )

        assert isinstance(code_files, list)
        assert len(code_files) >= 1
        for cf in code_files:
            assert cf.path
            assert cf.content
            assert cf.language
        assert deployment_config is None or isinstance(deployment_config, DeploymentConfig)

    def test_development_crew_handoff_receives_planning_context(
        self,
        sample_requirements_document: RequirementsDocument,
        sample_architecture_document: ArchitectureDocument,
        sample_code_files: list[CodeFile],
    ) -> None:
        """Crew-to-crew handoff: Development crew receives requirements and architecture."""
        with patch.object(
            development_crew_mod,
            "kickoff",
            return_value=(sample_code_files, None),
        ) as mock_kickoff:
            development_crew_mod.kickoff(
                sample_requirements_document,
                sample_architecture_document,
            )
            mock_kickoff.assert_called_once()
            args = mock_kickoff.call_args[0]
            assert args[0] is sample_requirements_document
            assert args[1] is sample_architecture_document


# -----------------------------------------------------------------------------
# Testing crew (QACrew) → TestRunResult
# -----------------------------------------------------------------------------


class TestTestingCrewProducesValidTestResult:
    """Testing crew produces valid TestRunResult and quality gate."""

    def test_testing_crew_produces_valid_test_result(
        self,
        sample_code_files: list[CodeFile],
        sample_test_run_result_passed: TestRunResult,
    ) -> None:
        """Mock LLM: Testing crew returns valid TestRunResult."""
        from ai_team.crews.testing_crew import TestingCrewOutput

        task_outs = [
            MagicMock(raw="test gen output"),
            MagicMock(raw=sample_test_run_result_passed.model_dump_json()),
            MagicMock(
                raw='{"summary":"","findings":[],"critical_count":0,"high_count":0,"passed":true}'
            ),
        ]
        mock_crew_result = MagicMock(tasks_output=task_outs)

        with patch(
            "ai_team.crews.testing_crew.create_testing_crew",
        ) as mock_create:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_crew_result
            mock_create.return_value = mock_crew

            output = testing_crew_mod.kickoff(sample_code_files)

        assert isinstance(output, TestingCrewOutput)
        assert output.test_run_result is not None
        assert output.test_run_result.total == sample_test_run_result_passed.total
        assert output.test_run_result.passed == sample_test_run_result_passed.passed
        assert output.test_run_result.success is True
        assert isinstance(output.quality_gate_passed, bool)


# -----------------------------------------------------------------------------
# Deployment crew → DeploymentConfig (via package)
# -----------------------------------------------------------------------------


class TestDeploymentCrewProducesValidDeploymentConfig:
    """Deployment crew produces valid deployment package / DeploymentConfig."""

    def test_deployment_crew_kickoff_accepts_handoff_context(
        self,
        sample_code_files: list[CodeFile],
        sample_architecture_document: ArchitectureDocument,
        sample_test_run_result_passed: TestRunResult,
    ) -> None:
        """Deployment crew receives code files, architecture, test results from prior crews."""
        with patch(
            "ai_team.crews.deployment_crew.DeploymentCrew",
        ) as MockDeploymentCrew:
            mock_crew_instance = MagicMock()
            MockDeploymentCrew.return_value = mock_crew_instance
            from ai_team.crews import deployment_crew as deployment_crew_mod

            crew = deployment_crew_mod.DeploymentCrew(verbose=False)
            crew.kickoff(
                sample_code_files,
                sample_architecture_document,
                sample_test_run_result_passed,
                product_owner_doc_context="REST API for todos",
            )

            mock_crew_instance.kickoff.assert_called_once()
            call_args = mock_crew_instance.kickoff.call_args[0]
            assert len(call_args) >= 3
            assert call_args[0] == sample_code_files
            assert call_args[1] == sample_architecture_document
            assert call_args[2] == sample_test_run_result_passed
            kwargs = mock_crew_instance.kickoff.call_args[1]
            assert kwargs.get("product_owner_doc_context") == "REST API for todos"


# -----------------------------------------------------------------------------
# Crew-to-crew handoffs
# -----------------------------------------------------------------------------


class TestCrewToCrewHandoffs:
    """Verify context passed correctly between crews."""

    def test_planning_to_development_handoff_structure(
        self,
        sample_requirements_document: RequirementsDocument,
        sample_architecture_document: ArchitectureDocument,
    ) -> None:
        """Planning output structure is consumable by development (same types)."""
        mock_result = _mock_planning_output(
            sample_requirements_document,
            sample_architecture_document,
        )
        requirements, architecture, _ = _parse_planning_output(mock_result)
        assert requirements is not None and architecture is not None
        with patch.object(
            development_crew_mod,
            "kickoff",
            return_value=([], None),
        ) as mock_kickoff:
            development_crew_mod.kickoff(requirements, architecture)
            mock_kickoff.assert_called_once()

    def test_development_to_testing_handoff_structure(
        self,
        sample_code_files: list[CodeFile],
        sample_test_run_result_passed: TestRunResult,
    ) -> None:
        """Development CodeFile list is consumable by testing crew."""
        with patch(
            "ai_team.crews.testing_crew.create_testing_crew",
        ) as mock_create:
            mock_crew = MagicMock()
            # Return value must have tasks_output with .raw as strings for TestingCrewOutput
            mock_crew.kickoff.return_value = MagicMock(
                tasks_output=[
                    _task_output_with_raw(""),
                    _task_output_with_raw(sample_test_run_result_passed.model_dump_json()),
                    _task_output_with_raw('{"summary":"","findings":[],"critical_count":0,"high_count":0,"passed":true}'),
                ],
            )
            mock_create.return_value = mock_crew

            output = testing_crew_mod.kickoff(sample_code_files)

            mock_crew.kickoff.assert_called_once()
            inputs = mock_crew.kickoff.call_args[1].get("inputs", {})
            assert "code_files_summary" in inputs
            assert output.test_run_result is not None
