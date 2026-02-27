#!/usr/bin/env python3
"""
Run an ai-team demo with DEV configuration (OpenRouter dev tier).

Loads the project description from the demo directory (project_description.txt
or input.json), sets AI_TEAM_ENV=dev, and invokes the full flow.

Usage:
    poetry run python scripts/run_demo.py demos/01_hello_world
    poetry run python scripts/run_demo.py demos/02_todo_app [--skip-estimate] [--monitor]

Requires OPENROUTER_API_KEY in the environment (e.g. from .env).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Project root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def _load_description(demo_dir: Path) -> str:
    """
    Load project description from demo directory.
    Prefer project_description.txt; else derive from input.json.
    """
    desc_file = demo_dir / "project_description.txt"
    if desc_file.is_file():
        return desc_file.read_text(encoding="utf-8").strip()

    input_file = demo_dir / "input.json"
    if not input_file.is_file():
        raise FileNotFoundError(
            f"Demo has neither project_description.txt nor input.json: {demo_dir}"
        )
    data = json.loads(input_file.read_text(encoding="utf-8"))
    if isinstance(data.get("description"), str) and data["description"].strip():
        return data["description"].strip()
    parts = []
    if data.get("project_name"):
        parts.append(str(data["project_name"]))
    if data.get("description"):
        parts.append(str(data["description"]))
    if data.get("stack"):
        stack = data["stack"]
        parts.append(f"Stack: {', '.join(stack) if isinstance(stack, list) else stack}")
    if not parts:
        raise ValueError(f"input.json has no description or project_name: {input_file}")
    return " — ".join(parts)


def _print_error_summary(result: dict, *, file: object) -> None:
    """Print a short error summary to stderr when the run has errors or failed phase."""
    state = result.get("state") or {}
    phase = state.get("current_phase", "")
    errors = state.get("errors") or []
    last_error = (state.get("metadata") or {}).get("last_crew_error") or {}
    if phase == "complete" and not errors:
        return
    if errors or last_error or phase == "error":
        lines = ["--- Run summary ---"]
        lines.append(f"Phase: {phase}")
        if last_error:
            msg = last_error.get("error") or last_error.get("message") or str(last_error)
            lines.append(f"Last crew error: {msg[:500]}{'...' if len(msg) > 500 else ''}")
        for i, err in enumerate(errors[:5], 1):
            msg = err.get("message", str(err))[:200]
            lines.append(f"  Error {i}: [{err.get('phase', '')}] {msg}...")
        if len(errors) > 5:
            lines.append(f"  ... and {len(errors) - 5} more.")
        lines.append("-------------------")
        print("\n".join(lines), file=file)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an ai-team demo with DEV configuration (OpenRouter dev tier).",
    )
    parser.add_argument(
        "demo_path",
        type=str,
        help="Path to demo directory (e.g. demos/01_hello_world, demos/02_todo_app).",
    )
    parser.add_argument(
        "--skip-estimate",
        action="store_true",
        help="Bypass cost estimation and confirmation (e.g. for CI).",
    )
    parser.add_argument(
        "--output",
        choices=("tui", "crewai"),
        default="crewai",
        help="Progress output: 'tui' = Rich TUI, 'crewai' = CrewAI default verbose (default: crewai).",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Use Rich TUI for progress (shortcut for --output tui).",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Project name for the monitor (default: demo directory name).",
    )
    args = parser.parse_args()

    repo = _repo_root()
    demo_dir = (Path(args.demo_path) if Path(args.demo_path).is_absolute() else repo / args.demo_path).resolve()
    if not demo_dir.is_dir():
        print(f"Error: Not a directory: {demo_dir}", file=sys.stderr)
        parser.print_help(sys.stderr)
        return 1

    try:
        description = _load_description(demo_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    os.environ["AI_TEAM_ENV"] = "dev"

    from ai_team.flows.main_flow import run_ai_team
    from ai_team.monitor import TeamMonitor

    use_tui = args.output == "tui" or args.monitor
    project_name = args.project_name or demo_dir.name
    monitor = TeamMonitor(project_name=project_name) if use_tui else None

    try:
        result = run_ai_team(
            description,
            monitor=monitor,
            skip_estimate=args.skip_estimate,
            env_override="dev",
        )
        _print_error_summary(result, file=sys.stderr)
        print(json.dumps(result, indent=2, default=str))
        state = result.get("state") or {}
        return 0 if state.get("current_phase") == "complete" else 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
