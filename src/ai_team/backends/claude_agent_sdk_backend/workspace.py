"""Workspace layout and artifact collection for file-based agent handoff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
from ai_team.core.team_profile import TeamProfile

logger = structlog.get_logger(__name__)


def infer_repo_root(workspace: Path) -> Path:
    """Walk parents to find a directory containing ``pyproject.toml``."""
    for p in [workspace, *workspace.parents]:
        if (p / "pyproject.toml").is_file():
            return p
    return workspace.resolve().parent


def read_claude_md_excerpt(repo_root: Path, *, max_chars: int = 8000) -> str:
    """Return trimmed CLAUDE.md contents for system prompt injection."""
    path = repo_root / "CLAUDE.md"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[... truncated ...]"
    return text


def write_profile_claude_context(workspace: Path, profile: TeamProfile) -> None:
    """Write ``workspace/docs/CLAUDE_PROFILE.md`` for orchestrator context (T7.2)."""
    lines = [
        f"# Team profile: {profile.name}",
        "",
        f"- **Agents:** {', '.join(profile.agents)}",
        f"- **Phases:** {', '.join(profile.phases)}",
        "",
    ]
    rag = profile.metadata.get("rag")
    if isinstance(rag, dict):
        topics = rag.get("knowledge_topics")
        if topics:
            lines.append("## Knowledge topics")
            lines.append("")
            lines.append(repr(topics))
            lines.append("")
    lines.append("Follow repository conventions in the repo root `CLAUDE.md` when present.")
    lines.append("")
    path = workspace / "docs" / "CLAUDE_PROFILE.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def ensure_workspace_layout(workspace: Path, description: str) -> None:
    """Create standard directories and seed a short project brief."""
    for sub in (
        "docs",
        "src",
        "tests",
        "infrastructure",
        "logs",
        ".github/workflows",
    ):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    brief = workspace / "docs" / "project_brief.md"
    if not brief.exists():
        brief.write_text(
            "# Project brief\n\n" + (description.strip() or "(no description provided)"),
            encoding="utf-8",
        )


def read_text_if_exists(path: Path) -> str | None:
    """Return file contents or None if missing."""
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.warning("claude_workspace_read_failed", path=str(path), error=str(e))
        return None


def read_json_if_exists(path: Path) -> Any | None:
    """Parse JSON file or return None."""
    raw = read_text_if_exists(path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSON lines; skip bad lines."""
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except json.JSONDecodeError:
            continue
    return out


def list_files_under(root: Path, *, max_files: int = 500) -> list[str]:
    """Relative paths for files under root (bounded)."""
    if not root.is_dir():
        return []
    paths: list[str] = []
    skip_dirs = {".git", "__pycache__", ".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
    for p in root.rglob("*"):
        rel_parts = p.relative_to(root).parts
        if p.is_file() and not any(part in skip_dirs for part in rel_parts):
            paths.append(str(p.relative_to(root)).replace("\\", "/"))
            if len(paths) >= max_files:
                break
    return sorted(paths)


def collect_deployment_hints(workspace: Path) -> dict[str, Any]:
    """Summarize common deployment paths if present."""
    hints: dict[str, Any] = {}
    for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml"):
        p = workspace / name
        if p.is_file():
            hints[name] = str(p.relative_to(workspace))
    gh = workspace / ".github" / "workflows"
    if gh.is_dir():
        hints["github_workflows"] = [
            str(x.relative_to(workspace)).replace("\\", "/")
            for x in gh.glob("*.yml")
        ]
    infra = workspace / "infrastructure"
    if infra.is_dir():
        hints["infrastructure_files"] = list_files_under(infra, max_files=100)
    return hints


def write_session_record(workspace: Path, payload: dict[str, Any]) -> None:
    """Persist session metadata for resume workflows."""
    log_dir = workspace / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "session.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
