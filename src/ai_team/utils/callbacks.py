"""
Event callback system for CrewAI crews: logging, metrics, and optional webhooks.

AITeamCallback implements CrewAI-style callback interfaces (task/crew/agent/guardrail)
with structlog, MetricsReport collection, and configurable webhook notifications.
Supports both sync and async callback usage.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# -----------------------------------------------------------------------------
# MetricsReport
# -----------------------------------------------------------------------------


class MetricsReport(BaseModel):
    """
    Aggregated metrics from callback events: durations, token estimates,
    retries, guardrail triggers, and tool call counts.
    """

    task_durations_seconds: Dict[str, float] = Field(
        default_factory=dict,
        description="Task key -> duration in seconds (start to complete).",
    )
    token_usage_per_agent: Dict[str, int] = Field(
        default_factory=dict,
        description="Agent role -> estimated token count (from response length).",
    )
    retry_counts_per_task: Dict[str, int] = Field(
        default_factory=dict,
        description="Task key -> number of retries.",
    )
    retry_counts_per_phase: Dict[str, int] = Field(
        default_factory=dict,
        description="Phase name -> number of retries.",
    )
    guardrail_trigger_count: Dict[str, int] = Field(
        default_factory=dict,
        description="Guardrail name -> trigger count.",
    )
    tool_call_counts_per_agent: Dict[str, int] = Field(
        default_factory=dict,
        description="Agent role -> number of tool calls.",
    )
    task_failure_count: int = Field(default=0, description="Total task failures (on_task_error).")

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary of all metrics."""
        return self.model_dump()

    def to_table(self) -> str:
        """Return a human-readable table summary of metrics."""
        lines: List[str] = []
        lines.append("MetricsReport")
        lines.append("-" * 40)
        if self.task_durations_seconds:
            lines.append("Task durations (s):")
            for k, v in sorted(self.task_durations_seconds.items()):
                lines.append(f"  {k}: {v:.2f}")
        if self.token_usage_per_agent:
            lines.append("Token usage (est) per agent:")
            for k, v in sorted(self.token_usage_per_agent.items()):
                lines.append(f"  {k}: {v}")
        if self.retry_counts_per_task:
            lines.append("Retries per task:")
            for k, v in sorted(self.retry_counts_per_task.items()):
                lines.append(f"  {k}: {v}")
        if self.retry_counts_per_phase:
            lines.append("Retries per phase:")
            for k, v in sorted(self.retry_counts_per_phase.items()):
                lines.append(f"  {k}: {v}")
        if self.guardrail_trigger_count:
            lines.append("Guardrail triggers:")
            for k, v in sorted(self.guardrail_trigger_count.items()):
                lines.append(f"  {k}: {v}")
        if self.tool_call_counts_per_agent:
            lines.append("Tool calls per agent:")
            for k, v in sorted(self.tool_call_counts_per_agent.items()):
                lines.append(f"  {k}: {v}")
        lines.append(f"Task failures: {self.task_failure_count}")
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# AITeamCallback
# -----------------------------------------------------------------------------


def _task_key(task: Any) -> str:
    """Derive a string key from a task object for metrics."""
    if hasattr(task, "description"):
        desc = getattr(task, "description", "") or ""
        return (desc[:60] + "..") if len(desc) > 60 else desc
    return str(task)[:60]


def _agent_role(agent: Any) -> str:
    """Derive agent role string for logging and metrics."""
    if agent is None:
        return "unknown"
    if hasattr(agent, "role"):
        return str(getattr(agent, "role", "unknown"))
    return str(agent)[:40]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate from character length (~4 chars per token)."""
    if not text:
        return 0
    return max(0, len(text) // 4)


class AITeamCallback:
    """
    Callback handler implementing CrewAI-style interfaces: task start/complete/error,
    agent action, crew start/complete, and guardrail trigger. Logs via structlog with
    context binding, collects metrics into MetricsReport, and optionally POSTs
    webhooks on phase transitions. Supports both sync and async usage.
    """

    def __init__(
        self,
        *,
        project_id: Optional[str] = None,
        phase: Optional[str] = None,
        webhook_url: Optional[str] = None,
        webhook_enabled: bool = False,
    ) -> None:
        self.project_id = project_id
        self.phase = phase or ""
        self.webhook_url = webhook_url
        self.webhook_enabled = bool(webhook_url and webhook_enabled)
        self._lock = threading.Lock()
        self._task_start_times: Dict[str, float] = {}
        self._metrics = MetricsReport()
        self._log = logger.bind(
            project_id=project_id or "",
            phase=phase or "",
        )

    def _bind_context(
        self,
        *,
        agent_role: Optional[str] = None,
        task_name: Optional[str] = None,
    ) -> structlog.BoundLogger:
        extra: Dict[str, str] = {}
        if agent_role is not None:
            extra["agent_role"] = agent_role
        if task_name is not None:
            extra["task_name"] = task_name
        return self._log.bind(**extra) if extra else self._log

    def on_task_start(self, task: Any, agent: Any) -> None:
        """Log task beginning and start timer."""
        task_name = _task_key(task)
        role = _agent_role(agent)
        self._bind_context(agent_role=role, task_name=task_name).info(
            "task_start",
            task=task_name,
            agent_role=role,
        )
        with self._lock:
            self._task_start_times[task_name] = time.monotonic()

    def on_task_complete(self, task: Any, agent: Any, output: Any) -> None:
        """Log completion, stop timer, and record metrics (duration, token estimate)."""
        task_name = _task_key(task)
        role = _agent_role(agent)
        with self._lock:
            start = self._task_start_times.pop(task_name, None)
            if start is not None:
                duration = time.monotonic() - start
                self._metrics.task_durations_seconds[task_name] = duration
            out_str = str(output) if output is not None else ""
            est = self._metrics.token_usage_per_agent.get(role, 0) + _estimate_tokens(out_str)
            self._metrics.token_usage_per_agent[role] = est
        self._bind_context(agent_role=role, task_name=task_name).info(
            "task_complete",
            task=task_name,
            agent_role=role,
            output_preview=out_str[:200] + "..." if len(out_str) > 200 else out_str,
        )

    def on_task_error(self, task: Any, agent: Any, error: BaseException) -> None:
        """Log error and increment failure counter."""
        task_name = _task_key(task)
        role = _agent_role(agent)
        with self._lock:
            self._metrics.task_failure_count += 1
            self._task_start_times.pop(task_name, None)
        self._bind_context(agent_role=role, task_name=task_name).error(
            "task_error",
            task=task_name,
            agent_role=role,
            error_type=type(error).__name__,
            error_message=str(error),
        )

    def on_agent_action(self, agent: Any, action: Any, tool: Any) -> None:
        """Log tool usage and increment tool call count per agent."""
        role = _agent_role(agent)
        tool_name = getattr(tool, "name", str(tool)) if tool else "unknown"
        with self._lock:
            self._metrics.tool_call_counts_per_agent[role] = (
                self._metrics.tool_call_counts_per_agent.get(role, 0) + 1
            )
        self._bind_context(agent_role=role).debug(
            "agent_action",
            agent_role=role,
            tool=tool_name,
            action_preview=str(action)[:150] if action else "",
        )

    def on_crew_start(self, crew: Any) -> None:
        """Log crew kickoff; optionally send phase webhook."""
        crew_name = getattr(crew, "name", str(crew))[:60] if crew else "unknown"
        self._log.info("crew_start", crew=crew_name, event_type="crew_start")
        self._send_webhook_sync("phase_transition", {"event": "crew_start", "crew": crew_name})

    def on_crew_complete(self, crew: Any, output: Any) -> None:
        """Log crew completion with summary; optionally send phase webhook."""
        crew_name = getattr(crew, "name", str(crew))[:60] if crew else "unknown"
        out_preview = str(output)[:300] + "..." if output and len(str(output)) > 300 else (str(output) or "")
        self._log.info(
            "crew_complete",
            crew=crew_name,
            output_preview=out_preview,
            event_type="crew_complete",
        )
        self._send_webhook_sync(
            "phase_transition",
            {"event": "crew_complete", "crew": crew_name, "output_preview": out_preview},
        )

    def on_guardrail_trigger(self, guardrail: Any, result: Any) -> None:
        """Log guardrail evaluation and increment trigger count."""
        name = getattr(guardrail, "__name__", getattr(guardrail, "name", str(guardrail)))[:60]
        status = getattr(result, "status", str(result)) if result else "unknown"
        with self._lock:
            self._metrics.guardrail_trigger_count[name] = (
                self._metrics.guardrail_trigger_count.get(name, 0) + 1
            )
        msg = getattr(result, "message", str(result)) if result else ""
        if status == "warn":
            self._log.warning("guardrail_trigger", guardrail=name, status=status, message=msg)
        else:
            self._log.info("guardrail_trigger", guardrail=name, status=status, message=msg)

    def record_retry(self, *, task: Optional[str] = None, phase: Optional[str] = None) -> None:
        """Record a retry for a task and/or phase (call from flow/routing)."""
        with self._lock:
            if task:
                self._metrics.retry_counts_per_task[task] = (
                    self._metrics.retry_counts_per_task.get(task, 0) + 1
                )
            if phase:
                self._metrics.retry_counts_per_phase[phase] = (
                    self._metrics.retry_counts_per_phase.get(phase, 0) + 1
                )
        if task or phase:
            self._log.warning("retry_recorded", task=task, phase=phase)

    def get_metrics(self) -> MetricsReport:
        """Return a snapshot of collected metrics."""
        with self._lock:
            return self._metrics.model_copy(deep=True)

    def _send_webhook_sync(self, event_type: str, details: Dict[str, Any]) -> None:
        if not self.webhook_enabled or not self.webhook_url:
            return
        payload = {
            "project_id": self.project_id,
            "event_type": event_type,
            "details": details,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                resp = client.post(self.webhook_url, json=payload)
                if resp.status_code >= 400:
                    self._log.warning(
                        "webhook_post_failed",
                        url=self.webhook_url,
                        status_code=resp.status_code,
                        body=resp.text[:500],
                    )
        except Exception as e:
            self._log.warning("webhook_post_error", url=self.webhook_url, error=str(e))

    async def _send_webhook_async(self, event_type: str, details: Dict[str, Any]) -> None:
        if not self.webhook_enabled or not self.webhook_url:
            return
        payload = {
            "project_id": self.project_id,
            "event_type": event_type,
            "details": details,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                if resp.status_code >= 400:
                    self._log.warning(
                        "webhook_post_failed",
                        url=self.webhook_url,
                        status_code=resp.status_code,
                        body=resp.text[:500],
                    )
        except Exception as e:
            self._log.warning("webhook_post_error", url=self.webhook_url, error=str(e))

    # ---------- Async variants ----------

    async def on_task_start_async(self, task: Any, agent: Any) -> None:
        """Async: log task beginning and start timer."""
        self.on_task_start(task, agent)

    async def on_task_complete_async(self, task: Any, agent: Any, output: Any) -> None:
        """Async: log completion, stop timer, record metrics."""
        self.on_task_complete(task, agent, output)

    async def on_task_error_async(self, task: Any, agent: Any, error: BaseException) -> None:
        """Async: log error, increment failure counter."""
        self.on_task_error(task, agent, error)

    async def on_agent_action_async(self, agent: Any, action: Any, tool: Any) -> None:
        """Async: log tool usage and increment tool call count."""
        self.on_agent_action(agent, action, tool)

    async def on_crew_start_async(self, crew: Any) -> None:
        """Async: log crew kickoff and optionally send webhook (async POST)."""
        crew_name = getattr(crew, "name", str(crew))[:60] if crew else "unknown"
        self._log.info("crew_start", crew=crew_name, event_type="crew_start")
        await self._send_webhook_async("phase_transition", {"event": "crew_start", "crew": crew_name})

    async def on_crew_complete_async(self, crew: Any, output: Any) -> None:
        """Async: log crew completion and optionally send webhook (async POST)."""
        crew_name = getattr(crew, "name", str(crew))[:60] if crew else "unknown"
        out_preview = str(output)[:300] + "..." if output and len(str(output)) > 300 else (str(output) or "")
        self._log.info("crew_complete", crew=crew_name, output_preview=out_preview, event_type="crew_complete")
        await self._send_webhook_async(
            "phase_transition",
            {"event": "crew_complete", "crew": crew_name, "output_preview": out_preview},
        )

    async def on_guardrail_trigger_async(self, guardrail: Any, result: Any) -> None:
        """Async: log guardrail evaluation and increment trigger count."""
        self.on_guardrail_trigger(guardrail, result)

    # ---------- CrewAI task_callback adapter ----------

    def get_task_callback(self) -> Any:
        """
        Return a callable suitable for CrewAI Crew task_callback.
        CrewAI may pass (task, output) or a single object; this adapter
        calls on_task_complete with task, agent (from task if present), and output.
        """
        def _task_callback(*args: Any, **kwargs: Any) -> None:
            task, agent = None, None
            output = None
            if len(args) >= 2:
                task, output = args[0], args[1]
            elif len(args) == 1:
                arg = args[0]
                if hasattr(arg, "task") and hasattr(arg, "output"):
                    task = getattr(arg, "task", None)
                    output = getattr(arg, "output", None)
                else:
                    task, output = arg, None
            if task is not None and hasattr(task, "agent"):
                agent = getattr(task, "agent", None)
            self.on_task_complete(task, agent, output)
        return _task_callback
