"""Map Claude SDK stream events to monitor-friendly dicts."""

from __future__ import annotations

from typing import Any, Protocol

from claude_agent_sdk import StreamEvent


class SupportsClaudeMonitor(Protocol):
    """Subset of :class:`TeamMonitor` used for Claude streaming."""

    def on_agent_start(self, role: str, task: str, model: str = "") -> None: ...

    def on_log(self, agent: str, message: str, level: str = "info") -> None: ...


def stream_event_to_dict(message: StreamEvent) -> dict[str, Any]:
    """Normalize a :class:`StreamEvent` for JSONL / UI."""
    return {
        "type": "claude_stream",
        "session_id": message.session_id,
        "event": message.event,
    }


def feed_monitor_from_claude_result(
    monitor: SupportsClaudeMonitor | None,
    *,
    session_id: str | None,
    cost_usd: float | None,
    stop_reason: str | None = None,
) -> None:
    """Update Rich TUI metrics when a :class:`ResultMessage` arrives."""
    if monitor is None:
        return
    fn = getattr(monitor, "on_claude_result", None)
    if callable(fn):
        fn(session_id, cost_usd, stop_reason)


def feed_monitor_from_stream_event(
    monitor: SupportsClaudeMonitor | None, message: StreamEvent
) -> None:
    """Best-effort Rich TUI updates from partial stream events."""
    if monitor is None:
        return
    ev = message.event or {}
    et = ev.get("type")
    if et == "content_block_start":
        cb = ev.get("content_block") or {}
        if cb.get("type") == "tool_use" and cb.get("name") == "Agent":
            sub = (cb.get("input") or {}).get("subagent_type", "subagent")
            monitor.on_agent_start(str(sub), "Claude Agent tool", model="claude")
    elif et == "content_block_delta":
        delta = ev.get("delta") or {}
        if delta.get("type") == "text_delta":
            text = str(delta.get("text", ""))
            if text:
                monitor.on_log("claude", text, level="info")
