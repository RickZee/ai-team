"""Run the top-level Claude Agent SDK ``query()`` for a team profile."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import structlog
from ai_team.backends.claude_agent_sdk_backend.agents.builder import (
    build_agent_definitions,
    orchestrator_system_prompt,
    orchestrator_user_prompt,
)
from ai_team.backends.claude_agent_sdk_backend.agents.definitions import (
    default_orchestrator_allowed_tools,
)
from ai_team.backends.claude_agent_sdk_backend.costs import append_cost_log
from ai_team.backends.claude_agent_sdk_backend.hooks.audit import (
    build_audit_hook,
    build_subagent_audit_hook,
)
from ai_team.backends.claude_agent_sdk_backend.hooks.quality import build_quality_post_tool_hook
from ai_team.backends.claude_agent_sdk_backend.hooks.security import build_security_pre_tool_hook
from ai_team.backends.claude_agent_sdk_backend.reasoning_log import append_thinking
from ai_team.backends.claude_agent_sdk_backend.tools.mcp_server import build_ai_team_mcp_server
from ai_team.backends.claude_agent_sdk_backend.tools.permissions import MCP_SERVER_KEY
from ai_team.backends.claude_agent_sdk_backend.workspace import (
    infer_repo_root,
    read_claude_md_excerpt,
)
from ai_team.config.settings import get_settings
from ai_team.core.team_profile import TeamProfile
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    Message,
    ResultMessage,
    query,
)
from claude_agent_sdk.types import (
    PermissionResultAllow,
    ThinkingBlock,
    ThinkingConfigAdaptive,
    ToolPermissionContext,
)

logger = structlog.get_logger(__name__)


def _anthropic_api_key() -> str:
    """Resolve API key from environment first, then :class:`Settings`."""
    k = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if k:
        return k
    try:
        return (get_settings().anthropic.api_key or "").strip()
    except Exception:
        return ""


def _ensure_api_key_in_env(key: str) -> None:
    """SDK subprocesses read ``ANTHROPIC_API_KEY`` from the environment."""
    if key and not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        os.environ["ANTHROPIC_API_KEY"] = key


def _hitl_can_use_tool_factory(
    default_answer: str,
) -> Callable[[str, dict[str, Any], ToolPermissionContext], Awaitable[Any]]:
    """Auto-answer ``AskUserQuestion`` when a default string is configured."""

    async def can_use_tool(
        tool_name: str,
        input_data: dict[str, Any],
        _ctx: ToolPermissionContext,
    ) -> PermissionResultAllow:
        if default_answer.strip() and tool_name == "AskUserQuestion":
            return PermissionResultAllow(
                updated_input={
                    **input_data,
                    "answers": [{"type": "text", "text": default_answer.strip()}],
                }
            )
        return PermissionResultAllow(updated_input=input_data)

    return can_use_tool


def _merge_mcp_servers(workspace: Path, profile: TeamProfile) -> dict[str, Any]:
    servers: dict[str, Any] = {MCP_SERVER_KEY: build_ai_team_mcp_server(workspace)}
    raw = profile.metadata.get("mcp_servers")
    if not isinstance(raw, dict):
        return servers
    for name, config in raw.items():
        if not isinstance(config, dict) or not name:
            continue
        transport = str(config.get("transport") or "stdio").lower()
        try:
            if transport == "stdio":
                cmd = config.get("command")
                if not cmd:
                    continue
                entry: dict[str, Any] = {
                    "command": str(cmd),
                    "args": list(config.get("args") or []),
                }
                env = config.get("env")
                if isinstance(env, dict):
                    entry["env"] = {str(k): str(v) for k, v in env.items()}
                servers[str(name)] = entry
            elif transport in ("http", "sse"):
                url = config.get("url")
                if not url:
                    continue
                servers[str(name)] = {
                    "type": "http" if transport == "http" else "sse",
                    "url": str(url),
                    "headers": {
                        str(k): str(v) for k, v in dict(config.get("headers") or {}).items()
                    },
                }
        except (TypeError, ValueError) as e:
            logger.warning("claude_mcp_server_skip", name=name, error=str(e))
    return servers


def _orchestrator_effort(profile: TeamProfile) -> str:
    meta_sdk = profile.metadata.get("claude_agent_sdk")
    if isinstance(meta_sdk, dict):
        v = meta_sdk.get("effort_orchestrator")
        if v in ("low", "medium", "high", "max"):
            return str(v)
    return "high"


def _use_tool_search(
    profile: TeamProfile, mcp_servers: dict[str, Any], explicit: bool | None
) -> bool:
    if explicit is not None:
        return bool(explicit)
    meta_sdk = profile.metadata.get("claude_agent_sdk")
    if isinstance(meta_sdk, dict) and meta_sdk.get("use_tool_search"):
        return True
    return len(mcp_servers) >= 3


def _build_options(
    *,
    description: str,
    profile: TeamProfile,
    workspace: Path,
    resume: str | None,
    fork_session: bool,
    max_budget_usd: float | None,
    max_turns: int | None,
    max_retries: int,
    include_partial_messages: bool,
    enable_file_checkpointing: bool,
    hitl_default_answer: str,
    use_tool_search: bool | None,
) -> tuple[ClaudeAgentOptions, str]:
    """Shared ClaudeAgentOptions for ``query()`` calls."""
    agents = build_agent_definitions(profile)
    if not agents:
        msg = (
            f"No Claude subagents built for profile {profile.name!r}. "
            "Ensure phases and agents overlap in team_profiles.yaml."
        )
        raise ValueError(msg)

    repo = infer_repo_root(workspace)
    sys_pre = orchestrator_system_prompt(profile, max_retries=max_retries)
    claude_md = read_claude_md_excerpt(repo)
    if claude_md.strip():
        sys_pre += "\n\n## Repository conventions (CLAUDE.md)\n\n" + claude_md.strip()

    profile_md = workspace / "docs" / "CLAUDE_PROFILE.md"
    if profile_md.is_file():
        sys_pre += (
            "\n\n## Team profile (this run)\n\nRead `docs/CLAUDE_PROFILE.md` in the workspace "
            "for agents, phases, and knowledge topics.\n"
        )

    rag = profile.metadata.get("rag")
    if isinstance(rag, dict):
        topics = rag.get("knowledge_topics")
        if topics:
            sys_pre += f"\n\n## Profile knowledge topics\n{topics!r}\n"

    meta_sdk = profile.metadata.get("claude_agent_sdk")
    include_skills = bool(isinstance(meta_sdk, dict) and meta_sdk.get("enable_skills"))

    security_hook = build_security_pre_tool_hook(workspace)
    quality_hook = build_quality_post_tool_hook(workspace)
    audit_path = workspace / "logs" / "audit.jsonl"
    audit_hook = build_audit_hook(audit_path)
    subagent_audit = build_subagent_audit_hook(audit_path)

    hooks: dict[str, list[HookMatcher]] = {
        "PreToolUse": [
            HookMatcher(matcher="Write|Edit|Bash|MultiEdit", hooks=[security_hook]),
        ],
        "PostToolUse": [
            HookMatcher(matcher="Write|Edit|MultiEdit", hooks=[quality_hook]),
            HookMatcher(hooks=[audit_hook]),
        ],
        "SubagentStart": [HookMatcher(hooks=[subagent_audit])],
        "SubagentStop": [HookMatcher(hooks=[subagent_audit])],
    }

    mcp_servers = _merge_mcp_servers(workspace, profile)
    want_search = _use_tool_search(profile, mcp_servers, use_tool_search)
    tools = list(default_orchestrator_allowed_tools(include_skill=include_skills))
    if want_search and "ToolSearch" not in tools:
        tools.append("ToolSearch")

    can_use: Any = None
    if hitl_default_answer.strip():
        can_use = _hitl_can_use_tool_factory(hitl_default_answer)

    opts = ClaudeAgentOptions(
        cwd=str(workspace.resolve()),
        system_prompt=sys_pre,
        agents=agents,
        allowed_tools=tools,
        permission_mode="acceptEdits",
        max_turns=max_turns or 50,
        max_budget_usd=max_budget_usd,
        resume=resume,
        fork_session=fork_session,
        mcp_servers=mcp_servers,
        hooks=hooks,
        add_dirs=[str(repo)],
        include_partial_messages=include_partial_messages,
        thinking=ThinkingConfigAdaptive(type="adaptive"),
        effort=_orchestrator_effort(profile),
        enable_file_checkpointing=enable_file_checkpointing,
        can_use_tool=can_use,
    )
    return opts, orchestrator_user_prompt(description)


async def iter_orchestrator_messages(
    description: str,
    profile: TeamProfile,
    workspace: Path,
    *,
    resume: str | None = None,
    fork_session: bool = False,
    max_budget_usd: float | None = None,
    max_turns: int | None = None,
    max_retries: int = 3,
    include_partial_messages: bool = False,
    enable_file_checkpointing: bool = False,
    log_reasoning: bool = False,
    hitl_default_answer: str = "",
    use_tool_search: bool | None = None,
) -> AsyncIterator[Message]:
    """Yield every message from the orchestrator ``query()`` (streaming-friendly)."""
    key = _anthropic_api_key()
    if not key:
        msg = "ANTHROPIC_API_KEY (or Settings.anthropic.api_key) is required for the claude-agent-sdk backend."
        raise ValueError(msg)
    _ensure_api_key_in_env(key)

    opts, user_prompt = _build_options(
        description=description,
        profile=profile,
        workspace=workspace,
        resume=resume,
        fork_session=fork_session,
        max_budget_usd=max_budget_usd,
        max_turns=max_turns,
        max_retries=max_retries,
        include_partial_messages=include_partial_messages,
        enable_file_checkpointing=enable_file_checkpointing,
        hitl_default_answer=hitl_default_answer,
        use_tool_search=use_tool_search,
    )
    async for msg in query(prompt=user_prompt, options=opts):
        if log_reasoning and isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, ThinkingBlock) and block.thinking:
                    append_thinking(
                        workspace,
                        thinking=block.thinking,
                        session_id=msg.session_id,
                        model=msg.model,
                    )
        yield msg


async def run_orchestrator(
    description: str,
    profile: TeamProfile,
    workspace: Path,
    *,
    resume: str | None = None,
    fork_session: bool = False,
    max_budget_usd: float | None = None,
    max_turns: int | None = None,
    max_retries: int = 3,
    include_partial_messages: bool = False,
    enable_file_checkpointing: bool = False,
    log_reasoning: bool = False,
    hitl_default_answer: str = "",
    use_tool_search: bool | None = None,
) -> ResultMessage | None:
    """
    Execute one orchestrator ``query()`` and return the final :class:`ResultMessage` if any.

    Raises:
        ValueError: If the API key is unset or no subagents are defined.
    """
    last: ResultMessage | None = None
    async for msg in iter_orchestrator_messages(
        description,
        profile,
        workspace,
        resume=resume,
        fork_session=fork_session,
        max_budget_usd=max_budget_usd,
        max_turns=max_turns,
        max_retries=max_retries,
        include_partial_messages=include_partial_messages,
        enable_file_checkpointing=enable_file_checkpointing,
        log_reasoning=log_reasoning,
        hitl_default_answer=hitl_default_answer,
        use_tool_search=use_tool_search,
    ):
        if isinstance(msg, ResultMessage):
            last = msg

    if last is not None:
        append_cost_log(
            workspace,
            phase="orchestrator",
            cost_usd=last.total_cost_usd,
            usage=last.usage,
        )
    return last
