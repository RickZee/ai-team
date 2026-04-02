"""Structured comparison of two orchestration backends (Phase 9)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BackendRunSnapshot(BaseModel):
    """Metrics captured for a single backend run."""

    backend_name: str = Field(..., description="crewai | langgraph")
    team_profile: str = Field(..., description="Team profile name used.")
    success: bool = Field(..., description="Whether the run reported success.")
    duration_sec: float = Field(..., ge=0.0, description="Wall-clock duration in seconds.")
    error: str | None = Field(default=None, description="Error message when success is false.")
    thread_id: str | None = Field(
        default=None,
        description="LangGraph thread id when present in raw result.",
    )
    current_phase: str | None = Field(
        default=None,
        description="Final or last-known phase from backend state.",
    )
    generated_files_count: int = Field(
        default=0,
        ge=0,
        description="Count of generated_files in state when available.",
    )


class ComparisonReport(BaseModel):
    """Side-by-side snapshot for CrewAI vs LangGraph (optional Claude Agent SDK)."""

    demo_path: str = Field(..., description="Resolved demo directory path.")
    description: str = Field(..., description="Project description passed to each backend.")
    env: str | None = Field(default=None, description="AI_TEAM_ENV override if set.")
    team_profile: str = Field(..., description="Team profile used for runs.")
    crewai: BackendRunSnapshot
    langgraph: BackendRunSnapshot
    claude_agent_sdk: BackendRunSnapshot | None = Field(
        default=None,
        description="Optional third backend when comparison includes Claude Agent SDK.",
    )

    def to_markdown(self) -> str:
        """Render a compact markdown table for logs or ``*.md`` artifacts."""
        lines = [
            "# Backend comparison",
            "",
            f"- **Demo:** `{self.demo_path}`",
            f"- **Team profile:** `{self.team_profile}`",
            f"- **Env:** `{self.env or 'default'}`",
            "",
        ]
        if self.claude_agent_sdk is not None:
            lines.extend(
                [
                    "| Metric | CrewAI | LangGraph | Claude Agent SDK |",
                    "|--------|--------|-----------|------------------|",
                    f"| Success | {self.crewai.success} | {self.langgraph.success} | {self.claude_agent_sdk.success} |",
                    f"| Duration (s) | {self.crewai.duration_sec:.3f} | {self.langgraph.duration_sec:.3f} | {self.claude_agent_sdk.duration_sec:.3f} |",
                    f"| Phase | {self.crewai.current_phase or '—'} | {self.langgraph.current_phase or '—'} | {self.claude_agent_sdk.current_phase or '—'} |",
                    f"| Generated files | {self.crewai.generated_files_count} | {self.langgraph.generated_files_count} | {self.claude_agent_sdk.generated_files_count} |",
                    f"| Error | {self.crewai.error or '—'} | {self.langgraph.error or '—'} | {self.claude_agent_sdk.error or '—'} |",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "| Metric | CrewAI | LangGraph |",
                    "|--------|--------|-----------|",
                    f"| Success | {self.crewai.success} | {self.langgraph.success} |",
                    f"| Duration (s) | {self.crewai.duration_sec:.3f} | {self.langgraph.duration_sec:.3f} |",
                    f"| Phase | {self.crewai.current_phase or '—'} | {self.langgraph.current_phase or '—'} |",
                    f"| Generated files | {self.crewai.generated_files_count} | {self.langgraph.generated_files_count} |",
                    f"| Error | {self.crewai.error or '—'} | {self.langgraph.error or '—'} |",
                    "",
                ]
            )
        return "\n".join(lines)

    def to_json_dict(self) -> dict[str, Any]:
        """JSON-serializable dict (for scripts and CI artifacts)."""
        return self.model_dump(mode="json")


def snapshot_from_project_result(
    *,
    backend_name: str,
    team_profile: str,
    duration_sec: float,
    result: Any,
) -> BackendRunSnapshot:
    """
    Build a snapshot from :class:`~ai_team.core.result.ProjectResult`.

    Accepts any object with ``success``, ``error``, ``raw`` attributes for tests/mocks.
    """
    success = bool(getattr(result, "success", False))
    error = getattr(result, "error", None)
    raw: dict[str, Any] = dict(getattr(result, "raw", None) or {})
    state = raw.get("state")
    if not isinstance(state, dict):
        state = {}

    files = state.get("generated_files")
    gen_count = len(files) if isinstance(files, list) else 0
    if gen_count == 0:
        raw_files = raw.get("generated_files")
        if isinstance(raw_files, list):
            gen_count = len(raw_files)
    phase = state.get("current_phase")
    current_phase = str(phase) if phase is not None else None
    if current_phase is None and isinstance(raw.get("phases"), list) and raw["phases"]:
        last = raw["phases"][-1]
        if isinstance(last, dict) and last.get("phase"):
            current_phase = str(last["phase"])

    thread_id = raw.get("thread_id")
    if thread_id is None and raw.get("session_id") is not None:
        thread_id = raw.get("session_id")
    tid = str(thread_id) if thread_id is not None else None

    return BackendRunSnapshot(
        backend_name=backend_name,
        team_profile=team_profile,
        success=success,
        duration_sec=duration_sec,
        error=str(error) if error else None,
        thread_id=tid,
        current_phase=current_phase,
        generated_files_count=gen_count,
    )
