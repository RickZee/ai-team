#!/usr/bin/env python3
"""
Run a demo project through the AI Team pipeline.

Usage:
    python scripts/run_demo.py "Create a REST API for todos"
    python scripts/run_demo.py --demo 01_hello_world
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src is on path when run from repo root
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AI Team demo")
    parser.add_argument("request", nargs="?", help="Natural-language project request")
    parser.add_argument("--demo", help="Demo id (e.g. 01_hello_world)")
    args = parser.parse_args()
    request = args.request or ""
    if args.demo:
        request = request or f"Run demo: {args.demo}"
    if not request.strip():
        parser.print_help()
        return 0
    from ai_team.flows.main_flow import run_ai_team
    result = run_ai_team(request)
    print("Result:", result.get("result"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
