"""Tool-bus checks: FM-012 uncommitted live writes."""

from __future__ import annotations

from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace

_DEV = frozenset({"development", "testing", "qa"})
_LIVE_PREFIXES = ("src/", "tests/")
_HARNESS_OK = ("docs/STATE.md", "docs/CONSTRAINTS.md", "docs/LESSONS.md", "logs/", ".harness/")


def _is_live_write(payload: dict[str, object]) -> bool:
    kind = str(payload.get("kind") or "")
    code = str(payload.get("code") or payload.get("result") or "")
    tool = str(payload.get("tool") or payload.get("tool_name") or "")
    if tool == "commit_write":
        return False
    if kind == "write" and code == "ok":
        refs = payload.get("artifact_refs") or payload.get("path") or ""
        paths = [str(x) for x in refs] if isinstance(refs, list) else [str(refs)]
        for p in paths:
            if p.startswith(_HARNESS_OK) or p.startswith(".harness/"):
                continue
            if p.startswith(_LIVE_PREFIXES) or p.startswith("src") or "/src/" in p:
                return True
        # Bare filename writes to src-like paths in payload.path
        path = str(payload.get("path") or "")
        if path.startswith(_LIVE_PREFIXES):
            return True
    return False


@check(id="CHK-draft-commit", failure_mode_id="FM-012", tier="A")
def draft_commit(trace: Trace) -> CheckResult:
    """Fail when a live src/tests write skipped draft-then-commit."""
    cid = "CHK-draft-commit"
    fm = "FM-012"
    results = [s for s in trace.spans_of("tool_result") if s.phase in _DEV or s.phase is None]
    uses = [s for s in trace.spans_of("tool_use") if s.phase in _DEV or s.phase is None]
    if not results and not uses:
        if any("no audit log" in w for w in trace.warnings):
            return na(cid, trace, "backend emits no tool-level audit", failure_mode_id=fm)
        # No tool activity at all
        if not any(s.phase in _DEV for s in trace.spans_of("phase_end")):
            return na(cid, trace, "no development phase", failure_mode_id=fm)

    offenders: list[str] = []
    for span in results:
        if _is_live_write(span.payload):
            offenders.append(span.span_id)

    if offenders:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=offenders,
            evidence_text="live write without draft-then-commit",
            detail={"offender_span_ids": offenders},
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text="writes drafted or committed")
