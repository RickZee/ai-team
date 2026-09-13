"""Deprecated import-path helpers. Removal: 2026-12-31 (v0.3.0)."""

from __future__ import annotations

import warnings

REMOVAL = "2026-12-31 (v0.3.0)"


def warn_moved(old: str, new: str) -> None:
    """Emit a DeprecationWarning pointing at the caller of a shim module."""
    warnings.warn(
        f"{old} is deprecated; import from {new} instead. Removal: {REMOVAL}.",
        DeprecationWarning,
        stacklevel=3,
    )
