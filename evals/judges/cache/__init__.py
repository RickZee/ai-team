"""Judge verdict cache package root (on-disk JSON under ``<key[:2]>/<key>.json``)."""

from __future__ import annotations


def warm_cache(*, tier: str = "B") -> int:
    """Populate the judge cache from a live tier (R11.7).

    Live warming spends money and is intentionally a no-op stub here until a
    budgeted Tier B/C run is wired. Returns 0.
    """
    _ = tier
    print(
        f"cache warm --tier {tier}: no-op (live warming requires a budgeted run; "
        "Phase 7 stores advisory alignment only)"
    )
    return 0
