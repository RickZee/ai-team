"""Shared paths for repository invariant tests."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def read_ratchets() -> dict[str, int]:
    """Load ``ratchets.toml`` (stdlib tomllib)."""
    import tomllib

    path = Path(__file__).with_name("ratchets.toml")
    if not path.is_file():
        raise AssertionError(f"missing ratchets file: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if not data:
        raise AssertionError(f"{path} is empty")
    return {k: int(v) for k, v in data.items() if isinstance(v, int)}
