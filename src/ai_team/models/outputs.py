"""
Pydantic models for all task outputs.

Unified structured output models for planning, development, testing, deployment,
and reporting. Includes validators, JSON schema export, and from_llm_response()
for parsing LLM output.
"""

from __future__ import annotations

import json
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# -----------------------------------------------------------------------------
# Requirements (Planning)
# -----------------------------------------------------------------------------


class MoSCoW(str, Enum):
    """MoSCoW priority levels for user stories."""

    MUST = "Must have"
    SHOULD = "Should have"
    COULD = "Could have"
    WONT = "Won't have (this time)"


class UserStory(BaseModel):
    """User story in 'As a... I want... So that...' format."""

    as_a: str = Field(..., description="Role or type of user")
    i_want: str = Field(..., description="Capability or feature desired")
    so_that: str = Field(..., description="Benefit or outcome")
    acceptance_criteria: List[str] = Field(
        ...,
        description="Testable acceptance criteria (Given/When/Then or checklist)",
        min_length=1,
    )
    priority: MoSCoW = Field(..., description="MoSCoW priority")

    @field_validator("acceptance_criteria")
    @classmethod
    def acceptance_criteria_non_empty_strings(cls, v: List[str]) -> List[str]:
        """Ensure each criterion is a non-empty string."""
        for i, c in enumerate(v):
            if not (isinstance(c, str) and c.strip()):
                raise ValueError(
                    f"acceptance_criteria[{i}] must be a non-empty string; got {repr(c)[:50]}"
                )
        return v


class NFR(BaseModel):
    """Non-functional requirement with category, description, and metric."""

    category: str = Field(..., description="e.g. performance, security, scalability")
    description: str = Field(..., description="Requirement description")
    metric: Optional[str] = Field(None, description="Measurable metric or target")


class RequirementsDocument(BaseModel):
    """Structured requirements document produced by the Product Owner agent."""

    project_name: str = Field(..., description="Name of the project")
    description: str = Field(..., description="Brief project description")
    target_users: List[str] = Field(
        default_factory=list,
        description="Primary user personas or roles",
    )
    user_stories: List[UserStory] = Field(
        ...,
        description="User stories with acceptance criteria",
        min_length=3,
    )
    non_functional_requirements: List[NFR] = Field(
        default_factory=list,
        description="NFRs for performance, security, scalability",
    )
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made")
    constraints: List[str] = Field(
        default_factory=list,
        description="Constraints (time, tech, scope)",
    )

    @model_validator(mode="after")
    def at_least_three_user_stories_all_have_acceptance_criteria(self) -> "RequirementsDocument":
        """Ensure at least 3 user stories and each has at least one acceptance criterion."""
        stories = self.user_stories
        if len(stories) < 3:
            raise ValueError(
                f"RequirementsDocument must have at least 3 user stories; got {len(stories)}. "
                "Add more user stories to meet the minimum."
            )
        for i, us in enumerate(stories):
            if not us.acceptance_criteria or len(us.acceptance_criteria) < 1:
                raise ValueError(
                    f"User story {i + 1} (as_a={us.as_a[:30]!r}...) must have at least one "
                    "acceptance criterion. Add acceptance_criteria for every user story."
                )
        return self

    @classmethod
    def from_llm_response(cls, raw: Union[str, Dict[str, Any]]) -> "RequirementsDocument":
        """Parse LLM response (JSON string or dict) into RequirementsDocument."""
        return _parse_llm_response(cls, raw, "RequirementsDocument")


# -----------------------------------------------------------------------------
# Architecture (Planning)
# -----------------------------------------------------------------------------


class Component(BaseModel):
    """A system component with name and description."""

    name: str = Field(..., description="Component identifier")
    responsibilities: str = Field(default="", description="What this component is responsible for")


class TechChoice(BaseModel):
    """A technology selection with justification."""

    technology: str = Field(..., description="Technology or tool name")
    justification: str = Field(..., description="Why this choice was made")


class Endpoint(BaseModel):
    """A single API or interface endpoint."""

    name: str = Field(..., description="Endpoint name or path")
    method: str = Field(default="", description="HTTP method or protocol")
    description: str = Field(default="", description="Brief description")


class Interface(BaseModel):
    """API or interface with a list of endpoints."""

    name: str = Field(..., description="Interface name")
    endpoints: List[Endpoint] = Field(
        default_factory=list,
        description="List of endpoints",
    )


class Entity(BaseModel):
    """Data model entity with fields and relationships."""

    name: str = Field(..., description="Entity name")
    fields: List[str] = Field(default_factory=list, description="Field names or definitions")
    relationships: List[str] = Field(
        default_factory=list,
        description="Relationships to other entities",
    )


class ADR(BaseModel):
    """Architecture Decision Record."""

    title: str = Field(..., description="Short decision title")
    context: str = Field(..., description="What is the issue we are facing?")
    decision: str = Field(..., description="What is the change we are proposing?")
    consequences: str = Field(..., description="What becomes easier or harder?")


class ArchitectureDocument(BaseModel):
    """Structured architecture document produced by the Architect agent."""

    system_overview: str = Field(..., description="High-level description of the system")
    components: List[Component] = Field(
        default_factory=list,
        description="Component list with responsibilities",
    )
    technology_stack: Dict[str, TechChoice] = Field(
        default_factory=dict,
        description="Technology stack keyed by name, with justification",
    )
    interfaces: List[Interface] = Field(
        default_factory=list,
        description="API/interfaces with endpoints",
    )
    data_model: List[Entity] = Field(
        default_factory=list,
        description="Data model entities with fields and relationships",
    )
    deployment_topology: str = Field(
        default="",
        description="Deployment topology recommendation",
    )
    adrs: List[ADR] = Field(
        default_factory=list,
        description="Architecture Decision Records",
    )

    @classmethod
    def from_llm_response(cls, raw: Union[str, Dict[str, Any]]) -> "ArchitectureDocument":
        """Parse LLM response (JSON string or dict) into ArchitectureDocument."""
        return _parse_llm_response(cls, raw, "ArchitectureDocument")


# -----------------------------------------------------------------------------
# Development outputs
# -----------------------------------------------------------------------------

_FILE_TYPES = Literal["source", "test", "config", "doc"]
_RECOGNIZED_LANGUAGES = frozenset({
    "python", "javascript", "typescript", "html", "css", "json", "yaml", "yml",
    "markdown", "md", "sql", "shell", "bash", "dockerfile", "go", "rust", "java",
    "kotlin", "swift", "c", "cpp", "csharp", "ruby", "php", "scala", "r", "vue",
    "svelte", "tsx", "jsx", "xml", "toml", "ini", "txt", "env",
})


class CodeFile(BaseModel):
    """Represents a generated code file with path, content, and metadata."""

    path: str = Field(..., description="Relative path of the file")
    content: str = Field(..., description="File contents")
    language: str = Field(..., description="Programming or markup language")
    file_type: _FILE_TYPES = Field(
        ...,
        description="Type of file: source, test, config, or doc",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Declared dependencies (e.g. imports, packages)",
    )
    size_bytes: int = Field(..., ge=0, description="Size of content in bytes")

    @field_validator("content")
    @classmethod
    def content_non_empty(cls, v: str) -> str:
        """Content must be non-empty."""
        if not v or not v.strip():
            raise ValueError("CodeFile content must be non-empty. Provide actual file content.")
        return v

    @field_validator("path")
    @classmethod
    def path_valid(cls, v: str) -> str:
        """Path must be valid: no traversal, no absolute path."""
        if not v or not v.strip():
            raise ValueError("CodeFile path must be non-empty.")
        normalized = v.replace("\\", "/").strip()
        if normalized.startswith("/") or ".." in normalized:
            raise ValueError(
                f"CodeFile path must be a relative path without '..'; got {v!r}. "
                "Use a path relative to the project root."
            )
        return v

    @field_validator("language", mode="before")
    @classmethod
    def language_recognized(cls, v: Any) -> str:
        """Language should be a recognized identifier."""
        s = str(v).strip().lower() if v else ""
        if not s:
            raise ValueError("CodeFile language must be non-empty.")
        if s not in _RECOGNIZED_LANGUAGES:
            # Allow but warn via description; accept unknown for extensibility
            pass
        return s

    @classmethod
    def from_llm_response(cls, raw: Union[str, Dict[str, Any]]) -> "CodeFile":
        """Parse LLM response (JSON string or dict) into CodeFile."""
        return _parse_llm_response(cls, raw, "CodeFile")


# -----------------------------------------------------------------------------
# Test results
# -----------------------------------------------------------------------------


class TestFailure(BaseModel):
    """A single test failure with name, error, and traceback."""

    test_name: str = Field(..., description="Test identifier or name")
    error: str = Field(..., description="Error message")
    traceback: str = Field(default="", description="Traceback or stack trace")


class TestResult(BaseModel):
    """Structured test run result: counts, coverage, failures, duration."""

    total: int = Field(0, ge=0, description="Total tests run")
    passed: int = Field(0, ge=0, description="Number of tests passed")
    failed: int = Field(0, ge=0, description="Number of tests failed")
    errors: int = Field(0, ge=0, description="Number of errors (e.g. collection/setup)")
    skipped: int = Field(0, ge=0, description="Number of tests skipped")
    coverage_line: float = Field(0.0, ge=0.0, le=1.0, description="Line coverage ratio 0–1")
    coverage_branch: float = Field(0.0, ge=0.0, le=1.0, description="Branch coverage ratio 0–1")
    failures: List[TestFailure] = Field(
        default_factory=list,
        description="List of test failures with error and traceback",
    )
    duration_seconds: float = Field(0.0, ge=0.0, description="Total test run duration in seconds")

    @classmethod
    def from_llm_response(cls, raw: Union[str, Dict[str, Any]]) -> "TestResult":
        """Parse LLM response (JSON string or dict) into TestResult."""
        return _parse_llm_response(cls, raw, "TestResult")


# -----------------------------------------------------------------------------
# Deployment
# -----------------------------------------------------------------------------


class DeploymentConfig(BaseModel):
    """Deployment configuration: Dockerfile, compose, CI pipeline, env, infrastructure."""

    dockerfile: str = Field(default="", description="Dockerfile content or path")
    docker_compose: str = Field(default="", description="Docker Compose content or path")
    ci_pipeline: str = Field(default="", description="CI pipeline configuration (e.g. YAML)")
    environment_variables: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variable definitions",
    )
    infrastructure: Optional[str] = Field(
        None,
        description="Terraform or CloudFormation template if applicable",
    )

    @classmethod
    def from_llm_response(cls, raw: Union[str, Dict[str, Any]]) -> "DeploymentConfig":
        """Parse LLM response (JSON string or dict) into DeploymentConfig."""
        return _parse_llm_response(cls, raw, "DeploymentConfig")


# -----------------------------------------------------------------------------
# Project report
# -----------------------------------------------------------------------------


def _default_timedelta() -> timedelta:
    """Default timedelta for ProjectReport.duration."""
    return timedelta(0)


class ProjectReport(BaseModel):
    """Final project report: id, name, status, files, test results, summary, duration, metrics."""

    project_id: str = Field(..., description="Project identifier")
    project_name: str = Field(..., description="Project name")
    status: str = Field(..., description="Final status (e.g. complete, failed)")
    files: List[CodeFile] = Field(
        default_factory=list,
        description="Generated code files",
    )
    test_results: TestResult = Field(
        default_factory=TestResult,
        description="Test run results",
    )
    summary: str = Field(default="", description="Executive summary")
    duration: timedelta = Field(
        default_factory=_default_timedelta,
        description="Total duration of the run",
    )
    agent_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-agent metrics (e.g. tokens, tasks)",
    )

    @classmethod
    def from_llm_response(cls, raw: Union[str, Dict[str, Any]]) -> "ProjectReport":
        """Parse LLM response (JSON string or dict) into ProjectReport."""
        return _parse_llm_response(cls, raw, "ProjectReport")


# -----------------------------------------------------------------------------
# JSON schema export and LLM parsing
# -----------------------------------------------------------------------------


def _parse_llm_response(
    model_class: type[BaseModel],
    raw: Union[str, Dict[str, Any]],
    label: str,
) -> BaseModel:
    """Parse JSON string or dict into a Pydantic model with clear validation errors."""
    from pydantic import ValidationError

    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            raise ValueError(f"{label}: LLM response is empty. Expected JSON object.")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"{label}: Invalid JSON from LLM: {e!s}. "
                "Ensure the response is valid JSON."
            ) from e
    else:
        data = raw

    if not isinstance(data, dict):
        raise ValueError(
            f"{label}: Expected a JSON object (dict); got {type(data).__name__}."
        )

    try:
        return model_class.model_validate(data)
    except ValidationError as e:
        parts = [f"{label} validation failed:"]
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            msg = err.get("msg", "invalid")
            parts.append(f"  - {loc}: {msg}")
        raise ValueError("\n".join(parts)) from e


def get_outputs_json_schema() -> Dict[str, Any]:
    """Return a combined JSON schema for all task output models in this module."""
    return {
        "RequirementsDocument": RequirementsDocument.model_json_schema(),
        "ArchitectureDocument": ArchitectureDocument.model_json_schema(),
        "CodeFile": CodeFile.model_json_schema(),
        "TestResult": TestResult.model_json_schema(),
        "DeploymentConfig": DeploymentConfig.model_json_schema(),
        "ProjectReport": ProjectReport.model_json_schema(),
    }
