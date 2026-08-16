"""Trace data models — the boundary between execution and scoring (R1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from evals.provenance import Provenance

SCHEMA_VERSION = 1

SpanType = Literal[
    "phase_start",
    "phase_end",
    "llm_call",
    "tool_use",
    "tool_result",
    "guardrail_check",
    "retry",
    "error",
    "human_interrupt",
    "spend_event",
    "smoke_probe",
    "subagent_start",
    "subagent_stop",
]

BackendName = Literal["crewai", "langgraph", "claude-agent-sdk"]
TraceStatus = Literal[
    "complete",
    "failed",
    "awaiting_human",
    "killed",
    "budget_abort",
]
ArtifactKind = Literal["source", "test", "doc", "config", "log", "other"]
CostSource = Literal["sdk_reported", "provider_usage", "token_estimate", "unknown"]


class Span(BaseModel):
    """One event within a Trace."""

    span_id: str
    parent_span_id: str | None = None
    type: SpanType
    t_start: datetime
    t_end: datetime | None = None
    agent_role: str | None = None
    phase: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_s(self) -> float | None:
        """Wall duration in seconds, or None if the span has no end."""
        if self.t_end is None:
            return None
        return (self.t_end - self.t_start).total_seconds()


class Artifact(BaseModel):
    """Workspace file inventory entry (content addressed via sha256)."""

    path: str
    size_bytes: int
    sha256: str
    kind: ArtifactKind


class CostRecord(BaseModel):
    """Normalized spend for a run with an explicit source attribution."""

    usd: float | None
    input_tokens: int | None
    output_tokens: int | None
    source: CostSource
    per_model: dict[str, float] = Field(default_factory=dict)


class Trace(BaseModel):
    """Normalized, immutable record of one backend × scenario run."""

    schema_version: int = SCHEMA_VERSION
    trace_id: str
    scenario_id: str
    backend: BackendName
    status: TraceStatus
    started_at: datetime
    ended_at: datetime | None
    spans: list[Span]
    artifacts: list[Artifact]
    cost: CostRecord
    provenance: Provenance
    warnings: list[str] = Field(default_factory=list)
    raw_result: dict[str, Any] = Field(default_factory=dict)
    workspace_dir: str | None = None

    def spans_of(self, *types: SpanType) -> list[Span]:
        """Return spans whose type is in *types* (empty *types* → all spans)."""
        if not types:
            return list(self.spans)
        wanted = set(types)
        return [s for s in self.spans if s.type in wanted]

    def phases(self) -> list[str]:
        """Ordered unique phase names from phase_start / phase_end spans."""
        seen: list[str] = []
        for s in self.spans:
            if s.type in ("phase_start", "phase_end") and s.phase and s.phase not in seen:
                seen.append(s.phase)
        return seen

    def phase_repeats(self) -> dict[tuple[str, str | None], int]:
        """Count phase_start events keyed by ``(phase, agent_role)``."""
        counts: dict[tuple[str, str | None], int] = {}
        for s in self.spans_of("phase_start"):
            if not s.phase:
                continue
            key = (s.phase, s.agent_role)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def errors(self) -> list[Span]:
        """Return all error spans."""
        return self.spans_of("error")

    def files(self, kind: str | None = None) -> list[Artifact]:
        """Return artifacts, optionally filtered by kind."""
        if kind is None:
            return list(self.artifacts)
        return [a for a in self.artifacts if a.kind == kind]

    def read_artifact(self, path: str) -> str | None:
        """Load artifact bytes from the content-addressed blob store.

        Returns None when the artifact is missing, binary-only, or the store
        has no blob for its hash. Wired through :mod:`evals.store` lazily to
        avoid circular imports at model-definition time.
        """
        match = next((a for a in self.artifacts if a.path == path), None)
        if match is None:
            return None
        from evals.store import get_blob

        raw = get_blob(match.sha256)
        if raw is None:
            return None
        if not isinstance(raw, bytes | bytearray):
            return None
        try:
            return bytes(raw).decode("utf-8")
        except UnicodeDecodeError:
            return None
