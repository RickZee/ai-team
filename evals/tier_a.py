"""Tier A offline replay runner (R11): checks + optional guardrails/judges + report."""

from __future__ import annotations

import hashlib
import json
import socket
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.aggregate import (
    GuardrailMetricRow,
    JudgeAlignmentSummary,
    JudgeVerdictRecord,
    SuiteCost,
    SuiteLatency,
    SuiteReport,
    assemble_suite_report,
)
from evals.checks import all_checks, ensure_checks_loaded
from evals.checks.base import CheckResult
from evals.gate import evaluate_gate, load_baseline
from evals.judges.exceptions import TierAMissingVerdict
from evals.provenance import collect
from evals.report import write_report
from evals.taxonomy.loader import load_taxonomy
from evals.trace.models import Trace

_EVALS_ROOT = Path(__file__).resolve().parent
_DEFAULT_FIXTURES = _EVALS_ROOT / "fixtures" / "traces"
_DEFAULT_RESULTS = _EVALS_ROOT / "results"


class _NetworkBlocker:
    """Context manager that blocks outbound TCP connects (model API egress)."""

    def __init__(self) -> None:
        self._orig = socket.socket.connect

    def __enter__(self) -> None:
        def _blocked(sock: socket.socket, address: Any) -> None:  # noqa: ANN401
            raise OSError(f"Tier A network blocked (attempted connect to {address!r})")

        socket.socket.connect = _blocked  # type: ignore[method-assign, assignment]

    def __exit__(self, *args: object) -> None:
        socket.socket.connect = self._orig  # type: ignore[method-assign]


def load_fixture_traces(traces_dir: Path) -> list[Trace]:
    """Load all ``*.json`` traces from *traces_dir* (sorted by filename)."""
    traces: list[Trace] = []
    if not traces_dir.is_dir():
        return traces
    for path in sorted(traces_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        traces.append(Trace.model_validate(data))
    return traces


def _run_checks(traces: list[Trace]) -> list[CheckResult]:
    ensure_checks_loaded()
    results: list[CheckResult] = []
    for trace in traces:
        for chk in all_checks(tier="A"):
            results.append(chk.run(trace))
    # Also run checks without tier filter that are registered as A/B/C — all_checks(tier=A)
    # already filters. Include any check whose tier is A or that has no stricter requirement.
    return results


def _cell_outcomes_from_checks(
    traces: list[Trace],
    results: list[CheckResult],
) -> dict[tuple[str, str], list[bool]]:
    """One trial per trace: success iff no applicable check failed on that trace."""
    fails: dict[str, bool] = defaultdict(bool)
    for r in results:
        if r.outcome == "fail":
            fails[r.trace_id] = True
    cells: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for t in traces:
        ok = not fails[t.trace_id]
        cells[(t.backend, t.scenario_id)].append(ok)
    return dict(cells)


def _load_guardrail_metrics() -> list[GuardrailMetricRow]:
    """Best-effort guardrail eval; empty when Phase 6 corpus is absent."""
    try:
        from evals.guardrail_eval import GuardrailEvaluator
    except ImportError:
        return []
    try:
        rows = GuardrailEvaluator().evaluate_for_report()
        return list(rows)
    except Exception:  # noqa: BLE001 — Tier A must not fail closed on missing corpus
        return []


def _load_cached_judges(
    traces: list[Trace],
    *,
    allow_network: bool = False,
) -> tuple[list[JudgeVerdictRecord], list[JudgeAlignmentSummary]]:
    """Serve judge verdicts from cache only in Tier A.

    When the judge cache is empty (not yet warmed), judges are skipped so Tier A
    stays green before Phase 7 cache warm. Once any cache entry exists, every
    configured prompt is required to hit cache — a miss raises
    :class:`TierAMissingVerdict` (R11.4).
    """
    try:
        from evals.golden import LabelingUnit, make_labeling_unit_id
        from evals.judges.base import BinaryJudge, VerdictCache, load_judge_spec
    except ImportError:
        return [], []

    prompts_dir = Path(__file__).resolve().parent / "judges" / "prompts"
    cache_dir = Path(__file__).resolve().parent / "judges" / "cache"
    prompt_files = sorted(prompts_dir.glob("*.md")) if prompts_dir.is_dir() else []
    if not prompt_files:
        return [], []

    cache_files = list(cache_dir.rglob("*.json")) if cache_dir.is_dir() else []
    if not cache_files and not allow_network:
        # Cache not warmed yet — skip judges rather than fail every PR.
        return [], []

    verdicts: list[JudgeVerdictRecord] = []
    cache = VerdictCache(root=cache_dir)
    for prompt_path in prompt_files:
        try:
            spec = load_judge_spec(prompt_path)
        except Exception:  # noqa: BLE001 — skip malformed prompts in Tier A
            continue
        judge = BinaryJudge(spec, cache=cache, allow_network=allow_network)
        fm = spec.failure_mode_id or "FM-000"
        for trace in traces:
            unit = LabelingUnit(
                labeling_unit_id=make_labeling_unit_id(trace.trace_id, "run", fm),
                trace_id=trace.trace_id,
                span_id="run",
                failure_mode_id=fm,
            )
            v = judge.judge(unit, trace)
            label: str = v.verdict
            if label not in {"pass", "fail", "error"}:
                label = "error"
            verdicts.append(
                JudgeVerdictRecord(
                    judge_id=v.judge_id,
                    trace_id=v.trace_id,
                    verdict=label,  # type: ignore[arg-type]
                    single_vendor=v.single_vendor,
                    vendor=v.provider,
                    eligible_to_gate=False,
                    cached=v.cached,
                )
            )
    return verdicts, []


def _deterministic_run_id(traces_dir: Path, git_sha: str) -> str:
    """Stable run id from corpus contents + commit (R11.5)."""
    h = hashlib.sha256()
    if traces_dir.is_dir():
        for path in sorted(traces_dir.glob("*.json")):
            h.update(path.name.encode())
            h.update(path.read_bytes())
    return f"tierA_{git_sha[:12]}_{h.hexdigest()[:10]}"


def run_tier_a(
    *,
    traces_dir: Path | None = None,
    out_dir: Path | None = None,
    run_id: str | None = None,
    block_network: bool = True,
    warn_only: bool = False,
    generated_at: datetime | None = None,
) -> tuple[SuiteReport, int, dict[str, Path]]:
    """Execute Tier A: fixture checks → aggregate → report → gate.

    Returns:
        ``(report, exit_code, artifact_paths)``. Exit 2 on harness errors
        (including :class:`TierAMissingVerdict`). With *warn_only*, gate
        regressions still exit 0.
    """
    fixtures = traces_dir or _DEFAULT_FIXTURES
    provenance = collect(tier="A")
    rid = run_id or _deterministic_run_id(fixtures, provenance.git_sha)
    results_dir = out_dir or (_DEFAULT_RESULTS / rid)

    def _body() -> tuple[SuiteReport, int, dict[str, Path]]:
        traces = load_fixture_traces(fixtures)
        if not traces:
            report = assemble_suite_report(
                run_id=rid,
                tier="A",
                check_results=[],
                provenance=provenance,
                notes=["no fixture traces found"],
                generated_at=generated_at,
                cost=SuiteCost(total_usd=0.0),
            )
            paths = write_report(report, out_dir=results_dir)
            return report, 2, paths

        check_results = _run_checks(traces)
        try:
            guardrails = _load_guardrail_metrics()
            judge_verdicts, judge_summaries = _load_cached_judges(traces, allow_network=False)
        except TierAMissingVerdict as exc:
            report = assemble_suite_report(
                run_id=rid,
                tier="A",
                check_results=check_results,
                provenance=provenance,
                notes=[str(exc)],
                generated_at=generated_at,
                cost=SuiteCost(total_usd=0.0),
            )
            paths = write_report(report, out_dir=results_dir)
            decision = evaluate_gate(report, None, harness_error=str(exc))
            return report, decision.exit_code, paths

        tax = load_taxonomy()
        cells = _cell_outcomes_from_checks(traces, check_results)
        # Durations for latency (optional)
        durations = [
            (t.ended_at - t.started_at).total_seconds() for t in traces if t.ended_at is not None
        ]
        durations.sort()
        p95 = durations[int(0.95 * (len(durations) - 1))] if durations else None
        p50 = durations[len(durations) // 2] if durations else None

        report = assemble_suite_report(
            run_id=rid,
            tier="A",
            check_results=check_results,
            provenance=provenance,
            taxonomy=tax,
            cell_outcomes=cells,
            judge_verdicts=judge_verdicts,
            judge_summaries=judge_summaries,
            guardrails=guardrails,
            cost=SuiteCost(total_usd=0.0, ceiling_usd=0.0),
            latency=SuiteLatency(
                p50_s=p50,
                p95_s=p95,
                max_s=durations[-1] if durations else None,
                n=len(durations),
            ),
            generated_at=generated_at,
            notes=["tier A offline replay; $0.00 model spend"],
        )
        paths = write_report(report, out_dir=results_dir)
        baseline = load_baseline("A")
        decision = evaluate_gate(report, baseline)
        (results_dir / "gate.md").write_text(decision.summary_markdown(), encoding="utf-8")
        exit_code = 0 if warn_only else int(decision.exit_code)
        return report, exit_code, paths

    if block_network:
        with _NetworkBlocker():
            return _body()
    return _body()
