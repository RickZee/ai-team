"""Collect reproducibility provenance for traces, verdicts, and reports (R14)."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, Field

_EVALS_ROOT = Path(__file__).resolve().parent
_DEFAULT_TAXONOMY_VERSION = "1.0.0"
_DEFAULT_PRICING_VERSION = "unset"


class Provenance(BaseModel):
    """Environment and version stamps required by R14.1."""

    git_sha: str
    git_dirty: bool
    python_version: str
    platform: str
    harness_version: str
    taxonomy_version: str
    pricing_table_version: str
    seed: int | None = None
    tier: str | None = None
    scenario_content_sha256: str = ""
    model_ids: dict[str, str] = Field(default_factory=dict)


def _read_version_file(path: Path, default: str) -> str:
    """Return stripped file contents or *default* when missing/empty."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return default
    return text or default


def _git_sha(cwd: Path) -> tuple[str, bool]:
    """Return ``(sha, dirty)``; degrade gracefully when git is unavailable."""
    try:
        sha_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        dirty_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown", True

    if sha_proc.returncode != 0:
        return "unknown", True

    sha = sha_proc.stdout.strip() or "unknown"
    dirty = dirty_proc.returncode != 0 or bool(dirty_proc.stdout.strip())
    return sha, dirty


def collect(
    *,
    cwd: Path | None = None,
    taxonomy_version: str | None = None,
    pricing_table_version: str | None = None,
    seed: int | None = None,
    tier: str | None = None,
    scenario_content_sha256: str = "",
    model_ids: dict[str, str] | None = None,
) -> Provenance:
    """Capture git, runtime, and harness version stamps.

    Args:
        cwd: Directory used for git queries (defaults to process CWD).
        taxonomy_version: Override; otherwise read taxonomy YAML version or default.
        pricing_table_version: Override; otherwise read ``evals/pricing.yaml`` version.
        seed: Optional RNG seed for the suite run.
        tier: Optional eval tier (``A`` / ``B`` / ``C``).
        scenario_content_sha256: Hash of the scenario JSON bytes.
        model_ids: Role → model id mapping actually used.

    Returns:
        A fully populated :class:`Provenance` instance.
    """
    root = cwd if cwd is not None else Path.cwd()
    git_sha, git_dirty = _git_sha(root)

    harness_version = _read_version_file(_EVALS_ROOT / "VERSION", "0.0.0")

    if taxonomy_version is None:
        taxonomy_version = _DEFAULT_TAXONOMY_VERSION
        tax_path = _EVALS_ROOT / "taxonomy" / "failure_modes.yaml"
        if tax_path.exists():
            # Lightweight parse — avoid importing the loader (circular risk early on).
            for line in tax_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("version:"):
                    taxonomy_version = stripped.split(":", 1)[1].strip().strip("\"'")
                    break

    if pricing_table_version is None:
        pricing_table_version = _DEFAULT_PRICING_VERSION
        pricing_path = _EVALS_ROOT / "pricing.yaml"
        if pricing_path.exists():
            for line in pricing_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("version:"):
                    pricing_table_version = stripped.split(":", 1)[1].strip().strip("\"'")
                    break

    return Provenance(
        git_sha=git_sha,
        git_dirty=git_dirty,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        harness_version=harness_version,
        taxonomy_version=taxonomy_version,
        pricing_table_version=pricing_table_version,
        seed=seed,
        tier=tier,
        scenario_content_sha256=scenario_content_sha256,
        model_ids=model_ids or {},
    )
