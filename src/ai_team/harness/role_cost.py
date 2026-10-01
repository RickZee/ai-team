"""Per-role token split for one run record, or for a batch of them.

The spend guard stores a single run total. Role totals come from the token
counts on each model message in ``state.json``. Dollars per role are that
role's share of the run total, by tokens, and are labeled as a share.

A batch report only counts runs whose messages account for most of the cost
log's own token total (``min_coverage``). A run whose messages cover less than
that would understate whichever role's messages went unrecorded.
"""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_USAGE_RE = re.compile(
    r"token_usage': \{'completion_tokens': (\d+), 'prompt_tokens': (\d+),"
    r".*?name='([^']+)'",
    re.DOTALL,
)


@dataclass(frozen=True)
class RoleTokens:
    """Tokens attributed to one role."""

    role: str
    input_tokens: int
    output_tokens: int
    messages: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class RoleReport:
    """Role split plus the run-level dollar total, when the cost log has one."""

    roles: tuple[RoleTokens, ...]
    spent_usd: float | None

    @property
    def token_total(self) -> int:
        return sum(role.total_tokens for role in self.roles)


def _from_mapping(message: dict[str, Any]) -> tuple[str, int, int] | None:
    name = message.get("name")
    if not isinstance(name, str) or not name:
        return None
    usage = message.get("usage_metadata")
    if not isinstance(usage, dict):
        meta = message.get("response_metadata")
        usage = meta.get("token_usage") if isinstance(meta, dict) else None
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
    completion = usage.get("completion_tokens", usage.get("output_tokens"))
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    return name, prompt, completion


def _walk(node: Any, found: list[tuple[str, int, int]]) -> None:
    if isinstance(node, dict):
        parsed = _from_mapping(node)
        if parsed is not None:
            found.append(parsed)
        for value in node.values():
            _walk(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk(value, found)
    elif isinstance(node, str):
        for completion, prompt, name in _USAGE_RE.findall(node):
            found.append((name, int(prompt), int(completion)))


def _run_total_row(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "logs" / "costs.jsonl"
    if not path.is_file():
        return None
    total: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "run_total":
            total = row
    return total


def _spent_usd(run_dir: Path) -> float | None:
    row = _run_total_row(run_dir)
    if row is None or not isinstance(row.get("spent_usd"), int | float):
        return None
    return float(row["spent_usd"])


def _logged_tokens(run_dir: Path) -> int | None:
    row = _run_total_row(run_dir)
    if row is None or not isinstance(row.get("total_tokens"), int):
        return None
    return int(row["total_tokens"])


def report_run(run_dir: Path) -> RoleReport:
    """Sum tokens by role for one ``output/runs/<id>`` directory.

    Args:
        run_dir: Run directory containing ``state.json``.

    Returns:
        Roles sorted by total tokens, descending.
    """
    state_path = run_dir / "state.json"
    found: list[tuple[str, int, int]] = []
    if state_path.is_file():
        _walk(json.loads(state_path.read_text(encoding="utf-8")), found)
    totals: dict[str, list[int]] = {}
    for name, prompt, completion in found:
        bucket = totals.setdefault(name, [0, 0, 0])
        bucket[0] += prompt
        bucket[1] += completion
        bucket[2] += 1
    roles = tuple(
        RoleTokens(role=name, input_tokens=prompt, output_tokens=completion, messages=count)
        for name, (prompt, completion, count) in sorted(
            totals.items(),
            key=lambda item: item[1][0] + item[1][1],
            reverse=True,
        )
    )
    return RoleReport(roles=roles, spent_usd=_spent_usd(run_dir))


def format_report(report: RoleReport) -> str:
    """Plain-text table. Dollar figures are a token share of the run total."""
    lines = [
        f"{'role':<22} {'in':>12} {'out':>10} {'share':>8} {'usd_share':>10}",
    ]
    total = report.token_total or 1
    for role in report.roles:
        share = role.total_tokens / total
        usd = ""
        if report.spent_usd is not None:
            usd = f"{report.spent_usd * share:.4f}"
        lines.append(
            f"{role.role:<22} {role.input_tokens:12d} {role.output_tokens:10d} "
            f"{share:8.1%} {usd:>10}"
        )
    spent = "n/a" if report.spent_usd is None else f"${report.spent_usd:.4f}"
    lines.append(f"run total tokens {report.token_total}  spent {spent}")
    lines.append("usd_share is this role's fraction of the run total, by tokens.")
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class BatchRole:
    """One role summed over the runs a batch report kept."""

    role: str
    input_tokens: int
    output_tokens: int
    runs: int
    median_run_share: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class BatchReport:
    """Role split over many runs, and why each excluded run was left out."""

    roles: tuple[BatchRole, ...]
    included: tuple[str, ...]
    skipped: dict[str, str]
    min_coverage: float

    @property
    def token_total(self) -> int:
        return sum(role.total_tokens for role in self.roles)


def report_runs(run_dirs: Iterable[Path], min_coverage: float = 0.9) -> BatchReport:
    """Sum tokens by role over several run directories.

    A run is kept only when its message tokens reach ``min_coverage`` of the
    ``run_total.total_tokens`` in its cost log. Every other run is listed in
    ``skipped`` with the reason, so the excluded share is visible.

    Args:
        run_dirs: ``output/runs/<id>`` directories.
        min_coverage: Fraction of the logged token total the messages must
            account for, between 0 and 1.

    Returns:
        Roles sorted by total tokens, descending.
    """
    sums: dict[str, list[int]] = {}
    shares: dict[str, list[float]] = {}
    included: list[str] = []
    skipped: dict[str, str] = {}
    for run_dir in run_dirs:
        name = run_dir.name
        if not (run_dir / "state.json").is_file():
            skipped[name] = "no state.json"
            continue
        logged = _logged_tokens(run_dir)
        if not logged:
            skipped[name] = "no run_total in logs/costs.jsonl"
            continue
        report = report_run(run_dir)
        coverage = report.token_total / logged
        if coverage < min_coverage:
            skipped[name] = f"messages cover {coverage:.0%} of logged tokens"
            continue
        included.append(name)
        run_total = report.token_total or 1
        for role in report.roles:
            bucket = sums.setdefault(role.role, [0, 0, 0])
            bucket[0] += role.input_tokens
            bucket[1] += role.output_tokens
            bucket[2] += 1
            shares.setdefault(role.role, []).append(role.total_tokens / run_total)
    roles = tuple(
        BatchRole(
            role=name,
            input_tokens=prompt,
            output_tokens=completion,
            runs=count,
            median_run_share=statistics.median(shares[name]),
        )
        for name, (prompt, completion, count) in sorted(
            sums.items(),
            key=lambda item: item[1][0] + item[1][1],
            reverse=True,
        )
    )
    return BatchReport(
        roles=roles,
        included=tuple(included),
        skipped=skipped,
        min_coverage=min_coverage,
    )


def format_batch_report(report: BatchReport) -> str:
    """Plain-text table for a batch. Shares are by tokens over the kept runs."""
    given = len(report.included) + len(report.skipped)
    lines = [
        f"runs given {given}, kept {len(report.included)} "
        f"(messages cover >= {report.min_coverage:.0%} of the cost log's tokens)",
        f"{'role':<22} {'in':>12} {'out':>10} {'share':>8} {'in:out':>8} "
        f"{'runs':>5} {'median_run_share':>17}",
    ]
    total = report.token_total or 1
    for role in report.roles:
        ratio = role.input_tokens / role.output_tokens if role.output_tokens else float("inf")
        lines.append(
            f"{role.role:<22} {role.input_tokens:12d} {role.output_tokens:10d} "
            f"{role.total_tokens / total:8.1%} {ratio:8.1f} {role.runs:5d} "
            f"{role.median_run_share:17.1%}"
        )
    reasons: dict[str, int] = {}
    for reason in report.skipped.values():
        key = "messages cover too little" if reason.startswith("messages cover") else reason
        reasons[key] = reasons.get(key, 0) + 1
    for reason, count in sorted(reasons.items()):
        lines.append(f"skipped {count}: {reason}")
    lines.append("share is this role's fraction of the kept runs' tokens.")
    return "\n".join(lines) + "\n"
