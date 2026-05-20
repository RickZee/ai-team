"""Pydantic models for artifact browser API responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RegistryRun(BaseModel):
    """A run entry from ``output/index.json`` or in-memory web state."""

    run_id: str = Field(..., description="Project / thread identifier.")
    output_dir: str | None = Field(default=None, description="Absolute bundle path when known.")
    started_at: str | None = None
    completed_at: str | None = None
    backend: str | None = None
    team_profile: str | None = None
    status: str | None = Field(default=None, description="Web session status when merged.")
    description: str | None = None


class ArtifactTreeNode(BaseModel):
    """Node in a nested file tree."""

    name: str
    path: str = Field(..., description="Path relative to tree root.")
    type: Literal["file", "dir"]
    size: int | None = Field(default=None, description="File size in bytes.")
    children: list[ArtifactTreeNode] = Field(default_factory=list)


class ArtifactFileContent(BaseModel):
    """File read response for the code viewer."""

    path: str
    root: Literal["workspace", "bundle"]
    content: str | None = Field(default=None, description="UTF-8 text when readable.")
    language: str | None = None
    size_bytes: int = 0
    is_binary: bool = False
    truncated: bool = False


class TestFailureItem(BaseModel):
    test_name: str
    error: str = ""
    traceback: str = ""


class FileCoverageItem(BaseModel):
    path: str
    line_coverage: float = 0.0
    branch_coverage: float = 0.0


class TestsPanelData(BaseModel):
    """Normalized test results for the Tests tab."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    coverage_line: float = 0.0
    coverage_branch: float = 0.0
    duration_seconds: float = 0.0
    failures: list[TestFailureItem] = Field(default_factory=list)
    per_file_coverage: list[FileCoverageItem] = Field(default_factory=list)
    raw_pytest: str | None = Field(default=None, description="pytest.txt excerpt when present.")
    source: str | None = Field(default=None, description="Which file supplied the data.")


class ArchitecturePanelData(BaseModel):
    """Architecture tab payload."""

    system_overview: str = ""
    ascii_diagram: str = ""
    components: list[dict[str, Any]] = Field(default_factory=list)
    technology_stack: list[dict[str, Any]] = Field(default_factory=list)
    interface_contracts: list[dict[str, Any]] = Field(default_factory=list)
    data_model_outline: str = ""
    deployment_topology: str = ""
    adrs: list[dict[str, Any]] = Field(default_factory=list)
    markdown_fallback: str | None = Field(
        default=None, description="Raw markdown when JSON architecture is unavailable."
    )
    source: str | None = None
