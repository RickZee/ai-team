"""Validate deterministic checks against labeled fail/pass fixtures (task 5.5).

Uses committed check fixtures under ``tests/fixtures/traces/`` (and copies in
``evals/fixtures/traces/``) as synthetic labeled units — fail ⇒ present,
pass ⇒ absent. These are not production human open-coding labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from evals.checks.registry import Check, all_checks, ensure_checks_loaded, get_check
from evals.taxonomy.loader import Taxonomy, load_taxonomy
from evals.trace.models import Trace

# Thresholds from task 5.5 DoD for detection:check FMs.
DEFAULT_TPR_FLOOR = 0.95
DEFAULT_TNR_FLOOR = 0.95

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVAL_FIXTURES = _REPO_ROOT / "evals" / "fixtures" / "traces"
_TEST_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "traces"

OutcomeWanted = Literal["fail", "pass", "na"]


def load_check_fixture(check_id: str, outcome: OutcomeWanted) -> Trace:
    """Load a synthetic check fixture by check id and expected outcome."""
    # Prefer evals/fixtures/traces/<trace_id>.json (Phase 5 copies).
    tid = f"{check_id}__{outcome}__fixture"
    for root in (_EVAL_FIXTURES, _TEST_FIXTURES):
        by_id = root / f"{tid}.json"
        if by_id.is_file():
            return Trace.model_validate_json(by_id.read_text(encoding="utf-8"))
        by_name = root / f"{check_id}__{outcome}.json"
        if by_name.is_file():
            return Trace.model_validate_json(by_name.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no fixture for {check_id} / {outcome}")


@dataclass(frozen=True)
class ConfusionMetrics:
    """Binary confusion counts and rates (fail verdict == present)."""

    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def tpr(self) -> float | None:
        """Recall on present (fail fixtures)."""
        denom = self.tp + self.fn
        return None if denom == 0 else self.tp / denom

    @property
    def tnr(self) -> float | None:
        """Specificity on absent (pass fixtures)."""
        denom = self.tn + self.fp
        return None if denom == 0 else self.tn / denom

    @property
    def precision(self) -> float | None:
        denom = self.tp + self.fp
        return None if denom == 0 else self.tp / denom

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.tpr
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)

    def as_dict(self) -> dict[str, Any]:
        """JSON-serializable metrics dict."""
        return {
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "tpr": self.tpr,
            "tnr": self.tnr,
            "precision": self.precision,
            "f1": self.f1,
        }


def _outcome_to_prediction(outcome: str) -> bool | None:
    """Map check outcome to predicted present (True) / absent (False)."""
    if outcome == "fail":
        return True
    if outcome == "pass":
        return False
    return None  # not_applicable / error excluded from denominators


def confusion_from_pairs(
    pairs: list[tuple[bool, bool]],
) -> ConfusionMetrics:
    """Compute confusion from ``(predicted_present, label_present)`` pairs."""
    tp = fp = tn = fn = 0
    for pred, label in pairs:
        if pred and label:
            tp += 1
        elif pred and not label:
            fp += 1
        elif (not pred) and (not label):
            tn += 1
        else:
            fn += 1
    return ConfusionMetrics(tp=tp, fp=fp, tn=tn, fn=fn)


def evaluate_check_on_fixtures(check: Check) -> ConfusionMetrics:
    """Run *check* on its fail (present) and pass (absent) fixture traces."""
    pairs: list[tuple[bool, bool]] = []
    for outcome, label_present in (("fail", True), ("pass", False)):
        trace = load_check_fixture(check.id, outcome)  # type: ignore[arg-type]
        result = check.run(trace)
        pred = _outcome_to_prediction(result.outcome)
        if pred is None:
            continue
        pairs.append((pred, label_present))
    return confusion_from_pairs(pairs)


def checks_for_fm(failure_mode_id: str) -> list[Check]:
    """Return registered checks bound to *failure_mode_id*."""
    ensure_checks_loaded()
    return [c for c in all_checks() if c.failure_mode_id == failure_mode_id]


def validate_fm_checks(
    failure_mode_id: str,
    *,
    tpr_floor: float = DEFAULT_TPR_FLOOR,
    tnr_floor: float = DEFAULT_TNR_FLOOR,
) -> dict[str, Any]:
    """Validate all checks for one FM against fixture labels; report metrics."""
    ensure_checks_loaded()
    checks = checks_for_fm(failure_mode_id)
    if not checks:
        chk = get_check(failure_mode_id)
        if chk is not None:
            checks = [chk]
    rows: list[dict[str, Any]] = []
    all_ok = True
    for chk in checks:
        metrics = evaluate_check_on_fixtures(chk)
        tpr_ok = metrics.tpr is not None and metrics.tpr >= tpr_floor
        tnr_ok = metrics.tnr is not None and metrics.tnr >= tnr_floor
        ok = tpr_ok and tnr_ok
        all_ok = all_ok and ok
        rows.append(
            {
                "check_id": chk.id,
                "failure_mode_id": chk.failure_mode_id,
                "ok": ok,
                "metrics": metrics.as_dict(),
                "tpr_floor": tpr_floor,
                "tnr_floor": tnr_floor,
            }
        )
    return {
        "failure_mode_id": failure_mode_id,
        "ok": all_ok and bool(rows),
        "checks": rows,
    }


def validate_all_check_fms(
    *,
    taxonomy: Taxonomy | None = None,
    tpr_floor: float = DEFAULT_TPR_FLOOR,
    tnr_floor: float = DEFAULT_TNR_FLOOR,
) -> dict[str, Any]:
    """Validate every active ``detection: check`` FM."""
    tax = taxonomy or load_taxonomy()
    results: list[dict[str, Any]] = []
    for fm in tax.active():
        if fm.detection != "check":
            continue
        results.append(validate_fm_checks(fm.id, tpr_floor=tpr_floor, tnr_floor=tnr_floor))
    return {
        "ok": all(r["ok"] for r in results) if results else True,
        "failure_modes": results,
    }


def format_validation_report(payload: dict[str, Any]) -> str:
    """Pretty-print a validate_fm_checks / validate_all_check_fms payload."""
    lines: list[str] = []
    fms = payload.get("failure_modes")
    if fms is None:
        fms = [payload]
    for block in fms:
        fm_id = block.get("failure_mode_id", "?")
        lines.append(f"## {fm_id}  ok={block.get('ok')}")
        for row in block.get("checks") or []:
            m = row["metrics"]
            lines.append(
                f"  {row['check_id']}: tp={m['tp']} fp={m['fp']} tn={m['tn']} fn={m['fn']} "
                f"TPR={_fmt(m['tpr'])} TNR={_fmt(m['tnr'])} ok={row['ok']}"
            )
    overall = payload.get("ok")
    if overall is not None and "failure_modes" in payload:
        lines.append(f"\noverall_ok={overall}")
    return "\n".join(lines)


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"
