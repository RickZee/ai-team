"""Aggregate check results, verdicts, and metrics into a SuiteReport (R13)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from evals.alignment import bias_corrected_rate
from evals.checks.base import CheckResult
from evals.provenance import Provenance
from evals.reliability import cell_summary, indistinguishable, wilson_ci
from evals.taxonomy.loader import Taxonomy, load_taxonomy

VENDOR_BY_BACKEND: dict[str, str] = {
    "crewai": "openrouter",
    "langgraph": "openrouter",
    "claude-agent-sdk": "anthropic",
}


class RateWithCI(BaseModel):
    """A rate with sample size and Wilson 95% CI (R13.3)."""

    value: float | None = Field(description="Point estimate in [0, 1], or None if n=0")
    n: int = Field(description="Denominator")
    successes: int = Field(default=0, description="Numerator")
    ci_low: float = 0.0
    ci_high: float = 0.0
    bias_corrected: float | None = Field(
        default=None, description="Bias-corrected rate beside raw (R8.7)"
    )
    bias_corrected_suppressed: bool = False
    suppression_reason: str | None = None

    def format(self) -> str:
        """Render as ``value (n=N, 95% CI [lo, hi])``."""
        if self.value is None:
            return f"n/a (n={self.n})"
        return f"{self.value:.3f} (n={self.n}, 95% CI [{self.ci_low:.3f}, {self.ci_high:.3f}])"


def make_rate(successes: int, n: int) -> RateWithCI:
    """Build a :class:`RateWithCI` from binomial counts."""
    lo, hi = wilson_ci(successes, n)
    value = (successes / n) if n > 0 else None
    return RateWithCI(value=value, n=n, successes=successes, ci_low=lo, ci_high=hi)


class FailedCheckRef(BaseModel):
    """One failed check with evidence pointers (R13.4)."""

    check_id: str
    failure_mode_id: str | None = None
    trace_id: str
    span_id: str | None = None
    evidence_text: str = ""


class ScorecardCell(BaseModel):
    """Backend × scenario reliability cell."""

    backend: str
    scenario_id: str
    outcome: Literal["pass", "fail", "indeterminate", "skipped"] = "pass"
    indeterminate_reason: str | None = None
    n: int = 0
    successes: int = 0
    pass_at_k: float = 0.0
    pass_pow_k: float = 0.0
    pass_rate: float = 0.0
    wilson_ci: tuple[float, float] = (0.0, 0.0)
    flaky: bool = False


class FailureModeIncidence(BaseModel):
    """Failure incidence for one FM with raw + bias-corrected rates."""

    failure_mode_id: str
    layer: str
    title: str = ""
    raw: RateWithCI
    fail_count: int = 0


class LayerIncidence(BaseModel):
    """Failure incidence grouped by taxonomy layer (R13.2)."""

    layer: str
    fail_count: int
    n: int
    rate: RateWithCI


class JudgeVerdictRecord(BaseModel):
    """One cached/live judge verdict included in the suite."""

    judge_id: str
    trace_id: str
    verdict: Literal["pass", "fail", "error"]
    single_vendor: bool = False
    vendor: str | None = None
    eligible_to_gate: bool = False
    cached: bool = True


class JudgeAlignmentSummary(BaseModel):
    """Alignment stats for one judge (may be advisory)."""

    judge_id: str
    eligible_to_gate: bool = False
    tpr: float | None = None
    tnr: float | None = None
    kappa: float | None = None
    failure_rate: RateWithCI | None = None
    suppressed: bool = False
    suppression_reason: str | None = None


class GuardrailMetricRow(BaseModel):
    """Per-guardrail confusion metrics for the report."""

    name: str
    n: int = 0
    precision: float | None = None
    recall: float | None = None
    fpr: float | None = None
    f1: float | None = None
    provisional: bool = True
    # Precision-recall curve points: list of {threshold, precision, recall}
    pr_curve: list[dict[str, float]] = Field(default_factory=list)


class CrossBackendComparison(BaseModel):
    """Cross-backend comparison that may be indeterminate under R7.6."""

    scenario_id: str
    backends: list[str]
    status: Literal["settled", "indeterminate"]
    reason: str | None = None


class SuiteCost(BaseModel):
    """Suite-level spend summary."""

    total_usd: float = 0.0
    ceiling_usd: float | None = None
    by_backend: dict[str, float] = Field(default_factory=dict)
    source_breakdown: dict[str, int] = Field(default_factory=dict)


class SuiteLatency(BaseModel):
    """Suite-level latency summary."""

    p50_s: float | None = None
    p95_s: float | None = None
    max_s: float | None = None
    n: int = 0


class SuiteReport(BaseModel):
    """Full machine-readable suite report (R13.1)."""

    schema_version: int = 1
    run_id: str
    tier: str
    generated_at: datetime
    verdict: Literal["pass", "fail", "warn", "error", "indeterminate"] = "pass"
    headline: str = ""
    check_results: list[CheckResult] = Field(default_factory=list)
    failed_checks: list[FailedCheckRef] = Field(default_factory=list)
    scorecard: list[ScorecardCell] = Field(default_factory=list)
    failure_mode_incidence: list[FailureModeIncidence] = Field(default_factory=list)
    layer_incidence: list[LayerIncidence] = Field(default_factory=list)
    judges: list[JudgeAlignmentSummary] = Field(default_factory=list)
    judge_verdicts: list[JudgeVerdictRecord] = Field(default_factory=list)
    suppressed: list[str] = Field(
        default_factory=list,
        description="Non-eligible judges / provisional guardrails (R12.3)",
    )
    guardrails: list[GuardrailMetricRow] = Field(default_factory=list)
    comparisons: list[CrossBackendComparison] = Field(default_factory=list)
    flaky_cells: list[str] = Field(default_factory=list)
    cost: SuiteCost = Field(default_factory=SuiteCost)
    latency: SuiteLatency = Field(default_factory=SuiteLatency)
    reliability: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance
    notes: list[str] = Field(default_factory=list)

    def model_dump_deterministic(self) -> dict[str, Any]:
        """Dump with sorted keys for stable JSON serialization."""
        return self.model_dump(mode="json")


def _attach_bias_correction(
    rate: RateWithCI,
    *,
    tpr: float | None,
    tnr: float | None,
) -> RateWithCI:
    """Copy *rate* with bias-corrected value when TPR/TNR available."""
    if rate.value is None or tpr is None or tnr is None:
        return rate
    corrected = bias_corrected_rate(rate.value, tpr, tnr)
    if corrected is None:
        denom = tpr + tnr - 1.0
        return rate.model_copy(
            update={
                "bias_corrected_suppressed": True,
                "suppression_reason": (
                    f"judge too weak to correct (TPR+TNR−1 = {denom:.2f}); "
                    "reporting raw rate only"
                ),
            }
        )
    return rate.model_copy(update={"bias_corrected": corrected})


def _failed_refs(results: list[CheckResult]) -> list[FailedCheckRef]:
    refs: list[FailedCheckRef] = []
    for r in results:
        if r.outcome != "fail":
            continue
        span_id = r.evidence_span_ids[0] if r.evidence_span_ids else None
        refs.append(
            FailedCheckRef(
                check_id=r.check_id,
                failure_mode_id=r.failure_mode_id,
                trace_id=r.trace_id,
                span_id=span_id,
                evidence_text=r.evidence_text[:500],
            )
        )
    return refs


def _scorecard_from_outcomes(
    outcomes_by_cell: dict[tuple[str, str], list[bool]],
) -> list[ScorecardCell]:
    cells: list[ScorecardCell] = []
    for (backend, scenario_id), outcomes in sorted(outcomes_by_cell.items()):
        summary = cell_summary(outcomes)
        wilson_raw = summary["wilson_ci"]
        assert isinstance(wilson_raw, tuple)
        wilson = (float(wilson_raw[0]), float(wilson_raw[1]))
        outcome: Literal["pass", "fail", "indeterminate", "skipped"] = (
            "pass" if cast(float, summary["pass_pow_k"]) == 1.0 else "fail"
        )
        cells.append(
            ScorecardCell(
                backend=backend,
                scenario_id=scenario_id,
                outcome=outcome,
                n=cast(int, summary["n"]),
                successes=cast(int, summary["successes"]),
                pass_at_k=cast(float, summary["pass_at_k"]),
                pass_pow_k=cast(float, summary["pass_pow_k"]),
                pass_rate=cast(float, summary["pass_rate"]),
                wilson_ci=wilson,
                flaky=cast(bool, summary["flaky"]),
            )
        )
    return cells


def _apply_r76_indeterminate(
    cells: list[ScorecardCell],
    verdicts: list[JudgeVerdictRecord],
) -> list[CrossBackendComparison]:
    """Mark cross-backend comparisons indeterminate under single-vendor R7.6."""
    comparisons: list[CrossBackendComparison] = []
    by_scenario: dict[str, list[ScorecardCell]] = defaultdict(list)
    for c in cells:
        by_scenario[c.scenario_id].append(c)

    for scenario_id, group in sorted(by_scenario.items()):
        backends = sorted({c.backend for c in group})
        if len(backends) < 2:
            continue
        single_vendor_hits = [
            v for v in verdicts if v.single_vendor and v.verdict in {"pass", "fail"}
        ]
        conflict = False
        reason: str | None = None
        for v in single_vendor_hits:
            for backend in backends:
                backend_vendor = VENDOR_BY_BACKEND.get(backend)
                if backend_vendor and v.vendor and backend_vendor == v.vendor:
                    conflict = True
                    reason = (
                        f"single-vendor judge ({v.judge_id}, vendor={v.vendor}) "
                        f"cannot settle comparison involving backend={backend}"
                    )
                    break
            if conflict:
                break
        if conflict:
            for c in group:
                c.outcome = "indeterminate"
                c.indeterminate_reason = reason
            comparisons.append(
                CrossBackendComparison(
                    scenario_id=scenario_id,
                    backends=backends,
                    status="indeterminate",
                    reason=reason,
                )
            )
        else:
            comparisons.append(
                CrossBackendComparison(
                    scenario_id=scenario_id,
                    backends=backends,
                    status="settled",
                    reason=None,
                )
            )
    return comparisons


def assemble_suite_report(
    *,
    run_id: str,
    tier: str,
    check_results: list[CheckResult],
    provenance: Provenance,
    taxonomy: Taxonomy | None = None,
    cell_outcomes: dict[tuple[str, str], list[bool]] | None = None,
    judge_verdicts: list[JudgeVerdictRecord] | None = None,
    judge_summaries: list[JudgeAlignmentSummary] | None = None,
    guardrails: list[GuardrailMetricRow] | None = None,
    cost: SuiteCost | None = None,
    latency: SuiteLatency | None = None,
    generated_at: datetime | None = None,
    notes: list[str] | None = None,
) -> SuiteReport:
    """Assemble a :class:`SuiteReport` from suite run artifacts.

    Args:
        run_id: Unique suite-run identifier.
        tier: ``A`` / ``B`` / ``C``.
        check_results: All deterministic check outcomes.
        provenance: Suite-level provenance stamp.
        taxonomy: Failure taxonomy (loaded if omitted).
        cell_outcomes: ``(backend, scenario_id) → [trial success bools]``.
        judge_verdicts: Optional binary judge verdicts.
        judge_summaries: Optional alignment summaries (eligible vs advisory).
        guardrails: Optional guardrail metric rows.
        cost: Suite cost summary.
        latency: Suite latency summary.
        generated_at: Override timestamp (tests / determinism).
        notes: Free-form notes.

    Returns:
        A fully populated :class:`SuiteReport`.
    """
    tax = taxonomy or load_taxonomy()
    fm_by_id = tax.by_id()
    verdicts = list(judge_verdicts or [])
    summaries = list(judge_summaries or [])
    guardrail_rows = list(guardrails or [])
    now = generated_at or datetime.now(UTC)

    failed = _failed_refs(check_results)

    # Failure incidence by FM: among applicable (non-NA) check results for that FM.
    by_fm: dict[str, list[CheckResult]] = defaultdict(list)
    for r in check_results:
        if r.failure_mode_id and r.outcome != "not_applicable":
            by_fm[r.failure_mode_id].append(r)

    fm_incidence: list[FailureModeIncidence] = []
    for fm_id, rows in sorted(by_fm.items()):
        fails = sum(1 for r in rows if r.outcome == "fail")
        n = len(rows)
        rate = make_rate(fails, n)
        # Attach bias correction from matching eligible judge if present.
        matching = next(
            (s for s in summaries if s.judge_id.endswith(fm_id.lower()) or fm_id in s.judge_id),
            None,
        )
        if matching and matching.tpr is not None and matching.tnr is not None:
            rate = _attach_bias_correction(rate, tpr=matching.tpr, tnr=matching.tnr)
        fm = fm_by_id.get(fm_id)
        fm_incidence.append(
            FailureModeIncidence(
                failure_mode_id=fm_id,
                layer=fm.layer if fm else "harness",
                title=fm.title if fm else "",
                raw=rate,
                fail_count=fails,
            )
        )

    # Layer breakdown: sum fails / applicable across FMs in that layer.
    layer_fails: dict[str, int] = defaultdict(int)
    layer_n: dict[str, int] = defaultdict(int)
    for item in fm_incidence:
        layer_fails[item.layer] += item.fail_count
        layer_n[item.layer] += item.raw.n
    for layer in ("model", "framework", "harness", "provider"):
        layer_n.setdefault(layer, 0)
        layer_fails.setdefault(layer, 0)
    layer_incidence = [
        LayerIncidence(
            layer=layer,
            fail_count=layer_fails[layer],
            n=layer_n[layer],
            rate=make_rate(layer_fails[layer], layer_n[layer]),
        )
        for layer in ("model", "framework", "harness", "provider")
    ]

    # Scorecard
    if cell_outcomes is None:
        # Derive one outcome per (backend, scenario) from check fails on that trace.
        # Without trace metadata we synthesize from check_results' detail if present.
        cell_outcomes = {}
    scorecard = _scorecard_from_outcomes(cell_outcomes)
    comparisons = _apply_r76_indeterminate(scorecard, verdicts)

    # Suppressed section for non-eligible judges + provisional guardrails.
    suppressed: list[str] = []
    for s in summaries:
        if not s.eligible_to_gate:
            s.suppressed = True
            reason = s.suppression_reason or "judge not gating-eligible (R8.6)"
            s.suppression_reason = reason
            suppressed.append(f"judge:{s.judge_id}: {reason}")
    for g in guardrail_rows:
        if g.provisional:
            suppressed.append(f"guardrail:{g.name}: provisional (n={g.n} below min_cases)")

    flaky = [f"{c.backend}/{c.scenario_id}" for c in scorecard if c.flaky]

    # Headline verdict
    has_fail = bool(failed) or any(c.outcome == "fail" for c in scorecard)
    has_indet = any(c.outcome == "indeterminate" for c in scorecard) or any(
        c.status == "indeterminate" for c in comparisons
    )
    if has_fail:
        verdict: Literal["pass", "fail", "warn", "error", "indeterminate"] = "fail"
        headline = f"FAIL — {len(failed)} failed check(s) across suite"
    elif has_indet:
        verdict = "indeterminate"
        headline = "INDETERMINATE — single-vendor judge blocked cross-backend comparison (R7.6)"
    else:
        verdict = "pass"
        headline = "PASS — no failed deterministic checks"

    # Reliability: mark indistinguishable cells (R9.5)
    reliability: dict[str, Any] = {"indistinguishable_pairs": []}
    for i, a in enumerate(scorecard):
        for b in scorecard[i + 1 :]:
            if a.scenario_id != b.scenario_id:
                continue
            from evals.reliability import CellResult

            ca = CellResult(successes=a.successes, n=a.n)
            cb = CellResult(successes=b.successes, n=b.n)
            if indistinguishable(ca, cb):
                reliability["indistinguishable_pairs"].append(
                    {
                        "scenario_id": a.scenario_id,
                        "a": a.backend,
                        "b": b.backend,
                        "reason": "Wilson CIs overlap (R9.5)",
                    }
                )

    return SuiteReport(
        run_id=run_id,
        tier=tier,
        generated_at=now,
        verdict=verdict,
        headline=headline,
        check_results=sorted(check_results, key=lambda r: (r.check_id, r.trace_id, r.outcome)),
        failed_checks=failed,
        scorecard=scorecard,
        failure_mode_incidence=fm_incidence,
        layer_incidence=layer_incidence,
        judges=summaries,
        judge_verdicts=verdicts,
        suppressed=suppressed,
        guardrails=guardrail_rows,
        comparisons=comparisons,
        flaky_cells=flaky,
        cost=cost or SuiteCost(total_usd=0.0),
        latency=latency or SuiteLatency(),
        reliability=reliability,
        provenance=provenance,
        notes=list(notes or []),
    )
