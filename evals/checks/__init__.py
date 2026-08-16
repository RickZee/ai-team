"""Deterministic check package — registry and implementations (R5)."""

from __future__ import annotations

from evals.checks.base import Check, CheckResult, failed, na, passed
from evals.checks.registry import (
    _REGISTRY,
    all_checks,
    check,
    checks_for,
    ensure_checks_loaded,
    get_check,
    validate_registry_against_taxonomy,
)

ensure_checks_loaded()

__all__ = [
    "Check",
    "CheckResult",
    "_REGISTRY",
    "all_checks",
    "check",
    "checks_for",
    "ensure_checks_loaded",
    "failed",
    "get_check",
    "na",
    "passed",
    "validate_registry_against_taxonomy",
]
