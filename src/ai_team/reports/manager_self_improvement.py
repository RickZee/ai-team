"""
Manager final report: per-backend run analysis, problems, lessons, and self-improvement proposals.

Core content is deterministic. An optional **manager narrative** is generated via the manager
LLM when ``OPENROUTER_API_KEY`` is set and ``AI_TEAM_MANAGER_REPORT_LLM`` is not disabled.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import structlog
from ai_team.config.settings import get_settings
from ai_team.core.results.writer import ResultsBundle
from ai_team.memory.lessons import FAILURE_PATTERN_TYPE, LESSON_PATTERN_TYPE
from ai_team.memory.memory_config import LongTermStore

logger = structlog.get_logger(__name__)


def _state_to_dict(state: Any) -> dict[str, Any]:
    if isinstance(state, dict):
        return state
    dump = getattr(state, "model_dump", None)
    if callable(dump):
        try:
            return cast(dict[str, Any], dump(mode="json"))
        except TypeError:
            return cast(dict[str, Any], dump())
    return {}


def _errors_as_list(state_dict: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in state_dict.get("errors") or []:
        if isinstance(e, dict):
            out.append(e)
        else:
            md = getattr(e, "model_dump", None)
            if callable(md):
                try:
                    out.append(md(mode="json"))
                except TypeError:
                    out.append(md())
            else:
                out.append({"message": str(e)})
    return out


def _fetch_failure_records_for_run(run_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
    s = get_settings()
    store = LongTermStore(sqlite_path=s.memory.sqlite_path, retention_days=s.memory.retention_days)
    rows = store.get_patterns(pattern_type=FAILURE_PATTERN_TYPE, limit=limit)
    found: list[dict[str, Any]] = []
    for row in rows:
        try:
            data = json.loads(str(row.get("content") or ""))
        except json.JSONDecodeError:
            continue
        if str(data.get("run_id") or "") == run_id:
            found.append(data)
    return found


def _fetch_recent_lessons(*, limit: int = 30) -> list[dict[str, Any]]:
    s = get_settings()
    store = LongTermStore(sqlite_path=s.memory.sqlite_path, retention_days=s.memory.retention_days)
    rows = store.get_patterns(pattern_type=LESSON_PATTERN_TYPE, limit=limit)
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            data = json.loads(str(row.get("content") or ""))
        except json.JSONDecodeError:
            continue
        out.append(data)
    return out


def _proposed_actions(errors: list[dict[str, Any]], test_results: dict[str, Any] | None) -> list[str]:
    actions: list[str] = []
    msgs = " ".join(str(e.get("message") or "") for e in errors).lower()
    if "guardrail" in msgs or any(e.get("type") == "GuardrailError" for e in errors):
        actions.append(
            "Calibrate behavioral guardrails for QA/testing: reduce false positives when "
            "outputs are verbose but still test-scoped; consider role-specific relevance thresholds."
        )
    if "scope" in msgs or "relevance" in msgs:
        actions.append(
            "Tighten QA prompts to require short, test-only outputs (assertions, file paths under tests/) "
            "and avoid generic repo/CI/Docker advice unless requested."
        )
    if isinstance(test_results, dict):
        lint = test_results.get("lint") or {}
        if isinstance(lint, dict) and lint.get("ok") is False:
            actions.append(
                "Run ruff from the generated workspace root; fix N999/package layout if workspace "
                "folder name breaks module naming."
            )
        tests = test_results.get("tests") or {}
        if isinstance(tests, dict) and tests.get("ok") is False:
            actions.append(
                "Run pytest with cwd set to the project workspace (or PYTHONPATH) so imports resolve."
            )
    if not actions:
        actions.append(
            "Continue capturing failure_record rows and promote recurring patterns with "
            "scripts/extract_lessons.py; review data/infra_backlog.jsonl for tooling fixes."
        )
    return actions


def build_manager_self_improvement_report(
    *,
    backend: str,
    run_id: str,
    team_profile: str,
    state: Any,
) -> dict[str, Any]:
    """
    Build structured report dict for this run (single backend per invocation).

    Includes cross-backend *reference* section so the markdown reads like the requested template.
    """
    d = _state_to_dict(state)
    errors = _errors_as_list(d)
    phase = str(d.get("current_phase") or "")
    tr = d.get("test_results") if isinstance(d.get("test_results"), dict) else None
    success = phase == "complete" and not errors

    failure_for_run = _fetch_failure_records_for_run(run_id)
    lessons = _fetch_recent_lessons()

    crewai_note = (
        "CrewAI flow uses the same long-term lesson store; failure_record rows are written on "
        "finalize (success) or handle_fatal_error / recorded errors."
    )
    langgraph_note = (
        "LangGraph persists failure_record at end of invoke/stream from graph state; "
        "promoted lessons inject into prompts on subsequent runs."
    )

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "run": {
            "run_id": run_id,
            "backend": backend,
            "team_profile": team_profile,
            "current_phase": phase,
            "outcome": "success" if success else "failure",
        },
        "summary": {
            "executive": (
                f"Run {run_id} on backend `{backend}` ({team_profile}) finished with phase `{phase}`. "
                f"{'No recorded errors.' if not errors else f'{len(errors)} error(s) recorded.'}"
            ),
        },
        "backends": {
            "langgraph": {
                "role_in_pipeline": "Primary graph orchestration with subgraphs per phase.",
                "notes": langgraph_note,
                "typical_failure_modes": [
                    "Behavioral guardrail failures in QA (scope/relevance).",
                    "file_writer rejecting root-level test files (use tests/).",
                    "pytest/ruff cwd or PYTHONPATH mismatch with workspace layout.",
                ],
            },
            "crewai": {
                "role_in_pipeline": "CrewAI Flow orchestrates crews; recursion limit raised for long runs.",
                "notes": crewai_note,
                "typical_failure_modes": [
                    "Crew/planning recursion or long retry loops (see flow recursion limit).",
                    "Phase errors surfaced via state.errors and last_crew_error metadata.",
                ],
            },
        },
        "this_run": {
            "backend": backend,
            "errors": errors,
            "test_results": tr,
            "failure_records_in_store_for_run": failure_for_run,
        },
        "lessons_in_store": {
            "promoted_lessons_recent": lessons,
        },
        "proposed_self_improvement": _proposed_actions(errors, tr),
    }
    return report


def try_generate_manager_narrative_summary(report: dict[str, Any]) -> str | None:
    """
    Optional LLM narrative (manager role) from the structured report JSON.

    Skips when ``AI_TEAM_MANAGER_REPORT_LLM`` is false, when no OpenRouter key is set,
    or when the call fails (returns None; deterministic report still written).
    """
    raw = (os.environ.get("AI_TEAM_MANAGER_REPORT_LLM") or "true").strip().lower()
    if raw not in ("1", "true", "yes"):
        return None
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        logger.debug("manager_narrative_llm_skipped", reason="no_openrouter_key")
        return None
    try:
        from ai_team.backends.langgraph_backend.graphs.langgraph_chat import (
            create_chat_model_for_role,
        )
        from ai_team.config.models import OpenRouterSettings
        from langchain_core.messages import HumanMessage, SystemMessage

        payload = json.dumps(report, default=str)
        if len(payload) > 14_000:
            payload = payload[:14_000] + "\n... [truncated for LLM context]"

        llm = create_chat_model_for_role("manager", OpenRouterSettings())
        sys_msg = SystemMessage(
            content=(
                "You are a senior Engineering Manager writing a concise internal run summary. "
                "Be factual; do not invent details not supported by the JSON."
            )
        )
        human_msg = HumanMessage(
            content=(
                "Given this structured self-improvement run report (JSON), write 2–4 short paragraphs: "
                "outcome, main problems, what prior lessons/failure records suggest, and top next steps. "
                "Do not repeat the JSON verbatim.\n\n"
                f"JSON:\n{payload}"
            )
        )
        resp = llm.invoke([sys_msg, human_msg])
        content = getattr(resp, "content", None)
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    parts.append(str(block["text"]))
                else:
                    parts.append(str(block))
            text = "".join(parts).strip()
        else:
            text = str(content or "").strip()
        return text or None
    except Exception as e:
        logger.warning("manager_narrative_llm_failed", error=str(e))
        return None


def render_manager_self_improvement_markdown(report: dict[str, Any]) -> str:
    run = report.get("run") or {}
    lines: list[str] = []
    lines.append("# Manager self-improvement report")
    lines.append("")
    lines.append(f"- **Run id**: `{run.get('run_id')}`")
    lines.append(f"- **Backend**: `{run.get('backend')}`")
    lines.append(f"- **Team profile**: `{run.get('team_profile')}`")
    lines.append(f"- **Phase**: `{run.get('current_phase')}`")
    lines.append(f"- **Outcome**: `{run.get('outcome')}`")
    lines.append(f"- **Generated at**: {report.get('generated_at')}")
    lines.append("")
    narrative = report.get("llm_narrative_summary")
    if isinstance(narrative, str) and narrative.strip():
        lines.append("## Manager narrative (LLM)")
        lines.append("")
        lines.append(narrative.strip())
        lines.append("")
    summ = report.get("summary") or {}
    lines.append("## Executive summary")
    lines.append("")
    lines.append(str(summ.get("executive") or "").strip() or "(none)")
    lines.append("")
    lines.append("## Reference: backends (for context)")
    lines.append("")
    be = report.get("backends") or {}
    for name in ("langgraph", "crewai"):
        block = be.get(name) or {}
        lines.append(f"### {name}")
        lines.append("")
        lines.append(str(block.get("notes") or "").strip())
        lines.append("")
        lines.append("**Typical failure modes**")
        for m in block.get("typical_failure_modes") or []:
            lines.append(f"- {m}")
        lines.append("")
    lines.append("## This run: problems observed")
    lines.append("")
    trun = report.get("this_run") or {}
    errs = trun.get("errors") or []
    if not errs:
        lines.append("- None recorded in state.")
    else:
        for i, e in enumerate(errs, 1):
            msg = str(e.get("message") or e)
            et = str(e.get("type") or "")
            ph = str(e.get("phase") or "")
            lines.append(f"{i}. **{et}** (phase: `{ph}`): {msg}")
    lines.append("")
    tr = trun.get("test_results")
    if isinstance(tr, dict) and tr:
        lines.append("### Test / lint signals")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(tr, indent=2, default=str)[:8000])
        lines.append("```")
        lines.append("")
    fr = trun.get("failure_records_in_store_for_run") or []
    lines.append("### Failure records persisted for this run (long-term store)")
    lines.append("")
    if not fr:
        lines.append("- None matched this `run_id` in `learned_patterns` (may still be processing).")
    else:
        lines.append("```json")
        lines.append(json.dumps(fr, indent=2, default=str)[:12000])
        lines.append("```")
    lines.append("")
    lessons = (report.get("lessons_in_store") or {}).get("promoted_lessons_recent") or []
    lines.append("## Lessons in store (promoted, recent)")
    lines.append("")
    if not lessons:
        lines.append("- None.")
    else:
        for les in lessons[:20]:
            role = les.get("agent_role")
            title = les.get("title")
            text = (les.get("text") or "")[:400]
            lines.append(f"- **{role}** — {title}: {text}")
    lines.append("")
    lines.append("## Proposed self-improvement actions")
    lines.append("")
    for a in report.get("proposed_self_improvement") or []:
        lines.append(f"- {a}")
    lines.append("")
    return "\n".join(lines)


def write_manager_self_improvement_report(
    bundle: ResultsBundle,
    *,
    backend: str,
    team_profile: str,
    state: Any,
) -> tuple[Path, Path]:
    """Write JSON + Markdown under ``output/.../reports/`` for this run."""
    report = build_manager_self_improvement_report(
        backend=backend,
        run_id=bundle.project_id,
        team_profile=team_profile,
        state=state,
    )
    llm_summary = try_generate_manager_narrative_summary(report)
    if llm_summary:
        report["llm_narrative_summary"] = llm_summary
    md = render_manager_self_improvement_markdown(report)
    bundle.init_dirs()
    reports_dir = bundle.output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / "manager_self_improvement_report.md"
    md_path.write_text(md.strip() + "\n", encoding="utf-8")
    json_path = reports_dir / "manager_self_improvement_report.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info(
        "manager_self_improvement_report_written",
        run_id=bundle.project_id,
        backend=backend,
        md=str(md_path),
    )
    return md_path, json_path
