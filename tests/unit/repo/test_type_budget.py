"""mypy ignore_errors LOC budget (R8.2). Line count, not module count.

to see this fail: add a new module to ``ignore_errors`` in pyproject.toml
without lowering another, or raise ``mypy_ignore_errors_loc``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from tests.unit.repo._paths import REPO_ROOT, read_ratchets


def _patterns() -> list[str]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns: list[str] = []
    for override in data.get("tool", {}).get("mypy", {}).get("overrides", []):
        if override.get("ignore_errors"):
            patterns.extend(override.get("module", []))
    if not patterns:
        raise AssertionError("no ignore_errors overrides found — parser broken or list emptied")
    return patterns


def _module_to_paths(pattern: str) -> list[Path]:
    """Map a mypy module glob to files under src/ or evals/."""
    if pattern.endswith(".*"):
        stem = pattern[:-2].replace(".", "/")
        base = REPO_ROOT / "src" / stem if stem.startswith("ai_team/") else REPO_ROOT / stem
        if not base.is_dir():
            return []
        return [p for p in base.rglob("*.py") if "vendor" not in p.parts]
    dotted = pattern.replace(".", "/")
    if dotted.startswith("ai_team/"):
        path = REPO_ROOT / "src" / f"{dotted}.py"
        pkg = REPO_ROOT / "src" / dotted / "__init__.py"
    else:
        path = REPO_ROOT / f"{dotted}.py"
        pkg = REPO_ROOT / dotted / "__init__.py"
    out = []
    if path.is_file():
        out.append(path)
    if pkg.is_file():
        out.append(pkg)
    return out


def test_ignore_errors_loc_within_budget() -> None:
    budget = read_ratchets()["mypy_ignore_errors_loc"]
    files: set[Path] = set()
    for pat in _patterns():
        if "vendor" in pat:
            continue
        files.update(_module_to_paths(pat))
    if not files:
        raise AssertionError("ignore_errors matched zero files — glob is stale")
    loc = 0
    for path in files:
        loc += sum(1 for _ in path.read_text(encoding="utf-8", errors="replace").splitlines())
    assert loc <= budget, (
        f"ignore_errors covers {loc} LOC across {len(files)} files; "
        f"budget is {budget}. Retire an override or, only with a commit-message "
        f"explanation, raise the floor in tests/unit/repo/ratchets.toml."
    )
