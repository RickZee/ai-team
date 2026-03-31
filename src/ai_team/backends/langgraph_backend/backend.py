"""LangGraph backend: main graph with checkpointer, stream, and resume (Phase 8)."""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import structlog
from ai_team.backends.langgraph_backend.checkpointer import (
    run_with_postgres_checkpointer,
)
from ai_team.backends.langgraph_backend.graphs.main_graph import (
    GraphMode,
    compile_main_graph,
)
from ai_team.config.settings import reload_settings
from ai_team.core.result import ProjectResult
from ai_team.core.results import ResultsBundle, Scorecard
from ai_team.core.team_profile import TeamProfile
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

logger = structlog.get_logger(__name__)


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
            thread_id = str(kwargs.get("thread_id") or uuid4())
            # Per-run workspace isolation (tools write under workspace/<project_id>/).
            try:
                os.environ["PROJECT_WORKSPACE_DIR"] = os.path.join("./workspace", thread_id)
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
            initial_state = self._build_initial_state(description, profile, thread_id)
            config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
            pg_uri = (os.environ.get("AI_TEAM_LANGGRAPH_POSTGRES_URI") or "").strip()
            if pg_uri:

                def _run(cp: BaseCheckpointSaver) -> Any:
                    g = self._compile_for_run(mode, cp)
                    return g.invoke(initial_state, config)

                final = run_with_postgres_checkpointer(pg_uri, _run)
            else:
                g = self._compile_for_run(mode, None)
                final = g.invoke(initial_state, config)
            try:
                # Persist final state + derived artifacts.
                b.write_state(final if isinstance(final, dict) else {"state": final})
                state_dict: dict[str, Any] = final if isinstance(final, dict) else {"state": final}
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
                b.write_scorecard(Scorecard(status="complete"))
            except Exception:
                pass
            return ProjectResult(
                backend_name=self.name,
                success=True,
                raw={"state": final, "thread_id": thread_id},
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
            config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
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
                b.write_state(final if isinstance(final, dict) else {"state": final})
                b.write_scorecard(Scorecard(status="complete"))
            except Exception:
                pass
            return ProjectResult(
                backend_name=self.name,
                success=True,
                raw={"state": final, "thread_id": thread_id},
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
        Stream LangGraph ``updates`` (and final state) for CLI/TUI/Gradio progress.

        Yields dicts with ``type`` of ``langgraph_update`` | ``langgraph_done`` | ``langgraph_error``.
        """
        mode = self._graph_mode(kwargs)
        thread_id = str(kwargs.get("thread_id") or uuid4())
        try:
            os.environ["PROJECT_WORKSPACE_DIR"] = os.path.join("./workspace", thread_id)
            reload_settings()
        except Exception:
            pass
        initial_state = self._build_initial_state(description, profile, thread_id)
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
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
                    b.write_scorecard(Scorecard(status="complete"))
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
        yield {
            "type": "run_started",
            "backend": self.name,
            "team_profile": profile.name,
        }
        result = await asyncio.to_thread(self.run, description, profile, env, **kwargs)
        yield {
            "type": "run_finished",
            "backend": self.name,
            "success": result.success,
            "result": result.model_dump(),
        }
