"""
Ground truth for the committed check fixtures (the layer a baseline cannot provide).

A baseline answers *"did this change since last time?"*. The fixture corpus asks a different
question: *"is this what it is supposed to be?"* — and it already carries the answer. A trace
whose id is ``CHK-draft-commit__pass__fixture`` was hand-built so that ``CHK-draft-commit``
passes on it. That is a specification, not an observation.

Using baseline machinery for it is what broke the gate. ``evals/baselines/tier_a.json`` held
one collapsed outcome per check, and because the corpus deliberately contains a failing
fixture for every check, ``baseline accept`` recorded ``"fail"`` for all twenty. The gate's
only regression rule is ``baseline == "pass" and "fail" in current``, so that branch became
dead code across the whole suite: a check could stop passing its own pass fixture, or start
passing its own fail fixture, and Tier A exited 0. Found on 2026-09-17 by a tester who
deleted a pass fixture and watched the gate wave it through
(``course/testing/runs/2026-09-17-stranger-3``, R12).

Three rules, none of which need a baseline:

1. **Completeness** — in a report that replays the fixture corpus, every check that ran has
   all three fixtures (``pass``, ``fail``, ``na``).
   This is the rule week 5 already teaches; it just was not enforced. It is also the only rule
   that can notice a *deleted* fixture, since an expectation table built from the files that
   exist cannot miss what is not there.
2. **Expectation** — every fixture produces the outcome its id declares, for its own check.
   Violations fail in both directions: pass→fail means the check broke, fail→pass means it
   went blind.
3. **Uniqueness** — no trace id is loaded twice. Duplicates silently double-count in every
   rate the suite reports.

Every rule is evaluated over a :class:`~evals.aggregate.SuiteReport`'s ``check_results``, so
this module touches no disk and the gate stays a pure function of the report.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Literal

from pydantic import BaseModel

from evals.checks.base import CheckResult

#: Trace-id suffix that marks a fixture carrying a declared expectation.
EXPECTATION_SUFFIX = "__fixture"

#: Outcomes every check must have a fixture for, in the fixture-id spelling.
REQUIRED_OUTCOMES: tuple[str, ...] = ("pass", "fail", "na")

#: Fixture-id spelling → ``CheckOutcome`` spelling.
_OUTCOME_ALIASES = {"na": "not_applicable"}

ViolationKind = Literal["expectation", "completeness", "uniqueness"]


class ContractViolation(BaseModel):
    """One broken promise about the fixture corpus."""

    kind: ViolationKind
    check_id: str
    message: str
    trace_id: str | None = None
    expected: str | None = None
    actual: str | None = None

    @property
    def gating(self) -> bool:
        """Uniqueness is reported but does not fail the gate: it asks a human to delete files."""
        return self.kind != "uniqueness"


def parse_expectation(trace_id: str) -> tuple[str, str] | None:
    """``CHK-x__pass__fixture`` → ``("CHK-x", "pass")``; anything else → ``None``.

    Traces without the suffix (the ``coverage__<backend>__<status>`` set, and every real
    run) carry no expectation and are exempt from rules 1 and 2.
    """
    if not trace_id.endswith(EXPECTATION_SUFFIX):
        return None
    stem = trace_id[: -len(EXPECTATION_SUFFIX)]
    check_id, sep, outcome = stem.rpartition("__")
    if not sep or not check_id or outcome not in REQUIRED_OUTCOMES:
        return None
    return check_id, outcome


def expected_outcome(fixture_outcome: str) -> str:
    """Fixture spelling → the ``CheckResult.outcome`` value it promises."""
    return _OUTCOME_ALIASES.get(fixture_outcome, fixture_outcome)


def _expectation_violations(results: list[CheckResult]) -> list[ContractViolation]:
    out: list[ContractViolation] = []
    for r in results:
        parsed = parse_expectation(r.trace_id)
        if parsed is None:
            continue
        owner, fixture_outcome = parsed
        # A fixture constrains only the check it was built for. Every other check running
        # over it is incidental (and almost always abstains).
        if owner != r.check_id:
            continue
        want = expected_outcome(fixture_outcome)
        if r.outcome != want:
            out.append(
                ContractViolation(
                    kind="expectation",
                    check_id=r.check_id,
                    trace_id=r.trace_id,
                    expected=want,
                    actual=r.outcome,
                    message=(
                        f"{r.check_id} returned {r.outcome} on its own {fixture_outcome} "
                        f"fixture, which is built to make it {want}"
                    ),
                )
            )
    return out


def _completeness_violations(results: list[CheckResult]) -> list[ContractViolation]:
    have: dict[str, set[str]] = defaultdict(set)
    for r in results:
        parsed = parse_expectation(r.trace_id)
        if parsed is None:
            continue
        owner, fixture_outcome = parsed
        have[owner].add(fixture_outcome)

    # Only a report that is replaying the fixture corpus has a corpus to be complete. A live
    # CORPUS run scores real traces and owes no fixtures; demanding them there would make
    # every non-replay report fail.
    if not have:
        return []

    ran = {r.check_id for r in results}
    out: list[ContractViolation] = []
    for check_id in sorted(ran):
        missing = [o for o in REQUIRED_OUTCOMES if o not in have.get(check_id, set())]
        if missing:
            out.append(
                ContractViolation(
                    kind="completeness",
                    check_id=check_id,
                    expected=",".join(REQUIRED_OUTCOMES),
                    actual=",".join(sorted(have.get(check_id, set()))) or "none",
                    message=(
                        f"{check_id} has no committed {'/'.join(missing)} fixture. "
                        "Every check needs all three outcomes, including a reason to abstain."
                    ),
                )
            )
    return out


def _owning_check(trace_id: str) -> str:
    parsed = parse_expectation(trace_id)
    return parsed[0] if parsed else ""


def _uniqueness_violations(results: list[CheckResult]) -> list[ContractViolation]:
    seen: Counter[tuple[str, str]] = Counter((r.check_id, r.trace_id) for r in results)
    dupes = sorted({trace_id for (_, trace_id), n in seen.items() if n > 1})
    return [
        ContractViolation(
            kind="uniqueness",
            check_id=_owning_check(t),
            trace_id=t,
            message=(
                f"trace {t} was loaded more than once, so it counts more than once in "
                "every rate this suite reports. Two files under evals/fixtures/traces/ "
                "most likely carry the same trace_id."
            ),
        )
        for t in dupes
    ]


def evaluate_fixture_contract(results: list[CheckResult]) -> list[ContractViolation]:
    """All three rules, worst first: expectation, completeness, then uniqueness."""
    return [
        *_expectation_violations(results),
        *_completeness_violations(results),
        *_uniqueness_violations(results),
    ]
