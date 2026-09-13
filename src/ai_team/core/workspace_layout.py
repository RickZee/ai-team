"""Standard per-run workspace directories (backend-neutral, R10.2)."""

from __future__ import annotations

from pathlib import Path


def ensure_workspace_layout(workspace: Path, description: str) -> None:
    """Create standard directories and seed a short project brief."""
    for sub in (
        "docs",
        "docs/contracts",
        "src",
        "tests",
        "infrastructure",
        "logs",
        ".github/workflows",
    ):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    contracts_keep = workspace / "docs" / "contracts" / ".gitkeep"
    if not contracts_keep.exists():
        contracts_keep.write_text("", encoding="utf-8")
    brief = workspace / "docs" / "project_brief.md"
    if not brief.exists():
        brief.write_text(
            "# Project brief\n\n" + (description.strip() or "(no description provided)"),
            encoding="utf-8",
        )
