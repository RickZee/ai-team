"""Session-wide guards that apply to every test in the suite.

These exist because of two defects found on 2026-09-12 that no amount of line coverage
would have caught: a unit test rewrote a committed golden record on every run
(`test_r16_unit_gaps.py` monkeypatched `VALIDATION_LOG` but not `ALIGNMENT_DIR`), and a
second test's assertion depended on the repo's `workspace/` directory being empty.

The rule both violate is the same one: **a test may not modify tracked files.** Ground
truth under `evals/golden/`, the replay corpus under `evals/fixtures/traces/`, and the
taxonomy are inputs to the $0 Tier A gate. A test that edits them corrupts the thing the
gate measures, and it does so silently — the suite still passes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Trees a test must never write to. Paths are repo-relative.
IMMUTABLE_TREES = (
    "evals/golden",
    "evals/fixtures/traces",
    "evals/taxonomy",
)


def _snapshot(root: Path) -> dict[str, str]:
    """Map repo-relative path -> sha256 for every file under the immutable trees."""
    digests: dict[str, str] = {}
    for rel in IMMUTABLE_TREES:
        tree = root / rel
        if not tree.exists():
            continue
        for path in sorted(tree.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            digests[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


@pytest.fixture(scope="session", autouse=True)
def _tracked_inputs_stay_immutable() -> Iterator[None]:
    before = _snapshot(REPO_ROOT)
    yield
    after = _snapshot(REPO_ROOT)

    modified = sorted(p for p in before.keys() & after.keys() if before[p] != after[p])
    removed = sorted(before.keys() - after.keys())
    added = sorted(after.keys() - before.keys())

    problems: list[str] = []
    if modified:
        problems.append(f"modified: {modified}")
    if removed:
        problems.append(f"removed: {removed}")
    if added:
        problems.append(f"created: {added}")

    assert not problems, (
        "the test suite wrote to tracked ground-truth files — "
        + "; ".join(problems)
        + ". Redirect the write to tmp_path (monkeypatch the module's directory constant, "
        "e.g. evals.alignment.ALIGNMENT_DIR and VALIDATION_LOG) rather than relaxing this guard."
    )
