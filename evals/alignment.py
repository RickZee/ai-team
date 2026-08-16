"""Judge alignment metrics: confusion, κ, bootstrap CI, bias correction (R8)."""

from __future__ import annotations

import json
import random
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from evals.golden import GoldenLabel
from evals.judges.base import Verdict

Split = Literal["dev", "test"]
VALIDATION_LOG = Path(__file__).resolve().parent / "golden" / ".validation_log.jsonl"
ALIGNMENT_DIR = Path(__file__).resolve().parent / "golden" / "alignment"

ADVISORY_NO_LIVE_REASON = "no live validation run; pending human golden set + budgeted align"


class Disagreement(BaseModel):
    """One test-split unit where judge and human differ (R8.8)."""

    labeling_unit_id: str
    human_label: Literal["present", "absent"]
    judge_verdict: Literal["pass", "fail", "error"]
    reason: str


class AlignmentReport(BaseModel):
    """Per-judge alignment summary on one split (design §4.8 / R8.5–R8.6)."""

    judge_id: str
    prompt_hash: str
    split: Split
    n: int
    tp: int
    fp: int
    tn: int
    fn: int
    tpr: float
    tnr: float
    precision: float
    f1: float
    accuracy: float
    kappa: float
    tpr_ci95: tuple[float, float]
    tnr_ci95: tuple[float, float]
    eligible_to_gate: bool
    ineligibility_reasons: list[str] = Field(default_factory=list)
    validated_at: datetime
    stale: bool = False
    disagreements: list[Disagreement] = Field(default_factory=list)


def confusion(
    verdicts: Sequence[Verdict],
    labels: Sequence[GoldenLabel],
) -> tuple[int, int, int, int]:
    """Return (tp, fp, tn, fn).

    Convention: judge ``fail`` predicts the failure mode is PRESENT; ``pass``
    predicts ABSENT. ``error`` verdicts are excluded from denominators.
    """
    by_id = {v.labeling_unit_id: v for v in verdicts}
    tp = fp = tn = fn = 0
    for lab in labels:
        verd = by_id.get(lab.labeling_unit_id)
        if verd is None or verd.verdict == "error":
            continue
        pred_present = verd.verdict == "fail"
        actual_present = lab.human_label == "present"
        if pred_present and actual_present:
            tp += 1
        elif pred_present and not actual_present:
            fp += 1
        elif not pred_present and not actual_present:
            tn += 1
        else:
            fn += 1
    return tp, fp, tn, fn


def cohens_kappa(tp: int, fp: int, tn: int, fn: int) -> float:
    """Cohen's κ for a 2×2 confusion matrix."""
    n = tp + fp + tn + fn
    if n == 0:
        return 0.0
    po = (tp + tn) / n
    p_yes = ((tp + fp) / n) * ((tp + fn) / n)
    p_no = ((tn + fn) / n) * ((tn + fp) / n)
    pe = p_yes + p_no
    if pe >= 1.0:
        return 0.0
    return (po - pe) / (1.0 - pe)


def bootstrap_ci(
    pairs: Sequence[tuple[Any, Any]],
    statistic: Callable[[Sequence[tuple[Any, Any]]], float],
    *,
    n_resamples: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile 95% bootstrap CI over paired observations."""
    if not pairs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(pairs)
    samples: list[float] = []
    for _ in range(n_resamples):
        resampled = [pairs[rng.randrange(n)] for _ in range(n)]
        samples.append(float(statistic(resampled)))
    samples.sort()
    lo_idx = int(0.025 * (n_resamples - 1))
    hi_idx = int(0.975 * (n_resamples - 1))
    return (samples[lo_idx], samples[hi_idx])


def bias_corrected_rate(observed: float, tpr: float, tnr: float) -> float | None:
    """Correct observed positive rate given validated TPR/TNR (R8.7).

    Returns ``None`` when ``TPR + TNR - 1 ≤ 0.2`` (unstable; suppress).
    """
    denom = tpr + tnr - 1.0
    if denom <= 0.2:
        return None
    return min(1.0, max(0.0, (observed + tnr - 1.0) / denom))


def _tpr_from_pairs(pairs: Sequence[tuple[bool, bool]]) -> float:
    """pairs are (pred_present, actual_present)."""
    actual_pos = [(p, a) for p, a in pairs if a]
    if not actual_pos:
        return 1.0
    return sum(1 for p, a in actual_pos if p) / len(actual_pos)


def _tnr_from_pairs(pairs: Sequence[tuple[bool, bool]]) -> float:
    actual_neg = [(p, a) for p, a in pairs if not a]
    if not actual_neg:
        return 1.0
    return sum(1 for p, a in actual_neg if not p) / len(actual_neg)


def build_alignment_report(
    *,
    judge_id: str,
    prompt_hash: str,
    split: Split,
    verdicts: Sequence[Verdict],
    labels: Sequence[GoldenLabel],
) -> AlignmentReport:
    """Assemble AlignmentReport with CIs, eligibility, and disagreements."""
    split_labels = [lab for lab in labels if lab.split == split]
    tp, fp, tn, fn = confusion(verdicts, split_labels)
    n = tp + fp + tn + fn
    tpr = tp / (tp + fn) if (tp + fn) else 1.0
    tnr = tn / (tn + fp) if (tn + fp) else 1.0
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    f1 = 2 * precision * tpr / (precision + tpr) if (precision + tpr) else 0.0
    accuracy = (tp + tn) / n if n else 0.0
    kappa = cohens_kappa(tp, fp, tn, fn)

    by_id = {v.labeling_unit_id: v for v in verdicts}
    pairs: list[tuple[bool, bool]] = []
    disagreements: list[Disagreement] = []
    for lab in split_labels:
        verd = by_id.get(lab.labeling_unit_id)
        if verd is None or verd.verdict == "error":
            continue
        pred = verd.verdict == "fail"
        actual = lab.human_label == "present"
        pairs.append((pred, actual))
        if pred != actual:
            disagreements.append(
                Disagreement(
                    labeling_unit_id=lab.labeling_unit_id,
                    human_label=lab.human_label,
                    judge_verdict=verd.verdict,
                    reason=verd.reason,
                )
            )

    tpr_ci = bootstrap_ci(pairs, _tpr_from_pairs, n_resamples=2000, seed=0)
    tnr_ci = bootstrap_ci(pairs, _tnr_from_pairs, n_resamples=2000, seed=0)

    reasons: list[str] = []
    eligible = True
    if n < 100:
        eligible = False
        reasons.append(f"n={n} < 100")
    if tpr < 0.90:
        eligible = False
        reasons.append(f"TPR={tpr:.3f} < 0.90")
    if tnr < 0.90:
        eligible = False
        reasons.append(f"TNR={tnr:.3f} < 0.90")
    if kappa < 0.70:
        eligible = False
        reasons.append(f"κ={kappa:.3f} < 0.70")

    return AlignmentReport(
        judge_id=judge_id,
        prompt_hash=prompt_hash,
        split=split,
        n=n,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        tpr=tpr,
        tnr=tnr,
        precision=precision,
        f1=f1,
        accuracy=accuracy,
        kappa=kappa,
        tpr_ci95=tpr_ci,
        tnr_ci95=tnr_ci,
        eligible_to_gate=eligible,
        ineligibility_reasons=reasons,
        validated_at=datetime.now(UTC),
        stale=False,
        disagreements=disagreements,
    )


def write_advisory_alignment(
    judge_id: str,
    *,
    prompt_hash: str = "pending",
    out_dir: Path | None = None,
) -> Path:
    """Write an advisory AlignmentReport without a live validation run."""
    report = AlignmentReport(
        judge_id=judge_id,
        prompt_hash=prompt_hash,
        split="test",
        n=0,
        tp=0,
        fp=0,
        tn=0,
        fn=0,
        tpr=0.0,
        tnr=0.0,
        precision=0.0,
        f1=0.0,
        accuracy=0.0,
        kappa=0.0,
        tpr_ci95=(0.0, 0.0),
        tnr_ci95=(0.0, 0.0),
        eligible_to_gate=False,
        ineligibility_reasons=[ADVISORY_NO_LIVE_REASON],
        validated_at=datetime.now(UTC),
        stale=False,
        disagreements=[],
    )
    root = out_dir or ALIGNMENT_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{judge_id}.json"
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def validation_log_has(
    judge_id: str,
    prompt_hash: str,
    *,
    log_path: Path | None = None,
) -> bool:
    """True if ``(judge_id, prompt_hash)`` already touched the test split."""
    path = log_path or VALIDATION_LOG
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        row = json.loads(text)
        if row.get("judge_id") == judge_id and row.get("prompt_hash") == prompt_hash:
            return True
    return False


def append_validation_log(
    judge_id: str,
    prompt_hash: str,
    *,
    allow_retest: bool = False,
    log_path: Path | None = None,
) -> None:
    """Append a test-split validation event (R8.4)."""
    path = log_path or VALIDATION_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "judge_id": judge_id,
        "prompt_hash": prompt_hash,
        "validated_at": datetime.now(UTC).isoformat(),
        "allow_retest": allow_retest,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
