"""Corpus sampling strategies and sample manifests (R2.3–R2.6).

Strategies are pure functions of ``(rows, n, seed)``. The high-level ``sample``
helper builds a reproducible ``SampleManifest`` (including ``corpus_state_hash``
and stratified ``imbalances``) and optionally writes it under ``evals/samples/``.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from evals.store import TraceIndexRow

StrategyName = Literal["random", "stratified", "extremes", "failed-only", "unlabeled"]

_DEFAULT_SAMPLES_ROOT = Path("evals/samples")

_FAILED_STATUSES = frozenset({"failed", "killed", "budget_abort"})


class StratumKey(BaseModel):
    """Stratification key: backend × scenario_id × status."""

    backend: str = Field(description="Orchestration backend name")
    scenario_id: str = Field(description="Scenario identifier")
    status: str = Field(description="Trace status")

    def as_tuple(self) -> tuple[str, str, str]:
        """Return a hashable key tuple."""
        return (self.backend, self.scenario_id, self.status)

    def label(self) -> str:
        """Stable string form for logging and imbalance records."""
        return f"{self.backend}|{self.scenario_id}|{self.status}"


class ImbalanceRecord(BaseModel):
    """Recorded shortfall when a stratum could not meet its quota (R2.4)."""

    stratum: StratumKey = Field(description="Stratum that fell short of its quota")
    quota: int = Field(description="Requested sample count for the stratum")
    available: int = Field(description="Traces present in the stratum")
    shortfall: int = Field(description="quota - taken from the stratum itself")
    donor: StratumKey = Field(description="Largest stratum used to fill the shortfall")
    filled: int = Field(description="Additional traces taken from the donor")


class SampleManifest(BaseModel):
    """Reproducible sample written to ``evals/samples/<sample_id>.json``."""

    sample_id: str = Field(description="Deterministic sample identifier")
    strategy: StrategyName = Field(description="Sampling strategy name")
    seed: int = Field(description="RNG seed used for selection")
    n: int = Field(description="Requested sample size")
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Equality filters applied before sampling",
    )
    corpus_state_hash: str = Field(
        description="sha256 of sorted newline-joined trace_ids in the input rows",
    )
    selection: list[str] = Field(description="Ordered list of selected trace_ids")
    imbalances: list[ImbalanceRecord] = Field(
        default_factory=list,
        description="Stratified shortfall fills; empty for other strategies",
    )


def corpus_state_hash(rows: list[TraceIndexRow]) -> str:
    """Return sha256 hex of sorted trace_ids (one per line)."""
    joined = "\n".join(sorted(r.trace_id for r in rows))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _make_sample_id(strategy: str, seed: int, state_hash: str) -> str:
    return f"{strategy}-{seed}-{state_hash[:12]}"


def _rng_sample(ids: list[str], k: int, rng: random.Random) -> list[str]:
    """Sample *k* ids without replacement, preserving determinism via *rng*."""
    if k <= 0 or not ids:
        return []
    if k >= len(ids):
        # Stable order: shuffle a copy then take all, so callers see seeded order.
        shuffled = list(ids)
        rng.shuffle(shuffled)
        return shuffled
    return rng.sample(ids, k)


def sample_random(rows: list[TraceIndexRow], n: int, seed: int) -> list[str]:
    """Uniform random sample of up to *n* trace_ids."""
    rng = random.Random(seed)
    ids = [r.trace_id for r in rows]
    return _rng_sample(ids, n, rng)


def _stratum_key(row: TraceIndexRow) -> StratumKey:
    return StratumKey(backend=row.backend, scenario_id=row.scenario_id, status=row.status)


def sample_stratified(
    rows: list[TraceIndexRow], n: int, seed: int
) -> tuple[list[str], list[ImbalanceRecord]]:
    """Equal-quota stratified sample by backend × scenario_id × status.

    When a stratum has fewer traces than its quota, the shortfall is filled from
    the largest stratum (by size, then key) that still has unselected traces.
    Imbalances are recorded for every shortfall (R2.4).
    """
    if n <= 0 or not rows:
        return [], []

    groups: dict[tuple[str, str, str], list[str]] = {}
    for row in rows:
        key = _stratum_key(row).as_tuple()
        groups.setdefault(key, []).append(row.trace_id)

    # Deterministic stratum order and within-stratum id order before shuffle.
    sorted_keys = sorted(groups.keys())
    for key in sorted_keys:
        groups[key] = sorted(groups[key])

    k = len(sorted_keys)
    base, rem = divmod(n, k)
    quotas: dict[tuple[str, str, str], int] = {}
    for i, key in enumerate(sorted_keys):
        quotas[key] = base + (1 if i < rem else 0)

    rng = random.Random(seed)
    selected: set[str] = set()
    selection: list[str] = []
    imbalances: list[ImbalanceRecord] = []
    shortfalls: list[tuple[tuple[str, str, str], int, int, int]] = []

    for key in sorted_keys:
        pool = groups[key]
        quota = quotas[key]
        taken_ids = _rng_sample(pool, min(quota, len(pool)), rng)
        for tid in taken_ids:
            selected.add(tid)
            selection.append(tid)
        if len(taken_ids) < quota:
            shortfalls.append((key, quota, len(pool), quota - len(taken_ids)))

    # Fill shortfalls from largest strata (cascading if needed).
    for key, quota, available, shortfall in shortfalls:
        remaining_need = shortfall
        # Donor candidates: largest first, then stable key order; skip empty remainder.
        donors = sorted(
            sorted_keys,
            key=lambda sk: (-len(groups[sk]), sk),
        )
        filled_total = 0
        primary_donor: tuple[str, str, str] | None = None
        for donor_key in donors:
            if remaining_need <= 0:
                break
            remaining = [tid for tid in groups[donor_key] if tid not in selected]
            if not remaining:
                continue
            if primary_donor is None:
                primary_donor = donor_key
            take = _rng_sample(remaining, min(remaining_need, len(remaining)), rng)
            for tid in take:
                selected.add(tid)
                selection.append(tid)
            filled_total += len(take)
            remaining_need -= len(take)

        donor_key = primary_donor if primary_donor is not None else key
        imbalances.append(
            ImbalanceRecord(
                stratum=StratumKey(backend=key[0], scenario_id=key[1], status=key[2]),
                quota=quota,
                available=available,
                shortfall=shortfall,
                donor=StratumKey(
                    backend=donor_key[0],
                    scenario_id=donor_key[1],
                    status=donor_key[2],
                ),
                filled=filled_total,
            )
        )

    return selection[:n], imbalances


def _metric_value(row: TraceIndexRow, attr: str) -> float:
    raw = getattr(row, attr)
    if raw is None:
        return float("-inf")
    return float(raw)


def sample_extremes(rows: list[TraceIndexRow], n: int, seed: int) -> list[str]:
    """Top ⌈n/3⌉ by duration_s, cost_usd, and retry_count, deduplicated.

    *seed* is accepted for signature uniformity; selection is fully determined by
    metric order with ``trace_id`` as a tie-breaker (design §4.2).
    """
    del seed  # unused — extremes are deterministic without RNG
    if n <= 0 or not rows:
        return []

    per_metric = math.ceil(n / 3)
    selection: list[str] = []
    seen: set[str] = set()

    for attr in ("duration_s", "cost_usd", "retry_count"):
        ranked = sorted(
            rows,
            key=lambda r: (_metric_value(r, attr), r.trace_id),
            reverse=True,
        )
        for row in ranked[:per_metric]:
            if row.trace_id not in seen:
                seen.add(row.trace_id)
                selection.append(row.trace_id)

    return selection


def sample_failed_only(rows: list[TraceIndexRow], n: int, seed: int) -> list[str]:
    """Random sample restricted to failed / killed / budget_abort traces."""
    failed = [r for r in rows if r.status in _FAILED_STATUSES]
    return sample_random(failed, n, seed)


def sample_unlabeled(rows: list[TraceIndexRow], n: int, seed: int) -> list[str]:
    """Random sample restricted to traces with ``label_count == 0``."""
    unlabeled = [r for r in rows if r.label_count == 0]
    return sample_random(unlabeled, n, seed)


_STRATEGY_FNS: dict[StrategyName, Callable[[list[TraceIndexRow], int, int], list[str]]] = {
    "random": sample_random,
    "extremes": sample_extremes,
    "failed-only": sample_failed_only,
    "unlabeled": sample_unlabeled,
}


def sample(
    rows: list[TraceIndexRow],
    strategy: StrategyName,
    n: int,
    seed: int,
    *,
    filters: dict[str, Any] | None = None,
) -> SampleManifest:
    """Build a reproducible ``SampleManifest`` for *strategy*.

    Args:
        rows: Index rows to sample from (already filter-applied by the caller).
        strategy: One of the supported strategy names.
        n: Requested sample size.
        seed: RNG seed (also recorded in the manifest).
        filters: Optional filters dict recorded in the manifest (not re-applied).

    Returns:
        A ``SampleManifest`` with deterministic ``sample_id`` and
        ``corpus_state_hash``.
    """
    filt = dict(filters) if filters else {}
    state_hash = corpus_state_hash(rows)
    imbalances: list[ImbalanceRecord] = []

    if strategy == "stratified":
        selection, imbalances = sample_stratified(rows, n, seed)
    elif strategy in _STRATEGY_FNS:
        selection = _STRATEGY_FNS[strategy](rows, n, seed)
    else:
        raise ValueError(f"unknown sampling strategy: {strategy!r}")

    return SampleManifest(
        sample_id=_make_sample_id(strategy, seed, state_hash),
        strategy=strategy,
        seed=seed,
        n=n,
        filters=filt,
        corpus_state_hash=state_hash,
        selection=selection,
        imbalances=imbalances,
    )


def write_manifest(
    manifest: SampleManifest,
    *,
    samples_root: Path | None = None,
) -> Path:
    """Write *manifest* to ``<samples_root>/<sample_id>.json`` (stable JSON)."""
    root = Path(samples_root) if samples_root is not None else _DEFAULT_SAMPLES_ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{manifest.sample_id}.json"
    # sort_keys + compact separators → byte-identical across runs
    payload = manifest.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
