"""
CLI entry point for ai-team.

Subcommands: run (default), estimate, compare-costs.
Run the full flow with optional --env and --complexity; estimate and compare-costs
show cost tables without executing the pipeline.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Literal, cast

import structlog
from ai_team.cli_run import RunOptions, execute_run
from dotenv import load_dotenv

logger = structlog.get_logger(__name__)

_ENV_CHOICES = ("dev", "test", "prod")
_COMPLEXITY_CHOICES = ("simple", "medium", "complex")
_SUBCOMMANDS = frozenset({"run", "estimate", "compare-costs"})
_Complexity = Literal["simple", "medium", "complex"]


def _preprocess_argv_for_subcommand(argv: list[str]) -> list[str]:
    """Ensure a subcommand is present so parsing is unambiguous.

    The top-level parser used to define an optional *description* positional before
    subparsers, which caused ``ai-team run "desc"`` to bind ``run`` as the
    description and treat the real description as the subcommand. We removed that
    positional; instead, if the user omits the subcommand (e.g.
    ``ai-team "Build a todo app"``), we insert ``run`` before the first argument
    when that token is not a flag and not already a known subcommand.
    """
    if not argv:
        return argv
    first = argv[0]
    if first.startswith("-") or first in _SUBCOMMANDS:
        return argv
    return ["run", *argv]


def _cmd_estimate(env: str, complexity: str) -> int:
    """Show cost estimate for the given environment and complexity."""
    from ai_team.config.cost_estimator import (
        display_estimate,
        estimate_run_cost,
    )
    from ai_team.config.models import OpenRouterSettings
    from pydantic import ValidationError

    os.environ["AI_TEAM_ENV"] = env
    try:
        settings = OpenRouterSettings()
    except ValidationError as e:
        logger.warning("openrouter_not_configured", error=str(e))
        print(
            "Error: OpenRouter not configured. Set OPENROUTER_API_KEY and related env vars.",
            file=sys.stderr,
        )
        return 1
    comp = cast(_Complexity, complexity)
    rows, total_with_buffer, within_budget = estimate_run_cost(settings, comp)
    display_estimate(settings, comp, rows, total_with_buffer, within_budget)
    return 0


def _cmd_compare_costs(complexity: str) -> int:
    """Show side-by-side cost comparison for dev, test, and prod."""
    from ai_team.config.cost_estimator import (
        display_compare_costs,
        estimate_run_cost,
    )
    from ai_team.config.models import Environment, OpenRouterSettings
    from pydantic import ValidationError

    env_results = []
    try:
        for env in (Environment.DEV, Environment.TEST, Environment.PROD):
            os.environ["AI_TEAM_ENV"] = str(env.value)
            settings = OpenRouterSettings()
            comp = cast(_Complexity, complexity)
            rows, total_with_buffer, _ = estimate_run_cost(settings, comp)
            env_results.append((env, rows, total_with_buffer))
    except ValidationError as e:
        logger.warning("openrouter_not_configured", error=str(e))
        print(
            "Error: OpenRouter not configured. Set OPENROUTER_API_KEY and related env vars.",
            file=sys.stderr,
        )
        return 1
    display_compare_costs(env_results, cast(_Complexity, complexity))
    return 0


_OUTPUT_CHOICES = ("tui", "crewai")


def _cmd_run(opts: RunOptions) -> int:
    """Run the selected backend from typed options (R12.4)."""
    return execute_run(opts)


def main() -> int:
    """Parse CLI args and dispatch to subcommands. Returns 0 on success, 1 on failure."""
    # LangGraph reads AI_TEAM_LANGGRAPH_GRAPH_MODE via os.environ; load_dotenv makes .env effective.
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="AI team: transform a project description into code (run, estimate, or compare-costs).",
    )
    parser.add_argument(
        "--backend",
        choices=("crewai", "langgraph", "claude-agent-sdk", "claude-sdk"),
        default="crewai",
        help=(
            "Orchestration backend: crewai (default), langgraph, or claude-agent-sdk "
            "(Anthropic Claude Agent SDK)."
        ),
    )
    parser.add_argument(
        "--team",
        default="full",
        help="Team profile from config/team_profiles.yaml (default: full).",
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    # run
    run_p = subparsers.add_parser("run", help="Run the full AI team flow.")
    run_p.add_argument(
        "--backend",
        choices=("crewai", "langgraph", "claude-agent-sdk", "claude-sdk"),
        default="crewai",
        help=(
            "Orchestration backend: crewai (default), langgraph, or claude-agent-sdk "
            "(requires ANTHROPIC_API_KEY and Claude Code CLI)."
        ),
    )
    run_p.add_argument(
        "--team",
        default="full",
        help="Team profile from config/team_profiles.yaml (default: full).",
    )
    run_p.add_argument(
        "run_description",
        nargs="?",
        default="",
        help="Project description (e.g. 'Create a REST API for a todo list').",
    )
    run_p.add_argument(
        "--env",
        choices=_ENV_CHOICES,
        default=None,
        help="Override environment (dev | test | prod). Default: use AI_TEAM_ENV.",
    )
    run_p.add_argument(
        "--complexity",
        choices=_COMPLEXITY_CHOICES,
        default=None,
        help="Override complexity (simple | medium | complex). Default: infer from description.",
    )
    run_p.add_argument(
        "--output",
        choices=_OUTPUT_CHOICES,
        default="crewai",
        help="Progress output: 'tui' = Rich TUI dashboard, 'crewai' = CrewAI default verbose (default: crewai).",
    )
    run_p.add_argument(
        "--monitor",
        action="store_true",
        help="Use Rich TUI for progress (shortcut for --output tui).",
    )
    run_p.add_argument(
        "--skip-estimate",
        action="store_true",
        help="Bypass cost estimation and confirmation (for CI/CD).",
    )
    run_p.add_argument(
        "--project-name",
        default="AI-Team Project",
        help="Project name shown in the monitor.",
    )
    run_p.add_argument(
        "--run-name",
        default="",
        help="Optional slug for workspace/output directory (overrides description-based slug).",
    )
    run_p.add_argument(
        "--thread-id",
        default="",
        help="LangGraph checkpointer thread id (default: random UUID). Ignored for CrewAI.",
    )
    run_p.add_argument(
        "--resume",
        default="",
        metavar="SESSION_OR_THREAD_ID",
        help=(
            "LangGraph: checkpoint thread id (with --resume-input for HITL). "
            "claude-agent-sdk: Claude session id to resume (use same --thread-id workspace if set)."
        ),
    )
    run_p.add_argument(
        "--resume-input",
        default="",
        help="Value for Command(resume=...) when using --resume.",
    )
    run_p.add_argument(
        "--stream",
        action="store_true",
        help=(
            "Stream events as JSON lines: LangGraph node updates, or Claude Agent SDK stream events."
        ),
    )
    run_p.add_argument(
        "--claude-budget",
        "--budget",
        type=float,
        default=None,
        dest="claude_budget",
        metavar="USD",
        help="claude-agent-sdk: max_budget_usd cap for the orchestrator query (default: sum of phase budgets). Alias: --budget.",
    )
    run_p.add_argument(
        "--fork-session",
        action="store_true",
        help="claude-agent-sdk: fork when resuming (new session id, same transcript fork).",
    )
    run_p.add_argument(
        "--langgraph-mode",
        choices=("placeholder", "full"),
        default=None,
        help=(
            "LangGraph main graph: placeholder (stubs) or full (subgraphs). "
            "Default: AI_TEAM_LANGGRAPH_GRAPH_MODE env or placeholder."
        ),
    )

    # estimate
    est_p = subparsers.add_parser(
        "estimate", help="Show cost estimate for an environment (no run)."
    )
    est_p.add_argument(
        "--env",
        choices=_ENV_CHOICES,
        default="dev",
        help="Environment to estimate (default: dev).",
    )
    est_p.add_argument(
        "--complexity",
        choices=_COMPLEXITY_CHOICES,
        default="medium",
        help="Complexity tier (default: medium).",
    )

    # compare-costs
    comp_p = subparsers.add_parser(
        "compare-costs",
        help="Compare estimated costs across dev, test, and prod.",
    )
    comp_p.add_argument(
        "--complexity",
        choices=_COMPLEXITY_CHOICES,
        default="medium",
        help="Complexity tier (default: medium).",
    )

    prune_p = subparsers.add_parser(
        "prune",
        help="Delete workspace/output run directories older than N days (default 14).",
    )
    prune_p.add_argument(
        "--older-than-days",
        type=int,
        default=14,
        help="Retention window in days (default: 14).",
    )

    argv = _preprocess_argv_for_subcommand(sys.argv[1:])
    args = parser.parse_args(argv)
    command = args.command

    if command is None:
        parser.print_help()
        return 2

    if command == "estimate":
        return _cmd_estimate(env=args.env, complexity=args.complexity)
    if command == "compare-costs":
        return _cmd_compare_costs(complexity=args.complexity)
    if command == "prune":
        from ai_team.core.results.cleanup import prune_runs

        removed = prune_runs(older_than_days=int(args.older_than_days))
        print(f"pruned {len(removed)} run(s)")
        return 0
    if command == "run":
        opts = RunOptions.from_namespace(args)
        if not opts.description and not opts.resume_thread:
            run_p.error(
                "Project description is required unless resuming (--resume SESSION_OR_THREAD_ID)."
            )
        return _cmd_run(opts)
    return 1


if __name__ == "__main__":
    sys.exit(main())
