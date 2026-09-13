"""Regression gate: compare SuiteReport to baseline (R12)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from evals.aggregate import SuiteReport
from evals.provenance import Provenance, collect

_BASELINES_DIR = Path(__file__).resolve().parent / "baselines"

ExitCode = Literal[0, 1, 2]  # pass / regression / harness error


class BaselineMetric(BaseModel):
    """One metric snapshot in a baseline file."""

    value: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Baseline(BaseModel):
    """Accepted baseline for a tier (R12.1)."""

    tier: str
    accepted_at: datetime
    git_sha: str
    reason: str
    # check_id → outcome that was accepted (typically "pass")
    check_outcomes: dict[str, str] = Field(default_factory=dict)
    # guardrail name → {recall, fpr, floors...}
    guardrails: dict[str, dict[str, float]] = Field(default_factory=dict)
    # judge_id → bias-corrected failure rate
    judge_failure_rates: dict[str, float] = Field(default_factory=dict)
    suite_pass_pow_k: float = 1.0
    suite_cost_usd: float = 0.0
    cost_ceiling_usd: float = 5.0
    p95_latency_s: float | None = None
    # Optional floors from thresholds.yaml (embedded for offline gate)
    guardrail_recall_floor: float = 0.90
    guardrail_fpr_ceiling: float = 0.10


class Regression(BaseModel):
    """One gate finding."""

    metric: str
    severity: Literal["fail", "warn"]
    message: str
    baseline_value: float | str | None = None
    current_value: float | str | None = None


class GateDecision(BaseModel):
    """Result of evaluate_gate (design §4.11)."""

    passed: bool
    exit_code: ExitCode = 0
    regressions: list[Regression] = Field(default_factory=list)
    warnings: list[Regression] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    suppressed: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)

    def summary_markdown(self) -> str:
        """Scorecard diff for GITHUB_STEP_SUMMARY (R12.8)."""
        lines = [
            "## Eval gate",
            "",
            f"**Result:** {'PASS' if self.passed else 'FAIL'} (exit {self.exit_code})",
            "",
        ]
        if self.regressions:
            lines.append("### Regressions")
            for r in self.regressions:
                lines.append(f"- **{r.metric}**: {r.message}")
            lines.append("")
        if self.warnings:
            lines.append("### Warnings")
            for w in self.warnings:
                lines.append(f"- **{w.metric}**: {w.message}")
            lines.append("")
        if self.improvements:
            lines.append("### Improvements")
            for i in self.improvements:
                lines.append(f"- {i}")
            lines.append("")
        if self.unchanged:
            lines.append("### Unchanged")
            for u in self.unchanged[:20]:
                lines.append(f"- {u}")
            if len(self.unchanged) > 20:
                lines.append(f"- … +{len(self.unchanged) - 20} more")
            lines.append("")
        if self.suppressed:
            lines.append("### Suppressed (non-gating)")
            for s in self.suppressed:
                lines.append(f"- {s}")
            lines.append("")
        return "\n".join(lines)


def load_baseline(tier: str, *, baselines_dir: Path | None = None) -> Baseline | None:
    """Load ``evals/baselines/<tier>.json`` or return None if absent."""
    root = baselines_dir or _BASELINES_DIR
    path = root / f"tier_{tier.lower()}.json"
    if not path.exists():
        # also try bare tier name
        path = root / f"{tier.lower()}.json"
    if not path.exists():
        return None
    return Baseline.model_validate_json(path.read_text(encoding="utf-8"))


def save_baseline(baseline: Baseline, *, baselines_dir: Path | None = None) -> Path:
    """Write baseline to ``evals/baselines/tier_<t>.json``."""
    root = baselines_dir or _BASELINES_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"tier_{baseline.tier.lower()}.json"
    path.write_text(
        baseline.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def baseline_from_report(
    report: SuiteReport,
    *,
    reason: str,
    provenance: Provenance | None = None,
) -> Baseline:
    """Construct a Baseline snapshot from a SuiteReport."""
    prov = provenance or report.provenance
    check_outcomes: dict[str, str] = {}
    for r in report.check_results:
        if r.outcome == "not_applicable":
            continue
        # Keep the worst outcome seen for each check_id across traces.
        prev = check_outcomes.get(r.check_id)
        if prev == "fail":
            continue
        check_outcomes[r.check_id] = r.outcome

    guardrails: dict[str, dict[str, float]] = {}
    for g in report.guardrails:
        if g.provisional:
            continue
        row: dict[str, float] = {}
        if g.recall is not None:
            row["recall"] = g.recall
        if g.fpr is not None:
            row["fpr"] = g.fpr
        if g.precision is not None:
            row["precision"] = g.precision
        guardrails[g.name] = row

    judge_rates: dict[str, float] = {}
    for j in report.judges:
        if not j.eligible_to_gate:
            continue
        if j.failure_rate and j.failure_rate.bias_corrected is not None:
            judge_rates[j.judge_id] = j.failure_rate.bias_corrected
        elif j.failure_rate and j.failure_rate.value is not None:
            judge_rates[j.judge_id] = j.failure_rate.value

    pass_pow = 1.0
    if report.scorecard:
        pass_pow = min(c.pass_pow_k for c in report.scorecard)

    return Baseline(
        tier=report.tier,
        accepted_at=datetime.now(UTC),
        git_sha=prov.git_sha,
        reason=reason,
        check_outcomes=check_outcomes,
        guardrails=guardrails,
        judge_failure_rates=judge_rates,
        suite_pass_pow_k=pass_pow,
        suite_cost_usd=report.cost.total_usd,
        cost_ceiling_usd=report.cost.ceiling_usd or 5.0,
        p95_latency_s=report.latency.p95_s,
    )


class _GateAccum:
    """Mutable buckets filled by per-criterion evaluators."""

    def __init__(self, suppressed: list[str]) -> None:
        self.regressions: list[Regression] = []
        self.warnings: list[Regression] = []
        self.improvements: list[str] = []
        self.unchanged: list[str] = []
        self.suppressed = suppressed


def _eval_deterministic_checks(report: SuiteReport, baseline: Baseline, acc: _GateAccum) -> None:
    """Baseline pass → current fail is a regression."""
    current_by_check: dict[str, set[str]] = {}
    for r in report.check_results:
        if r.outcome == "not_applicable":
            continue
        current_by_check.setdefault(r.check_id, set()).add(r.outcome)

    for check_id, base_outcome in sorted(baseline.check_outcomes.items()):
        cur = current_by_check.get(check_id)
        if cur is None:
            acc.unchanged.append(f"check:{check_id} (not run)")
            continue
        if base_outcome == "pass" and "fail" in cur:
            fail_row = next(
                (r for r in report.check_results if r.check_id == check_id and r.outcome == "fail"),
                None,
            )
            detail = ""
            if fail_row:
                span = fail_row.evidence_span_ids[0] if fail_row.evidence_span_ids else "n/a"
                detail = f" (FM={fail_row.failure_mode_id}, trace={fail_row.trace_id}, span={span})"
            acc.regressions.append(
                Regression(
                    metric=f"check:{check_id}",
                    severity="fail",
                    message=f"passed in baseline, now fails{detail}",
                    baseline_value="pass",
                    current_value="fail",
                )
            )
        elif base_outcome == "fail" and cur == {"pass"}:
            acc.improvements.append(f"check:{check_id} fail→pass")
        else:
            acc.unchanged.append(f"check:{check_id}={','.join(sorted(cur))}")


def _eval_guardrails(report: SuiteReport, baseline: Baseline, acc: _GateAccum) -> None:
    """Non-provisional guardrails vs recall floor / FPR ceiling."""
    for g in report.guardrails:
        if g.provisional:
            acc.suppressed.append(f"guardrail:{g.name}: provisional — excluded from gate")
            continue
        base = baseline.guardrails.get(g.name, {})
        floor = baseline.guardrail_recall_floor
        ceil = baseline.guardrail_fpr_ceiling
        if g.recall is not None:
            if g.recall < floor:
                acc.regressions.append(
                    Regression(
                        metric=f"guardrail:{g.name}:recall",
                        severity="fail",
                        message=f"recall {g.recall:.3f} below floor {floor:.3f}",
                        baseline_value=base.get("recall"),
                        current_value=g.recall,
                    )
                )
            elif base.get("recall") is not None and g.recall > base["recall"] + 1e-9:
                acc.improvements.append(f"guardrail:{g.name} recall ↑")
            else:
                acc.unchanged.append(f"guardrail:{g.name}:recall")
        if g.fpr is not None:
            if g.fpr > ceil:
                acc.regressions.append(
                    Regression(
                        metric=f"guardrail:{g.name}:fpr",
                        severity="fail",
                        message=f"FPR {g.fpr:.3f} above ceiling {ceil:.3f}",
                        baseline_value=base.get("fpr"),
                        current_value=g.fpr,
                    )
                )
            else:
                acc.unchanged.append(f"guardrail:{g.name}:fpr")


def _eval_judges(report: SuiteReport, baseline: Baseline, acc: _GateAccum) -> None:
    """Gating-eligible judge failure rate: +5pp → fail."""
    for j in report.judges:
        if not j.eligible_to_gate:
            acc.suppressed.append(f"judge:{j.judge_id}: not eligible — excluded from gate")
            continue
        cur_rate: float | None = None
        if j.failure_rate:
            cur_rate = (
                j.failure_rate.bias_corrected
                if j.failure_rate.bias_corrected is not None
                else j.failure_rate.value
            )
        if cur_rate is None:
            continue
        base_rate = baseline.judge_failure_rates.get(j.judge_id)
        if base_rate is None:
            acc.unchanged.append(f"judge:{j.judge_id} (no baseline rate)")
            continue
        if cur_rate > base_rate + 0.05:
            acc.regressions.append(
                Regression(
                    metric=f"judge:{j.judge_id}:failure_rate",
                    severity="fail",
                    message=(
                        f"bias-corrected failure rate rose by >5pp "
                        f"({base_rate:.3f} → {cur_rate:.3f})"
                    ),
                    baseline_value=base_rate,
                    current_value=cur_rate,
                )
            )
        elif cur_rate < base_rate - 1e-9:
            acc.improvements.append(f"judge:{j.judge_id} failure rate ↓")
        else:
            acc.unchanged.append(f"judge:{j.judge_id}:failure_rate")


def _eval_suite_pass_pow(report: SuiteReport, baseline: Baseline, acc: _GateAccum) -> None:
    """Suite pass^k drop → fail."""
    current_pow = 1.0
    if report.scorecard:
        current_pow = min(c.pass_pow_k for c in report.scorecard)
    if current_pow < baseline.suite_pass_pow_k - 1e-12:
        acc.regressions.append(
            Regression(
                metric="suite:pass_pow_k",
                severity="fail",
                message=f"pass^k dropped ({baseline.suite_pass_pow_k:.3f} → {current_pow:.3f})",
                baseline_value=baseline.suite_pass_pow_k,
                current_value=current_pow,
            )
        )
    elif current_pow > baseline.suite_pass_pow_k + 1e-12:
        acc.improvements.append("suite pass^k ↑")
    else:
        acc.unchanged.append("suite:pass_pow_k")


def _eval_cost(report: SuiteReport, baseline: Baseline, acc: _GateAccum) -> None:
    """Cost: >25% → warn; exceeds ceiling → fail."""
    cost = report.cost.total_usd
    if cost > baseline.cost_ceiling_usd:
        acc.regressions.append(
            Regression(
                metric="suite:cost",
                severity="fail",
                message=f"cost ${cost:.4f} exceeds ceiling ${baseline.cost_ceiling_usd:.2f}",
                baseline_value=baseline.suite_cost_usd,
                current_value=cost,
            )
        )
    elif baseline.suite_cost_usd > 0 and cost > baseline.suite_cost_usd * 1.25:
        acc.warnings.append(
            Regression(
                metric="suite:cost",
                severity="warn",
                message=(f"cost rose by >25% " f"(${baseline.suite_cost_usd:.4f} → ${cost:.4f})"),
                baseline_value=baseline.suite_cost_usd,
                current_value=cost,
            )
        )
    else:
        acc.unchanged.append("suite:cost")


def _eval_p95_latency(report: SuiteReport, baseline: Baseline, acc: _GateAccum) -> None:
    """p95 latency >50% → warn."""
    if (
        report.latency.p95_s is not None
        and baseline.p95_latency_s is not None
        and baseline.p95_latency_s > 0
        and report.latency.p95_s > baseline.p95_latency_s * 1.50
    ):
        acc.warnings.append(
            Regression(
                metric="suite:p95_latency",
                severity="warn",
                message=(
                    f"p95 latency rose by >50% "
                    f"({baseline.p95_latency_s:.2f}s → {report.latency.p95_s:.2f}s)"
                ),
                baseline_value=baseline.p95_latency_s,
                current_value=report.latency.p95_s,
            )
        )
    else:
        acc.unchanged.append("suite:p95_latency")


def evaluate_gate(
    report: SuiteReport,
    baseline: Baseline | None,
    *,
    harness_error: str | None = None,
) -> GateDecision:
    """Compare *report* to *baseline* per the R12.2 table.

    Decision table (in order): harness error → no baseline → deterministic
    checks → guardrails → judges → pass^k → cost → p95 latency.

    Exit codes: 0 pass, 1 regression, 2 harness error.
    Non-eligible judges and provisional guardrails go to ``suppressed`` only (R12.3).
    """
    if harness_error:
        return GateDecision(
            passed=False,
            exit_code=2,
            regressions=[
                Regression(
                    metric="harness",
                    severity="fail",
                    message=harness_error,
                )
            ],
            suppressed=list(report.suppressed),
        )

    if baseline is None:
        return GateDecision(
            passed=True,
            exit_code=0,
            warnings=[
                Regression(
                    metric="baseline",
                    severity="warn",
                    message="no baseline on disk; gate is advisory only",
                )
            ],
            suppressed=list(report.suppressed),
        )

    acc = _GateAccum(list(report.suppressed))
    _eval_deterministic_checks(report, baseline, acc)
    _eval_guardrails(report, baseline, acc)
    _eval_judges(report, baseline, acc)
    _eval_suite_pass_pow(report, baseline, acc)
    _eval_cost(report, baseline, acc)
    _eval_p95_latency(report, baseline, acc)

    passed = len(acc.regressions) == 0
    return GateDecision(
        passed=passed,
        exit_code=0 if passed else 1,
        regressions=acc.regressions,
        warnings=acc.warnings,
        improvements=acc.improvements,
        suppressed=acc.suppressed,
        unchanged=acc.unchanged,
    )


def accept_baseline(
    report: SuiteReport,
    *,
    reason: str,
    baselines_dir: Path | None = None,
    provenance: Provenance | None = None,
) -> Path:
    """Write a new baseline from *report*, refusing when git is dirty (R14.2)."""
    prov = provenance or collect(tier=report.tier)
    if prov.git_dirty:
        raise RuntimeError(
            "baseline accept refused: working tree is dirty (R14.2). "
            "Commit or stash changes first."
        )
    if not reason.strip():
        raise ValueError("baseline accept requires a non-empty --reason")
    baseline = baseline_from_report(report, reason=reason.strip(), provenance=prov)
    return save_baseline(baseline, baselines_dir=baselines_dir)
