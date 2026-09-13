"""No pytest file lives outside ``testpaths`` (R6.3).

to see this fail: add ``evals/test_orphan.py``.
"""

from __future__ import annotations

from tests.unit.repo._paths import REPO_ROOT

# Vendor copies, local debris, and tool modules named test_*.py are not pytest files.
_SKIP_PARTS = frozenset(
    {"vendor", "node_modules", ".venv", "workspace", ".archive", ".git", "output", "dist"}
)
_SKIP_FILES = frozenset({"src/ai_team/tools/test_tools.py"})


def test_no_test_files_outside_testpaths() -> None:
    found: list[str] = []
    for path in REPO_ROOT.rglob("test_*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part in _SKIP_PARTS for part in path.parts):
            continue
        if rel in _SKIP_FILES:
            continue
        if rel.startswith("tests/"):
            continue
        found.append(rel)
    # Empty glob of the repo would be a broken walker, not a pass.
    scanned = list(REPO_ROOT.joinpath("tests").rglob("test_*.py"))
    if not scanned:
        raise AssertionError("tests/ contained zero test_*.py files — walker is broken")
    assert not found, (
        "pytest will never collect these (testpaths = ['tests']). "
        "Move them under tests/ or delete them:\n" + "\n".join(found)
    )
