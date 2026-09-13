"""Acceptance-list monotonicity: FM-014."""

from __future__ import annotations

import json
from typing import Any

from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace


def _snapshots_from_trace(trace: Trace) -> list[dict[str, Any]]:
    raw = trace.raw_result.get("acceptance_snapshots")
    if isinstance(raw, list):
        return [s for s in raw if isinstance(s, dict)]
    text = trace.read_artifact("logs/acceptance.jsonl")
    if not text:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and isinstance(row.get("snapshot"), list):
            rows.append(row)
    return rows


def _item_map(snapshot: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in snapshot:
        if isinstance(item, dict) and item.get("id"):
            out[str(item["id"])] = item
    return out


@check(id="CHK-acceptance-monotonic", failure_mode_id="FM-014", tier="A")
def acceptance_monotonic(trace: Trace) -> CheckResult:
    """Fail when ACCEPTANCE.json items are removed, rewritten, or illegally flipped."""
    cid = "CHK-acceptance-monotonic"
    fm = "FM-014"
    has_file = any(a.path in {"ACCEPTANCE.json", "logs/acceptance.jsonl"} for a in trace.artifacts)
    snaps = _snapshots_from_trace(trace)
    if not snaps and not has_file:
        return na(
            cid,
            trace,
            "inconclusive: no acceptance artifacts",
            failure_mode_id=fm,
        )
    if len(snaps) < 2:
        first = snaps[0] if snaps else None
        if first is None:
            return na(cid, trace, "inconclusive: no acceptance snapshots", failure_mode_id=fm)
        return passed(
            cid, trace, failure_mode_id=fm, evidence_text="single snapshot; nothing to diff"
        )

    first_items = _item_map(snaps[0].get("snapshot") or [])
    last_items = _item_map(snaps[-1].get("snapshot") or [])
    problems: list[str] = []

    removed = sorted(set(first_items) - set(last_items))
    if removed:
        problems.append(f"removed ids: {removed}")

    for iid, first in first_items.items():
        last = last_items.get(iid)
        if last is None:
            continue
        for field in ("description", "steps"):
            if first.get(field) != last.get(field):
                problems.append(f"{iid}: {field} changed")
        if first.get("id") != last.get("id"):
            problems.append(f"{iid}: id changed")
        if first.get("passes") is True and last.get("passes") is False:
            demotions = last.get("demotions") or []
            if not demotions:
                problems.append(f"{iid}: true→false without demotions[]")
        if first.get("passes") is False and last.get("passes") is True:
            evidence = last.get("evidence") or []
            if not evidence:
                problems.append(f"{iid}: false→true with empty evidence")
            else:
                inventory = {a.path for a in trace.artifacts}
                dangling = [p for p in evidence if str(p) not in inventory]
                if dangling:
                    problems.append(f"{iid}: dangling evidence {dangling}")

    if problems:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text="; ".join(problems),
            detail={"problems": problems},
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text="acceptance list is monotonic")
