"""Week-over-week drift over receipts / traces. Warn-only, $0, no model APIs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DriftWindow(BaseModel):
    """Aggregate metrics for one window of receipts."""

    n: int = 0
    fm_hits: dict[str, int] = Field(default_factory=dict)
    smoke_pass: int = 0
    smoke_n: int = 0
    files_written: list[int] = Field(default_factory=list)
    cost: list[float] = Field(default_factory=list)
    cost_per_accepted: list[float] = Field(default_factory=list)


class DriftReport(BaseModel):
    """Compare current vs previous window."""

    current: DriftWindow
    previous: DriftWindow
    warnings: list[str] = Field(default_factory=list)


def _as_receipt(raw: dict[str, Any]) -> dict[str, Any]:
    return raw


def summarize_receipts(receipts: list[dict[str, Any]]) -> DriftWindow:
    """Aggregate a list of receipt dicts."""
    win = DriftWindow(n=len(receipts))
    for rec in receipts:
        for fm in rec.get("failure_ids") or []:
            win.fm_hits[str(fm)] = win.fm_hits.get(str(fm), 0) + 1
        smoke = rec.get("smoke") or {}
        if smoke:
            win.smoke_n += 1
            if smoke.get("success"):
                win.smoke_pass += 1
        tests = rec.get("tests") or {}
        files = tests.get("files_written")
        if files is None:
            files = rec.get("files_written")
        if isinstance(files, int):
            win.files_written.append(files)
        cost = rec.get("cost_usd")
        if isinstance(cost, int | float):
            win.cost.append(float(cost))
        cpa = rec.get("cost_per_accepted_change")
        if isinstance(cpa, int | float):
            win.cost_per_accepted.append(float(cpa))
    return win


def compare_windows(
    current: DriftWindow,
    previous: DriftWindow,
    *,
    rate_tolerance: float = 0.25,
) -> DriftReport:
    """Warn when rates move beyond *rate_tolerance* (relative)."""
    warnings: list[str] = []

    def _rate(hits: int, n: int) -> float:
        return hits / n if n else 0.0

    if previous.n and current.n:
        for fm, hits in current.fm_hits.items():
            prev = _rate(previous.fm_hits.get(fm, 0), previous.n)
            now = _rate(hits, current.n)
            if prev > 0 and now - prev > rate_tolerance:
                warnings.append(f"{fm} rate {prev:.2f} → {now:.2f}")
            elif prev == 0 and now > rate_tolerance:
                warnings.append(f"{fm} appeared at rate {now:.2f}")
        if previous.smoke_n and current.smoke_n:
            prev_s = previous.smoke_pass / previous.smoke_n
            now_s = current.smoke_pass / current.smoke_n
            if prev_s - now_s > rate_tolerance:
                warnings.append(f"smoke pass {prev_s:.2f} → {now_s:.2f}")
        if previous.cost and current.cost:
            prev_c = sum(previous.cost) / len(previous.cost)
            now_c = sum(current.cost) / len(current.cost)
            if prev_c > 0 and (now_c - prev_c) / prev_c > rate_tolerance:
                warnings.append(f"mean cost {prev_c:.4f} → {now_c:.4f}")
    return DriftReport(current=current, previous=previous, warnings=warnings)


def load_receipts_from_dir(root: Path) -> list[dict[str, Any]]:
    """Load ``receipt.json`` files under *root* (``output/runs/*`` or a test dir)."""
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    paths = sorted(root.glob("**/receipt.json"))
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            out.append(_as_receipt(data))
    return out


def drift_from_dirs(current_dir: Path, previous_dir: Path) -> DriftReport:
    """Compare two directories of receipts."""
    return compare_windows(
        summarize_receipts(load_receipts_from_dir(current_dir)),
        summarize_receipts(load_receipts_from_dir(previous_dir)),
    )
