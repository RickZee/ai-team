"""Workspace isolation check: FM-004."""

from __future__ import annotations

from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace


@check(id="CHK-workspace-isolation", failure_mode_id="FM-004", tier="A")
def workspace_isolation(trace: Trace) -> CheckResult:
    """Fail when suite sibling workspace dirs collide with this trace's dir.

    Suite runners attach ``raw_result.suite_workspace_dirs`` — the list of
    workspace paths allocated in the same suite run. A single-trace eval
    without that context returns ``not_applicable``.
    """
    cid = "CHK-workspace-isolation"
    fm = "FM-004"

    siblings = trace.raw_result.get("suite_workspace_dirs")
    if not isinstance(siblings, list) or not siblings:
        return na(
            cid,
            trace,
            "no suite_workspace_dirs context on trace",
            failure_mode_id=fm,
        )

    paths = [str(p) for p in siblings if p]
    if not paths:
        return na(cid, trace, "empty suite_workspace_dirs", failure_mode_id=fm)

    mine = trace.workspace_dir
    # Count duplicates across the suite
    counts: dict[str, int] = {}
    for p in paths:
        counts[p] = counts.get(p, 0) + 1
    collisions = {p: n for p, n in counts.items() if n > 1}

    if collisions:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text="suite workspace_dir collision detected",
            detail={
                "workspace_dir": mine,
                "collisions": collisions,
                "suite_workspace_dirs": paths,
            },
        )
    return passed(
        cid,
        trace,
        failure_mode_id=fm,
        evidence_text="all suite workspace dirs unique",
        detail={"suite_size": len(paths)},
    )
