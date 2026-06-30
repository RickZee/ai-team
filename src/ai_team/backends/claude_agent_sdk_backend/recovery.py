"""Retry orchestrator runs on recoverable SDK/CLI failures."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import structlog
from ai_team.backends.claude_agent_sdk_backend.costs import (
    append_cost_log,
    default_total_budget_usd,
)
from ai_team.backends.claude_agent_sdk_backend.orchestrator import iter_orchestrator_messages
from ai_team.core.team_profile import TeamProfile
from claude_agent_sdk import ResultMessage

logger = structlog.get_logger(__name__)


def _runtime_smoke_failure(workspace: Path) -> str | None:
    """Return a fix instruction if the booted app fails its runtime smoke test.

    This is the *quality* gate (distinct from SDK/CLI transient failures): a run
    can finish with ``is_error=False`` and a green pytest suite while the actual
    app does not boot or 500s on every request. We boot it and probe real HTTP
    endpoints; on failure we return a concrete, developer-actionable instruction
    so the next attempt fixes the runtime defect instead of re-asserting success.

    Returns ``None`` when the app smokes clean, or when the smoke was legitimately
    skipped (no bootable entrypoint / Docker unavailable) — those are not defects.
    """
    try:
        from ai_team.tools.smoke_tools import load_or_run_smoke

        # Reuse a fresh smoke result if the QA agent already booted the app this
        # attempt; otherwise boot it. Avoids a redundant (and for compose,
        # expensive) second boot per recovery attempt.
        result = load_or_run_smoke(workspace)
    except Exception as e:  # noqa: BLE001 - never let the gate crash the run
        logger.warning("claude_smoke_gate_error", error=str(e))
        return None
    if not result.ran or result.success:
        return None
    failing = next((p for p in result.probes if not p.ok), None)
    detail = result.message
    if failing is not None:
        detail = (
            f"{failing.method} {failing.path} returned "
            f"{failing.status if failing.status is not None else 'no response'}: "
            f"{failing.detail[:300]}"
        )
    logs = (result.logs or "").strip()
    log_hint = f"\nServer logs:\n{logs[-1500:]}" if logs else ""
    return (
        "[System: Unit tests passed but the RUNNING app failed a runtime smoke "
        f"test. {detail}{log_hint}\n"
        "Fix the runtime defect (boot error or 5xx from a real request) at its "
        "root cause — not by changing tests — then re-run pytest and "
        "run_app_smoke until both pass.]"
    )


def _recoverable_failure(msg: ResultMessage) -> bool:
    """Heuristic: budget, turns, rate limits, and transient server errors."""
    parts: list[str] = []
    if msg.stop_reason:
        parts.append(str(msg.stop_reason).lower())
    if msg.errors:
        parts.extend(str(e).lower() for e in msg.errors)
    blob = " ".join(parts)
    keys = (
        "budget",
        "max_turn",
        "turn limit",
        "rate_limit",
        "rate limit",
        "overloaded",
        "timeout",
        "503",
        "529",
        "try again",
    )
    return any(k in blob for k in keys)


async def _last_result_from_iter(
    description: str,
    profile: TeamProfile,
    workspace: Path,
    *,
    log_attempt_cost: bool = True,
    **opts: Any,
) -> ResultMessage | None:
    last: ResultMessage | None = None
    async for msg in iter_orchestrator_messages(description, profile, workspace, **opts):
        if isinstance(msg, ResultMessage):
            last = msg
    if log_attempt_cost and last is not None:
        append_cost_log(
            workspace,
            phase="orchestrator_recovery_attempt",
            cost_usd=last.total_cost_usd,
            usage=last.usage,
        )
    return last


async def run_orchestrator_with_recovery(
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
    recovery_max_attempts: int = 3,
    **orchestrator_extras: Any,
) -> tuple[ResultMessage | None, list[str]]:
    """
    Run the orchestrator up to ``recovery_max_attempts`` times with widened limits.

    On each recoverable failure, increases ``max_turns`` and ``max_budget_usd`` slightly
    and appends a short instruction to the user prompt.
    """
    base_turns = max_turns or 50
    base_budget = (
        float(max_budget_usd) if max_budget_usd is not None else default_total_budget_usd()
    )
    logs: list[str] = []
    last: ResultMessage | None = None
    prompt = description

    for attempt in range(1, recovery_max_attempts + 1):
        turn_budget = base_turns + (attempt - 1) * 15
        usd_budget = base_budget * (1.0 + 0.25 * (attempt - 1))
        logger.info(
            "claude_recovery_attempt",
            attempt=attempt,
            max_turns=turn_budget,
            max_budget_usd=usd_budget,
        )
        last = await _last_result_from_iter(
            prompt,
            profile,
            workspace,
            resume=resume if attempt == 1 else None,
            fork_session=fork_session if attempt == 1 else False,
            max_budget_usd=usd_budget,
            max_turns=turn_budget,
            max_retries=max_retries,
            include_partial_messages=include_partial_messages,
            enable_file_checkpointing=enable_file_checkpointing,
            log_attempt_cost=True,
            **orchestrator_extras,
        )
        if last is None:
            logs.append(f"attempt {attempt}: no ResultMessage")
            prompt = (
                description
                + "\n\n[System: Previous attempt produced no final result; continue carefully.]"
            )
            continue
        if not last.is_error:
            # SDK run finished cleanly — now apply the runtime quality gate.
            # A green run over a non-booting / 5xx-ing app is not a real success;
            # feed the smoke failure back and let the team self-correct.
            smoke_fix = _runtime_smoke_failure(workspace)
            if smoke_fix is None:
                logs.append(f"attempt {attempt}: success")
                return last, logs
            logs.append(f"attempt {attempt}: runtime smoke failed")
            if attempt >= recovery_max_attempts:
                logs.append("runtime smoke still failing at final attempt")
                return last, logs
            # Invalidate this attempt's smoke result so the next attempt is
            # evaluated against a fresh boot (load_or_run_smoke would otherwise
            # reuse the just-written failing result).
            with contextlib.suppress(OSError):
                (workspace / "docs" / "smoke_results.json").unlink(missing_ok=True)
            prompt = description + "\n\n" + smoke_fix
            resume = None
            fork_session = False
            continue
        reason = last.stop_reason or "error"
        logs.append(f"attempt {attempt}: is_error=True stop_reason={reason!r}")
        if attempt >= recovery_max_attempts or not _recoverable_failure(last):
            return last, logs
        prompt = (
            description + f"\n\n[System: Attempt {attempt} stopped ({reason}). "
            "Continue with a narrower scope; avoid repeating failed tool patterns.]"
        )
        resume = None
        fork_session = False

    return last, logs
