"""Check liveness and signal-chain coverage (``eval-coverage`` R2, R4, R11).

An eval suite can be wrong two ways. It can score the wrong thing — that is
``eval-methodology-alignment``, which points the corpus at the tree the harness
actually writes. Or it can score *nothing* and report a verdict anyway.

This module measures the second. It answers one question per check: over this
corpus, did you ever decide anything? A check that returns ``not_applicable`` on
every trace contributes a row to a coverage table and no information, and today
nothing in the repo distinguishes it from a check that works.

Everything here is pure, offline, and $0.00. ``liveness_from_report`` folds a
``SuiteReport`` that is already on disk, so the first liveness table costs
nothing but reading a file.

Verdict ladder (most to least severe):

``unreachable``
    Blind, *and* the mandatory evidence has no producer in the signal chain.
    No corpus could change this — it is a code defect.
``blind``
    Zero ``pass`` and zero ``fail`` over this corpus.
``thin``
    Decided on fewer than ``THIN_DECIDED_FLOOR`` traces, or abstained on more
    than ``THIN_NA_SHARE`` of them.
``live``
    Decided on enough traces to mean something.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from evals.checks import all_checks, ensure_checks_loaded
from evals.checks.base import CheckResult
from evals.provenance import Provenance, collect
from evals.trace.models import Trace

__all__ = [
    "CheckLiveness",
    "CoverageReport",
    "Liveness",
    "SignalFlag",
    "SignalRow",
    "blocking_signals",
    "classify",
    "liveness_from_report",
    "liveness_from_results",
    "liveness_over_corpus",
    "load_traces",
    "render_markdown",
    "render_side_by_side",
    "render_signals_markdown",
    "signal_chain",
    "unreachable_span_types",
]

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

#: Minimum decided traces (pass + fail) before a check counts as ``live``.
#: Deliberately low. This is not a statistical threshold — ``eval-harness`` R6
#: owns ``min_cases`` for anything that gates. It exists so that a check decided
#: by its own two fixtures cannot render as coverage.
THIN_DECIDED_FLOOR = 10

#: Abstention share above which a check is ``thin`` however much it decided.
THIN_NA_SHARE = 0.90

#: ``not_applicable`` share above which a report is stamped EVIDENCE-STARVED (R11.1).
EVIDENCE_STARVED_SHARE = 0.50

Liveness = Literal["live", "thin", "blind", "unreachable"]
SignalFlag = Literal["orphan_signal", "unreachable_signal", "no_producer"]
CorpusKind = Literal["FIXTURE-ONLY", "CORPUS", "LIVE"]

_SEVERITY: dict[str, int] = {"unreachable": 0, "blind": 1, "thin": 2, "live": 3}


# ---------------------------------------------------------------------------
# Signal chain (R4) — static, correct on an empty repo
# ---------------------------------------------------------------------------

#: Span type → (harness writer modules, log files, parser functions).
#:
#: Hand-maintained, and the design document says so (§2.5). The writer column can
#: drift from the code; the parser column cannot, because R4.6 gates on it. A
#: drifting writer column degrades a report, a drifting parser column breaks a
#: check, and only the second is worth a gate.
_PRODUCERS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "phase_start": (
        ("harness/context_pressure.py", "agents/prompts.py (AGENT-WRITTEN — FM-018)"),
        ("logs/phases.jsonl",),
        ("parse_phases_jsonl",),
    ),
    "phase_end": (
        ("harness/context_pressure.py", "agents/prompts.py (AGENT-WRITTEN — FM-018)"),
        ("logs/phases.jsonl",),
        ("parse_phases_jsonl",),
    ),
    "llm_call": (
        ("core/results/writer.py", "claude_agent_sdk_backend/costs.py"),
        ("logs/costs.jsonl",),
        ("parse_costs_jsonl",),
    ),
    "spend_event": (
        ("core/results/writer.py", "claude_agent_sdk_backend/costs.py"),
        ("logs/costs.jsonl",),
        ("parse_costs_jsonl",),
    ),
    "tool_use": (("tools/bus.py",), ("logs/audit.jsonl",), ("parse_audit_jsonl",)),
    "tool_result": (("tools/bus.py",), ("logs/audit.jsonl",), ("parse_audit_jsonl",)),
    "guardrail_check": (
        ("guardrails/* (structlog only — no JSONL writer)",),
        ("logs/audit.jsonl (SDK hook events only)",),
        ("parse_audit_jsonl",),
    ),
    "retry": (
        ("harness/context_pressure.py",),
        ("logs/phases.jsonl",),
        ("parse_phases_jsonl",),
    ),
    # No parser constructs an ``error`` span. ``builder.py`` maps an "error"
    # *status* to ``failed``; that is not a span. Reads of this type are
    # therefore unreachable, exactly like ``human_interrupt``.
    "error": ((), (), ()),
    "human_interrupt": ((), (), ()),
    "smoke_probe": (
        ("tools/smoke_tools.py",),
        ("docs/smoke_report.json", "docs/ui_smoke_results.json"),
        ("parse_smoke_report", "parse_ui_smoke_report"),
    ),
    "subagent_start": (
        ("claude_agent_sdk_backend/orchestrator.py",),
        ("logs/audit.jsonl",),
        ("parse_audit_jsonl",),
    ),
    "subagent_stop": (
        ("claude_agent_sdk_backend/orchestrator.py",),
        ("logs/audit.jsonl",),
        ("parse_audit_jsonl",),
    ),
    "session_start": (
        ("harness/session_loop.py",),
        ("logs/sessions.jsonl",),
        ("parse_sessions_jsonl",),
    ),
    "session_end": (
        ("harness/session_loop.py",),
        ("logs/sessions.jsonl",),
        ("parse_sessions_jsonl",),
    ),
    "regression_check": (
        ("harness/session_loop.py",),
        ("logs/sessions.jsonl",),
        ("parse_sessions_jsonl",),
    ),
    "qa_verdict": (
        ("harness/qa_verdicts.py",),
        ("docs/qa_verdicts.jsonl",),
        ("parse_qa_verdicts_jsonl",),
    ),
}

#: Span types each check reads at all — mandatory or as optional context.
#:
#: A signal read optionally is still read, so this is the table that decides
#: ``orphan_signal``. Seed for R1: once ``@check(requires=...)`` lands (task 2.3)
#: both tables are replaced by the declarations themselves and deleted. Until
#: then they are derived from the check bodies by inspection, and
#: ``test_coverage.py`` asserts they stay in step with the registry.
_CHECK_SPAN_READS: dict[str, tuple[str, ...]] = {
    "CHK-acceptance-monotonic": (),
    "CHK-constraint-survival": ("phase_start",),
    "CHK-draft-commit": ("phase_end", "tool_result", "tool_use"),
    "CHK-evaluator-capitulation": (),
    "CHK-gate-env-fidelity": (),
    "CHK-guardrail-fp-budget": ("guardrail_check",),
    "CHK-hallucination-density": (),
    "CHK-interrupt-latency": ("human_interrupt",),
    "CHK-lesson-effectiveness": (),
    "CHK-listener-self-trigger": (),
    "CHK-metric-source-agreement": (),
    "CHK-phase-repeat-bounded": ("phase_start",),
    "CHK-premature-termination": ("error", "phase_end", "session_end", "spend_event"),
    "CHK-provider-error-rate": ("error", "llm_call", "retry"),
    "CHK-required-artifacts": (),
    "CHK-runtime-smoke-present": ("smoke_probe",),
    "CHK-spend-ceiling": ("spend_event",),
    "CHK-tool-call-emitted": ("phase_end", "tool_use"),
    "CHK-verifier-independence": ("tool_result", "tool_use"),
    "CHK-workspace-isolation": (),
}

#: Span types a check cannot decide without, as ``any_of`` groups.
#:
#: Each inner tuple is satisfied by **one** member being present. A check is
#: ``unreachable`` only when some group is satisfiable by no producible span type
#: — one unreachable member in a group whose other members are producible does
#: not blind the check. ``CHK-provider-error-rate`` is exactly that case: it reads
#: the unreachable ``error`` type, but ``llm_call`` and ``retry`` keep it alive.
_CHECK_SPAN_MANDATORY: dict[str, tuple[tuple[str, ...], ...]] = {
    "CHK-constraint-survival": (("phase_start",),),
    "CHK-draft-commit": (("tool_use", "tool_result"),),
    "CHK-guardrail-fp-budget": (("guardrail_check",),),
    "CHK-interrupt-latency": (("human_interrupt",),),
    "CHK-phase-repeat-bounded": (("phase_start",),),
    "CHK-premature-termination": (("phase_end", "session_end"),),
    "CHK-provider-error-rate": (("error", "llm_call", "retry"),),
    "CHK-runtime-smoke-present": (("smoke_probe",),),
    "CHK-tool-call-emitted": (("tool_use",),),
    "CHK-verifier-independence": (("tool_use", "tool_result"),),
}


class SignalRow(BaseModel):
    """One span type's path from harness writer to check consumer (R4.1)."""

    span_type: str
    harness_writers: tuple[str, ...] = ()
    log_files: tuple[str, ...] = ()
    parsers: tuple[str, ...] = ()
    consumers: tuple[str, ...] = ()
    flags: tuple[SignalFlag, ...] = ()


def signal_chain() -> list[SignalRow]:
    """Build the signal-chain inventory statically (R4.5).

    Takes no corpus and runs no check, so it is correct on a fresh clone with an
    empty trace store.

    Returns:
        One :class:`SignalRow` per known span type, ordered by span type.
    """
    consumers: dict[str, list[str]] = {}
    for check_id, span_types in _CHECK_SPAN_READS.items():
        for span_type in span_types:
            consumers.setdefault(span_type, []).append(check_id)

    rows: list[SignalRow] = []
    for span_type in sorted(set(_PRODUCERS) | set(consumers)):
        writers, log_files, parsers = _PRODUCERS.get(span_type, ((), (), ()))
        used_by = tuple(sorted(consumers.get(span_type, ())))
        flags: list[SignalFlag] = []
        if parsers and not used_by:
            flags.append("orphan_signal")
        if used_by and not parsers:
            flags.append("unreachable_signal")
        if not writers:
            flags.append("no_producer")
        rows.append(
            SignalRow(
                span_type=span_type,
                harness_writers=writers,
                log_files=log_files,
                parsers=parsers,
                consumers=used_by,
                flags=tuple(flags),
            )
        )
    return rows


def unreachable_span_types() -> frozenset[str]:
    """Span types a check reads that no parser produces (R2.2 ``unreachable``)."""
    return frozenset(row.span_type for row in signal_chain() if "unreachable_signal" in row.flags)


def blocking_signals(check_id: str) -> tuple[str, ...]:
    """Mandatory span types that make *check_id* structurally undecidable.

    Returns the members of any ``any_of`` group in which **every** member is
    unproducible. A group with one unreachable member and one producible member
    is not blocking — the check can still decide.

    Args:
        check_id: Registered check id.

    Returns:
        Sorted unreachable span types from fully-blocked groups; empty when the
        check can decide given a corpus.
    """
    dead = unreachable_span_types()
    blocked: set[str] = set()
    for group in _CHECK_SPAN_MANDATORY.get(check_id, ()):
        if group and all(member in dead for member in group):
            blocked.update(group)
    return tuple(sorted(blocked))


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------


class CheckLiveness(BaseModel):
    """Whether one check ever decided anything over one corpus (R2.1)."""

    check_id: str
    failure_mode_id: str | None = None
    tier: str = "A"
    n_pass: int = 0
    n_fail: int = 0
    n_na: int = 0
    n_error: int = 0
    na_reason_text_top: list[tuple[str, int]] = Field(default_factory=list)
    liveness: Liveness = "blind"
    unreachable_signals: tuple[str, ...] = ()

    @property
    def n_decided(self) -> int:
        """Pass + fail. Errors are never decisions (``EVAL_METHODOLOGY.md`` §6)."""
        return self.n_pass + self.n_fail

    @property
    def n_total(self) -> int:
        """Every result recorded for this check, abstentions and errors included."""
        return self.n_pass + self.n_fail + self.n_na + self.n_error

    @property
    def na_share(self) -> float:
        """Abstention share, or 0.0 when the check produced no results."""
        return (self.n_na / self.n_total) if self.n_total else 0.0

    def rate_text(self) -> str:
        """Pass rate, or ``n=<k>`` when the denominator is too small to show (R3.3)."""
        if self.n_decided == 0:
            return "—"
        if self.n_decided < THIN_DECIDED_FLOOR:
            return f"n={self.n_decided}"
        return f"{100 * self.n_pass / self.n_decided:.0f}% (n={self.n_decided})"


class CoverageReport(BaseModel):
    """Liveness over one corpus, with the R11 stamp."""

    corpus_label: str
    corpus_kind: CorpusKind
    n_traces: int = 0
    n_unloadable: int = 0
    checks: list[CheckLiveness] = Field(default_factory=list)
    na_share: float = 0.0
    evidence_starved: bool = False
    top_abstainers: list[tuple[str, int]] = Field(default_factory=list)
    provenance: Provenance | None = None

    def by_liveness(self, verdict: Liveness) -> list[CheckLiveness]:
        """Checks holding *verdict*, in registry order."""
        return [c for c in self.checks if c.liveness == verdict]

    def counts(self) -> dict[str, int]:
        """Verdict → number of checks."""
        tally: Counter[str] = Counter(str(c.liveness) for c in self.checks)
        return {v: tally.get(v, 0) for v in ("live", "thin", "blind", "unreachable")}

    def stamps(self) -> list[str]:
        """Stamps this report has earned, in render order."""
        marks: list[str] = [str(self.corpus_kind)]
        if self.evidence_starved:
            marks.append("EVIDENCE-STARVED")
        return marks

    def headline(self) -> str:
        """One line naming blind and unreachable counts (R2.4)."""
        tally = self.counts()
        parts = [
            f"{len(self.checks)} checks",
            f"{tally['live']} live",
            f"{tally['thin']} thin",
            f"{tally['blind']} blind",
            f"{tally['unreachable']} unreachable",
        ]
        n_err = sum(c.n_error for c in self.checks)
        err = f", {n_err} errored" if n_err else ""
        return (
            f"{', '.join(parts)} over {self.n_traces} traces "
            f"[{' · '.join(self.stamps())}, na {100 * self.na_share:.0f}%{err}]"
        )

    def verdict_suffix(self) -> str:
        """``(instruments incomplete)`` when any check is unreachable (R2.5)."""
        return " (instruments incomplete)" if self.counts()["unreachable"] else ""


def classify(
    *,
    n_pass: int,
    n_fail: int,
    n_na: int,
    n_error: int = 0,
    unreachable: bool = False,
) -> Liveness:
    """Apply the R2.2 verdict rule.

    ``unreachable`` is tested first: a check that is both starved and broken is a
    code defect and should be reported as one.

    Args:
        n_pass: Pass count over the corpus.
        n_fail: Fail count over the corpus.
        n_na: ``not_applicable`` count over the corpus.
        n_error: Error count. Never folded into decisions.
        unreachable: True when mandatory evidence has no producer.

    Returns:
        One of ``unreachable`` / ``blind`` / ``thin`` / ``live``.
    """
    decided = n_pass + n_fail
    if unreachable:
        return "unreachable"
    if decided == 0:
        return "blind"
    total = decided + n_na + n_error
    if decided < THIN_DECIDED_FLOOR:
        return "thin"
    if total and (n_na / total) > THIN_NA_SHARE:
        return "thin"
    return "live"


def _fold(
    rows: Iterable[tuple[str, str | None, str, str]],
    *,
    corpus_label: str,
    corpus_kind: CorpusKind,
    n_traces: int,
    n_unloadable: int = 0,
    provenance: Provenance | None = None,
) -> CoverageReport:
    """Fold ``(check_id, fm_id, outcome, na_text)`` rows into a report."""
    tallies: dict[str, Counter[str]] = {}
    fms: dict[str, str | None] = {}
    na_texts: dict[str, Counter[str]] = {}

    for check_id, fm_id, outcome, na_text in rows:
        tallies.setdefault(check_id, Counter())[outcome] += 1
        fms.setdefault(check_id, fm_id)
        if outcome == "not_applicable" and na_text:
            na_texts.setdefault(check_id, Counter())[na_text.strip()[:80]] += 1

    checks: list[CheckLiveness] = []
    for check_id in sorted(tallies):
        tally = tallies[check_id]
        blind_signals = blocking_signals(check_id)
        n_pass = tally.get("pass", 0)
        n_fail = tally.get("fail", 0)
        n_na = tally.get("not_applicable", 0)
        n_error = tally.get("error", 0)
        checks.append(
            CheckLiveness(
                check_id=check_id,
                failure_mode_id=fms.get(check_id),
                n_pass=n_pass,
                n_fail=n_fail,
                n_na=n_na,
                n_error=n_error,
                na_reason_text_top=na_texts.get(check_id, Counter()).most_common(3),
                liveness=classify(
                    n_pass=n_pass,
                    n_fail=n_fail,
                    n_na=n_na,
                    n_error=n_error,
                    unreachable=bool(blind_signals),
                ),
                unreachable_signals=blind_signals,
            )
        )

    total = sum(c.n_total for c in checks)
    total_na = sum(c.n_na for c in checks)
    share = (total_na / total) if total else 0.0
    return CoverageReport(
        corpus_label=corpus_label,
        corpus_kind=corpus_kind,
        n_traces=n_traces,
        n_unloadable=n_unloadable,
        checks=checks,
        na_share=share,
        evidence_starved=share > EVIDENCE_STARVED_SHARE,
        top_abstainers=Counter({c.check_id: c.n_na for c in checks if c.n_na}).most_common(3),
        provenance=provenance,
    )


def liveness_from_results(
    results: Sequence[CheckResult],
    *,
    corpus_label: str,
    corpus_kind: CorpusKind = "CORPUS",
    n_traces: int | None = None,
    n_unloadable: int = 0,
    provenance: Provenance | None = None,
) -> CoverageReport:
    """Fold :class:`CheckResult` objects into a :class:`CoverageReport`."""
    traces = n_traces if n_traces is not None else len({r.trace_id for r in results})
    return _fold(
        ((r.check_id, r.failure_mode_id, r.outcome, r.evidence_text) for r in results),
        corpus_label=corpus_label,
        corpus_kind=corpus_kind,
        n_traces=traces,
        n_unloadable=n_unloadable,
        provenance=provenance,
    )


def liveness_from_report(path: Path) -> CoverageReport:
    """Fold a ``SuiteReport`` JSON already on disk — no checks re-run.

    This is the cheapest liveness measurement available: the reports under
    ``evals/results/`` can be folded before a single line of check code changes.

    Args:
        path: Path to a ``report.json`` carrying ``check_results``.

    Returns:
        A :class:`CoverageReport` stamped ``FIXTURE-ONLY`` when the report's
        provenance does not say otherwise.

    Raises:
        ValueError: When the document carries no ``check_results`` array.
    """
    doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    raw = doc.get("check_results")
    if not isinstance(raw, list):
        raise ValueError(f"no check_results array in {path}")

    rows = [
        (
            str(r.get("check_id", "?")),
            r.get("failure_mode_id"),
            str(r.get("outcome", "error")),
            str(r.get("evidence_text", "")),
        )
        for r in raw
        if isinstance(r, dict)
    ]
    n_traces = len({str(r.get("trace_id")) for r in raw if isinstance(r, dict)})
    kind: CorpusKind = str(doc.get("corpus_kind", "FIXTURE-ONLY"))  # type: ignore[assignment]
    if kind not in ("FIXTURE-ONLY", "CORPUS", "LIVE"):
        kind = "FIXTURE-ONLY"
    return _fold(
        rows,
        corpus_label=f"{path.parent.name}/report.json",
        corpus_kind=kind,
        n_traces=n_traces,
    )


def load_traces(root: Path) -> tuple[list[Trace], int]:
    """Load ``*.json`` traces from *root*, tolerating unreadable documents.

    Args:
        root: Directory of trace documents.

    Returns:
        ``(traces, n_unloadable)``.
    """
    traces: list[Trace] = []
    unloadable = 0
    if not root.is_dir():
        return traces, unloadable
    for path in sorted(root.glob("*.json")):
        try:
            traces.append(Trace.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 — a bad document must not stop the audit
            unloadable += 1
    return traces, unloadable


def liveness_over_corpus(
    traces: Sequence[Trace],
    *,
    corpus_label: str,
    corpus_kind: CorpusKind = "CORPUS",
    tier: str | None = "A",
    n_unloadable: int = 0,
    with_provenance: bool = False,
) -> CoverageReport:
    """Run every registered check over *traces* and fold the outcomes.

    A check that raises is recorded as ``error`` and never as a decision — errors
    are not failures (``EVAL_METHODOLOGY.md`` §6).
    """
    ensure_checks_loaded()
    results: list[CheckResult] = []
    for trace in traces:
        for chk in all_checks(tier=tier):
            try:
                results.append(chk.run(trace))
            except Exception as exc:  # noqa: BLE001 — audit must survive one bad check
                results.append(
                    CheckResult(
                        check_id=chk.id,
                        failure_mode_id=chk.failure_mode_id,
                        trace_id=trace.trace_id,
                        outcome="error",
                        evidence_text=f"{type(exc).__name__}: {exc}",
                    )
                )
    return liveness_from_results(
        results,
        corpus_label=corpus_label,
        corpus_kind=corpus_kind,
        n_traces=len(traces),
        n_unloadable=n_unloadable,
        provenance=collect(tier=tier) if with_provenance else None,
    )


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

_MARK = {"live": "live", "thin": "thin", "blind": "BLIND", "unreachable": "UNREACHABLE"}


def render_markdown(report: CoverageReport, *, include_na_reasons: bool = True) -> str:
    """Render one corpus's liveness as markdown."""
    lines = [
        f"# Check liveness — {report.corpus_label}",
        "",
        f"**{report.headline()}**",
        "",
        "| Check | FM | pass | fail | n/a | err | na% | rate | liveness |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for c in sorted(report.checks, key=lambda x: (_SEVERITY[x.liveness], x.check_id)):
        lines.append(
            f"| `{c.check_id}` | {c.failure_mode_id or '—'} | {c.n_pass} | {c.n_fail} "
            f"| {c.n_na} | {c.n_error} | {100 * c.na_share:.0f}% | {c.rate_text()} "
            f"| {_MARK[c.liveness]} |"
        )

    erroring = [c for c in report.checks if c.n_error]
    if erroring:
        lines += [
            "",
            "## Checks that raised",
            "",
            "An error is not a failure (`EVAL_METHODOLOGY.md` §6) and never counts as a",
            "decision — but a check erroring on every trace is as blind as one abstaining.",
            "",
        ]
        for c in sorted(erroring, key=lambda x: -x.n_error):
            lines.append(f"- `{c.check_id}` — {c.n_error} of {c.n_total} raised")

    tally = report.counts()
    if tally["unreachable"]:
        lines += [
            "",
            "## Unreachable — no corpus can fix these",
            "",
        ]
        for c in report.by_liveness("unreachable"):
            lines.append(
                f"- `{c.check_id}` ({c.failure_mode_id or 'no FM'}) — no parser produces "
                f"{', '.join(c.unreachable_signals)}"
            )

    if report.evidence_starved:
        lines += [
            "",
            "## EVIDENCE-STARVED",
            "",
            f"`not_applicable` is {100 * report.na_share:.1f}% of all check results. "
            "Top abstainers:",
            "",
        ]
        for check_id, n in report.top_abstainers:
            lines.append(f"- `{check_id}` — {n} abstentions")

    if include_na_reasons:
        lines += [
            "",
            "## Why checks abstained",
            "",
            "| Check | Reason | Count |",
            "| --- | --- | ---: |",
        ]
        for c in sorted(report.checks, key=lambda x: -x.n_na):
            for text, n in c.na_reason_text_top:
                lines.append(f"| `{c.check_id}` | {text} | {n} |")

    return "\n".join(lines) + "\n"


def render_side_by_side(fixtures: CoverageReport, corpus: CoverageReport) -> str:
    """Render two corpora in one table (R2.8).

    A check that is ``live`` on fixtures and ``blind`` on the corpus is the exact
    defect this module exists to surface, and one column cannot show it.
    """
    by_id = {c.check_id: c for c in corpus.checks}
    lines = [
        "# Check liveness — fixtures vs corpus",
        "",
        f"- **fixtures:** {fixtures.headline()}",
        f"- **corpus:** {corpus.headline()}",
        "",
        "| Check | FM | fixtures | corpus | delta |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in sorted(fixtures.checks, key=lambda x: (_SEVERITY[x.liveness], x.check_id)):
        c = by_id.get(f.check_id)
        if c is None:
            c_cell = "not run"
        elif c.n_error and not c.n_decided:
            c_cell = f"{_MARK[c.liveness]} ({c.n_error} raised)"
        else:
            c_cell = f"{_MARK[c.liveness]} ({c.n_decided} decided)"
        delta = ""
        if c and _SEVERITY[c.liveness] < _SEVERITY[f.liveness]:
            delta = f"↓ {_MARK[f.liveness]} → {_MARK[c.liveness]}"
        lines.append(
            f"| `{f.check_id}` | {f.failure_mode_id or '—'} "
            f"| {_MARK[f.liveness]} ({f.n_decided} decided) | {c_cell} | {delta} |"
        )
    return "\n".join(lines) + "\n"


def render_signals_markdown(rows: Sequence[SignalRow]) -> str:
    """Render the signal-chain inventory as markdown (R4.6)."""
    lines = [
        "# Signal chain — harness writer → parser → check",
        "",
        "| Span type | Harness writers | Parsers | Consumers | Flags |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| `{r.span_type}` | {', '.join(r.harness_writers) or '—'} "
            f"| {', '.join(r.parsers) or '**none**'} "
            f"| {', '.join(f'`{c}`' for c in r.consumers) or '—'} "
            f"| {', '.join(r.flags) or 'ok'} |"
        )
    flagged = [r for r in rows if r.flags]
    if flagged:
        lines += ["", "## Flags", ""]
        for r in flagged:
            lines.append(f"- `{r.span_type}` — {', '.join(r.flags)}")
    return "\n".join(lines) + "\n"
