"""
CLI entry point for ai-team.

Run the full flow with optional Rich TUI monitor.
"""

from __future__ import annotations

import argparse
import json
import sys

import structlog
from ai_team.flows.main_flow import run_ai_team
from ai_team.monitor import TeamMonitor

logger = structlog.get_logger(__name__)


def main() -> int:
    """Parse CLI args and run the AI team flow. Returns 0 on success, 1 on failure."""
    parser = argparse.ArgumentParser(
        description="Run the AI team flow: transform a project description into code.",
    )
    parser.add_argument(
        "description",
        nargs="?",
        default="",
        help="Project description (e.g. 'Create a REST API for a todo list').",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Show the Rich TUI monitor (live phases, agents, guardrails) during the run.",
    )
    parser.add_argument(
        "--project-name",
        default="AI-Team Project",
        help="Project name shown in the monitor (used when --monitor is set). Default: AI-Team Project.",
    )
    args = parser.parse_args()

    description = (args.description or "").strip()
    if not description:
        parser.error('Project description is required (e.g. ai-team "Create a REST API")')

    monitor = None
    if args.monitor:
        monitor = TeamMonitor(project_name=args.project_name)

    try:
        result = run_ai_team(description, monitor=monitor)
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


if __name__ == "__main__":
    sys.exit(main())
