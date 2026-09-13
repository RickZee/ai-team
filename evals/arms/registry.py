"""Arm registry by string id. Duplicate registration raises (R1.4)."""

from __future__ import annotations

from collections.abc import Callable

from evals.arms.base import Arm

_REGISTRY: dict[str, Callable[[], Arm]] = {}
_LOADED = False


class DuplicateArmError(ValueError):
    """Raised when two factories claim the same ``arm_id``."""


def register(arm_id: str, factory: Callable[[], Arm]) -> None:
    """Register *factory* under *arm_id*."""
    if arm_id in _REGISTRY:
        raise DuplicateArmError(f"duplicate arm id: {arm_id}")
    _REGISTRY[arm_id] = factory


def get_arm(arm_id: str) -> Arm:
    """Construct the arm for *arm_id*."""
    ensure_arms_loaded()
    if arm_id not in _REGISTRY:
        raise KeyError(f"unknown arm: {arm_id}")
    return _REGISTRY[arm_id]()


def all_arm_ids() -> list[str]:
    """Return registered arm ids."""
    ensure_arms_loaded()
    return sorted(_REGISTRY)


def ensure_arms_loaded() -> None:
    """Import arm modules so registration side-effects run."""
    global _LOADED
    if _LOADED:
        return
    import evals.arms.ai_team  # noqa: F401
    import evals.arms.reference  # noqa: F401
    import evals.arms.solo  # noqa: F401

    _LOADED = True
