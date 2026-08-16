"""Artifact presence and hallucination-density checks."""

from __future__ import annotations

from pathlib import Path

from evals.checks._helpers import scenario_config
from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.fixtures import count_hallucinations  # import, do not copy
from evals.trace.models import Trace


@check(id="CHK-required-artifacts", failure_mode_id=None, tier="A")
def required_artifacts(trace: Trace) -> CheckResult:
    """Fail when scenario ``expected.files`` are not all present in artifacts."""
    cid = "CHK-required-artifacts"
    cfg = scenario_config(trace)
    expected = cfg.get("expected") if isinstance(cfg.get("expected"), dict) else {}
    files = expected.get("files") if isinstance(expected, dict) else None
    if not files:
        # Allow direct override
        files = trace.raw_result.get("expected_files")
    if not isinstance(files, list) or not files:
        return na(cid, trace, "scenario has no expected.files")

    present = {a.path for a in trace.artifacts}
    # Also match by basename
    basenames = {Path(p).name for p in present}
    missing: list[str] = []
    for f in files:
        f_s = str(f)
        if (
            f_s in present
            or Path(f_s).name in basenames
            or any(p.endswith(f_s) or p.endswith("/" + f_s) for p in present)
        ):
            continue
        missing.append(f_s)

    if missing:
        return failed(
            cid,
            trace,
            evidence_text=f"missing expected files: {missing}",
            detail={"missing": missing, "present": sorted(present)},
        )
    return passed(cid, trace, evidence_text="all expected.files present")


@check(id="CHK-hallucination-density", failure_mode_id=None, tier="A")
def hallucination_density(trace: Trace) -> CheckResult:
    """Fail when ``count_hallucinations()`` exceeds the configured threshold.

    Uses :func:`evals.fixtures.count_hallucinations` against ``workspace_dir``
    when present. Fixture traces may set ``raw_result.hallucination_count`` to
    avoid depending on a live workspace while still exercising the threshold.
    """
    cid = "CHK-hallucination-density"
    cfg = scenario_config(trace)
    threshold = int(cfg.get("max_hallucinations", trace.raw_result.get("max_hallucinations", 0)))

    if "hallucination_count" in trace.raw_result:
        try:
            count = int(trace.raw_result["hallucination_count"])
        except (TypeError, ValueError):
            return na(cid, trace, "hallucination_count unparseable")
    elif trace.workspace_dir:
        ws = Path(trace.workspace_dir)
        if not ws.is_dir():
            return na(cid, trace, f"workspace_dir missing: {ws}")
        count = count_hallucinations(ws)
    else:
        return na(cid, trace, "no workspace_dir or hallucination_count")

    if count > threshold:
        return failed(
            cid,
            trace,
            evidence_text=f"hallucination_count={count} > threshold={threshold}",
            detail={"hallucination_count": count, "threshold": threshold},
        )
    return passed(
        cid,
        trace,
        evidence_text=f"hallucination_count={count} ≤ {threshold}",
        detail={"hallucination_count": count, "threshold": threshold},
    )
