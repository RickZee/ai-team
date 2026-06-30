"""Pydantic models for agent outputs and shared state.

Crew flows use domain models in ``requirements``, ``architecture``, ``development``,
and ``qa_models``. LLM structured-output parsing with extra validators lives in
``outputs`` — import from there for task ``output_pydantic`` schemas.
"""

from ai_team.models.architecture import (
    ArchitectureDecisionRecord,
    ArchitectureDocument,
    Component,
    InterfaceContract,
    TechnologyChoice,
)
from ai_team.models.development import CodeFile, CodeFileList, DeploymentConfig
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
    "CodeFile",
    "CodeFileList",
    "DeploymentConfig",
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
