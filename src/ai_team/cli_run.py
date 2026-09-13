"""Run-path options and execution, separate from argparse (R12.4)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import structlog
from ai_team.backends.registry import get_backend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile, load_team_profile
from ai_team.monitor import TeamMonitor

logger = structlog.get_logger(__name__)

_CLAUDE_BACKENDS = ("claude-agent-sdk", "claude-sdk")


@dataclass(frozen=True)
class RunOptions:
    """Typed run surface. Built from argparse or constructed in tests."""

    description: str
    env: str | None = None
    complexity: str | None = None
    output_mode: str = "crewai"
    skip_estimate: bool = False
    project_name: str = "AI-Team Project"
    run_name: str = ""
    backend_name: str = "crewai"
    team: str = "full"
    thread_id: str = ""
    stream: bool = False
    resume_thread: str = ""
    resume_input: str = ""
    langgraph_mode: str | None = None
    claude_budget: float | None = None
    fork_session: bool = False

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> RunOptions:
        """Map parsed CLI flags onto the run surface (one field per flag)."""
        monitor = bool(getattr(args, "monitor", False))
        return cls(
            description=(getattr(args, "run_description", "") or "").strip(),
            env=getattr(args, "env", None),
            complexity=getattr(args, "complexity", None),
            output_mode="tui" if monitor else (getattr(args, "output", None) or "crewai"),
            skip_estimate=bool(getattr(args, "skip_estimate", False)),
            project_name=getattr(args, "project_name", None) or "AI-Team Project",
            run_name=getattr(args, "run_name", "") or "",
            backend_name=getattr(args, "backend", None) or "crewai",
            team=getattr(args, "team", None) or "full",
            thread_id=getattr(args, "thread_id", "") or "",
            stream=bool(getattr(args, "stream", False)),
            resume_thread=(getattr(args, "resume", "") or "").strip(),
            resume_input=getattr(args, "resume_input", "") or "",
            langgraph_mode=getattr(args, "langgraph_mode", None),
            claude_budget=getattr(args, "claude_budget", None),
            fork_session=bool(getattr(args, "fork_session", False)),
        )


def _maybe_monitor(opts: RunOptions) -> TeamMonitor | None:
    use_tui = opts.output_mode == "tui" and opts.backend_name in (
        "crewai",
        "langgraph",
        *_CLAUDE_BACKENDS,
    )
    return TeamMonitor(project_name=opts.project_name) if use_tui else None


def _run_post_run_quality_gates(profile: TeamProfile) -> None:
    """Backend-agnostic post-run gates: deployment README + runtime smoke.

    Warn-only: failures are logged and the run is not aborted. The smoke gate
    also produces evidence (``docs/smoke_results.json``) when agents did not.
    """
    from ai_team.config.settings import get_settings

    ws = get_settings().project.workspace_dir
    try:
        from ai_team.guardrails.quality import deployment_artifacts_guardrail

        res = deployment_artifacts_guardrail(ws, profile.phases)
        if not res.passed:
            logger.warning(
                "deployment_artifacts_check",
                message=res.message,
                suggestions=res.suggestions,
                workspace=str(ws),
            )
    except Exception as exc:
        logger.debug("deployment_artifacts_check_skipped", error=str(exc))

    if "testing" not in {str(p).strip().lower() for p in profile.phases}:
        return
    try:
        from ai_team.guardrails.quality import runtime_smoke_guardrail
        from ai_team.tools.smoke_tools import load_or_run_smoke

        load_or_run_smoke(ws)
        res = runtime_smoke_guardrail(ws, profile.phases)
        if not res.passed:
            logger.warning(
                "runtime_smoke_check",
                message=res.message,
                suggestions=res.suggestions,
                workspace=str(ws),
            )
    except Exception as exc:
        logger.debug("runtime_smoke_check_skipped", error=str(exc))


def _finish_run(pr: ProjectResult, profile: TeamProfile) -> None:
    if os.environ.get("AI_TEAM_SKIP_POST_RUN"):
        return
    from ai_team.memory.self_improvement_runtime import persist_run_metrics

    persist_run_metrics(pr)
    _run_post_run_quality_gates(profile)


def _print_run_result(pr: ProjectResult, opts: RunOptions) -> int:
    raw = pr.raw
    out: dict[str, object] = {
        "backend": pr.backend_name,
        "team_profile": pr.team_profile,
        "success": pr.success,
        "error": pr.error,
        "result": raw.get("result"),
        "state": raw.get("state"),
    }
    if opts.backend_name == "langgraph":
        out["thread_id"] = raw.get("thread_id")
    if opts.backend_name in _CLAUDE_BACKENDS:
        out["session_id"] = raw.get("session_id")
        out["workspace"] = raw.get("workspace")
    print(json.dumps(out, indent=2, default=str))
    return 0 if pr.success else 1


def _base_run_kw(opts: RunOptions, monitor: TeamMonitor | None) -> dict[str, Any]:
    return {
        "monitor": monitor,
        "skip_estimate": opts.skip_estimate,
        "complexity_override": opts.complexity,
        "run_label": opts.run_name,
    }


def _apply_langgraph_kw(kw: dict[str, Any], opts: RunOptions) -> None:
    if opts.thread_id.strip():
        kw["thread_id"] = opts.thread_id.strip()
    if opts.langgraph_mode is not None:
        kw["graph_mode"] = opts.langgraph_mode


def _apply_claude_kw(kw: dict[str, Any], opts: RunOptions, hitl_default: str) -> None:
    resume_thr = (opts.resume_thread or "").strip()
    if resume_thr:
        kw["resume_session_id"] = resume_thr
    if opts.fork_session:
        kw["fork_session"] = True
    if opts.claude_budget is not None:
        kw["max_budget_usd"] = opts.claude_budget
    if hitl_default:
        kw["hitl_default_answer"] = hitl_default
    if opts.thread_id.strip():
        kw["thread_id"] = opts.thread_id.strip()


def _run_langgraph_resume(
    backend: Any, opts: RunOptions, profile: TeamProfile, monitor: TeamMonitor | None
) -> int:
    from ai_team.backends.langgraph_backend.backend import LangGraphBackend

    if not isinstance(backend, LangGraphBackend):
        print("Error: resume requires LangGraph backend.", file=sys.stderr)
        return 1
    resume_kw: dict[str, Any] = {
        "monitor": monitor,
        "skip_estimate": opts.skip_estimate,
        "complexity_override": opts.complexity,
    }
    if opts.langgraph_mode is not None:
        resume_kw["graph_mode"] = opts.langgraph_mode
    pr = backend.resume(opts.resume_thread.strip(), opts.resume_input, profile, **resume_kw)
    _finish_run(pr, profile)
    return _print_run_result(pr, opts)


def _run_langgraph_stream(
    backend: Any, opts: RunOptions, profile: TeamProfile, monitor: TeamMonitor | None
) -> int:
    from ai_team.backends.langgraph_backend.backend import LangGraphBackend

    if not isinstance(backend, LangGraphBackend):
        print("Error: internal backend type mismatch.", file=sys.stderr)
        return 1
    use_tui = monitor is not None
    if monitor:
        monitor.start()
    run_kw = _base_run_kw(opts, monitor if use_tui else None)
    _apply_langgraph_kw(run_kw, opts)
    print_jsonl = opts.stream and not use_tui
    try:
        for ev in backend.iter_stream_events(opts.description.strip(), profile, **run_kw):
            if print_jsonl:
                print(json.dumps(ev, default=str))
    finally:
        if monitor:
            monitor.stop()
    return 0


def _run_claude_stream(
    backend: Any, opts: RunOptions, profile: TeamProfile, monitor: TeamMonitor | None
) -> int:
    from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend
    from ai_team.config.settings import get_settings

    if not isinstance(backend, ClaudeAgentBackend):
        print("Error: internal backend type mismatch.", file=sys.stderr)
        return 1
    has_desc = bool((opts.description or "").strip())
    desc = (
        opts.description.strip()
        if has_desc
        else "Continue the project from the saved Claude session and workspace logs."
    )
    use_tui = monitor is not None
    if monitor:
        monitor.start()
    hitl_default = (get_settings().human_feedback.default_response or "").strip()
    run_kw = _base_run_kw(opts, monitor if use_tui else None)
    _apply_claude_kw(run_kw, opts, hitl_default)
    print_jsonl = opts.stream and not use_tui

    async def _stream_claude() -> None:
        async for ev in backend.stream(desc, profile, env=opts.env, **run_kw):
            if print_jsonl:
                print(json.dumps(ev, default=str))

    try:
        asyncio.run(_stream_claude())
    finally:
        if monitor:
            monitor.stop()
    return 0


def _run_backend_sync(
    backend: Any, opts: RunOptions, profile: TeamProfile, monitor: TeamMonitor | None
) -> int:
    from ai_team.config.settings import get_settings

    hitl_default = (get_settings().human_feedback.default_response or "").strip()
    run_kw = _base_run_kw(opts, monitor)
    if opts.backend_name == "langgraph":
        _apply_langgraph_kw(run_kw, opts)
    if opts.backend_name in _CLAUDE_BACKENDS:
        _apply_claude_kw(run_kw, opts, hitl_default)
    desc_run = opts.description.strip() if (opts.description or "").strip() else ""
    if not desc_run:
        desc_run = "Continue from previous run (no new description text provided)."
    pr = backend.run(desc_run, profile, env=opts.env, **run_kw)
    _finish_run(pr, profile)
    return _print_run_result(pr, opts)


def _dispatch_run(opts: RunOptions, profile: TeamProfile, monitor: TeamMonitor | None) -> int:
    backend = get_backend(opts.backend_name)
    resume_thr = (opts.resume_thread or "").strip()
    use_tui = monitor is not None

    if not os.environ.get("AI_TEAM_SKIP_POST_RUN"):
        from ai_team.memory.self_improvement_runtime import maybe_extract_lessons_at_startup

        maybe_extract_lessons_at_startup()

    if opts.backend_name == "langgraph" and resume_thr:
        return _run_langgraph_resume(backend, opts, profile, monitor)
    if opts.backend_name == "langgraph" and (opts.stream or use_tui):
        return _run_langgraph_stream(backend, opts, profile, monitor)
    if opts.backend_name in _CLAUDE_BACKENDS and (opts.stream or use_tui):
        return _run_claude_stream(backend, opts, profile, monitor)
    return _run_backend_sync(backend, opts, profile, monitor)


def execute_run(opts: RunOptions) -> int:
    """Run the selected backend. Callable from tests without argparse."""
    resume_thr = (opts.resume_thread or "").strip()
    has_desc = bool((opts.description or "").strip())
    if not resume_thr and not has_desc:
        return 2
    if opts.env is not None:
        os.environ["AI_TEAM_ENV"] = opts.env
    try:
        profile = load_team_profile(opts.team)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    monitor = _maybe_monitor(opts)
    try:
        return _dispatch_run(opts, profile, monitor)
    except Exception as e:
        logger.exception("ai_team_run_failed", error=str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1
