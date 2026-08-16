"""Golden labeling units and deterministic split assignment (R8.1–R8.3).

Production open-coding (task 5.2) and judge golden-set labeling are human
steps — see ``evals/golden/README.md``. This module provides append-only
storage and split helpers only; it does not invent labels.

``LabelingUnit`` is the identity atom judges consume. ``GoldenLabel`` is the
append-only JSONL record persisted under ``evals/golden/<FM>.jsonl``.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

SplitName = Literal["dev", "test"]
HumanLabel = Literal["present", "absent"]

_DEFAULT_GOLDEN_ROOT = Path("evals/golden")


class LabelingUnit(BaseModel):
    """Identity of one ``(trace, span|run, FM)`` unit for judges / alignment."""

    labeling_unit_id: str = Field(description="Stable id: trace_id|span_id|failure_mode_id")
    trace_id: str = Field(description="Trace under review")
    span_id: str | None = Field(
        default=None,
        description="Span id, or None / 'run' for whole-run units",
    )
    failure_mode_id: str = Field(description="FM-### taxonomy id")


class GoldenLabel(BaseModel):
    """Persisted human label for a labeling unit (R8.1)."""

    labeling_unit_id: str
    trace_id: str
    span_id: str | None = None
    failure_mode_id: str
    human_label: HumanLabel
    annotator: str
    labeled_at: datetime
    notes: str = ""
    split: SplitName


def make_labeling_unit_id(trace_id: str, span_id: str | None, failure_mode_id: str) -> str:
    """Build the stable labeling-unit id used for split assignment."""
    sid = span_id if span_id else "run"
    return f"{trace_id}|{sid}|{failure_mode_id}"


def assign_split(labeling_unit_id: str) -> SplitName:
    """Assign ``test`` iff ``sha256(id) % 100 < 40``, else ``dev`` (design §4.8)."""
    digest = hashlib.sha256(labeling_unit_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return "test" if bucket < 40 else "dev"


def golden_path(failure_mode_id: str, *, golden_root: Path | None = None) -> Path:
    """Return ``evals/golden/<FM-###>.jsonl``."""
    root = Path(golden_root) if golden_root is not None else _DEFAULT_GOLDEN_ROOT
    return root / f"{failure_mode_id}.jsonl"


def load_golden(
    failure_mode_id: str,
    *,
    golden_root: Path | None = None,
) -> list[GoldenLabel]:
    """Load append-only golden labels for one failure mode."""
    path = golden_path(failure_mode_id, golden_root=golden_root)
    if not path.is_file():
        return []
    out: list[GoldenLabel] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            out.append(GoldenLabel.model_validate_json(text))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid golden line {path}:{line_no}: {exc}") from exc
    return out


def append_golden(
    label: GoldenLabel,
    *,
    golden_root: Path | None = None,
) -> Path:
    """Append one golden label; refuses duplicate ``labeling_unit_id``."""
    path = golden_path(label.failure_mode_id, golden_root=golden_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {
        u.labeling_unit_id for u in load_golden(label.failure_mode_id, golden_root=golden_root)
    }
    if label.labeling_unit_id in existing:
        raise ValueError(f"labeling unit already present: {label.labeling_unit_id}")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(label.model_dump_json() + "\n")
    return path


def make_label(
    *,
    trace_id: str,
    span_id: str | None,
    failure_mode_id: str,
    human_label: HumanLabel,
    annotator: str,
    notes: str = "",
) -> GoldenLabel:
    """Construct a golden label with deterministic split assignment."""
    lu_id = make_labeling_unit_id(trace_id, span_id, failure_mode_id)
    return GoldenLabel(
        labeling_unit_id=lu_id,
        trace_id=trace_id,
        span_id=span_id if span_id else "run",
        failure_mode_id=failure_mode_id,
        human_label=human_label,
        annotator=annotator,
        labeled_at=datetime.now(tz=UTC),
        notes=notes,
        split=assign_split(lu_id),
    )


def class_counts(units: Sequence[GoldenLabel]) -> dict[str, int]:
    """Count present/absent labels."""
    c = Counter(u.human_label for u in units)
    return {"present": int(c.get("present", 0)), "absent": int(c.get("absent", 0))}


def split_counts(units: Sequence[GoldenLabel]) -> dict[str, dict[str, int]]:
    """Return ``{split: {present, absent}}`` counts."""
    out: dict[str, dict[str, int]] = {
        "dev": {"present": 0, "absent": 0},
        "test": {"present": 0, "absent": 0},
    }
    for u in units:
        out[u.split][u.human_label] += 1
    return out


def stratification_ok(
    units: Sequence[GoldenLabel],
    *,
    min_class_fraction: float = 0.25,
) -> tuple[bool, str]:
    """Check each split holds ≥ *min_class_fraction* of each class (R8.3 helper).

    Vacuously True when a class has zero total labels (typical while all FMs
    are ``detection: check`` and the judge golden set is empty).
    """
    totals = class_counts(units)
    by_split = split_counts(units)
    for label in ("present", "absent"):
        total = totals[label]
        if total == 0:
            continue
        for split_name in ("dev", "test"):
            n = by_split[split_name][label]
            frac = n / total
            if frac < min_class_fraction:
                return (
                    False,
                    f"{split_name} holds {n}/{total}={frac:.2%} of {label} "
                    f"(need ≥ {min_class_fraction:.0%})",
                )
    return True, "ok"


def list_golden_fms(*, golden_root: Path | None = None) -> list[str]:
    """Return FM ids that have a golden JSONL file."""
    root = Path(golden_root) if golden_root is not None else _DEFAULT_GOLDEN_ROOT
    if not root.is_dir():
        return []
    return sorted(p.stem for p in root.glob("FM-*.jsonl"))


def golden_stats_table(*, golden_root: Path | None = None) -> str:
    """Format a stats table for ``golden stats`` CLI."""
    fms = list_golden_fms(golden_root=golden_root)
    lines = [
        f"{'FM':<10} {'n':>5} {'present':>8} {'absent':>8} " f"{'dev':>5} {'test':>5} {'strat':>6}",
    ]
    if not fms:
        lines.append("(no golden JSONL files — judge FMs only; check FMs use fixtures)")
        return "\n".join(lines)
    for fm in fms:
        units = load_golden(fm, golden_root=golden_root)
        cc = class_counts(units)
        sc = split_counts(units)
        ok, _ = stratification_ok(units)
        lines.append(
            f"{fm:<10} {len(units):>5} {cc['present']:>8} {cc['absent']:>8} "
            f"{sc['dev']['present'] + sc['dev']['absent']:>5} "
            f"{sc['test']['present'] + sc['test']['absent']:>5} "
            f"{'ok' if ok else 'FAIL':>6}"
        )
    return "\n".join(lines)
