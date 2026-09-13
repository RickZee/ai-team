"""Relative markdown links and source paths resolve (R4).

Workspace artifacts use the ``<workspace>/`` prefix and are skipped.
External http(s) links are out of scope.

Targets inside the repo must be **git-tracked**. A file that exists only
locally (gitignored ``.archive/`` drafts) is a CI miss — that is how
``docs/prompts/PROMPTS.md`` pointed at ``.archive/phase-7-agentcore-deployment.md``
and passed on a dirty tree.

to see this fail: add ``[x](does-not-exist.md)`` to README.md.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tests.unit.repo._paths import REPO_ROOT

_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "workspace", "output", ".archive"})


def _tracked_paths() -> set[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO_ROOT)
    paths = {p.decode() for p in raw.split(b"\0") if p}
    if not paths:
        raise AssertionError("git ls-files returned empty — not a clone?")
    return paths


def _tracked_in_repo(resolved: Path, tracked: set[str]) -> bool:
    try:
        rel = resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return False
    if rel in tracked:
        return True
    prefix = rel if rel.endswith("/") else f"{rel}/"
    return any(t.startswith(prefix) for t in tracked)


def test_relative_markdown_links_resolve() -> None:
    tracked = _tracked_paths()
    md_files = [REPO_ROOT / rel for rel in sorted(tracked) if rel.endswith(".md")]
    md_files = [p for p in md_files if not any(part in _SKIP_DIRS for part in p.parts)]
    if not md_files:
        raise AssertionError("no markdown files found — walker broken")
    missing: list[str] = []
    for path in md_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        in_fence = False
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in _LINK_RE.finditer(line):
                target = match.group(2).strip()
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                if "<workspace>/" in target:
                    continue
                href = target.split("#", 1)[0].split("?", 1)[0]
                if not href or " " in href or "," in href:
                    continue
                resolved = (path.parent / href).resolve()
                if not _tracked_in_repo(resolved, tracked):
                    missing.append(
                        f"{path.relative_to(REPO_ROOT)}:{i} → {href} is not a git-tracked path"
                    )
    assert not missing, "Unresolvable relative links:\n" + "\n".join(missing[:50])
