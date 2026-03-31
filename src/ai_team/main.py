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
from ai_team.backends.registry import get_backend
from ai_team.core.team_profile import load_team_profile
from ai_team.monitor import TeamMonitor
from dotenv import load_dotenv

logger = structlog.get_logger(__name__)

_ENV_CHOICES = ("dev", "test", "prod")
_COMPLEXITY_CHOICES = ("simple", "medium", "complex")
_SUBCOMMANDS = frozenset({"run", "estimate", "compare-costs"})


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
    from ai_team.config.models import Environment, OpenRouterSettings
    from pydantic import ValidationError

    try:
        settings = OpenRouterSettings(ai_team_env=Environment(env))
    except ValidationError as e:
        logger.warning("openrouter_not_configured", error=str(e))
        print(
            "Error: OpenRouter not configured. Set OPENROUTER_API_KEY and related env vars.",
            file=sys.stderr,
        )
        return 1
    comp = complexity  # type: str
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
            settings = OpenRouterSettings(ai_team_env=env)
            rows, total_with_buffer, _ = estimate_run_cost(settings, complexity)
            env_results.append((env, rows, total_with_buffer))
    except ValidationError as e:
        logger.warning("openrouter_not_configured", error=str(e))
        print(
            "Error: OpenRouter not configured. Set OPENROUTER_API_KEY and related env vars.",
            file=sys.stderr,
        )
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
    backend_name: str = "crewai",
    team: str = "full",
    thread_id: str = "",
    stream: bool = False,
    resume_thread: str = "",
    resume_input: str = "",
    langgraph_mode: str | None = None,
) -> int:
    """Run the AI team flow with optional env and complexity overrides."""
    if not (resume_thread or "").strip() and not (description or "").strip():
        return 2  # caller should print usage
    if env is not None:
        os.environ["AI_TEAM_ENV"] = env
    try:
        profile = load_team_profile(team)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    use_tui = output_mode == "tui" and backend_name in ("crewai", "langgraph")
    monitor_obj = TeamMonitor(project_name=project_name) if use_tui else None
    try:
        from ai_team.backends.langgraph_backend.backend import LangGraphBackend

        backend = get_backend(backend_name)

        if backend_name == "langgraph" and (resume_thread or "").strip():
            if not isinstance(backend, LangGraphBackend):
                print("Error: resume requires LangGraph backend.", file=sys.stderr)
                return 1
            resume_kw: dict[str, object] = {
                "monitor": monitor_obj,
                "skip_estimate": skip_estimate,
                "complexity_override": complexity,
            }
            if langgraph_mode is not None:
                resume_kw["graph_mode"] = langgraph_mode
            pr = backend.resume(
                (resume_thread or "").strip(),
                resume_input,
                profile,
                **resume_kw,
            )
            raw = pr.raw
            out: dict[str, object] = {
                "backend": pr.backend_name,
                "team_profile": pr.team_profile,
                "success": pr.success,
                "error": pr.error,
                "result": raw.get("result"),
                "state": raw.get("state"),
                "thread_id": raw.get("thread_id"),
            }
            print(json.dumps(out, indent=2, default=str))
            return 0 if pr.success else 1

        if backend_name == "langgraph" and (stream or use_tui):
            if not isinstance(backend, LangGraphBackend):
                print("Error: internal backend type mismatch.", file=sys.stderr)
                return 1
            if monitor_obj:
                monitor_obj.start()
            run_kw: dict[str, object] = {
                "monitor": monitor_obj if use_tui else None,
                "skip_estimate": skip_estimate,
                "complexity_override": complexity,
            }
            if thread_id.strip():
                run_kw["thread_id"] = thread_id.strip()
            if langgraph_mode is not None:
                run_kw["graph_mode"] = langgraph_mode
            print_jsonl = stream and not use_tui
            try:
                for ev in backend.iter_stream_events(
                    description.strip(),
                    profile,
                    **run_kw,
                ):
                    if print_jsonl:
                        print(json.dumps(ev, default=str))
            finally:
                if monitor_obj:
                    monitor_obj.stop()
            return 0

        run_kw = {
            "monitor": monitor_obj,
            "skip_estimate": skip_estimate,
            "complexity_override": complexity,
        }
        if thread_id.strip() and backend_name == "langgraph":
            run_kw["thread_id"] = thread_id.strip()
        if backend_name == "langgraph" and langgraph_mode is not None:
            run_kw["graph_mode"] = langgraph_mode
        pr = backend.run(
            description.strip(),
            profile,
            env=env,
            **run_kw,
        )
        raw = pr.raw
        out = {
            "backend": pr.backend_name,
            "team_profile": pr.team_profile,
            "success": pr.success,
            "error": pr.error,
            "result": raw.get("result"),
            "state": raw.get("state"),
        }
        if backend_name == "langgraph":
            out["thread_id"] = raw.get("thread_id")
        print(json.dumps(out, indent=2, default=str))
        return 0 if pr.success else 1
    except Exception as e:
        logger.exception("ai_team_run_failed", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Parse CLI args and dispatch to subcommands. Returns 0 on success, 1 on failure."""
    # LangGraph reads AI_TEAM_LANGGRAPH_GRAPH_MODE via os.environ; load_dotenv makes .env effective.
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="AI team: transform a project description into code (run, estimate, or compare-costs).",
    )
    parser.add_argument(
        "--backend",
        choices=("crewai", "langgraph"),
        default="crewai",
        help="Orchestration backend: crewai (default) or langgraph (skeleton graph).",
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
        choices=("crewai", "langgraph"),
        default="crewai",
        help="Orchestration backend: crewai (default) or langgraph (skeleton graph).",
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
        "--thread-id",
        default="",
        help="LangGraph checkpointer thread id (default: random UUID). Ignored for CrewAI.",
    )
    run_p.add_argument(
        "--resume",
        default="",
        metavar="THREAD_ID",
        help="Resume a LangGraph run from checkpoint (use with --resume-input for HITL).",
    )
    run_p.add_argument(
        "--resume-input",
        default="",
        help="Value for Command(resume=...) when using --resume.",
    )
    run_p.add_argument(
        "--stream",
        action="store_true",
        help="Stream LangGraph node updates as JSON lines (stdout; use with --backend langgraph).",
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
    if command == "run":
        description = (args.run_description or "").strip()
        resume_thr = (getattr(args, "resume", "") or "").strip()
        if not description and not resume_thr:
            run_p.error(
                "Project description is required unless resuming (--resume THREAD_ID)."
            )
        output_mode = "tui" if args.monitor else args.output
        return _cmd_run(
            description=description,
            env=args.env,
            complexity=args.complexity,
            output_mode=output_mode,
            skip_estimate=args.skip_estimate,
            project_name=args.project_name,
            backend_name=args.backend,
            team=args.team,
            thread_id=getattr(args, "thread_id", "") or "",
            stream=bool(getattr(args, "stream", False)),
            resume_thread=resume_thr,
            resume_input=getattr(args, "resume_input", "") or "",
            langgraph_mode=getattr(args, "langgraph_mode", None),
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
