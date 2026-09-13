"""Ladder table: JSON first, Markdown rendered from that JSON (R5 / FM-008)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

MIN_N = 3
MIN_N_FOR_RATIO = 5

STAMP_MIXED = "MIXED-MODEL — NOT A HARNESS COMPARISON"
STAMP_UNDERPOWERED = "UNDERPOWERED"
STAMP_STALE = "STALE"
STAMP_NEVER = "never measured"
STAMP_DERIVED = "DERIVED — RATIO OF TWO NOISY ESTIMATES"


class ClaimRefusalError(ValueError):
    """Renderer refused to emit an unfalsifiable comparison."""


class LadderArmRow(BaseModel):
    """One arm's aggregated metrics."""

    arm_id: str
    n: int
    cost_usd_mean: float | None = None
    cost_usd_ci: list[float] | None = None
    wall_clock_s_mean: float | None = None
    wall_clock_s_ci: list[float] | None = None
    fm_incidence: dict[str, float] = Field(default_factory=dict)
    smoke_pass_rate: float | None = None
    accepted_change_rate: float | None = None
    demotion_rate: float | None = None
    qa_false_negative_rate: float | None = None
    source_ref: str = ""
    divergences: list[dict[str, Any]] = Field(default_factory=list)
    phase_cost: dict[str, float] = Field(default_factory=dict)
    phase_wall_clock: dict[str, float] = Field(default_factory=dict)
    staleness: str | None = None
    cost_per_fm_avoided: float | None = None
    cost_per_fm_avoided_stamp: str | None = None


class LadderReport(BaseModel):
    """JSON source of truth for the ladder table."""

    stamps: list[str] = Field(default_factory=list)
    arms: list[LadderArmRow] = Field(default_factory=list)
    no_measured_effect: list[str] = Field(default_factory=list)


def _mean_ci(values: list[float]) -> tuple[float | None, list[float] | None]:
    if not values:
        return None, None
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, [mean, mean]
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    se = var**0.5 / (len(values) ** 0.5)
    return mean, [mean - 1.96 * se, mean + 1.96 * se]


def render_ladder(
    traces: list[dict[str, Any]],
    *,
    allow_mixed_model: bool = False,
    allow_underpowered: bool = False,
    default_model: str | None = None,
) -> dict[str, Any]:
    """Group traces by ``arm_id`` and emit the JSON ladder document.

    Raises :class:`ClaimRefusalError` without the corresponding flag.
    """
    by_arm: dict[str, list[dict[str, Any]]] = {}
    models: set[str] = set()
    for t in traces:
        arm = str(t.get("arm_id") or "unknown")
        by_arm.setdefault(arm, []).append(t)
        mid = t.get("model_id") or (t.get("provenance") or {}).get("model_ids", {})
        if isinstance(mid, dict):
            models.update(str(v) for v in mid.values() if v)
        elif mid:
            models.add(str(mid))

    stamps: list[str] = []
    mixed = len(models) > 1
    if mixed and not allow_mixed_model:
        raise ClaimRefusalError("model ids differ across arms; pass --allow-mixed-model")
    if mixed:
        stamps.append(STAMP_MIXED)

    ns = [len(v) for v in by_arm.values()]
    under = bool(ns) and min(ns) < MIN_N
    if under and not allow_underpowered:
        raise ClaimRefusalError(f"n < {MIN_N} per arm; pass --allow-underpowered")
    if under:
        stamps.append(STAMP_UNDERPOWERED)

    rows: list[LadderArmRow] = []
    no_effect: list[str] = []
    for arm_id, group in sorted(by_arm.items()):
        costs = [
            float(t["cost"]["usd"])
            for t in group
            if isinstance(t.get("cost"), dict) and t["cost"].get("usd") is not None
        ]
        walls = [float(t["wall_clock_s"]) for t in group if t.get("wall_clock_s") is not None]
        c_mean, c_ci = _mean_ci(costs)
        w_mean, w_ci = _mean_ci(walls)
        n = len(group)
        fm: dict[str, float] = {}
        for t in group:
            for fm_id, hit in (t.get("fm_incidence") or {}).items():
                fm[str(fm_id)] = fm.get(str(fm_id), 0.0) + float(hit)
        if n:
            fm = {k: v / n for k, v in fm.items()}
        first = group[0]
        measured_model = first.get("ablation_model_id")
        staleness = None
        if first.get("family") == "ablation":
            if measured_model is None:
                staleness = STAMP_NEVER
            elif default_model and measured_model != default_model:
                staleness = STAMP_STALE
        ratio = first.get("cost_per_fm_avoided")
        ratio_stamp = None
        if ratio is not None and n < MIN_N_FOR_RATIO:
            ratio = None
        elif ratio is not None:
            ratio_stamp = STAMP_DERIVED
        delta = first.get("ablation_delta")
        if delta == 0 and first.get("ablation_measured") is False:
            no_effect.append(arm_id)
            # never render an unmeasured zero as a measured delta
            delta = None
        elif delta == 0 and first.get("ablation_measured") is True:
            no_effect.append(arm_id)
        rows.append(
            LadderArmRow(
                arm_id=arm_id,
                n=n,
                cost_usd_mean=c_mean,
                cost_usd_ci=c_ci,
                wall_clock_s_mean=w_mean,
                wall_clock_s_ci=w_ci,
                fm_incidence=fm,
                smoke_pass_rate=_rate(group, "smoke_pass"),
                accepted_change_rate=_rate(group, "accepted_change"),
                demotion_rate=_rate(group, "demotion"),
                qa_false_negative_rate=_rate(group, "qa_false_negative"),
                source_ref=str(first.get("source_ref") or ""),
                divergences=list(first.get("divergences") or []),
                phase_cost=dict(first.get("phase_cost") or {}),
                phase_wall_clock=dict(first.get("phase_wall_clock") or {}),
                staleness=staleness,
                cost_per_fm_avoided=ratio,
                cost_per_fm_avoided_stamp=ratio_stamp,
            )
        )
    report = LadderReport(stamps=stamps, arms=rows, no_measured_effect=no_effect)
    return report.model_dump(mode="json")


def _rate(group: list[dict[str, Any]], key: str) -> float | None:
    vals = [t.get(key) for t in group if t.get(key) is not None]
    if not vals:
        return None
    numeric = [float(v) for v in vals if v is not None]
    return sum(numeric) / len(numeric)


def markdown_from_ladder_json(doc: dict[str, Any]) -> str:
    """Render Markdown *from the JSON* — never recompute (FM-008)."""
    lines = ["# Ladder report", ""]
    stamps = doc.get("stamps") or []
    if stamps:
        lines.append("**Stamps:** " + " · ".join(stamps))
        lines.append("")
    lines.append(
        "| arm_id | n | cost_usd | wall_clock_s | smoke_pass | accepted | demotion | qa_fn |"
    )
    lines.append("| --- | ---: | --- | --- | --- | --- | --- | --- |")
    for arm in doc.get("arms") or []:
        cost = arm.get("cost_usd_mean")
        wall = arm.get("wall_clock_s_mean")
        lines.append(
            f"| {arm.get('arm_id')} | {arm.get('n')} | "
            f"{_fmt(cost)} | {_fmt(wall)} | {_fmt(arm.get('smoke_pass_rate'))} | "
            f"{_fmt(arm.get('accepted_change_rate'))} | {_fmt(arm.get('demotion_rate'))} | "
            f"{_fmt(arm.get('qa_false_negative_rate'))} |"
        )
    lines.append("")
    for arm in doc.get("arms") or []:
        lines.append(f"## {arm.get('arm_id')}")
        lines.append("")
        lines.append(f"- source_ref: `{arm.get('source_ref') or '—'}`")
        if arm.get("staleness"):
            lines.append(f"- staleness: **{arm['staleness']}**")
        if arm.get("cost_per_fm_avoided_stamp"):
            lines.append(
                f"- cost_per_fm_avoided: {_fmt(arm.get('cost_per_fm_avoided'))} "
                f"({arm['cost_per_fm_avoided_stamp']})"
            )
        lines.append("- received a full scenario contract rather than a thin brief")
        for div in arm.get("divergences") or []:
            lines.append(
                f"- divergence `{div.get('field')}`: expected {div.get('expected')!r} "
                f"actual {div.get('actual')!r} — {div.get('reason')}"
            )
        lines.append("")
    none = doc.get("no_measured_effect") or []
    if none:
        lines.append("## components with no measured effect at this n")
        lines.append("")
        for name in none:
            lines.append(f"- {name}")
        lines.append("")
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)
