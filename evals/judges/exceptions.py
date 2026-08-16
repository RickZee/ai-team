"""Judge-related exceptions for the eval harness."""

from __future__ import annotations


class TierAMissingVerdict(RuntimeError):  # noqa: N818 — name fixed by design §4.7 / R11.4
    """Raised when Tier A needs a cached judge verdict that is not present (R11.4).

    The message names the missing cache key and the ``cache warm`` command so the
    operator can populate the cache from a live run without guessing.
    """

    def __init__(self, cache_key: str, *, judge_id: str | None = None) -> None:
        self.cache_key = cache_key
        self.judge_id = judge_id
        warm = "python -m evals.cli cache warm --tier B"
        judge_bit = f" judge_id={judge_id}" if judge_id else ""
        super().__init__(
            f"Tier A cache miss for key={cache_key}{judge_bit}; " f"populate with: {warm}"
        )
