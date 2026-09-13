"""Relative markdown links and source paths resolve (R4).

Workspace artifacts use the ``<workspace>/`` prefix and are skipped.
External http(s) links are out of scope.

to see this fail: add ``[x](does-not-exist.md)`` to README.md.
"""

from __future__ import annotations

import re

from tests.unit.repo._paths import REPO_ROOT

_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_SKIP_DIRS = frozenset({".git", "node_modules", ".venv", "workspace", "output", ".archive"})


def test_relative_markdown_links_resolve() -> None:
    md_files = [
        p for p in REPO_ROOT.rglob("*.md") if not any(part in _SKIP_DIRS for part in p.parts)
    ]
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
                if not resolved.exists():
                    missing.append(f"{path.relative_to(REPO_ROOT)}:{i} → {href} does not exist")
    assert not missing, "Unresolvable relative links:\n" + "\n".join(missing[:50])
