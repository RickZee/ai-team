#!/usr/bin/env python3
"""
Run an ai-team demo with DEV configuration (OpenRouter dev tier).

Loads the project description from the demo directory (project_description.txt
or input.json), optional ``team_profile`` from input.json, sets AI_TEAM_ENV=dev,
and invokes the flow.

Usage:
    uv run python scripts/run_demo.py demos/01_hello_world
    uv run python scripts/run_demo.py demos/00_smoke_test --skip-estimate --backend langgraph
    uv run python scripts/run_demo.py demos/02_todo_app [--skip-estimate] [--monitor] [--team backend-api]

Requires OPENROUTER_API_KEY in the environment (e.g. from .env).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

from ai_team.config.demo_input import load_demo_input, resolve_team_profile

# Default wall-clock budget for a single demo run. The pipeline has no internal
# watchdog, so a hung LLM/tool call can otherwise block indefinitely.
DEFAULT_TIMEOUT_S = 900
# After the first alarm, how long the run gets to unwind before the process exits hard.
TIMEOUT_GRACE_S = 30

_RUN_CONTEXT: dict[str, Any] = {}


class DemoTimeoutError(BaseException):
    """Raised when a demo run exceeds the wall-clock budget.

    Subclasses ``BaseException`` (like ``BudgetExceededError``) so the phase and subgraph
    ``except Exception`` handlers cannot swallow it and retry — they did, and a 900 s
    watchdog let a LangGraph run go on for 1,600 s (2026-09-13) and past 15 min (2026-09-16).
    """


def _install_timeout(seconds: int) -> bool:
    """Arm a two-stage SIGALRM watchdog. Returns True if armed.

    Stage 1 raises :class:`DemoTimeoutError` so the run can unwind. If the process is still
    alive ``TIMEOUT_GRACE_S`` later (a handler swallowed it, or the main thread is blocked),
    stage 2 finalizes the run record as ``timeout`` and hard-exits with 124, so a timed-out
    run cannot keep spending.

    SIGALRM is Unix-only and only fires on the main thread; both hold here
    (run_demo.py runs the flow synchronously on the main thread). On platforms
    without SIGALRM (e.g. Windows) this is a no-op and the run is untimed.
    """
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        return False
    fired = {"n": 0}

    def _handler(_signum: int, _frame: object) -> None:
        fired["n"] += 1
        if fired["n"] == 1:
            signal.alarm(TIMEOUT_GRACE_S)
            raise DemoTimeoutError(f"Run exceeded {seconds}s wall-clock budget")
        print(
            f"Error: run still alive {TIMEOUT_GRACE_S}s after the {seconds}s watchdog; "
            "exiting hard.",
            file=sys.stderr,
        )
        _finalize_run("timeout")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(124)

    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    return True


def _cancel_timeout() -> None:
    """Disarm the SIGALRM watchdog if armed."""
    if hasattr(signal, "SIGALRM"):
        signal.alarm(0)


def _finalize_run(status: str) -> None:
    """Close the run record this invocation created (best-effort, never raises).

    CLI runs never called ``ResultsBundle.finalize()``, so their ``run.json`` kept
    ``completed_at: null`` and no spend row — two thirds of the corpus on 2026-09-16.
    Picks run folders created after this process started whose record is still open
    (a backend that finalizes itself, like the Claude SDK, is left alone).
    """
    if _RUN_CONTEXT.get("finalized"):
        return
    _RUN_CONTEXT["finalized"] = True
    try:
        from ai_team.config.settings import get_settings
        from ai_team.core.results.writer import RUNS_SUBDIR, ResultsBundle
        from ai_team.core.spend_guard import current_spend

        started = float(_RUN_CONTEXT.get("started", 0.0))
        runs = Path(get_settings().project.output_dir) / RUNS_SUBDIR
        for run_dir in sorted(runs.glob("*/run.json"), key=lambda p: p.stat().st_mtime):
            if run_dir.stat().st_mtime < started:
                continue
            data = json.loads(run_dir.read_text(encoding="utf-8"))
            if data.get("completed_at"):
                continue
            run_id = run_dir.parent.name
            spend = current_spend(run_id=run_id)
            if not spend.get("calls") and spend.get("observed_usd") is None:
                spend = current_spend()
            # Zero calls is a measurement. Omitting the row made $0 runs vanish
            # from every chart that reads logs/costs.jsonl.
            ResultsBundle(run_id).finalize(
                final_status=status,
                spend=dict(spend),
                backend=_RUN_CONTEXT.get("backend"),
            )
    except Exception as e:  # noqa: BLE001 - finalizing must never mask the run's outcome
        print(f"Warning: could not finalize run record: {e}", file=sys.stderr)


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


KEY_VAR_FOR_BACKEND = {
    "langgraph": "OPENROUTER_API_KEY",
    "crewai": "OPENROUTER_API_KEY",
    "claude-agent-sdk": "ANTHROPIC_API_KEY",
}


def _missing_api_key(backend: str, graph_mode: str) -> str | None:
    """
    Say plainly, before anything spends or stalls, that the run has no key.

    An empty ``OPENROUTER_API_KEY=`` in the environment deliberately beats ``.env`` — that is
    how the $0 placeholder run guarantees it cannot spend. But when the same empty value is
    still around for a real run, the failure surfaces ~3 s in as litellm's "Missing
    credentials ... set the OPENAI_API_KEY environment variable", naming a variable this
    project does not use (2026-09-17, course/testing/runs/2026-09-17-stranger-2, F22).
    Name the right variable, and say which of the two situations this is.
    """
    if graph_mode == "placeholder":
        return None
    var = KEY_VAR_FOR_BACKEND.get(backend)
    if var is None:
        return None
    if os.environ.get(var):
        return None
    if var in os.environ:
        return (
            f"{var} is set but empty in this shell, which overrides .env and means "
            f"'do not spend'. Run `unset {var}` and try again."
        )
    from ai_team.config.models import OpenRouterSettings

    if var == "OPENROUTER_API_KEY" and OpenRouterSettings().openrouter_api_key:
        return None
    if var == "ANTHROPIC_API_KEY":
        from ai_team.config.settings import get_settings

        if getattr(get_settings().anthropic, "api_key", ""):
            return None
    return f"{var} is not set. Put it in .env or export it, or use --graph-mode placeholder."


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
    from ai_team.backends.crewai_backend.flows.main_flow import run_ai_team

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
        choices=("crewai", "langgraph", "claude-agent-sdk", "strands", "agent-framework"),
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

    key_problem = _missing_api_key(args.backend, args.graph_mode)
    if key_problem:
        print(f"Error: {key_problem}", file=sys.stderr)
        return 1

    from ai_team.monitor import TeamMonitor

    use_tui = args.output == "tui" or args.monitor
    project_name = args.project_name or demo_dir.name
    monitor = TeamMonitor(project_name=project_name) if use_tui else None

    _RUN_CONTEXT.update(started=time.time() - 1, backend=args.backend)
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
        _cancel_timeout()
        ok = _run_success(result)
        phase = str((result.get("state") or {}).get("current_phase") or "")
        _finalize_run("complete" if ok else (phase if phase == "awaiting_human" else "failed"))
        _print_error_summary(result, file=sys.stderr)
        print(json.dumps(result, indent=2, default=str))
        return 0 if ok else 1
    except DemoTimeoutError as e:
        _cancel_timeout()
        _finalize_run("timeout")
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

        _cancel_timeout()
        _finalize_run("error")
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
