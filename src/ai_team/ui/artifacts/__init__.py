"""Artifact browser service for web dashboard."""

from ai_team.ui.artifacts.models import (
    ArchitecturePanelData,
    ArtifactFileContent,
    ArtifactTreeNode,
    RegistryRun,
    TestsPanelData,
)
from ai_team.ui.artifacts.service import (
    build_tree,
    load_architecture_panel,
    load_registry,
    load_tests_panel,
    read_artifact_file,
    resolve_project_paths,
    workspace_zip_bytes,
)

__all__ = [
    "ArchitecturePanelData",
    "ArtifactFileContent",
    "ArtifactTreeNode",
    "RegistryRun",
    "TestsPanelData",
    "build_tree",
    "load_architecture_panel",
    "load_registry",
    "load_tests_panel",
    "read_artifact_file",
    "resolve_project_paths",
    "workspace_zip_bytes",
]
