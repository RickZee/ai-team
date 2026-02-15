"""
Developer agent tools: code generation, file writing, dependencies, code review.

Common tools are used by DeveloperBase; backend/frontend-specific tools are used
by BackendDeveloper and FrontendDeveloper. Full implementations (e.g. secure file
writer, sandbox execution) are added in phase 2.8 / 2.9; these stubs allow
developer agents to be instantiated and wired into crews.
"""

from typing import Any, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


# -----------------------------------------------------------------------------
# Common developer tool input schemas
# -----------------------------------------------------------------------------


class CodeGenerationInput(BaseModel):
    """Input for code_generation tool."""

    prompt: str = Field(..., description="Description of the code to generate.")
    language: Optional[str] = Field(default=None, description="Target language (e.g. python, typescript).")
    context: Optional[str] = Field(default=None, description="Additional context (architecture, requirements).")


class FileWriterInput(BaseModel):
    """Input for file_writer tool."""

    path: str = Field(..., description="Relative path where the file should be written.")
    content: str = Field(..., description="Full file content to write.")
    overwrite: bool = Field(default=False, description="Whether to overwrite existing file.")


class DependencyResolverInput(BaseModel):
    """Input for dependency_resolver tool."""

    manifest_path: Optional[str] = Field(default=None, description="Path to requirements.txt, package.json, etc.")
    dependency_name: Optional[str] = Field(default=None, description="Single dependency to add or resolve.")
    action: str = Field(default="list", description="One of: list, add, check.")


class CodeReviewerInput(BaseModel):
    """Input for code_reviewer tool."""

    code: str = Field(..., description="Code snippet or file content to review.")
    focus: Optional[str] = Field(default=None, description="Focus area: style, security, performance, correctness.")


# -----------------------------------------------------------------------------
# Backend-specific tool input schemas
# -----------------------------------------------------------------------------


class DatabaseSchemaDesignInput(BaseModel):
    """Input for database_schema_design tool."""

    requirements: str = Field(..., description="Requirements or entities to model.")
    dialect: Optional[str] = Field(default="postgresql", description="SQL dialect (postgresql, mysql, sqlite).")


class ApiImplementationInput(BaseModel):
    """Input for api_implementation tool."""

    spec: str = Field(..., description="API spec (OpenAPI snippet or endpoint description).")
    framework: Optional[str] = Field(default="fastapi", description="Framework: fastapi, flask, express, gin.")


class OrmGeneratorInput(BaseModel):
    """Input for orm_generator tool."""

    schema_or_entities: str = Field(..., description="Schema DDL or entity descriptions.")
    orm: Optional[str] = Field(default="sqlalchemy", description="ORM: sqlalchemy, django, prisma, gorm.")


# -----------------------------------------------------------------------------
# Frontend-specific tool input schemas
# -----------------------------------------------------------------------------


class ComponentGeneratorInput(BaseModel):
    """Input for component_generator tool."""

    description: str = Field(..., description="Description of the UI component to generate.")
    framework: Optional[str] = Field(default="react", description="Framework: react, vue, svelte.")
    props: Optional[str] = Field(default=None, description="Optional props/API as JSON or list.")


class StateManagementInput(BaseModel):
    """Input for state_management tool."""

    requirement: str = Field(..., description="State management need (e.g. global store, form state).")
    library: Optional[str] = Field(default=None, description="Library: redux, zustand, pinia, context.")


class ApiClientGeneratorInput(BaseModel):
    """Input for api_client_generator tool."""

    base_url_or_spec: str = Field(..., description="API base URL or OpenAPI spec path.")
    language: Optional[str] = Field(default="typescript", description="Client language: typescript, javascript.")


# -----------------------------------------------------------------------------
# Common developer tools (DeveloperBase)
# -----------------------------------------------------------------------------


def _stub_message(tool_name: str) -> str:
    """Return a consistent stub message for not-yet-implemented tools."""
    return (
        f"[{tool_name}] Tool stub: full implementation in phase 2.8/2.9. "
        "Use your reasoning to produce the output; the result will be validated by guardrails."
    )


class CodeGenerationTool(BaseTool):
    """Generate code from a prompt with optional language and context."""

    name: str = "code_generation"
    description: str = (
        "Generate code from a natural language prompt. Provide the prompt, optional language "
        "and context (e.g. from architecture doc or requirements). Follow PEP8 for Python, "
        "ESLint conventions for JavaScript/TypeScript."
    )
    args_schema: Type[BaseModel] = CodeGenerationInput

    def _run(
        self,
        prompt: str,
        language: Optional[str] = None,
        context: Optional[str] = None,
    ) -> str:
        logger.debug("code_generation", prompt=prompt[:80], language=language)
        return _stub_message("code_generation")


class FileWriterTool(BaseTool):
    """Write content to a file at a given path (stub; secure writer in phase 2.8)."""

    name: str = "file_writer"
    description: str = (
        "Write content to a file at the given path. Use relative paths within the project. "
        "Set overwrite=true to replace existing files. All writes are validated by guardrails."
    )
    args_schema: Type[BaseModel] = FileWriterInput

    def _run(
        self,
        path: str,
        content: str,
        overwrite: bool = False,
    ) -> str:
        logger.debug("file_writer", path=path, overwrite=overwrite)
        return _stub_message("file_writer")


class DependencyResolverTool(BaseTool):
    """List, add, or check project dependencies (stub)."""

    name: str = "dependency_resolver"
    description: str = (
        "List, add, or check dependencies for a project. Use manifest_path for requirements.txt, "
        "package.json, go.mod, etc. Action: list, add, or check."
    )
    args_schema: Type[BaseModel] = DependencyResolverInput

    def _run(
        self,
        manifest_path: Optional[str] = None,
        dependency_name: Optional[str] = None,
        action: str = "list",
    ) -> str:
        logger.debug("dependency_resolver", action=action, manifest=manifest_path)
        return _stub_message("dependency_resolver")


class CodeReviewerTool(BaseTool):
    """Review code for style, security, performance, and correctness."""

    name: str = "code_reviewer"
    description: str = (
        "Review code for style (PEP8/ESLint), security, performance, and correctness. "
        "Use as part of self-review before marking a task complete."
    )
    args_schema: Type[BaseModel] = CodeReviewerInput

    def _run(
        self,
        code: str,
        focus: Optional[str] = None,
    ) -> str:
        logger.debug("code_reviewer", focus=focus)
        return _stub_message("code_reviewer")


# -----------------------------------------------------------------------------
# Backend-specific tools
# -----------------------------------------------------------------------------


class DatabaseSchemaDesignTool(BaseTool):
    """Design database schema from requirements (stub)."""

    name: str = "database_schema_design"
    description: str = (
        "Design database schema (tables, indexes) from requirements. Supports PostgreSQL, MySQL, SQLite."
    )
    args_schema: Type[BaseModel] = DatabaseSchemaDesignInput

    def _run(
        self,
        requirements: str,
        dialect: Optional[str] = None,
    ) -> str:
        logger.debug("database_schema_design", dialect=dialect)
        return _stub_message("database_schema_design")


class ApiImplementationTool(BaseTool):
    """Implement API endpoints from spec (stub)."""

    name: str = "api_implementation"
    description: str = (
        "Implement API endpoints from a spec. Supports FastAPI, Flask, Django, Express, Gin."
    )
    args_schema: Type[BaseModel] = ApiImplementationInput

    def _run(
        self,
        spec: str,
        framework: Optional[str] = None,
    ) -> str:
        logger.debug("api_implementation", framework=framework)
        return _stub_message("api_implementation")


class OrmGeneratorTool(BaseTool):
    """Generate ORM models from schema (stub)."""

    name: str = "orm_generator"
    description: str = (
        "Generate ORM models (SQLAlchemy, Django, Prisma, GORM) from schema or entity descriptions."
    )
    args_schema: Type[BaseModel] = OrmGeneratorInput

    def _run(
        self,
        schema_or_entities: str,
        orm: Optional[str] = None,
    ) -> str:
        logger.debug("orm_generator", orm=orm)
        return _stub_message("orm_generator")


# -----------------------------------------------------------------------------
# Frontend-specific tools
# -----------------------------------------------------------------------------


class ComponentGeneratorTool(BaseTool):
    """Generate UI components (stub)."""

    name: str = "component_generator"
    description: str = (
        "Generate UI components for React, Vue, or Svelte. Optionally specify props/API."
    )
    args_schema: Type[BaseModel] = ComponentGeneratorInput

    def _run(
        self,
        description: str,
        framework: Optional[str] = None,
        props: Optional[str] = None,
    ) -> str:
        logger.debug("component_generator", framework=framework)
        return _stub_message("component_generator")


class StateManagementTool(BaseTool):
    """Generate state management code (stub)."""

    name: str = "state_management"
    description: str = (
        "Generate state management setup (Redux, Zustand, Pinia, Context API) from requirements."
    )
    args_schema: Type[BaseModel] = StateManagementInput

    def _run(
        self,
        requirement: str,
        library: Optional[str] = None,
    ) -> str:
        logger.debug("state_management", library=library)
        return _stub_message("state_management")


class ApiClientGeneratorTool(BaseTool):
    """Generate API client code from spec or base URL (stub)."""

    name: str = "api_client_generator"
    description: str = (
        "Generate typed API client code (TypeScript/JavaScript) from base URL or OpenAPI spec."
    )
    args_schema: Type[BaseModel] = ApiClientGeneratorInput

    def _run(
        self,
        base_url_or_spec: str,
        language: Optional[str] = "typescript",
    ) -> str:
        logger.debug("api_client_generator", language=language)
        return _stub_message("api_client_generator")


# -----------------------------------------------------------------------------
# Tool list factories
# -----------------------------------------------------------------------------


def get_developer_common_tools() -> List[BaseTool]:
    """Tools shared by all developers (DeveloperBase)."""
    return [
        CodeGenerationTool(),
        FileWriterTool(),
        DependencyResolverTool(),
        CodeReviewerTool(),
    ]


def get_backend_developer_tools() -> List[BaseTool]:
    """Additional tools for BackendDeveloper."""
    return [
        DatabaseSchemaDesignTool(),
        ApiImplementationTool(),
        OrmGeneratorTool(),
    ]


def get_frontend_developer_tools() -> List[BaseTool]:
    """Additional tools for FrontendDeveloper."""
    return [
        ComponentGeneratorTool(),
        StateManagementTool(),
        ApiClientGeneratorTool(),
    ]


def get_fullstack_developer_tools() -> List[BaseTool]:
    """All developer tools for FullstackDeveloper (common + backend + frontend)."""
    return (
        get_developer_common_tools()
        + get_backend_developer_tools()
        + get_frontend_developer_tools()
    )
