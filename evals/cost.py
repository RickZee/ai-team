"""Cost normalization and suite-level budget ledger (R10).

``BudgetLedger`` is process-local and per-suite-run — deliberately *not* a
module-level singleton (taxonomy §7 / SpendGuard cross-contamination).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
import yaml

from evals.store import TraceStore
from evals.trace.models import CostRecord, Trace

logger = structlog.get_logger(__name__)

_EVALS_ROOT = Path(__file__).resolve().parent
_DEFAULT_PRICING_PATH = _EVALS_ROOT / "pricing.yaml"

# Fallback unit costs when the corpus has no historical token medians (design §5.1).
_DEFAULT_SCENARIO_USD: dict[str, float] = {
    "smoke-test": 0.04,
    "hello-world-smoke": 0.04,
    "todo-api-beginner": 0.25,
}
_DEFAULT_FALLBACK_USD = 0.10

# Heuristic split when only a total token count is known.
_DEFAULT_INPUT_FRACTION = 0.8


@dataclass(frozen=True)
class ModelRate:
    """Per-million-token rates for one model id."""

    input_per_mtok: float
    output_per_mtok: float


@dataclass(frozen=True)
class PricingTable:
    """Loaded ``evals/pricing.yaml`` content."""

    version: str
    models: dict[str, ModelRate]


class BudgetExceededError(RuntimeError):
    """Raised when cumulative spend crosses the suite ceiling."""

    def __init__(self, spent_usd: float, ceiling_usd: float) -> None:
        self.spent_usd = spent_usd
        self.ceiling_usd = ceiling_usd
        super().__init__(f"budget exceeded: spent ${spent_usd:.4f} > ceiling ${ceiling_usd:.4f}")


@dataclass
class BudgetLedger:
    """Per-suite-run spend tracker. Thread explicitly; never use a global.

    Args:
        ceiling_usd: Hard suite ceiling (R10.3). Default $5.00.
    """

    ceiling_usd: float
    spent_usd: float = 0.0
    records: list[CostRecord] = field(default_factory=list)
    aborted: bool = False

    def remaining(self) -> float:
        """Return unspent budget (floored at zero)."""
        return max(0.0, self.ceiling_usd - self.spent_usd)

    def crossed(self) -> bool:
        """True when cumulative measured spend has reached/crossed the ceiling."""
        return self.spent_usd >= self.ceiling_usd

    def record(self, cost: CostRecord) -> None:
        """Add *cost* to the ledger.

        Missing ``usd`` contributes ``0.0`` (unknown costs do not invent spend),
        but the record is still retained for reporting.
        """
        amount = float(cost.usd) if cost.usd is not None else 0.0
        self.spent_usd += amount
        self.records.append(cost)
        if self.crossed():
            self.aborted = True
            logger.warning(
                "budget_ceiling_crossed",
                spent_usd=self.spent_usd,
                ceiling_usd=self.ceiling_usd,
            )

    def mark_aborted(self) -> None:
        """Flag the suite as budget-aborted (remaining runs skipped)."""
        self.aborted = True


def load_pricing(path: Path | None = None) -> PricingTable:
    """Load and validate ``evals/pricing.yaml``.

    Args:
        path: Optional override path (defaults to ``evals/pricing.yaml``).

    Returns:
        Parsed :class:`PricingTable`.

    Raises:
        FileNotFoundError: When the pricing file is missing.
        ValueError: When the YAML shape is invalid.
    """
    pricing_path = path or _DEFAULT_PRICING_PATH
    raw = yaml.safe_load(pricing_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"pricing.yaml must be a mapping: {pricing_path}")
    version = str(raw.get("version") or "unset")
    models_raw = raw.get("models") or {}
    if not isinstance(models_raw, dict):
        raise ValueError("pricing.yaml 'models' must be a mapping")
    models: dict[str, ModelRate] = {}
    for model_id, rates in models_raw.items():
        if not isinstance(rates, dict):
            raise ValueError(f"pricing entry for {model_id!r} must be a mapping")
        models[str(model_id)] = ModelRate(
            input_per_mtok=float(rates["input_per_mtok"]),
            output_per_mtok=float(rates["output_per_mtok"]),
        )
    return PricingTable(version=version, models=models)


def _estimate_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    model_ids: dict[str, str],
    pricing: PricingTable,
) -> tuple[float | None, dict[str, float], list[str]]:
    """Return ``(usd, per_model, missing_model_ids)``."""
    if not model_ids:
        # Unknown model → unknown cost (R10.2); never invent a silent zero.
        return None, {}, ["<unspecified>"]

    missing: list[str] = []
    per_model: dict[str, float] = {}
    # Spread tokens evenly across roles when we only have aggregate counts.
    n_roles = max(1, len(model_ids))
    in_each = input_tokens // n_roles
    out_each = output_tokens // n_roles
    # Give remainder to the first role so totals are preserved.
    in_rem = input_tokens - in_each * n_roles
    out_rem = output_tokens - out_each * n_roles

    total = 0.0
    for i, (_role, model_id) in enumerate(model_ids.items()):
        rate = pricing.models.get(model_id)
        if rate is None:
            missing.append(model_id)
            continue
        inp = in_each + (in_rem if i == 0 else 0)
        out = out_each + (out_rem if i == 0 else 0)
        usd = (inp / 1_000_000.0) * rate.input_per_mtok + (out / 1_000_000.0) * rate.output_per_mtok
        per_model[model_id] = per_model.get(model_id, 0.0) + usd
        total += usd

    if missing:
        return None, per_model, missing
    return total, per_model, missing


def normalize_cost(
    trace: Trace,
    *,
    pricing: PricingTable | None = None,
) -> CostRecord:
    """Normalize ``trace.cost`` per R10.1 / R10.2.

    Preference order: ``sdk_reported`` / ``provider_usage`` with a concrete
    ``usd`` value are returned unchanged. Otherwise estimate from token counts
    and ``evals/pricing.yaml``. A missing model id warns loudly and yields
    ``source: "unknown"`` — never a silent zero.

    Args:
        trace: Trace whose cost field should be normalized.
        pricing: Optional pre-loaded rate table.

    Returns:
        A :class:`CostRecord` suitable for budget accounting and reporting.
    """
    table = pricing if pricing is not None else load_pricing()
    existing = trace.cost

    if existing.source in ("sdk_reported", "provider_usage") and existing.usd is not None:
        return existing.model_copy(deep=True)

    input_tokens = existing.input_tokens
    output_tokens = existing.output_tokens

    # Pull token totals from llm_call / spend_event spans when the CostRecord
    # was left partially empty (common for CrewAI / LangGraph).
    if input_tokens is None and output_tokens is None:
        inp_sum = 0
        out_sum = 0
        found = False
        for span in trace.spans:
            if span.type not in ("llm_call", "spend_event"):
                continue
            payload = span.payload or {}
            usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else payload
            if not isinstance(usage, dict):
                continue
            for in_key in ("input_tokens", "prompt_tokens", "input"):
                if usage.get(in_key) is not None:
                    inp_sum += int(usage[in_key])
                    found = True
                    break
            for out_key in ("output_tokens", "completion_tokens", "output"):
                if usage.get(out_key) is not None:
                    out_sum += int(usage[out_key])
                    found = True
                    break
            # Aggregate-only fields
            if usage.get("total_tokens") is not None and not (
                any(usage.get(k) is not None for k in ("input_tokens", "prompt_tokens", "input"))
                or any(
                    usage.get(k) is not None
                    for k in ("output_tokens", "completion_tokens", "output")
                )
            ):
                total = int(usage["total_tokens"])
                inp_sum += int(total * _DEFAULT_INPUT_FRACTION)
                out_sum += total - int(total * _DEFAULT_INPUT_FRACTION)
                found = True
        if found:
            input_tokens = inp_sum
            output_tokens = out_sum

    if input_tokens is None and existing.input_tokens is not None:
        input_tokens = existing.input_tokens
    if output_tokens is None:
        output_tokens = existing.output_tokens

    # LangGraph path: total tokens parked on input_tokens, output None.
    if input_tokens is not None and output_tokens is None and existing.source == "token_estimate":
        total = int(input_tokens)
        input_tokens = int(total * _DEFAULT_INPUT_FRACTION)
        output_tokens = total - input_tokens

    if input_tokens is None and output_tokens is None:
        logger.warning(
            "cost_unknown_no_tokens",
            trace_id=trace.trace_id,
            backend=trace.backend,
        )
        return CostRecord(
            usd=existing.usd,
            input_tokens=existing.input_tokens,
            output_tokens=existing.output_tokens,
            source="unknown",
            per_model=dict(existing.per_model),
        )

    inp = int(input_tokens or 0)
    out = int(output_tokens or 0)
    model_ids = dict(trace.provenance.model_ids or {})

    usd, per_model, missing = _estimate_usd(
        input_tokens=inp,
        output_tokens=out,
        model_ids=model_ids,
        pricing=table,
    )
    if missing:
        logger.warning(
            "cost_unknown_missing_model_pricing",
            trace_id=trace.trace_id,
            missing_models=missing,
            pricing_version=table.version,
        )
        return CostRecord(
            usd=None,
            input_tokens=inp,
            output_tokens=out,
            source="unknown",
            per_model=per_model,
        )

    return CostRecord(
        usd=usd,
        input_tokens=inp,
        output_tokens=out,
        source="token_estimate",
        per_model=per_model,
    )


def historical_median_tokens(
    scenario_id: str,
    *,
    store: TraceStore | None = None,
    backend: str | None = None,
) -> tuple[int | None, int | None]:
    """Return ``(median_input, median_output)`` from the local trace corpus.

    Returns ``(None, None)`` when fewer than one matching row has token data.
    """
    store = store or TraceStore()
    filters: dict[str, Any] = {"scenario_id": scenario_id}
    if backend is not None:
        filters["backend"] = backend
    rows = store.query(**filters)
    inputs: list[int] = []
    outputs: list[int] = []
    for row in rows:
        try:
            trace = store.load(row.trace_id)
        except (OSError, ValueError, FileNotFoundError):
            continue
        if trace.cost.input_tokens is not None:
            inputs.append(int(trace.cost.input_tokens))
        if trace.cost.output_tokens is not None:
            outputs.append(int(trace.cost.output_tokens))
    med_in = int(statistics.median(inputs)) if inputs else None
    med_out = int(statistics.median(outputs)) if outputs else None
    return med_in, med_out


def project_run_cost(
    scenario_id: str,
    *,
    backend: str | None = None,
    pricing: PricingTable | None = None,
    store: TraceStore | None = None,
    model_ids: dict[str, str] | None = None,
) -> float:
    """Project USD cost for one live run of *scenario_id*.

    Uses ``pricing.yaml`` × historical median tokens when available; otherwise
    falls back to the design §5.1 unit estimates.
    """
    table = pricing if pricing is not None else load_pricing()
    med_in, med_out = historical_median_tokens(scenario_id, store=store, backend=backend)
    if med_in is None and med_out is None:
        return float(_DEFAULT_SCENARIO_USD.get(scenario_id, _DEFAULT_FALLBACK_USD))

    inp = int(med_in or 0)
    out = int(med_out or 0)
    ids = model_ids or {}
    if not ids:
        # Use the first pricing entry as a conservative proxy when roles are
        # unknown — projection is advisory (R10.6), not billing.
        if table.models:
            first = next(iter(table.models))
            ids = {"default": first}
        else:
            return float(_DEFAULT_SCENARIO_USD.get(scenario_id, _DEFAULT_FALLBACK_USD))

    usd, _, missing = _estimate_usd(
        input_tokens=inp,
        output_tokens=out,
        model_ids=ids,
        pricing=table,
    )
    if usd is None or missing:
        return float(_DEFAULT_SCENARIO_USD.get(scenario_id, _DEFAULT_FALLBACK_USD))
    return float(usd)


def project_suite_cost(
    *,
    scenario_ids: list[str],
    backends: list[str],
    k: int,
    pricing: PricingTable | None = None,
    store: TraceStore | None = None,
) -> float:
    """Project total spend for ``len(scenarios) × len(backends) × k`` live runs."""
    total = 0.0
    for scenario_id in scenario_ids:
        for backend in backends:
            unit = project_run_cost(scenario_id, backend=backend, pricing=pricing, store=store)
            total += unit * max(1, k)
    return total
