"""
CLI entry point for ai-team.

Subcommands: run (default), estimate, compare-costs.
Run the full flow with optional --env and --complexity; estimate and compare-costs
show cost tables without executing the pipeline.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import structlog
from ai_team.flows.main_flow import run_ai_team
from ai_team.monitor import TeamMonitor

logger = structlog.get_logger(__name__)

_ENV_CHOICES = ("dev", "test", "prod")
_COMPLEXITY_CHOICES = ("simple", "medium", "complex")


def _cmd_estimate(env: str, complexity: str) -> int:
    """Show cost estimate for the given environment and complexity."""
    from pydantic import ValidationError

    from ai_team.config.cost_estimator import (
        display_estimate,
        estimate_run_cost,
    )
    from ai_team.config.models import Environment, OpenRouterSettings

    try:
        settings = OpenRouterSettings(ai_team_env=Environment(env))
    except ValidationError as e:
        logger.warning("openrouter_not_configured", error=str(e))
        print("Error: OpenRouter not configured. Set OPENROUTER_API_KEY and related env vars.", file=sys.stderr)
        return 1
    comp = complexity  # type: str
    rows, total_with_buffer, within_budget = estimate_run_cost(settings, comp)
    display_estimate(settings, comp, rows, total_with_buffer, within_budget)
    return 0


def _cmd_compare_costs(complexity: str) -> int:
    """Show side-by-side cost comparison for dev, test, and prod."""
    from pydantic import ValidationError

    from ai_team.config.cost_estimator import (
        display_compare_costs,
        estimate_run_cost,
    )
    from ai_team.config.models import Environment, OpenRouterSettings

    env_results = []
    try:
        for env in (Environment.DEV, Environment.TEST, Environment.PROD):
            settings = OpenRouterSettings(ai_team_env=env)
            rows, total_with_buffer, _ = estimate_run_cost(settings, complexity)
            env_results.append((env, rows, total_with_buffer))
    except ValidationError as e:
        logger.warning("openrouter_not_configured", error=str(e))
        print("Error: OpenRouter not configured. Set OPENROUTER_API_KEY and related env vars.", file=sys.stderr)
        return 1
    display_compare_costs(env_results, complexity)
    return 0


_OUTPUT_CHOICES = ("tui", "crewai")


def _cmd_run(
    description: str,
    env: str | None,
    complexity: str | None,
    output_mode: str,
    skip_estimate: bool,
    project_name: str,
) -> int:
    """Run the AI team flow with optional env and complexity overrides."""
    if not (description or "").strip():
        return 2  # caller should print usage
    if env is not None:
        os.environ["AI_TEAM_ENV"] = env
    use_tui = output_mode == "tui"
    monitor_obj = TeamMonitor(project_name=project_name) if use_tui else None
    try:
        result = run_ai_team(
            description.strip(),
            monitor=monitor_obj,
            skip_estimate=skip_estimate,
            env_override=env,
            complexity_override=complexity,
        )
        out = {
            "result": result.get("result"),
            "state": result.get("state"),
        }
        print(json.dumps(out, indent=2, default=str))
        return 0
    except Exception as e:
        logger.exception("ai_team_run_failed", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Parse CLI args and dispatch to subcommands. Returns 0 on success, 1 on failure."""
    parser = argparse.ArgumentParser(
        description="AI team: transform a project description into code (run, estimate, or compare-costs).",
    )
    parser.add_argument(
        "description",
        nargs="?",
        default="",
        help="Project description (used when no subcommand: same as 'run <description>').",
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    # run
    run_p = subparsers.add_parser("run", help="Run the full AI team flow.")
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

    # estimate
    est_p = subparsers.add_parser("estimate", help="Show cost estimate for an environment (no run).")
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

    args = parser.parse_args()
    command = args.command

    # Backward compatibility: no subcommand but description given => run
    if command is None:
        description = (args.description or "").strip()
        if not description:
            parser.error(
                'Project description is required. Use: ai-team run "description" or ai-team "description"'
            )
        return _cmd_run(
            description=description,
            env=None,
            complexity=None,
            output_mode="crewai",
            skip_estimate=False,
            project_name="AI-Team Project",
        )

    if command == "estimate":
        return _cmd_estimate(env=args.env, complexity=args.complexity)
    if command == "compare-costs":
        return _cmd_compare_costs(complexity=args.complexity)
    if command == "run":
        description = (args.run_description or "").strip()
        if not description:
            run_p.error('Project description is required (e.g. ai-team run "Create a REST API")')
        output_mode = "tui" if args.monitor else args.output
        return _cmd_run(
            description=description,
            env=args.env,
            complexity=args.complexity,
            output_mode=output_mode,
            skip_estimate=args.skip_estimate,
            project_name=args.project_name,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
