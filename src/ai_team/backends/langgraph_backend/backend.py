"""LangGraph backend: main graph with checkpointer, stream, and resume (Phase 8)."""

from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from ai_team.backends.langgraph_backend.checkpointer import (
    run_with_postgres_checkpointer,
)
from ai_team.backends.langgraph_backend.graphs.main_graph import (
    GraphMode,
    compile_main_graph,
)
from ai_team.backends.langgraph_backend.graphs.spend_guard import (
    BudgetExceededError,
    reset_spend_guard,
)
from ai_team.config.settings import reload_settings
from ai_team.core.payload_flatten import flatten_state_payload
from ai_team.core.result import ProjectResult
from ai_team.core.results import ResultsBundle, scorecard_from_langgraph_state
from ai_team.core.run_naming import resolve_run_id
from ai_team.core.stream_helpers import stream_via_threaded_run
from ai_team.core.team_profile import TeamProfile
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

logger = structlog.get_logger(__name__)

DEFAULT_RECURSION_LIMIT = 50


def _recursion_limit() -> int:
    """Graph superstep cap; override via AI_TEAM_LANGGRAPH_RECURSION_LIMIT."""
    raw = (os.environ.get("AI_TEAM_LANGGRAPH_RECURSION_LIMIT") or "").strip()
    if not raw:
        return DEFAULT_RECURSION_LIMIT
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning("bad_recursion_limit_env", value=raw, fallback=DEFAULT_RECURSION_LIMIT)
        return DEFAULT_RECURSION_LIMIT


class LangGraphBackend:
    """Runs the compiled LangGraph main graph (placeholder or full subgraph wiring)."""

    name: str = "langgraph"

    def _graph_mode(self, kwargs: dict[str, Any]) -> GraphMode:
        raw_mode = kwargs.get("graph_mode") or os.environ.get(
            "AI_TEAM_LANGGRAPH_GRAPH_MODE", "placeholder"
        )
        return cast(
            GraphMode,
            raw_mode if raw_mode in ("placeholder", "full") else "placeholder",
        )

    def _build_initial_state(
        self,
        description: str,
        profile: TeamProfile,
        thread_id: str,
    ) -> dict[str, Any]:
        return {
            "project_description": description,
            # Keep project_id stable and aligned with checkpoint thread id.
            "project_id": thread_id,
            "current_phase": "intake",
            "phase_history": [],
            "errors": [],
            "retry_count": 0,
            "max_retries": 3,
            "messages": [],
            "generated_files": [],
            "metadata": {
                "team_profile": profile.name,
                "agents": profile.agents,
                "phases": profile.phases,
                "model_overrides": profile.model_overrides,
                "profile_rag": profile.metadata.get("rag"),
            },
        }

    def _compile_for_run(
        self,
        mode: GraphMode,
        checkpointer: BaseCheckpointSaver | None,
    ) -> CompiledStateGraph:
        return compile_main_graph(mode=mode, checkpointer=checkpointer)

    def run(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> ProjectResult:
        """Invoke the main graph; ``ProjectResult.raw`` holds ``state`` and ``thread_id``.

        Keyword arguments:
            thread_id: Optional LangGraph checkpointer thread id.
            graph_mode: ``placeholder`` (default, no LLM in main nodes) or ``full``
                (Phase-3 subgraphs). When omitted, ``AI_TEAM_LANGGRAPH_GRAPH_MODE`` is used.
            resume_thread_id: If set with ``resume_input``, invokes ``Command(resume=...)``
                instead of a fresh ``initial_state``.

        In ``full`` mode, ``human_review`` may call ``interrupt()``; resume with LangGraph
        ``Command(resume=...)`` using the same thread id.
        """
        _ = env
        resume_tid = (kwargs.get("resume_thread_id") or "").strip()
        if resume_tid:
            return self.resume(
                resume_tid,
                str(kwargs.get("resume_input", "")),
                profile,
                **kwargs,
            )
        try:
            mode = self._graph_mode(kwargs)
            thread_id = resolve_run_id(
                description=description,
                team_profile=profile.name,
                run_label=str(kwargs.get("run_label") or ""),
                thread_id=str(kwargs.get("thread_id") or ""),
            )
            # Per-run workspace isolation (tools write under workspace/<project_id>/).
            try:
                ws_override = kwargs.get("workspace_dir")
                ws_path = (
                    str(ws_override) if ws_override else os.path.join("./workspace", thread_id)
                )
                os.environ["PROJECT_WORKSPACE_DIR"] = ws_path
                reload_settings()
            except Exception:
                pass
            b = ResultsBundle(thread_id)
            try:
                meta = b.default_run_metadata(
                    backend=self.name,
                    team_profile=profile.name,
                    env=env,
                    argv=[],
                    extra={"graph_mode": mode},
                )
                b.write_run(meta)
            except Exception:
                pass
            # Reset the per-run spend guard so a crash/retry loop can't burn
            # money unbounded. Budget resolves from AI_TEAM_RUN_BUDGET_USD (or a
            # run_budget_usd kwarg); 0 disables the ceiling but keeps tracking.
            reset_spend_guard(kwargs.get("run_budget_usd"))
            initial_state = self._build_initial_state(description, profile, thread_id)
            # Cap total graph supersteps explicitly rather than relying on the
            # LangGraph default (25). Bounds a pathological loop deterministically;
            # override via AI_TEAM_LANGGRAPH_RECURSION_LIMIT.
            config: dict[str, Any] = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": _recursion_limit(),
            }
            pg_uri = (os.environ.get("AI_TEAM_LANGGRAPH_POSTGRES_URI") or "").strip()
            if pg_uri:

                def _run(cp: BaseCheckpointSaver) -> Any:
                    g = self._compile_for_run(mode, cp)
                    return g.invoke(initial_state, config)

                final = run_with_postgres_checkpointer(pg_uri, _run)
            else:
                g = self._compile_for_run(mode, None)
                final = g.invoke(initial_state, config)
            state_dict: dict[str, Any] = final if isinstance(final, dict) else {"state": final}
            # Self-improvement capture should not depend on result bundle persistence.
            with contextlib.suppress(Exception):
                from ai_team.memory.lessons import record_run_failures

                record_run_failures(
                    run_id=thread_id,
                    backend=self.name,
                    team_profile=profile.name,
                    state=state_dict,
                )
            try:
                # Persist final state + derived artifacts.
                b.write_state(final if isinstance(final, dict) else {"state": final})
                # Planning artifacts (best-effort).
                planning_req = state_dict.get("requirements") or {}
                planning_arch = state_dict.get("architecture") or {}
                if planning_req:
                    b.write_artifact_json("planning", "requirements.json", planning_req)
                if planning_arch:
                    b.write_artifact_json("planning", "architecture.json", planning_arch)
                # Testing artifacts (best-effort).
                tr = state_dict.get("test_results") or {}
                if tr:
                    b.write_artifact_json("testing", "test_results.json", tr)
                    lint_out = ((tr.get("lint") or {}).get("output") or "").strip()
                    test_out = ((tr.get("tests") or {}).get("output") or "").strip()
                    if lint_out:
                        b.write_artifact_text("testing", "ruff.txt", lint_out + "\n")
                    if test_out:
                        b.write_artifact_text("testing", "pytest.txt", test_out + "\n")
                b.write_scorecard(scorecard_from_langgraph_state(thread_id, state_dict))
            except Exception:
                pass
            return ProjectResult(
                backend_name=self.name,
                success=bool(
                    (final.get("current_phase") if isinstance(final, dict) else None) == "complete"
                ),
                raw={"state": flatten_state_payload(final), "thread_id": thread_id},
                team_profile=profile.name,
            )
        except BudgetExceededError as e:
            # Spend ceiling hit: a deliberate, non-retryable abort. Fail the run
            # cleanly rather than letting it bubble as an unhandled BaseException.
            logger.error("langgraph_backend_budget_abort", error=str(e))
            return ProjectResult(
                backend_name=self.name,
                success=False,
                raw={"state": {"current_phase": "error"}, "thread_id": thread_id},
                error=str(e),
                team_profile=profile.name,
            )
        except Exception as e:
            logger.exception("langgraph_backend_run_failed", error=str(e))
            return ProjectResult(
                backend_name=self.name,
                success=False,
                raw={},
                error=str(e),
                team_profile=profile.name,
            )

    def resume(
        self,
        thread_id: str,
        resume_input: str,
        profile: TeamProfile,
        **kwargs: Any,
    ) -> ProjectResult:
        """
        Resume an interrupted graph with ``Command(resume=...)`` (e.g. HITL).

        ``thread_id`` must match the checkpoint thread used when the interrupt occurred.
        """
        _ = profile
        try:
            mode = self._graph_mode(kwargs)
            config: dict[str, Any] = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": _recursion_limit(),
            }
            cmd = Command(resume=resume_input)
            b = ResultsBundle(thread_id)
            pg_uri = (os.environ.get("AI_TEAM_LANGGRAPH_POSTGRES_URI") or "").strip()
            if pg_uri:

                def _run(cp: BaseCheckpointSaver) -> Any:
                    g = self._compile_for_run(mode, cp)
                    return g.invoke(cmd, config)

                final = run_with_postgres_checkpointer(pg_uri, _run)
            else:
                g = self._compile_for_run(mode, None)
                final = g.invoke(cmd, config)
            try:
                final_dict = final if isinstance(final, dict) else {"state": final}
                b.write_state(final_dict)
                b.write_scorecard(scorecard_from_langgraph_state(thread_id, final_dict))
            except Exception:
                pass
            return ProjectResult(
                backend_name=self.name,
                success=True,
                raw={"state": flatten_state_payload(final), "thread_id": thread_id},
                team_profile=profile.name,
            )
        except Exception as e:
            logger.exception("langgraph_backend_resume_failed", error=str(e))
            return ProjectResult(
                backend_name=self.name,
                success=False,
                raw={},
                error=str(e),
                team_profile=profile.name,
            )

    def iter_stream_events(
        self,
        description: str,
        profile: TeamProfile,
        **kwargs: Any,
    ) -> Iterator[dict[str, Any]]:
        """
        Stream LangGraph ``updates`` (and final state) for CLI/TUI/web progress.

        Yields dicts with ``type`` of ``langgraph_update`` | ``langgraph_done`` | ``langgraph_error``.
        """
        mode = self._graph_mode(kwargs)
        thread_id = resolve_run_id(
            description=description,
            team_profile=profile.name,
            run_label=str(kwargs.get("run_label") or ""),
            thread_id=str(kwargs.get("thread_id") or ""),
        )
        try:
            os.environ["PROJECT_WORKSPACE_DIR"] = os.path.join("./workspace", thread_id)
            reload_settings()
        except Exception:
            pass
        reset_spend_guard(kwargs.get("run_budget_usd"))
        initial_state = self._build_initial_state(description, profile, thread_id)
        config: dict[str, Any] = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": _recursion_limit(),
        }
        monitor = kwargs.get("monitor")
        b = ResultsBundle(thread_id)
        try:
            meta = b.default_run_metadata(
                backend=self.name,
                team_profile=profile.name,
                env=None,
                argv=[],
                extra={"graph_mode": mode},
            )
            b.write_run(meta)
        except Exception:
            pass

        yield {
            "type": "run_started",
            "backend": self.name,
            "team_profile": profile.name,
            "thread_id": thread_id,
        }
        with contextlib.suppress(Exception):
            b.append_event(
                {
                    "type": "run_started",
                    "backend": self.name,
                    "team_profile": profile.name,
                    "thread_id": thread_id,
                    "ts": str(datetime.now(UTC).isoformat()),
                }
            )

        try:
            pg_uri = (os.environ.get("AI_TEAM_LANGGRAPH_POSTGRES_URI") or "").strip()

            def _stream_graph(g: CompiledStateGraph) -> Iterator[dict[str, Any]]:
                for chunk in g.stream(
                    initial_state,
                    config,
                    stream_mode="updates",
                ):
                    ev: dict[str, Any] = {
                        "type": "langgraph_update",
                        "thread_id": thread_id,
                        "chunk": chunk,
                    }
                    if monitor is not None and hasattr(monitor, "on_langgraph_update"):
                        monitor.on_langgraph_update(chunk)
                    with contextlib.suppress(Exception):
                        b.append_event({"type": "langgraph_update", "chunk": chunk})
                    yield ev
                snap = g.get_state(config)
                try:
                    final_state = cast(dict[str, Any], snap.values)
                    with contextlib.suppress(Exception):
                        from ai_team.memory.lessons import record_run_failures

                        record_run_failures(
                            run_id=thread_id,
                            backend=self.name,
                            team_profile=profile.name,
                            state=final_state,
                        )
                    b.write_state(final_state)
                    # Planning artifacts (best-effort).
                    planning_req = final_state.get("requirements") or {}
                    planning_arch = final_state.get("architecture") or {}
                    if planning_req:
                        b.write_artifact_json("planning", "requirements.json", planning_req)
                    if planning_arch:
                        b.write_artifact_json("planning", "architecture.json", planning_arch)
                    # Testing artifacts (best-effort).
                    tr = final_state.get("test_results") or {}
                    if tr:
                        b.write_artifact_json("testing", "test_results.json", tr)
                        lint_out = ((tr.get("lint") or {}).get("output") or "").strip()
                        test_out = ((tr.get("tests") or {}).get("output") or "").strip()
                        if lint_out:
                            b.write_artifact_text("testing", "ruff.txt", lint_out + "\n")
                        if test_out:
                            b.write_artifact_text("testing", "pytest.txt", test_out + "\n")
                    b.append_event({"type": "langgraph_done"})
                    b.write_scorecard(scorecard_from_langgraph_state(thread_id, final_state))
                except Exception:
                    pass
                yield {
                    "type": "langgraph_done",
                    "thread_id": thread_id,
                    "state": snap.values,
                }

            if pg_uri:
                from langgraph.checkpoint.postgres import PostgresSaver

                with PostgresSaver.from_conn_string(pg_uri) as cp:
                    cp.setup()
                    g = self._compile_for_run(mode, cp)
                    yield from _stream_graph(g)
            else:
                g = self._compile_for_run(mode, None)
                yield from _stream_graph(g)
        except BudgetExceededError as e:
            logger.error("langgraph_stream_budget_abort", error=str(e))
            yield {
                "type": "langgraph_error",
                "thread_id": thread_id,
                "error": str(e),
                "budget_exceeded": True,
            }
        except Exception as e:
            logger.exception("langgraph_stream_failed", error=str(e))
            yield {
                "type": "langgraph_error",
                "thread_id": thread_id,
                "error": str(e),
            }

    async def stream(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield stream events when ``stream_graph`` is true; otherwise start/finish around ``run``."""
        stream_graph = bool(kwargs.pop("stream_graph", False))
        if stream_graph:
            for ev in self.iter_stream_events(description, profile, **kwargs):
                yield ev
            return
        async for event in stream_via_threaded_run(
            backend_name=self.name,
            run_fn=self.run,
            description=description,
            profile=profile,
            env=env,
            **kwargs,
        ):
            yield event
