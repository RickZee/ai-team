"""Per-role token split for one run record.

The spend guard stores a single run total. Role totals come from the token
counts on each model message in ``state.json``. Dollars per role are that
role's share of the run total, by tokens, and are labeled as a share.
"""

from __future__ import annotations

import json
import re
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


def _spent_usd(run_dir: Path) -> float | None:
    path = run_dir / "logs" / "costs.jsonl"
    if not path.is_file():
        return None
    spent: float | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") == "run_total" and isinstance(row.get("spent_usd"), int | float):
            spent = float(row["spent_usd"])
    return spent


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
