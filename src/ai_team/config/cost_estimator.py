"""
Pipeline cost estimation before execution.

Estimates cost per role from token budgets and pricing, applies complexity
multipliers and a retry buffer, and optionally requires confirmation for
TEST/PROD before any LLM calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Literal, Tuple

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ai_team.config.models import (
    ROLE_TOKEN_BUDGETS,
    Environment,
    OpenRouterSettings,
)

logger = structlog.get_logger()

# Complexity multipliers: simple (0.5x), medium (1.0x), complex (2.0x)
COMPLEXITY_MULTIPLIERS: dict[str, float] = {
    "simple": 0.5,
    "medium": 1.0,
    "complex": 2.0,
}
# 20% retry buffer for guardrail failures
RETRY_BUFFER = 0.20

ComplexityType = Literal["simple", "medium", "complex"]

# Keywords that suggest complex projects (from PROMPTS.md)
COMPLEX_KEYWORDS = re.compile(
    r"\b(microservices?|ML|machine\s+learning|distributed|Kubernetes|k8s|multi-tenant)\b",
    re.IGNORECASE,
)


@dataclass
class RoleCostRow:
    """Cost estimate for a single agent role."""

    role: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


def get_complexity_from_description(description: str) -> ComplexityType:
    """
    Infer complexity from project description length and keywords.

    - complex: mentions microservices, ML, distributed, etc. (checked first)
    - simple: < 100 words
    - medium: otherwise
    """
    if not description or not description.strip():
        return "medium"
    text = description.strip()
    if COMPLEX_KEYWORDS.search(text):
        return "complex"
    word_count = len(text.split())
    if word_count < 100:
        return "simple"
    return "medium"


def estimate_run_cost(
    settings: OpenRouterSettings,
    complexity: ComplexityType,
) -> tuple[List[RoleCostRow], float, bool]:
    """
    Calculate estimated cost per role using token budgets × pricing.

    Applies complexity multiplier to token counts and a 20% retry buffer
    to the total. Checks total against AI_TEAM_MAX_COST_PER_RUN.

    Returns:
        (rows per role, total_cost_usd_with_buffer, within_budget)
    """
    mult = COMPLEXITY_MULTIPLIERS.get(complexity, 1.0)
    rows: List[RoleCostRow] = []
    total_raw = 0.0

    for role, budget in ROLE_TOKEN_BUDGETS.items():
        inp = int(budget["input"] * mult)
        out = int(budget["output"] * mult)
        config = settings.get_model_for_role(role)
        cost = config.pricing.estimate(inp, out)
        total_raw += cost
        rows.append(
            RoleCostRow(
                role=role,
                model_id=config.model_id,
                input_tokens=inp,
                output_tokens=out,
                cost_usd=round(cost, 4),
            )
        )

    total_with_buffer = total_raw * (1.0 + RETRY_BUFFER)
    max_cost = settings.max_cost_per_run
    within_budget = total_with_buffer <= max_cost

    logger.info(
        "cost_estimate_computed",
        complexity=complexity,
        total_raw_usd=round(total_raw, 4),
        total_with_buffer_usd=round(total_with_buffer, 4),
        max_cost_per_run=max_cost,
        within_budget=within_budget,
    )
    return (rows, round(total_with_buffer, 4), within_budget)


def display_estimate(
    settings: OpenRouterSettings,
    complexity: ComplexityType,
    rows: List[RoleCostRow],
    total_with_buffer: float,
    within_budget: bool,
) -> None:
    """
    Render Rich table (per-role model, tokens, cost) and panel (env, complexity, budget).
    """
    console = Console()

    table = Table(
        title="Pipeline cost estimate (token budgets × pricing, with retry buffer)",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Role", style="cyan")
    table.add_column("Model", style="dim")
    table.add_column("Input tokens", justify="right")
    table.add_column("Output tokens", justify="right")
    table.add_column("Cost (USD)", justify="right", style="green")

    for r in rows:
        table.add_row(
            r.role,
            r.model_id.split("/")[-1] if "/" in r.model_id else r.model_id,
            str(r.input_tokens),
            str(r.output_tokens),
            f"{r.cost_usd:.4f}",
        )

    budget_status = "OK" if within_budget else "OVER BUDGET"
    panel_content = (
        f"Environment: [bold]{settings.ai_team_env.value}[/bold]\n"
        f"Complexity: [bold]{complexity}[/bold] "
        f"(×{COMPLEXITY_MULTIPLIERS[complexity]})\n"
        f"Total (incl. {int(RETRY_BUFFER * 100)}% retry buffer): "
        f"[bold]${total_with_buffer:.4f}[/bold]\n"
        f"Budget limit: ${settings.max_cost_per_run:.2f} — [bold]{budget_status}[/bold]"
    )
    panel = Panel(panel_content, title="Run summary", border_style="blue")

    console.print(table)
    console.print(panel)


def confirm_and_proceed(
    settings: OpenRouterSettings,
    complexity: ComplexityType,
    total_cost: float,
) -> bool:
    """
    Confirm before running pipeline. Auto-confirm for DEV; require input for TEST/PROD.

    Returns True to proceed, False to cancel.
    """
    env = settings.ai_team_env
    if env == Environment.DEV:
        logger.info("cost_confirm_auto", env=env.value, reason="DEV auto-confirm")
        return True
    if env in (Environment.TEST, Environment.PROD) and settings.prod_confirm:
        console = Console()
        console.print(
            f"\n[yellow]Environment is [bold]{env.value}[/bold]. "
            f"Estimated cost: ${total_cost:.4f}. Proceed? (y/N)[/yellow]"
        )
        try:
            reply = input("> ").strip().lower() or "n"
        except (EOFError, KeyboardInterrupt):
            reply = "n"
        ok = reply in ("y", "yes")
        logger.info("cost_confirm_user", env=env.value, reply=reply, proceed=ok)
        return ok
    return True


def run_estimate_and_confirm(
    settings: OpenRouterSettings,
    complexity: ComplexityType,
    *,
    show: bool = True,
) -> bool:
    """
    Run full estimate, optionally display Rich table/panel, check budget, and confirm.

    Call this at the start of the pipeline (e.g. in intake_request) before any LLM calls.
    Returns True to proceed, False to cancel (caller should abort or route to human feedback).
    """
    rows, total_with_buffer, within_budget = estimate_run_cost(settings, complexity)
    if show:
        display_estimate(settings, complexity, rows, total_with_buffer, within_budget)
    if not within_budget:
        logger.warning(
            "cost_over_budget",
            total=total_with_buffer,
            max_cost=settings.max_cost_per_run,
        )
    return confirm_and_proceed(settings, complexity, total_with_buffer)


def display_compare_costs(
    env_results: List[Tuple[Environment, List[RoleCostRow], float]],
    complexity: ComplexityType,
) -> None:
    """
    Render a side-by-side table of per-role costs and totals for all environments.

    env_results: list of (Environment, rows from estimate_run_cost, total_with_buffer).
    """
    if not env_results:
        return
    console = Console()
    # Columns: Role | dev (USD) | test (USD) | prod (USD)
    table = Table(
        title=f"Cost comparison by environment (complexity: {complexity}, with retry buffer)",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Role", style="cyan")
    for env, _, _ in env_results:
        table.add_column(f"{env.value.capitalize()} (USD)", justify="right", style="dim")

    # Build role -> cost per env from first env's row order (all have same roles)
    role_order = [r.role for r in env_results[0][1]]
    env_costs: List[Tuple[Environment, dict[str, float], float]] = []
    for env, rows, total in env_results:
        by_role = {r.role: r.cost_usd for r in rows}
        env_costs.append((env, by_role, total))

    for role in role_order:
        cells = [role]
        for _env, by_role, _total in env_costs:
            cells.append(f"{by_role.get(role, 0):.4f}")
        table.add_row(*cells)

    # Totals row
    totals_row = ["Total (incl. buffer)"]
    for _env, _by_role, total in env_costs:
        totals_row.append(f"${total:.4f}")
    table.add_row(*totals_row, style="bold")
    console.print(table)
