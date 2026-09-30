"""Resolve orchestration backends by name and execution target."""

from __future__ import annotations

from ai_team.backends.common.targets import ExecutionTarget, UnsupportedTargetError
from ai_team.core.backend import Backend

PUBLIC_BACKENDS: tuple[str, ...] = (
    "crewai",
    "langgraph",
    "claude-agent-sdk",
    "strands",
    "agent-framework",
)
CLI_BACKEND_CHOICES: tuple[str, ...] = (*PUBLIC_BACKENDS, "claude-sdk")
TARGET_CHOICES: tuple[str, ...] = tuple(member.value for member in ExecutionTarget)

_STUB_SPECS = {
    "strands": ".kiro/specs/aws-strands-agentcore",
    "agent-framework": ".kiro/specs/azure-agent-framework",
}
_TARGETS: dict[str, frozenset[str]] = {
    "crewai": frozenset({ExecutionTarget.LOCAL.value}),
    "langgraph": frozenset({ExecutionTarget.LOCAL.value}),
    "claude-agent-sdk": frozenset({ExecutionTarget.LOCAL.value}),
    "claude-sdk": frozenset({ExecutionTarget.LOCAL.value}),
    "strands": frozenset(TARGET_CHOICES),
    "agent-framework": frozenset(TARGET_CHOICES),
    "fake-remote": frozenset(TARGET_CHOICES),
}


def supported_targets(name: str) -> frozenset[str]:
    """Targets ``name`` can run. Unknown names raise ``ValueError``."""
    key = _normalize(name)
    if key not in _TARGETS:
        raise ValueError(_unknown_backend(name))
    return _TARGETS[key]


def list_backend_names() -> list[str]:
    """Public backend names, in catalog order. Excludes the conformance double."""
    return list(PUBLIC_BACKENDS)


def get_backend(name: str, *, target: str = "local") -> Backend:
    """Return a backend for ``name`` on ``target``.

    An unknown target, or a target the backend does not support, raises
    :class:`UnsupportedTargetError` before any spend. Strands and Agent
    Framework raise ``NotImplementedError`` naming their spec, also before spend.

    Args:
        name: ``crewai``, ``langgraph``, ``claude-agent-sdk``, ``strands``,
            ``agent-framework``, or the conformance-only ``fake-remote``.
        target: ``local``, ``container``, or ``cloud``.
    """
    key = _normalize(name)
    if key not in _TARGETS:
        raise ValueError(_unknown_backend(name))
    _require_target(key, target)
    if key in _STUB_SPECS:
        supported = ", ".join(sorted(_TARGETS[key]))
        raise NotImplementedError(
            f"{key} is not implemented yet: see {_STUB_SPECS[key]}. "
            f"Supported targets: {supported}."
        )
    if key == "crewai":
        from ai_team.backends.crewai_backend.backend import CrewAIBackend

        return CrewAIBackend()
    if key == "langgraph":
        from ai_team.backends.langgraph_backend.backend import LangGraphBackend

        return LangGraphBackend()
    if key in ("claude-agent-sdk", "claude-sdk"):
        from ai_team.backends.claude_agent_sdk_backend.backend import ClaudeAgentBackend

        return ClaudeAgentBackend()
    if key == "fake-remote":
        from ai_team.backends.common.targets import FakeRemoteBackend

        return FakeRemoteBackend()
    raise ValueError(_unknown_backend(name))


def _normalize(name: str) -> str:
    return (name or "crewai").strip().lower()


def _unknown_backend(name: str) -> str:
    known = " | ".join(PUBLIC_BACKENDS)
    return f"Unknown backend {name!r}. Use: {known}"


def _require_target(key: str, target: str) -> None:
    cleaned = (target or "").strip().lower()
    if cleaned not in TARGET_CHOICES:
        supported = ", ".join(TARGET_CHOICES)
        raise UnsupportedTargetError(f"Unknown target {target!r}. Supported targets: {supported}.")
    allowed = _TARGETS[key]
    if cleaned not in allowed:
        supported = ", ".join(sorted(allowed))
        raise UnsupportedTargetError(
            f"Backend {key} does not support target {cleaned!r}. Supported targets: {supported}."
        )
