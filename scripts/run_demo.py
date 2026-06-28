#!/usr/bin/env python3
"""
Run an ai-team demo with DEV configuration (OpenRouter dev tier).

Loads the project description from the demo directory (project_description.txt
or input.json), optional ``team_profile`` from input.json, sets AI_TEAM_ENV=dev,
and invokes the flow.

Usage:
    poetry run python scripts/run_demo.py demos/01_hello_world
    poetry run python scripts/run_demo.py demos/00_smoke_test --skip-estimate --backend langgraph
    poetry run python scripts/run_demo.py demos/02_todo_app [--skip-estimate] [--monitor] [--team backend-api]

Requires OPENROUTER_API_KEY in the environment (e.g. from .env).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path

from ai_team.utils.demo_input import load_demo_input, resolve_team_profile

# Default wall-clock budget for a single demo run. The pipeline has no internal
# watchdog, so a hung LLM/tool call can otherwise block indefinitely.
DEFAULT_TIMEOUT_S = 900


class DemoTimeoutError(Exception):
    """Raised when a demo run exceeds the wall-clock budget."""


def _install_timeout(seconds: int) -> bool:
    """Arm a SIGALRM watchdog that raises DemoTimeoutError. Returns True if armed.

    SIGALRM is Unix-only and only fires on the main thread; both hold here
    (run_demo.py runs the flow synchronously on the main thread). On platforms
    without SIGALRM (e.g. Windows) this is a no-op and the run is untimed.
    """
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        return False

    def _handler(_signum: int, _frame: object) -> None:
        raise DemoTimeoutError(f"Run exceeded {seconds}s wall-clock budget")

    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    return True


def _cancel_timeout() -> None:
    """Disarm the SIGALRM watchdog if armed."""
    if hasattr(signal, "SIGALRM"):
        signal.alarm(0)


def _repo_root() -> Path:
    """Project root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


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


def _run_success(result: dict) -> bool:
    if result.get("success") is False:
        return False
    state = result.get("state") or {}
    if not state:
        return result.get("success") is True
    return state.get("current_phase") == "complete"


def _run_crewai(
    description: str,
    *,
    team: str,
    monitor: object | None,
    skip_estimate: bool,
) -> dict:
    from ai_team.flows.main_flow import run_ai_team

    return run_ai_team(
        description,
        monitor=monitor,
        skip_estimate=skip_estimate,
        env_override="dev",
        team_profile=team,
    )


def _run_backend(
    description: str,
    *,
    backend_name: str,
    team: str,
    monitor: object | None,
    skip_estimate: bool,
    graph_mode: str = "full",
) -> dict:
    from ai_team.backends.registry import get_backend
    from ai_team.core.team_profile import load_team_profile

    profile = load_team_profile(team)
    backend = get_backend(backend_name)
    pr = backend.run(
        description,
        profile,
        env="dev",
        monitor=monitor,
        skip_estimate=skip_estimate,
        graph_mode=graph_mode,
    )
    raw = pr.raw
    return {
        "backend": pr.backend_name,
        "team_profile": pr.team_profile,
        "success": pr.success,
        "error": pr.error,
        "result": raw.get("result"),
        "state": raw.get("state"),
    }


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
        "--backend",
        default="crewai",
        choices=("crewai", "langgraph", "claude-agent-sdk"),
        help="Orchestration backend (default: crewai). Use langgraph for profile-aware lean crews.",
    )
    parser.add_argument(
        "--team",
        default=None,
        help="Team profile (overrides team_profile in input.json; default: full or input.json).",
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
    parser.add_argument(
        "--graph-mode",
        default="full",
        choices=("placeholder", "full"),
        help="LangGraph mode: 'full' runs real LLM calls (default), 'placeholder' stubs nodes.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help=(
            f"Wall-clock budget in seconds; aborts a hung run (default: {DEFAULT_TIMEOUT_S}). "
            "Set 0 to disable."
        ),
    )
    args = parser.parse_args()

    repo = _repo_root()
    demo_dir = (
        Path(args.demo_path) if Path(args.demo_path).is_absolute() else repo / args.demo_path
    ).resolve()
    if not demo_dir.is_dir():
        print(f"Error: Not a directory: {demo_dir}", file=sys.stderr)
        parser.print_help(sys.stderr)
        return 1

    try:
        demo = load_demo_input(demo_dir)
        team = resolve_team_profile(demo_dir, cli_team=args.team)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    os.environ["AI_TEAM_ENV"] = "dev"

    from ai_team.monitor import TeamMonitor

    use_tui = args.output == "tui" or args.monitor
    project_name = args.project_name or demo_dir.name
    monitor = TeamMonitor(project_name=project_name) if use_tui else None

    armed = _install_timeout(args.timeout)
    if armed:
        print(f"Watchdog armed: {args.timeout}s wall-clock budget.", file=sys.stderr)
    try:
        if args.backend == "crewai":
            result = _run_crewai(
                demo.description,
                team=team,
                monitor=monitor,
                skip_estimate=args.skip_estimate,
            )
        else:
            result = _run_backend(
                demo.description,
                backend_name=args.backend,
                team=team,
                monitor=monitor,
                skip_estimate=args.skip_estimate,
                graph_mode=args.graph_mode,
            )
        _print_error_summary(result, file=sys.stderr)
        print(json.dumps(result, indent=2, default=str))
        return 0 if _run_success(result) else 1
    except DemoTimeoutError as e:
        print(
            f"Error: {e}. The run was aborted by the watchdog "
            f"(--timeout {args.timeout}). Re-run with a larger --timeout, "
            "or check for a hung LLM/tool call.",
            file=sys.stderr,
        )
        sys.stderr.flush()
        return 124
    except Exception as e:
        import traceback

        traceback.print_exc(file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        sys.stderr.flush()
        return 1
    finally:
        _cancel_timeout()


if __name__ == "__main__":
    rc = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # Force-exit to kill dangling non-daemon threads from CrewAI/LiteLLM internals
    # that would otherwise keep the process alive indefinitely after flow completes.
    os._exit(rc)
