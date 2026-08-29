"""Check registration decorator and lookup helpers (R5.4)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar, Literal

from evals.checks.base import Check, CheckResult, CheckTier
from evals.trace.models import Trace

_REGISTRY: dict[str, Check] = {}
_LOADED = False


class _FunctionCheck:
    """Adapter wrapping a plain function as a :class:`Check`."""

    id: ClassVar[str]
    failure_mode_id: ClassVar[str | None]
    tier: ClassVar[CheckTier]

    def __init__(
        self,
        check_id: str,
        failure_mode_id: str | None,
        tier: CheckTier,
        fn: Callable[[Trace], CheckResult],
    ) -> None:
        self.id = check_id  # type: ignore[misc]
        self.failure_mode_id = failure_mode_id  # type: ignore[misc]
        self.tier = tier  # type: ignore[misc]
        self._fn = fn

    def run(self, trace: Trace) -> CheckResult:
        """Delegate to the registered function."""
        return self._fn(trace)


def check(
    *,
    id: str,
    failure_mode_id: str | None = None,
    tier: Literal["A", "B", "C"] = "A",
) -> Callable[[Callable[[Trace], CheckResult]], Callable[[Trace], CheckResult]]:
    """Register a check function into the global registry.

    Args:
        id: Stable check id (e.g. ``CHK-tool-call-emitted``).
        failure_mode_id: Bound FM id, or None for cross-cutting checks.
        tier: Minimum tier that runs this check.

    Returns:
        Decorator that registers and returns the original function.
    """

    def deco(fn: Callable[[Trace], CheckResult]) -> Callable[[Trace], CheckResult]:
        if id in _REGISTRY:
            raise ValueError(f"duplicate check id: {id}")
        _REGISTRY[id] = _FunctionCheck(id, failure_mode_id, tier, fn)
        return fn

    return deco


def all_checks(tier: str | None = None) -> list[Check]:
    """Return registered checks, optionally filtered to those at or below *tier*.

    Tier ordering: A ⊂ B ⊂ C — requesting ``B`` includes A and B checks.
    """
    ensure_checks_loaded()
    order = {"A": 0, "B": 1, "C": 2}
    checks = list(_REGISTRY.values())
    if tier is None:
        return checks
    if tier not in order:
        raise ValueError(f"unknown tier: {tier}")
    max_rank = order[tier]
    return [c for c in checks if order.get(str(c.tier), 99) <= max_rank]


def checks_for(failure_mode_id: str) -> list[Check]:
    """Return checks bound to *failure_mode_id*."""
    ensure_checks_loaded()
    return [c for c in _REGISTRY.values() if c.failure_mode_id == failure_mode_id]


def get_check(check_id: str) -> Check | None:
    """Look up a single check by id."""
    ensure_checks_loaded()
    return _REGISTRY.get(check_id)


def validate_registry_against_taxonomy(
    *,
    taxonomy: Any | None = None,
) -> list[str]:
    """Cross-check taxonomy ``implemented_by`` against the live registry.

    Args:
        taxonomy: Optional pre-loaded :class:`~evals.taxonomy.loader.Taxonomy`.
            When None, loads the package default.

    Returns:
        List of human-readable mismatch messages (empty when consistent).
    """
    from evals.taxonomy.loader import Taxonomy, load_taxonomy

    ensure_checks_loaded()
    tax: Taxonomy = taxonomy if taxonomy is not None else load_taxonomy()
    errors: list[str] = []

    registered_by_fm: dict[str, set[str]] = {}
    for chk in _REGISTRY.values():
        if chk.failure_mode_id:
            registered_by_fm.setdefault(chk.failure_mode_id, set()).add(chk.id)

    for fm in tax.active():
        if fm.detection != "check":
            continue
        declared = set(fm.implemented_by)
        registered = registered_by_fm.get(fm.id, set())
        missing = declared - registered
        if missing:
            errors.append(f"{fm.id}: declared checks not registered: {sorted(missing)}")
        if not declared and not registered:
            errors.append(f"{fm.id}: detection:check with no implementation")
        extra = registered - declared
        if extra:
            errors.append(
                f"{fm.id}: registered checks missing from taxonomy implemented_by: "
                f"{sorted(extra)}"
            )

    known_ids = {fm.id for fm in tax.failure_modes}
    for chk in _REGISTRY.values():
        if chk.failure_mode_id and chk.failure_mode_id not in known_ids:
            errors.append(f"{chk.id}: failure_mode_id {chk.failure_mode_id} not in taxonomy")

    return errors


def ensure_checks_loaded() -> None:
    """Import check modules so ``@check`` decorators populate the registry."""
    global _LOADED
    if _LOADED:
        return
    import evals.checks.artifacts  # noqa: F401
    import evals.checks.context  # noqa: F401
    import evals.checks.feedback  # noqa: F401
    import evals.checks.guardrails  # noqa: F401
    import evals.checks.isolation  # noqa: F401
    import evals.checks.observability  # noqa: F401
    import evals.checks.provider  # noqa: F401
    import evals.checks.spend  # noqa: F401
    import evals.checks.tools_bus  # noqa: F401
    import evals.checks.trajectory  # noqa: F401
    import evals.checks.verification  # noqa: F401

    _LOADED = True
