"""
CLI to run evals for one or all backends.

Usage:
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --compare
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --backend langgraph
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --all
    AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --backend crewai --scenario todo-api-beginner
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FILE_MAP = {
    "crewai": "evals/backends/test_crewai_eval.py",
    "langgraph": "evals/backends/test_langgraph_eval.py",
    "claude-agent-sdk": "evals/backends/test_claude_sdk_eval.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-Team eval runner")
    parser.add_argument(
        "--backend",
        choices=list(_FILE_MAP),
        help="Run evals for a single backend.",
    )
    parser.add_argument(
        "--scenario",
        default="smoke-test",
        help="Scenario ID from evals/scenarios/ (default: smoke-test).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all backend evals sequentially.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Cross-backend comparison (all backends, same scenario, side-by-side report).",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip LLM judge (faster, no Anthropic API calls for scoring).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Pass -v to pytest.",
    )
    args = parser.parse_args()

    # Load .env so ANTHROPIC_API_KEY etc. are available to subprocess
    _dotenv = _REPO_ROOT / ".env"
    dotenv_vars: dict[str, str] = {}
    if _dotenv.exists():
        for line in _dotenv.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                dotenv_vars[k.strip()] = v.strip()

    env = {
        **dotenv_vars,
        **os.environ,  # shell env wins over .env
        "AI_TEAM_USE_REAL_LLM": "1",
        "EVAL_SCENARIO": args.scenario,
    }
    if args.no_judge:
        env["EVAL_NO_JUDGE"] = "1"

    base_cmd = ["uv", "run", "pytest", "--tb=short", "-s"]
    if args.verbose:
        base_cmd.append("-v")

    if args.compare:
        cmd = base_cmd + ["evals/test_backend_comparison.py"]
    elif args.all:
        cmd = base_cmd + ["evals/backends/"]
    elif args.backend:
        cmd = base_cmd + [_FILE_MAP[args.backend]]
    else:
        parser.print_help()
        sys.exit(0)

    result = subprocess.run(cmd, env=env, cwd=_REPO_ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
