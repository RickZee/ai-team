"""Guardrail classifier evaluation against labeled corpora (R6).

Reuses ``ConfusionCounts``, ``score``, and ``format_report`` from
``ai_team.guardrails.corpus_metrics`` — do not reimplement confusion accounting.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from ai_team.guardrails.behavioral import (
    role_adherence_guardrail,
    scope_control_guardrail,
)
from ai_team.guardrails.corpus_metrics import ConfusionCounts, format_report, score
from ai_team.guardrails.security import code_safety_guardrail

from evals.corpora.format import GuardrailCase, load_corpus
from evals.store import TraceStore
from evals.trace.models import Trace

CORPORA_DIR = Path(__file__).resolve().parent / "corpora" / "guardrails"
THRESHOLDS_PATH = CORPORA_DIR / "thresholds.yaml"

InvokeFn = Callable[[dict[str, Any]], str]


def _acceptance_met(trace: Trace) -> bool:
    """Heuristic: complete status and at least one source/test artifact."""
    if trace.status != "complete":
        return False
    produced = [a for a in trace.files() if a.kind in {"source", "test"}]
    return bool(produced) or bool(trace.raw_result.get("acceptance_met"))


def _status_to_outcome(status: str) -> str:
    """Normalize a GuardrailResult.status to ``fail`` or ``pass`` for scoring."""
    return "fail" if status == "fail" else "pass"


def invoke_scope_relevance(payload: dict[str, Any]) -> str:
    """Invoke ``scope_control_guardrail`` with corpus case input."""
    result = scope_control_guardrail(
        str(payload.get("task_output", "")),
        str(payload.get("original_requirements", "")),
        max_expansion=float(payload.get("max_expansion", 0.25)),
        min_relevance=float(payload.get("min_relevance", 0.15)),
    )
    return _status_to_outcome(result.status)


def invoke_role_boundary(payload: dict[str, Any]) -> str:
    """Invoke ``role_adherence_guardrail`` with corpus case input."""
    result = role_adherence_guardrail(
        str(payload.get("task_output", payload.get("output", ""))),
        str(payload.get("role", "qa_engineer")),
        is_supervisor=bool(payload.get("is_supervisor", False)),
    )
    return _status_to_outcome(result.status)


def invoke_security_patterns(payload: dict[str, Any]) -> str:
    """Invoke ``code_safety_guardrail`` with corpus case input."""
    result = code_safety_guardrail(str(payload.get("code", payload.get("task_output", ""))))
    return _status_to_outcome(result.status)


DEFAULT_INVOKERS: dict[str, InvokeFn] = {
    "scope_relevance": invoke_scope_relevance,
    "role_boundary": invoke_role_boundary,
    "security_patterns": invoke_security_patterns,
}


@dataclass(frozen=True)
class GuardrailThresholds:
    """Asymmetric floors from ``thresholds.yaml``."""

    recall_floor: float
    fpr_ceiling: float
    min_cases: int


@dataclass
class GuardrailEvalResult:
    """Scored result for one guardrail corpus."""

    name: str
    counts: ConfusionCounts
    provisional: bool
    thresholds: GuardrailThresholds
    gate_fail: bool
    report_line: str


def load_thresholds(path: Path | None = None) -> dict[str, GuardrailThresholds]:
    """Load per-guardrail floors from YAML."""
    raw = yaml.safe_load((path or THRESHOLDS_PATH).read_text(encoding="utf-8")) or {}
    out: dict[str, GuardrailThresholds] = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, Mapping):
            continue
        out[str(name)] = GuardrailThresholds(
            recall_floor=float(cfg["recall_floor"]),
            fpr_ceiling=float(cfg["fpr_ceiling"]),
            min_cases=int(cfg["min_cases"]),
        )
    return out


def is_provisional(corpus: list[GuardrailCase], thresholds: GuardrailThresholds) -> bool:
    """R6.4: below min_cases or <15 of either label → provisional (not gating)."""
    if len(corpus) < thresholds.min_cases:
        return True
    n_violation = sum(1 for c in corpus if c.label == "violation")
    n_benign = sum(1 for c in corpus if c.label == "benign")
    return n_violation < 15 or n_benign < 15


class GuardrailEvaluator:
    """Score one named guardrail against a labeled corpus.

    Also supports a no-arg factory used by Tier A reporting
    (``GuardrailEvaluator().evaluate_for_report()``).
    """

    def __init__(
        self,
        name: str | None = None,
        invoke: InvokeFn | None = None,
    ) -> None:
        self.name = name or ""
        self.invoke = invoke

    def evaluate(self, corpus: list[GuardrailCase]) -> ConfusionCounts:
        """Return confusion counts; firing == invoke returns ``fail``."""
        if self.invoke is None:
            msg = "GuardrailEvaluator.evaluate requires an invoke callable"
            raise RuntimeError(msg)
        outcomes = [(self.invoke(c.input) == "fail", c.label == "violation") for c in corpus]
        return score(outcomes)

    def sweep(
        self,
        corpus: list[GuardrailCase],
        param: str,
        values: list[float],
    ) -> list[tuple[float, ConfusionCounts]]:
        """Evaluate at each parameter value (e.g. ``min_relevance`` floor).

        Each case's ``input`` is copied with ``param`` overridden before invoke.
        """
        if self.invoke is None:
            msg = "GuardrailEvaluator.sweep requires an invoke callable"
            raise RuntimeError(msg)
        curve: list[tuple[float, ConfusionCounts]] = []
        for value in values:
            patched: list[GuardrailCase] = []
            for case in corpus:
                payload = dict(case.input)
                payload[param] = value
                patched.append(case.model_copy(update={"input": payload}))
            curve.append((value, self.evaluate(patched)))
        return curve

    def evaluate_for_report(
        self,
        corpora_dir: Path | None = None,
        *,
        thresholds_path: Path | None = None,
    ) -> list[Any]:
        """Return ``GuardrailMetricRow``-compatible rows for SuiteReport."""
        from evals.aggregate import GuardrailMetricRow

        rows: list[Any] = []
        for result in evaluate_all(corpora_dir, thresholds_path=thresholds_path):
            pr_curve: list[dict[str, float]] = []
            if result.name == "scope_relevance" and result.name in DEFAULT_INVOKERS:
                root = corpora_dir or CORPORA_DIR
                path = root / f"{result.name}.jsonl"
                if path.is_file():
                    corpus = load_corpus(path)
                    ev = GuardrailEvaluator(result.name, DEFAULT_INVOKERS[result.name])
                    for value, counts in ev.sweep(
                        corpus, "min_relevance", scope_relevance_sweep_values()
                    ):
                        pr_curve.append(
                            {
                                "threshold": value,
                                "precision": counts.precision,
                                "recall": counts.recall,
                            }
                        )
            rows.append(
                GuardrailMetricRow(
                    name=result.name,
                    n=result.counts.total,
                    precision=result.counts.precision,
                    recall=result.counts.recall,
                    fpr=result.counts.false_positive_rate,
                    f1=result.counts.f1,
                    provisional=result.provisional,
                    pr_curve=pr_curve,
                )
            )
        return rows


def evaluate_guardrail(
    name: str,
    corpus: list[GuardrailCase],
    *,
    thresholds: GuardrailThresholds,
    invoke: InvokeFn | None = None,
) -> GuardrailEvalResult:
    """Evaluate one guardrail and apply provisional / gate rules."""
    invoker = invoke or DEFAULT_INVOKERS[name]
    evaluator = GuardrailEvaluator(name, invoker)
    counts = evaluator.evaluate(corpus)
    provisional = is_provisional(corpus, thresholds)
    gate_fail = False
    if not provisional:
        gate_fail = (
            counts.recall < thresholds.recall_floor
            or counts.false_positive_rate > thresholds.fpr_ceiling
        )
    line = format_report(name, counts)
    if provisional:
        line = f"{line} [provisional: n<{thresholds.min_cases} or class imbalance]"
    return GuardrailEvalResult(
        name=name,
        counts=counts,
        provisional=provisional,
        thresholds=thresholds,
        gate_fail=gate_fail,
        report_line=line,
    )


def evaluate_all(
    corpora_dir: Path | None = None,
    *,
    thresholds_path: Path | None = None,
) -> list[GuardrailEvalResult]:
    """Score every ``*.jsonl`` corpus that has a matching thresholds entry."""
    root = corpora_dir or CORPORA_DIR
    thresholds = load_thresholds(thresholds_path)
    results: list[GuardrailEvalResult] = []
    for path in sorted(root.glob("*.jsonl")):
        name = path.stem
        if name not in thresholds:
            continue
        if name not in DEFAULT_INVOKERS:
            continue
        corpus = load_corpus(path)
        results.append(evaluate_guardrail(name, corpus, thresholds=thresholds[name]))
    return results


def mine_false_positive_candidates(
    store: TraceStore,
    *,
    out_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Extract FP candidates: guardrail_check fail on otherwise-accepted runs.

    Writes a labeling queue JSONL (unlabeled) when ``out_path`` is set.
    """
    queue: list[dict[str, Any]] = []
    for row in store.query():
        try:
            trace = store.load(row.trace_id)
        except (OSError, ValueError, KeyError) as exc:
            queue.append(
                {
                    "case_id": f"mine-error-{row.trace_id}",
                    "origin_trace_id": row.trace_id,
                    "error": str(exc),
                    "note": "failed to load trace during mine",
                }
            )
            continue
        queue.extend(_candidates_from_trace(trace))

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            for item in queue:
                fh.write(json_dumps(item) + "\n")
    return queue


def _candidates_from_trace(trace: Trace) -> list[dict[str, Any]]:
    if not _acceptance_met(trace):
        return []
    out: list[dict[str, Any]] = []
    for span in trace.spans_of("guardrail_check"):
        outcome = str(span.payload.get("outcome") or span.payload.get("status") or "").lower()
        if outcome not in {"fail", "failed", "violation"}:
            continue
        out.append(
            {
                "case_id": f"mine-{trace.trace_id}-{span.span_id}",
                "origin_trace_id": trace.trace_id,
                "span_id": span.span_id,
                "guardrail": span.payload.get("guardrail") or span.payload.get("name"),
                "input": span.payload.get("input") or span.payload,
                "label": None,
                "source": "observed",
                "note": "candidate false positive — human label required",
            }
        )
    return out


def json_dumps(obj: dict[str, Any]) -> str:
    """Stable JSON for queue lines."""
    import json

    return json.dumps(obj, sort_keys=True, default=str)


def scope_relevance_sweep_values() -> list[float]:
    """Default floor sweep 0.05–0.50 inclusive, step 0.05."""
    return [round(0.05 + 0.05 * i, 2) for i in range(10)]
