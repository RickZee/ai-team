"""
Failure-driven self-improvement: capture failures, extract lessons, and load them for prompt injection.

This module is intentionally deterministic (no LLM required) so it is safe to run
in CI and can be used as a stable feedback loop across backends (CrewAI/LangGraph).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from ai_team.config.settings import get_settings
from ai_team.memory.memory_config import LongTermStore

logger = structlog.get_logger(__name__)


FAILURE_PATTERN_TYPE = "failure_record"
LESSON_PATTERN_TYPE = "lesson"
INFRA_PATTERN_TYPE = "infra_issue"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _long_term_store() -> LongTermStore:
    s = get_settings()
    return LongTermStore(sqlite_path=s.memory.sqlite_path, retention_days=s.memory.retention_days)


def _to_dict(obj: Any) -> dict[str, Any]:
    """Best-effort conversion of Pydantic models or plain dicts to dict."""
    if isinstance(obj, dict):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return {}


def _iter_errors(state_like: Any) -> Iterable[dict[str, Any]]:
    d = _to_dict(state_like)
    errs = d.get("errors") or []
    for e in errs:
        if isinstance(e, dict):
            yield e
        else:
            yield _to_dict(e)


def _extract_test_signals(state_like: Any) -> dict[str, Any]:
    d = _to_dict(state_like)
    tr = d.get("test_results") or {}
    if not isinstance(tr, dict):
        return {}
    lint = tr.get("lint") or {}
    tests = tr.get("tests") or {}
    return {
        "passed": bool(tr.get("passed")) if "passed" in tr else None,
        "ruff": {
            "ok": (lint.get("ok") if isinstance(lint, dict) else None),
            "returncode": (lint.get("returncode") if isinstance(lint, dict) else None),
            "violations": None,
            "output_snippet": ((lint.get("output") or "")[:2000] if isinstance(lint, dict) else ""),
        },
        "pytest": {
            "ok": (tests.get("ok") if isinstance(tests, dict) else None),
            "returncode": (tests.get("returncode") if isinstance(tests, dict) else None),
            "output_snippet": (
                (tests.get("output") or "")[:4000] if isinstance(tests, dict) else ""
            ),
        },
    }


def record_run_failures(
    *,
    run_id: str,
    backend: str,
    team_profile: str,
    state: Any,
) -> int:
    """
    Persist failure records for a run into long-term memory.

    Stores one row per error in the long-term SQLite `learned_patterns` table
    using `pattern_type = failure_record` and JSON content.
    """
    store = _long_term_store()
    count = 0
    test_signals = _extract_test_signals(state)
    state_dict = _to_dict(state)
    current_phase = str(state_dict.get("current_phase") or "")

    for err in _iter_errors(state):
        record = {
            "run_id": run_id,
            "timestamp": _now_iso(),
            "backend": backend,
            "team_profile": team_profile,
            "phase": str(err.get("phase") or current_phase),
            "agent_role": (err.get("guardrail", {}) or {}).get("details", {}).get("agent_role")
            if isinstance(err.get("guardrail"), dict)
            else None,
            "error_type": str(err.get("type") or err.get("error_type") or "Error"),
            "message": str(err.get("message") or ""),
            "guardrail": err.get("guardrail"),
            "test_signals": test_signals,
            "retry_count": state_dict.get("retry_count"),
            "max_retries": state_dict.get("max_retries"),
        }
        try:
            store.add_pattern(FAILURE_PATTERN_TYPE, json.dumps(record, ensure_ascii=False))
            count += 1
        except Exception as e:
            logger.warning("failure_record_persist_failed", error=str(e))

    # If there were no explicit errors but tests failed, persist a synthetic failure record.
    if count == 0:
        tr = state_dict.get("test_results")
        if isinstance(tr, dict) and tr.get("passed") is False:
            record = {
                "run_id": run_id,
                "timestamp": _now_iso(),
                "backend": backend,
                "team_profile": team_profile,
                "phase": "testing",
                "agent_role": "qa_engineer",
                "error_type": "TestFailure",
                "message": "Tests did not pass.",
                "guardrail": None,
                "test_signals": test_signals,
                "retry_count": state_dict.get("retry_count"),
                "max_retries": state_dict.get("max_retries"),
            }
            try:
                store.add_pattern(FAILURE_PATTERN_TYPE, json.dumps(record, ensure_ascii=False))
                count += 1
            except Exception as e:
                logger.warning("failure_record_persist_failed", error=str(e))

    logger.info(
        "failure_records_persisted",
        run_id=run_id,
        backend=backend,
        team_profile=team_profile,
        count=count,
        current_phase=current_phase,
    )
    return count


@dataclass(frozen=True)
class Lesson:
    lesson_id: str
    agent_role: str
    title: str
    text: str
    created_at: str
    evidence_count: int


def _parse_failure_record(row: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return json.loads(str(row.get("content") or ""))
    except Exception:
        return None


def extract_lessons(*, promote_threshold: int = 2, limit: int = 500) -> dict[str, int]:
    """
    Deterministically promote recurring failure patterns into `lesson` patterns.

    Returns counters: {"scanned": N, "promoted": M, "infra_flagged": K}.
    """
    store = _long_term_store()
    rows = store.get_patterns(pattern_type=FAILURE_PATTERN_TYPE, limit=limit)
    scanned = 0

    # Cluster keys are stable strings so we can count occurrences.
    buckets: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        fr = _parse_failure_record(r)
        if not fr:
            continue
        scanned += 1
        key = "|".join(
            [
                str(fr.get("phase") or ""),
                str(fr.get("error_type") or ""),
                str(fr.get("message") or "")[:200],
                str(
                    (fr.get("guardrail") or {}).get("phase")
                    if isinstance(fr.get("guardrail"), dict)
                    else ""
                ),
            ]
        )
        buckets.setdefault(key, []).append(fr)

    promoted = 0
    infra_flagged = 0
    for key, items in buckets.items():
        if len(items) < promote_threshold:
            continue
        sample = items[0]
        phase = str(sample.get("phase") or "")
        guardrail = sample.get("guardrail") or {}
        is_guardrail = isinstance(guardrail, dict) and guardrail.get("phase") == "behavioral"

        # Very simple infra heuristic: pytest import/module failures are environment/tooling.
        msg = str(sample.get("message") or "")
        pytest_out = ((sample.get("test_signals") or {}).get("pytest") or {}).get(
            "output_snippet"
        ) or ""
        is_infra = ("ModuleNotFoundError" in pytest_out) or ("No module named" in pytest_out)

        if is_infra:
            infra = {
                "id": key,
                "created_at": _now_iso(),
                "description": "pytest import/module resolution failure in isolated workspace",
                "phase": phase or "testing",
                "message": msg[:500],
                "evidence_count": len(items),
                "sample": sample,
                "status": "open",
            }
            try:
                store.add_pattern(INFRA_PATTERN_TYPE, json.dumps(infra, ensure_ascii=False))
                infra_flagged += 1
            except Exception as e:
                logger.warning("infra_issue_persist_failed", error=str(e))
            continue

        agent_role = str(sample.get("agent_role") or ("qa_engineer" if is_guardrail else "manager"))
        title = "Avoid guardrail violations" if is_guardrail else "Prevent recurring failure"
        text = (
            f"Recurring failure detected ({len(items)} runs). "
            f"Phase: {phase}. Error: {sample.get('error_type')}. "
            f"Message: {msg}\n\n"
        )
        if is_guardrail:
            text += (
                "When acting in this role, do not include production code or role-inappropriate edits "
                "in your output unless explicitly instructed. Prefer concise test-focused feedback."
            )
        else:
            text += "Before finalizing output, validate assumptions and address the failure cause directly."

        lesson = {
            "lesson_id": key,
            "agent_role": agent_role,
            "title": title,
            "text": text,
            "created_at": _now_iso(),
            "evidence_count": len(items),
        }
        try:
            store.add_pattern(LESSON_PATTERN_TYPE, json.dumps(lesson, ensure_ascii=False))
            promoted += 1
        except Exception as e:
            logger.warning("lesson_persist_failed", error=str(e))

    logger.info(
        "lessons_extracted",
        scanned=scanned,
        promoted=promoted,
        infra_flagged=infra_flagged,
        promote_threshold=promote_threshold,
    )
    return {"scanned": scanned, "promoted": promoted, "infra_flagged": infra_flagged}


def load_role_lessons(*, agent_role: str, limit: int = 20) -> list[Lesson]:
    """Load promoted lessons applicable to `agent_role`."""
    store = _long_term_store()
    rows = store.get_patterns(pattern_type=LESSON_PATTERN_TYPE, limit=limit)
    out: list[Lesson] = []
    for r in rows:
        try:
            data = json.loads(str(r.get("content") or ""))
        except Exception:
            continue
        if str(data.get("agent_role") or "") != agent_role:
            continue
        out.append(
            Lesson(
                lesson_id=str(data.get("lesson_id") or r.get("id") or ""),
                agent_role=agent_role,
                title=str(data.get("title") or "Lesson"),
                text=str(data.get("text") or ""),
                created_at=str(data.get("created_at") or r.get("created_at") or ""),
                evidence_count=int(data.get("evidence_count") or 0),
            )
        )
    return out


def write_infra_backlog(*, path: str = "data/infra_backlog.jsonl", limit: int = 200) -> int:
    """
    Export infra issues into a JSONL backlog file under the repo (gitignored).
    Returns number of lines written.
    """
    store = _long_term_store()
    rows = store.get_patterns(pattern_type=INFRA_PATTERN_TYPE, limit=limit)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in rows:
        lines.append(str(r.get("content") or "").strip())
    p.write_text("\n".join([ln for ln in lines if ln]) + ("\n" if lines else ""), encoding="utf-8")
    return len([ln for ln in lines if ln])
