"""
AI Team CLI entry point.

Invoked via `ai-team` console script (pyproject.toml).
"""

import argparse
import sys
from typing import NoReturn

from ai_team.flows.main_flow import run_ai_team


def main() -> None:
    """Parse arguments and run the AI Team flow."""
    parser = argparse.ArgumentParser(
        prog="ai-team",
        description="Autonomous Multi-Agent Software Development Team",
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="",
        help="Natural-language project request (e.g. 'Create a REST API for todos')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )
    args = parser.parse_args()
    request = args.request or ""
    if not request.strip():
        parser.print_help()
        sys.exit(0)
    result = run_ai_team(request)
    if args.json:
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Result:", result.get("result"))
    sys.exit(0)


if __name__ == "__main__":
    main()
