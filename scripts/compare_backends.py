#!/usr/bin/env python3
"""
Compare CrewAI vs LangGraph on the same demo input (Phase 9).

Produces JSON (stdout) and optional markdown file.

Usage:
  poetry run python scripts/compare_backends.py demos/01_hello_world --env dev
  poetry run python scripts/compare_backends.py demos/01_hello_world --team backend-api --markdown out.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the same demo through CrewAI and LangGraph; emit comparison report.",
    )
    parser.add_argument(
        "demo_path",
        type=str,
        help="Path to demo directory (e.g. demos/01_hello_world).",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="Set AI_TEAM_ENV for both runs (e.g. dev, test, prod).",
    )
    parser.add_argument(
        "--team",
        default="full",
        help="Team profile from config/team_profiles.yaml (default: full).",
    )
    parser.add_argument(
        "--skip-estimate",
        action="store_true",
        help="Bypass cost estimation and confirmation.",
    )
    parser.add_argument(
        "--complexity",
        default=None,
        choices=("simple", "medium", "complex"),
        help="Optional complexity override for CrewAI flow.",
    )
    parser.add_argument(
        "--markdown",
        default="",
        metavar="PATH",
        help="Write markdown report to PATH in addition to JSON on stdout.",
    )
    args = parser.parse_args()

    repo = _repo_root()
    raw = Path(args.demo_path)
    demo_dir = raw.resolve() if raw.is_absolute() else (repo / raw).resolve()
    if not demo_dir.is_dir():
        print(f"Error: Not a directory: {demo_dir}", file=sys.stderr)
        return 1

    try:
        from ai_team.utils.backend_comparison import compare_backends_for_demo_dir

        report = compare_backends_for_demo_dir(
            demo_dir,
            team=args.team,
            env=args.env,
            skip_estimate=args.skip_estimate,
            complexity_override=args.complexity,
        )
    except (FileNotFoundError, ValueError, KeyError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(report.to_json_dict(), indent=2, default=str))
    md_path = (args.markdown or "").strip()
    if md_path:
        out = Path(md_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.to_markdown(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
