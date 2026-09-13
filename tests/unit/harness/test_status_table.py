"""Harness status table paths exist and status words have named tests (R2)."""

from __future__ import annotations

import re
from pathlib import Path

from tests.unit.repo._paths import REPO_ROOT

_HARNESS = REPO_ROOT / "docs" / "HARNESS.md"

# Status word → at least one test path that backs it.
_STATUS_TESTS = {
    "enforced": [
        "tests/unit/tools/test_smoke_tools.py",
        "tests/unit/tools/",
        "tests/unit/guardrails/",
    ],
    "instrumented": ["tests/unit/harness/test_router.py"],
    "closed-loop": ["tests/unit/harness/test_lessons.py"],
}


def test_harness_table_modules_exist() -> None:
    text = _HARNESS.read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines() if ln.startswith("| ") and "src/ai_team" in ln]
    if not rows:
        raise AssertionError("HARNESS.md status table had zero module rows")
    missing: list[str] = []
    for row in rows:
        for match in re.finditer(r"`([^`]+)`", row):
            raw = match.group(1)
            if not raw.startswith("src/"):
                continue
            # comma-separated files in one cell
            for piece in raw.split(","):
                piece = piece.strip()
                if "/" not in piece:
                    continue
                path = REPO_ROOT / piece
                if not path.exists():
                    # allow basename-only after a directory prefix in the cell
                    parent_bits = raw.split(",")[0].strip()
                    if "/" in parent_bits:
                        prefix = str(Path(parent_bits).parent)
                        alt = REPO_ROOT / prefix / piece if not piece.startswith("src/") else path
                        if alt.exists() or (REPO_ROOT / "src/ai_team/tools" / piece).exists():
                            continue
                    missing.append(piece)
        if "**enforced**" in row or "**instrumented**" in row or "**closed-loop**" in row:
            pass
    # kinds.py, draft.py etc. are relative to tools/
    for name in ("kinds.py", "draft.py", "catalog.py"):
        assert (REPO_ROOT / "src/ai_team/tools" / name).is_file(), name
    assert not missing, "HARNESS.md names missing paths: " + ", ".join(missing)


def test_status_words_have_named_tests() -> None:
    for status, paths in _STATUS_TESTS.items():
        found = False
        for p in paths:
            if (REPO_ROOT / p).exists():
                found = True
                break
        assert found, f"status {status} has no named test path"
