"""Pydantic models for development-phase outputs (code files, deployment config)."""

from pydantic import BaseModel, Field


class CodeFile(BaseModel):
    """Represents a generated code file."""

    path: str = Field(..., description="Relative path of the file")
    content: str = Field(..., description="File contents")
    language: str = Field(..., description="Programming or markup language")
    description: str = Field(..., description="Brief description of the file")
    has_tests: bool = Field(default=False, description="Whether the file has associated tests")


class CodeFileList(BaseModel):
    """Wrapper for task output that is a list of CodeFile (CrewAI output_pydantic).

    Uses a named field (not RootModel) to avoid CrewAI's JSON encoder bug where
    it calls .items() on a list root, causing AttributeError.
    """

    files: list[CodeFile] = Field(default_factory=list, description="List of generated code files")


class DeploymentConfig(BaseModel):
    """Deployment configuration output (Dockerfile, compose, CI/CD)."""

    dockerfile: str | None = Field(default=None, description="Dockerfile content or path")
    docker_compose: str | None = Field(default=None, description="Docker Compose content or path")
    ci_cd_config: str | None = Field(default=None, description="CI/CD pipeline configuration")
    environment_variables: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variable definitions",
    )
