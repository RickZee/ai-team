"""Tests for run directory naming helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ai_team.core.run_naming import (
    allocate_run_id,
    derive_run_label,
    slugify_run_label,
)


def test_slugify_run_label() -> None:
    assert slugify_run_label("Smoke Test Calculator!") == "smoke-test-calculator"
    assert slugify_run_label("  ") == ""


def test_derive_run_label_prefers_description() -> None:
    assert (
        derive_run_label(
            description="Write a Python add function",
            team_profile="prototype",
        )
        == "write-a-python-add-function"
    )


def test_derive_run_label_falls_back_to_profile() -> None:
    assert derive_run_label(description="ab", team_profile="prototype") == "prototype"


def test_derive_run_label_explicit_wins() -> None:
    assert derive_run_label(explicit="smoke-test", description="ignored") == "smoke-test"


def test_allocate_run_id_increments_index(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    runs = tmp_path / "output" / "runs"
    ws.mkdir(parents=True)
    runs.mkdir(parents=True)
    started = datetime(2026, 6, 28, 18, 14, 23, tzinfo=UTC)
    first = allocate_run_id(
        "smoke-test",
        search_roots=[ws, runs],
        started_at=started,
    )
    assert first == "2026-06-28_181423_smoke-test_01"
    assert (ws / first).is_dir()  # reserved atomically by allocate_run_id
    second = allocate_run_id(
        "smoke-test",
        search_roots=[ws, runs],
        started_at=started,
    )
    assert second == "2026-06-28_181423_smoke-test_02"


def test_allocate_run_id_concurrent_same_second_no_collision(tmp_path: Path) -> None:
    """Regression: Compare tab launches 3 backends in parallel with the same
    label in the same second; each must get a distinct id, not race on an
    empty directory listing."""
    ws = tmp_path / "workspace"
    runs = tmp_path / "output" / "runs"
    ws.mkdir(parents=True)
    runs.mkdir(parents=True)
    started = datetime(2026, 6, 28, 18, 14, 23, tzinfo=UTC)

    ids = [
        allocate_run_id("todo-app", search_roots=[ws, runs], started_at=started)
        for _ in range(3)
    ]

    assert len(set(ids)) == 3
    for run_id in ids:
        assert (ws / run_id).is_dir()
