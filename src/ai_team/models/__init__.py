"""Pydantic models for agent outputs and shared state."""

from ai_team.models.architecture import (
    ArchitectureDecisionRecord,
    ArchitectureDocument,
    Component,
    InterfaceContract,
    TechnologyChoice,
)
from ai_team.models.qa_models import (
    BugReport,
    CoverageReport,
    FileCoverage,
    GeneratedTestFile,
    TestExecutionResult,
    TestResult,
)
from ai_team.models.requirements import (
    AcceptanceCriterion,
    NonFunctionalRequirement,
    RequirementsDocument,
    UserStory,
)

__all__ = [
    "AcceptanceCriterion",
    "ArchitectureDecisionRecord",
    "ArchitectureDocument",
    "BugReport",
    "Component",
    "CoverageReport",
    "FileCoverage",
    "GeneratedTestFile",
    "InterfaceContract",
    "NonFunctionalRequirement",
    "RequirementsDocument",
    "TestExecutionResult",
    "TestResult",
    "TechnologyChoice",
    "UserStory",
]
