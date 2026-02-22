"""
Token usage tracking during pipeline runs.

Tracks actual token usage via CrewAI LLM hooks, compares to pre-run estimates,
emits budget warnings when total cost exceeds AI_TEAM_MAX_COST_PER_RUN,
and saves usage reports to logs/cost_report_{timestamp}.json.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from rich.console import Console
from rich.table import Table

from ai_team.config.cost_estimator import RoleCostRow
from ai_team.config.models import OpenRouterSettings

logger = structlog.get_logger(__name__)

# Rough chars-per-token for estimation when real usage is not available
CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    if not text:
        return 0
    return max(0, len(str(text)) // CHARS_PER_TOKEN)


def _normalize_role(role: str) -> str:
    """Normalize agent role to match ROLE_TOKEN_BUDGETS keys (e.g. 'Backend Developer' -> 'backend_developer')."""
    if not role:
        return "unknown"
    key = role.lower().strip().replace(" ", "_").replace("-", "_")
    if key == "devops_engineer":
        key = "devops"
    return key


@dataclass
class UsageRecord:
    """Single usage record: role and token/cost for one LLM call."""

    role: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class TokenTracker:
    """
    Tracks actual token usage during a pipeline run and compares to pre-run estimate.

    Use record() to log usage (e.g. from CrewAI LLM hooks). summary() prints a Rich
    table comparing estimated vs actual per role. total_cost supports budget checks.
    If total_cost exceeds max_cost_per_run mid-run, a warning is logged (run is not aborted).
    """

    def __init__(self, settings: OpenRouterSettings) -> None:
        self._settings = settings
        self._max_cost = settings.max_cost_per_run
        self._records: List[UsageRecord] = []
        self._lock = threading.Lock()
        self._hook_registered = False

    def record(
        self,
        role: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> None:
        """
        Record one LLM call's usage. Call from CrewAI after_llm_call hook or manually.

        If cumulative total_cost exceeds AI_TEAM_MAX_COST_PER_RUN, logs a warning
        (does not abort the run).
        """
        with self._lock:
            self._records.append(
                UsageRecord(
                    role=role,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                )
            )
            total = self._total_cost_unsafe()
        if total > self._max_cost:
            logger.warning(
                "token_tracker_over_budget",
                total_cost_usd=round(total, 4),
                max_cost_per_run=self._max_cost,
                message="Run cost exceeds AI_TEAM_MAX_COST_PER_RUN; continuing (no abort).",
            )

    @property
    def total_cost(self) -> float:
        """Total cost so far for budget enforcement checks."""
        with self._lock:
            return self._total_cost_unsafe()

    def _total_cost_unsafe(self) -> float:
        """Sum of all record costs; must be called with _lock held."""
        return sum(r.cost_usd for r in self._records)

    def _aggregate_by_role(self) -> Dict[str, Dict[str, Any]]:
        """Aggregate records by role: input_tokens, output_tokens, cost_usd."""
        with self._lock:
            agg: Dict[str, Dict[str, Any]] = {}
            for r in self._records:
                key = _normalize_role(r.role)
                if key not in agg:
                    agg[key] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
                agg[key]["input_tokens"] += r.input_tokens
                agg[key]["output_tokens"] += r.output_tokens
                agg[key]["cost_usd"] += r.cost_usd
        return agg

    def summary(
        self,
        estimated_rows: Optional[List[RoleCostRow]] = None,
        *,
        console: Optional[Console] = None,
    ) -> None:
        """
        Print a Rich table comparing estimated vs actual usage per role.

        If estimated_rows is provided (e.g. from cost_estimator.estimate_run_cost),
        shows estimated and actual side by side; otherwise shows actual only.
        """
        agg = self._aggregate_by_role()
        out_console = console or Console()

        table = Table(
            title="Token usage: estimated vs actual",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Role", style="cyan")
        table.add_column("Est. input", justify="right", style="dim")
        table.add_column("Est. output", justify="right", style="dim")
        table.add_column("Est. cost (USD)", justify="right", style="dim")
        table.add_column("Actual input", justify="right")
        table.add_column("Actual output", justify="right")
        table.add_column("Actual cost (USD)", justify="right", style="green")

        # Build set of all roles (estimated + actual)
        roles_seen: Dict[str, bool] = {}
        if estimated_rows:
            for r in estimated_rows:
                roles_seen[_normalize_role(r.role)] = True
        for key in agg:
            roles_seen[key] = True

        for role_key in sorted(roles_seen.keys()):
            est_inp = est_out = est_cost = ""
            if estimated_rows:
                for r in estimated_rows:
                    if _normalize_role(r.role) == role_key:
                        est_inp = str(r.input_tokens)
                        est_out = str(r.output_tokens)
                        est_cost = f"{r.cost_usd:.4f}"
                        break
            actual = agg.get(role_key, {})
            act_inp = str(actual.get("input_tokens", 0))
            act_out = str(actual.get("output_tokens", 0))
            act_cost = f"{actual.get('cost_usd', 0):.4f}"
            table.add_row(
                role_key,
                est_inp,
                est_out,
                est_cost,
                act_inp,
                act_out,
                act_cost,
            )

        total_actual = self.total_cost
        total_est = ""
        if estimated_rows:
            total_est = f"{sum(r.cost_usd for r in estimated_rows):.4f}"
        table.add_row(
            "[bold]Total[/bold]",
            "",
            "",
            total_est,
            "",
            "",
            f"[bold]{total_actual:.4f}[/bold]",
        )
        out_console.print(table)

    def save_report(self, logs_dir: Optional[Path] = None) -> Path:
        """
        Save usage report to logs/cost_report_{timestamp}.json.

        Creates logs_dir if needed. Returns the path of the written file.
        """
        logs_path = logs_dir or Path("logs")
        logs_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = logs_path / f"cost_report_{timestamp}.json"

        agg = self._aggregate_by_role()
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "total_cost_usd": round(self.total_cost, 6),
            "max_cost_per_run": self._max_cost,
            "by_role": {
                role: {
                    "input_tokens": data["input_tokens"],
                    "output_tokens": data["output_tokens"],
                    "cost_usd": round(data["cost_usd"], 6),
                }
                for role, data in sorted(agg.items())
            },
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("token_tracker_report_saved", path=str(path))
        return path

    def register_crewai_hook(self) -> None:
        """
        Register a CrewAI after_llm_call hook that records usage to this tracker.

        Estimates input tokens from context.messages and output from context.response,
        computes cost via OpenRouterSettings pricing for the agent's role.
        """
        try:
            from crewai.hooks import register_after_llm_call_hook
        except ImportError:
            logger.warning(
                "token_tracker_hook_skip",
                reason="crewai.hooks.register_after_llm_call_hook not available",
            )
            return

        def _after_llm(context: Any) -> None:
            try:
                agent = getattr(context, "agent", None)
                role = getattr(agent, "role", "unknown") if agent else "unknown"
                role_key = _normalize_role(role)
                messages = getattr(context, "messages", []) or []
                response = getattr(context, "response", None) or ""
                inp = sum(
                    _estimate_tokens(
                        m.get("content", "") if isinstance(m, dict) else str(m)
                    )
                    for m in messages
                )
                out = _estimate_tokens(response)
                config = self._settings.get_model_for_role(role_key)
                cost = config.pricing.estimate(inp, out)
                self.record(role_key, inp, out, cost)
            except Exception as e:
                logger.warning("token_tracker_hook_error", error=str(e))

        register_after_llm_call_hook(_after_llm)
        self._hook_registered = True
        logger.debug("token_tracker_hook_registered")

    def unregister_crewai_hook(self) -> None:
        """Unregister the after_llm_call hook if it was registered (best-effort)."""
        if not self._hook_registered:
            return
        try:
            from crewai.hooks import clear_after_llm_call_hooks

            clear_after_llm_call_hooks()
            self._hook_registered = False
            logger.debug("token_tracker_hook_cleared")
        except ImportError:
            pass
