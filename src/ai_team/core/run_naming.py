"""Human-readable run directory names for workspace and output/runs."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_INDEX_SUFFIX_RE = re.compile(r"^(\d{2,})$")


def slugify_run_label(text: str, *, max_len: int = 32) -> str:
    """Normalize *text* into a filesystem-safe slug."""
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    if len(slug) <= max_len:
        return slug or ""
    trimmed = slug[:max_len].rstrip("-")
    if "-" in trimmed:
        trimmed = trimmed.rsplit("-", 1)[0].rstrip("-")
    return trimmed or slug[:max_len].rstrip("-")


def derive_run_label(
    *,
    description: str = "",
    team_profile: str = "",
    explicit: str = "",
) -> str:
    """Choose the slug segment for a run id.

    Priority: explicit label → description slug (if meaningful) → team profile → ``run``.
    """
    if explicit.strip():
        slug = slugify_run_label(explicit)
        if slug:
            return slug
    desc_slug = slugify_run_label(description)
    if len(desc_slug) >= 3:
        return desc_slug
    profile_slug = slugify_run_label(team_profile)
    if profile_slug:
        return profile_slug
    return "run"


def allocate_run_id(
    label: str,
    *,
    search_roots: list[Path],
    started_at: datetime | None = None,
) -> str:
    """Return ``{YYYY-MM-DD}_{HHMMSS}_{slug}_{nn}`` with collision-safe index.

    Reserves the id by atomically creating its directory under the first
    writable search root (``mkdir`` fails if it already exists), so
    concurrent callers allocating the same label within the same second
    (e.g. the Compare tab launching 3 backends in parallel) can't both
    observe an empty directory listing and pick the same index.
    """
    when = started_at or datetime.now(UTC)
    slug = slugify_run_label(label) or "run"
    prefix = f"{when.strftime('%Y-%m-%d')}_{when.strftime('%H%M%S')}_{slug}_"
    max_index = 0
    for root in search_roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir() or not child.name.startswith(prefix):
                continue
            suffix = child.name[len(prefix) :]
            match = _INDEX_SUFFIX_RE.match(suffix)
            if match:
                max_index = max(max_index, int(match.group(1)))

    reserve_root = next((root for root in search_roots if root.is_dir()), None)
    if reserve_root is None and search_roots:
        # No search root exists yet (e.g. first run in a fresh workspace).
        # Without this the mkdir-based reservation below is skipped entirely
        # and concurrent callers (e.g. Compare launching 3 backends at once)
        # all return the same unreserved run_id.
        reserve_root = search_roots[0]
        os.makedirs(reserve_root, exist_ok=True)

    index = max_index + 1
    while True:
        run_id = f"{prefix}{index:02d}"
        if reserve_root is None:
            return run_id
        try:
            os.makedirs(reserve_root / run_id, exist_ok=False)
        except FileExistsError:
            index += 1
            continue
        return run_id


def default_run_search_roots() -> list[Path]:
    """Workspace and output/runs directories used for collision detection."""
    from ai_team.config.settings import get_settings
    from ai_team.core.results.writer import RUNS_SUBDIR

    settings = get_settings()
    ws = Path(settings.project.workspace_dir).resolve()
    runs = Path(settings.project.output_dir).resolve() / RUNS_SUBDIR
    return [ws, runs]


def resolve_run_id(
    *,
    description: str = "",
    team_profile: str = "",
    run_label: str = "",
    thread_id: str = "",
) -> str:
    """Allocate a new run id or return an explicit *thread_id* unchanged."""
    explicit_tid = thread_id.strip()
    if explicit_tid:
        return explicit_tid
    label = derive_run_label(
        description=description,
        team_profile=team_profile,
        explicit=run_label,
    )
    return allocate_run_id(label, search_roots=default_run_search_roots())
