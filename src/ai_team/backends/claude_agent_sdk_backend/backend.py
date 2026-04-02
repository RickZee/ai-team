"""Claude Agent SDK :class:`Backend` implementation."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog
from ai_team.backends.claude_agent_sdk_backend.costs import default_total_budget_usd
from ai_team.backends.claude_agent_sdk_backend.orchestrator import (
    iter_orchestrator_messages,
    run_orchestrator,
)
from ai_team.backends.claude_agent_sdk_backend.recovery import run_orchestrator_with_recovery
from ai_team.backends.claude_agent_sdk_backend.streaming import (
    feed_monitor_from_claude_result,
    feed_monitor_from_stream_event,
    stream_event_to_dict,
)
from ai_team.backends.claude_agent_sdk_backend.workspace import (
    collect_deployment_hints,
    ensure_workspace_layout,
    list_files_under,
    read_json_if_exists,
    read_jsonl,
    read_text_if_exists,
    write_profile_claude_context,
    write_session_record,
)
from ai_team.backends.claude_agent_sdk_backend.workspace_snapshots import (
    restore_workspace_subtrees,
    snapshot_workspace_subtrees,
)
from ai_team.config.settings import reload_settings
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile
from claude_agent_sdk import ResultMessage, StreamEvent

logger = structlog.get_logger(__name__)


class ClaudeAgentBackend:
    """Run the multi-agent pipeline via Anthropic's Claude Agent SDK (Claude Code CLI)."""

    name: str = "claude-agent-sdk"

    def _workspace_path(self, kwargs: dict[str, Any]) -> Path:
        tid = str(kwargs.get("thread_id") or uuid4())
        raw = kwargs.get("workspace_dir")
        if raw:
            return Path(str(raw)).resolve()
        return (Path.cwd() / "workspace" / tid).resolve()

    def run(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> ProjectResult:
        """Execute orchestrator ``query()``; map workspace artifacts to :class:`ProjectResult`."""
        _ = env
        workspace = self._workspace_path(kwargs)
        try:
            os.environ["PROJECT_WORKSPACE_DIR"] = str(workspace)
            reload_settings()
        except Exception:
            pass

        ensure_workspace_layout(workspace, description)
        write_profile_claude_context(workspace, profile)

        snap_tag = kwargs.get("workspace_snapshot_tag")
        do_snap = bool(kwargs.get("workspace_snapshot")) or bool(snap_tag)
        snapshot_name = str(snap_tag or "pre_run")
        if do_snap:
            snapshot_workspace_subtrees(workspace, snapshot_name)

        resume = (kwargs.get("resume_session_id") or "").strip() or None
        fork_session = bool(kwargs.get("fork_session", False))
        budget = kwargs.get("max_budget_usd")
        max_budget = float(budget) if budget is not None else default_total_budget_usd()
        max_turns = kwargs.get("max_turns")
        max_turns_i = int(max_turns) if max_turns is not None else None
        checkpointing = bool(kwargs.get("enable_file_checkpointing", False))
        recovery_attempts = max(1, int(kwargs.get("recovery_max_attempts", 1)))
        orch_kw: dict[str, Any] = {
            "resume": resume,
            "fork_session": fork_session,
            "max_budget_usd": max_budget,
            "max_turns": max_turns_i,
            "max_retries": int(kwargs.get("max_retries", 3)),
            "include_partial_messages": False,
            "enable_file_checkpointing": checkpointing,
            "log_reasoning": bool(kwargs.get("log_reasoning", True)),
            "hitl_default_answer": str(kwargs.get("hitl_default_answer", "")),
            "use_tool_search": kwargs.get("use_tool_search"),
        }

        try:
            if recovery_attempts > 1:
                result_msg, _rec_logs = asyncio.run(
                    run_orchestrator_with_recovery(
                        description,
                        profile,
                        workspace,
                        recovery_max_attempts=recovery_attempts,
                        **orch_kw,
                    )
                )
            else:
                result_msg = asyncio.run(
                    run_orchestrator(
                        description,
                        profile,
                        workspace,
                        **orch_kw,
                    )
                )
        except ValueError as e:
            logger.warning("claude_agent_backend_config_error", error=str(e))
            if bool(kwargs.get("restore_workspace_on_failure")) and do_snap:
                restore_workspace_subtrees(workspace, snapshot_name)
            return ProjectResult(
                backend_name=self.name,
                success=False,
                raw={"workspace": str(workspace)},
                error=str(e),
                team_profile=profile.name,
            )
        except Exception as e:
            logger.exception("claude_agent_backend_run_failed", error=str(e))
            if bool(kwargs.get("restore_workspace_on_failure")) and do_snap:
                restore_workspace_subtrees(workspace, snapshot_name)
            return ProjectResult(
                backend_name=self.name,
                success=False,
                raw={"workspace": str(workspace)},
                error=str(e),
                team_profile=profile.name,
            )

        raw = self._collect_raw(workspace, result_msg)
        raw["team_profile"] = profile.name
        raw["agents"] = profile.agents
        raw["phases"] = profile.phases

        success = result_msg is not None and not result_msg.is_error
        err = (
            None
            if success
            else (
                result_msg.stop_reason or "error"
                if result_msg
                else "No result message from Claude Agent SDK"
            )
        )

        if (
            bool(kwargs.get("restore_workspace_on_failure"))
            and do_snap
            and (result_msg is None or result_msg.is_error)
        ):
            restore_workspace_subtrees(workspace, snapshot_name)

        if result_msg is not None:
            write_session_record(
                workspace,
                {
                    "session_id": result_msg.session_id,
                    "success": success,
                    "total_cost_usd": result_msg.total_cost_usd,
                    "stop_reason": result_msg.stop_reason,
                },
            )

        return ProjectResult(
            backend_name=self.name,
            success=success,
            raw=raw,
            error=err,
            team_profile=profile.name,
        )

    def _collect_raw(
        self,
        workspace: Path,
        result_msg: ResultMessage | None,
    ) -> dict[str, Any]:
        docs = workspace / "docs"
        src = workspace / "src"
        return {
            "workspace": str(workspace),
            "requirements": read_text_if_exists(docs / "requirements.md"),
            "architecture": read_text_if_exists(docs / "architecture.md"),
            "generated_files": list_files_under(src),
            "test_results": read_json_if_exists(docs / "test_results.json"),
            "deployment_config": collect_deployment_hints(workspace),
            "cost_usd": result_msg.total_cost_usd if result_msg else None,
            "session_id": result_msg.session_id if result_msg else None,
            "usage": result_msg.usage if result_msg else None,
            "phases": read_jsonl(workspace / "logs" / "phases.jsonl"),
        }

    async def stream(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield stream events; optionally forward to ``monitor`` (Rich TUI)."""
        _ = env
        workspace = self._workspace_path(kwargs)
        try:
            os.environ["PROJECT_WORKSPACE_DIR"] = str(workspace)
            reload_settings()
        except Exception:
            pass

        ensure_workspace_layout(workspace, description)
        write_profile_claude_context(workspace, profile)
        monitor = kwargs.get("monitor")

        resume = (kwargs.get("resume_session_id") or "").strip() or None
        fork_session = bool(kwargs.get("fork_session", False))
        budget = kwargs.get("max_budget_usd")
        max_budget = float(budget) if budget is not None else default_total_budget_usd()
        orch_stream_kw: dict[str, Any] = {
            "max_retries": int(kwargs.get("max_retries", 3)),
            "include_partial_messages": True,
            "enable_file_checkpointing": bool(kwargs.get("enable_file_checkpointing", False)),
            "log_reasoning": bool(kwargs.get("log_reasoning", True)),
            "hitl_default_answer": str(kwargs.get("hitl_default_answer", "")),
            "use_tool_search": kwargs.get("use_tool_search"),
        }

        yield {
            "type": "run_started",
            "backend": self.name,
            "team_profile": profile.name,
            "workspace": str(workspace),
        }

        last: ResultMessage | None = None
        try:
            async for msg in iter_orchestrator_messages(
                description,
                profile,
                workspace,
                resume=resume,
                fork_session=fork_session,
                max_budget_usd=max_budget,
                max_turns=int(kwargs["max_turns"]) if kwargs.get("max_turns") is not None else None,
                **orch_stream_kw,
            ):
                if isinstance(msg, StreamEvent):
                    feed_monitor_from_stream_event(monitor, msg)
                    yield stream_event_to_dict(msg)
                elif isinstance(msg, ResultMessage):
                    last = msg
                    feed_monitor_from_claude_result(
                        monitor,
                        session_id=msg.session_id,
                        cost_usd=msg.total_cost_usd,
                        stop_reason=msg.stop_reason,
                    )
                    yield {
                        "type": "result",
                        "success": not msg.is_error,
                        "cost_usd": msg.total_cost_usd,
                        "session_id": msg.session_id,
                        "stop_reason": msg.stop_reason,
                        "is_error": msg.is_error,
                    }
        except ValueError as e:
            yield {"type": "claude_error", "error": str(e)}
            return
        except Exception as e:
            logger.exception("claude_agent_backend_stream_failed", error=str(e))
            yield {"type": "claude_error", "error": str(e)}
            return

        raw = self._collect_raw(workspace, last)
        raw["team_profile"] = profile.name
        yield {
            "type": "run_finished",
            "backend": self.name,
            "success": last is not None and not last.is_error,
            "result": ProjectResult(
                backend_name=self.name,
                success=last is not None and not last.is_error,
                raw=raw,
                error=None
                if last is not None and not last.is_error
                else (last.stop_reason if last else "no result"),
                team_profile=profile.name,
            ).model_dump(),
        }
