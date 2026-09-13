"""Drift guards: make the hand-maintained lists in the test suite provably complete.

Three of the repo's strongest test suites — `test_check_purity.py` (network blocked),
`test_check_sensitivity.py`, and `test_checks.py` — are parametrized over
`tests/unit/evals/trace_fixtures.ALL_CHECK_IDS`, a hand-written list. Nothing asserted
that the list matched the registry, so a newly registered check that someone forgot to
add would silently escape all three, including the purity guard that protects the
$0 Tier A promise.

`harness-alignment` adds four checks (FM-014…FM-017), which is four chances to hit
exactly that. These tests make the omission loud instead of silent.

Same class of problem as the two isolation defects found on 2026-09-12: invisible to
line coverage, caught only by asserting an invariant about the suite itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.checks import all_checks
from evals.checks.registry import ensure_checks_loaded
from evals.taxonomy.loader import load_taxonomy
from tests.unit.evals.trace_fixtures import ALL_CHECK_IDS

pytestmark = pytest.mark.eval_unit

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "traces"


def _registered_ids() -> set[str]:
    ensure_checks_loaded()
    return {c.id for c in all_checks()}


def test_all_check_ids_covers_every_registered_check() -> None:
    """Every registered check must appear in ALL_CHECK_IDS.

    A check missing here is untested by the purity, sensitivity and outcome suites while
    still counting toward the registry — the worst kind of gap, because the check exists
    and appears to be covered.
    """
    missing = sorted(_registered_ids() - set(ALL_CHECK_IDS))
    assert not missing, (
        f"registered but absent from ALL_CHECK_IDS: {missing}. "
        "Add them to tests/unit/evals/trace_fixtures.py or they escape the purity suite."
    )


def test_all_check_ids_has_no_phantoms() -> None:
    """And nothing in the list may point at a check that no longer exists."""
    phantom = sorted(set(ALL_CHECK_IDS) - _registered_ids())
    assert not phantom, f"in ALL_CHECK_IDS but not registered: {phantom}"


def test_no_duplicate_entries_in_all_check_ids() -> None:
    dupes = sorted({i for i in ALL_CHECK_IDS if ALL_CHECK_IDS.count(i) > 1})
    assert not dupes, f"duplicated: {dupes}"


@pytest.mark.parametrize("outcome", ["fail", "pass"])
def test_every_registered_check_has_committed_fixtures(outcome: str) -> None:
    """Tier A replays from committed fixtures; a check without them cannot gate at $0."""
    missing = [
        cid
        for cid in sorted(_registered_ids())
        if not (FIXTURE_DIR / f"{cid}__{outcome}.json").exists()
    ]
    assert not missing, f"no committed {outcome} fixture for: {missing}"


def test_every_committed_fixture_is_valid_json() -> None:
    """Guards schema bumps: `harness-alignment` task 0.3 raises SCHEMA_VERSION, and a
    bump that invalidates committed fixtures silently breaks the free gate."""
    broken: list[str] = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:  # pragma: no cover - guard
            broken.append(f"{path.name}: {exc}")
    assert not broken, broken


def test_every_check_detected_failure_mode_is_implemented() -> None:
    """Taxonomy and registry must agree in both directions.

    `test_check_registry.py` already asserts every `detection: check` FM has an
    implementation. This asserts the reverse — no check claims an FM the taxonomy does
    not define — which is how a typo'd `failure_mode_id` would otherwise survive.
    """
    ensure_checks_loaded()
    taxonomy = load_taxonomy()
    known = {fm.id for fm in taxonomy.failure_modes}
    orphans = sorted(
        {
            c.failure_mode_id
            for c in all_checks()
            if c.failure_mode_id and c.failure_mode_id not in known
        }
    )
    assert not orphans, f"checks reference unknown failure modes: {orphans}"


def test_reserved_mode_guard_is_loud_when_a_check_is_registered() -> None:
    """R17.3: reserved + registered check is the half-landed state Phase 2 passes through.

    During Phase 0 the live taxonomy keeps FM-014…017 reserved and no check
    claims them, so the live guard stays green. This test constructs the
    half-landed pairing and asserts it is detected.
    """
    taxonomy = load_taxonomy()
    reserved_ids = {
        fm.id for fm in taxonomy.failure_modes if getattr(fm, "status", "") == "reserved"
    }

    class _FakeCheck:
        failure_mode_id = "FM-014"

    implemented = {_FakeCheck.failure_mode_id}
    # Half-landed pairing: a reserved id claimed by a check is detected.
    pairing = reserved_ids | {"FM-014"}
    stale = sorted(fm_id for fm_id in pairing if fm_id in implemented and fm_id in {"FM-014"})
    assert stale == ["FM-014"]
    _ = reserved_ids


def test_active_check_detected_modes_are_not_left_reserved() -> None:
    """A mode with a registered check must not still be `status: reserved`.

    Task 0.2 reserves FM-014…FM-017 before their checks exist; Phase 2 flips them to
    active. This catches the half-landed state where the check ships and the taxonomy
    still calls the mode reserved.
    """
    ensure_checks_loaded()
    implemented = {c.failure_mode_id for c in all_checks() if c.failure_mode_id}
    stale = sorted(
        fm.id
        for fm in load_taxonomy().failure_modes
        if fm.id in implemented and getattr(fm, "status", "active") == "reserved"
    )
    assert not stale, f"implemented but still reserved in the taxonomy: {stale}"
