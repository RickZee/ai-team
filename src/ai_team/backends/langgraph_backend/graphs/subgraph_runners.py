"""
Invoke compiled Phase-3 subgraphs from main-graph nodes (state mapping + errors).

Subgraphs share ``messages`` with the parent ``LangGraphProjectState`` via ``add_messages``.
Only **new** messages produced after the input seed are merged to avoid duplicating history.

Subgraph compilation is cached per ``(phase, agents, model_overrides)`` so identical
profiles share a compiled graph while different profiles get correctly filtered agents.
"""

from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog
from ai_team.backends.langgraph_backend.graphs.state import LangGraphProjectState
from ai_team.config.settings import get_settings
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

logger = structlog.get_logger(__name__)

_CACHE_MAX = 16

_FENCED_JSON_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


def _nested_config(config: RunnableConfig, suffix: str) -> RunnableConfig:
    base = dict(config) if config else {}
    conf = dict(base.get("configurable") or {})
    tid = conf.get("thread_id")
    if tid is not None:
        conf["thread_id"] = f"{tid}/{suffix}"
    base["configurable"] = conf
    return base


def _message_delta(
    seed: list[BaseMessage], out_msgs: list[BaseMessage]
) -> list[BaseMessage]:
    """Return messages appended after ``seed`` (subgraph output is typically seed + new)."""
    if len(out_msgs) < len(seed):
        return list(out_msgs)
    return list(out_msgs[len(seed) :])


def _extract_profile_from_state(
    state: LangGraphProjectState,
) -> tuple[frozenset[str], tuple[tuple[str, str], ...]]:
    """Read agents and model_overrides from ``state.metadata``."""
    meta = state.get("metadata") or {}
    agents = frozenset(meta.get("agents") or [])
    raw_overrides: dict[str, str] = meta.get("model_overrides") or {}
    overrides = tuple(sorted(raw_overrides.items()))
    return agents, overrides


@lru_cache(maxsize=_CACHE_MAX)
def _cached_planning(
    agents: frozenset[str],
    overrides: tuple[tuple[str, str], ...],
) -> CompiledStateGraph:
    from ai_team.backends.langgraph_backend.graphs.planning import (
        compile_planning_subgraph,
    )

    return compile_planning_subgraph(agents=agents, model_overrides=dict(overrides))


@lru_cache(maxsize=_CACHE_MAX)
def _cached_development(
    agents: frozenset[str],
    overrides: tuple[tuple[str, str], ...],
) -> CompiledStateGraph:
    from ai_team.backends.langgraph_backend.graphs.development import (
        compile_development_subgraph,
    )

    return compile_development_subgraph(agents=agents, model_overrides=dict(overrides))


@lru_cache(maxsize=_CACHE_MAX)
def _cached_testing(
    agents: frozenset[str],
    overrides: tuple[tuple[str, str], ...],
) -> CompiledStateGraph:
    from ai_team.backends.langgraph_backend.graphs.testing import (
        compile_testing_subgraph,
    )

    return compile_testing_subgraph(agents=agents, model_overrides=dict(overrides))


@lru_cache(maxsize=_CACHE_MAX)
def _cached_deployment(
    agents: frozenset[str],
    overrides: tuple[tuple[str, str], ...],
) -> CompiledStateGraph:
    from ai_team.backends.langgraph_backend.graphs.deployment import (
        compile_deployment_subgraph,
    )

    return compile_deployment_subgraph(agents=agents, model_overrides=dict(overrides))


def reset_subgraph_cache() -> None:
    """Clear all cached compiled subgraphs (for tests)."""
    _cached_planning.cache_clear()
    _cached_development.cache_clear()
    _cached_testing.cache_clear()
    _cached_deployment.cache_clear()


def _subgraph_context(state: LangGraphProjectState) -> dict[str, Any]:
    """Initial keys for Phase-5 ``LangGraphSubgraphState`` (guardrails + scope hints)."""
    return {
        "guardrail_checks": [],
        "project_description": (state.get("project_description") or "").strip(),
        "requirements": state.get("requirements") or {},
        "architecture": state.get("architecture") or {},
        "generated_files": state.get("generated_files") or [],
    }


def _parse_structured_planning(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract requirements + architecture from fenced JSON blocks."""
    req: dict[str, Any] = {}
    arch: dict[str, Any] = {}
    for block in _FENCED_JSON_RE.findall(text or ""):
        try:
            obj = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "requirements" in obj and isinstance(obj["requirements"], dict):
            req = obj["requirements"]
        if isinstance(obj, dict) and "architecture" in obj and isinstance(obj["architecture"], dict):
            arch = obj["architecture"]
    return req, arch


def _workspace_root() -> Path:
    root = Path(get_settings().project.workspace_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_cmd(cmd: list[str], *, timeout_s: int, cwd: Path) -> dict[str, Any]:
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return {"ok": r.returncode == 0, "returncode": r.returncode, "output": out}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "output": f"Timed out after {timeout_s}s"}
    except FileNotFoundError:
        return {"ok": False, "returncode": None, "output": f"Command not found: {cmd[0]}"}
    except Exception as e:
        return {"ok": False, "returncode": None, "output": f"Error running {cmd[0]}: {e}"}


def _run_real_quality_gate() -> dict[str, Any]:
    """
    Run real lint + tests in the workspace and return a structured QA result.

    This is the authoritative source of truth for `test_results` in state.
    """
    root = _workspace_root()
    ruff = _run_cmd(["ruff", "check", "."], timeout_s=60, cwd=root)
    pytest = _run_cmd(["pytest", "-q"], timeout_s=300, cwd=root)
    passed = bool(ruff["ok"]) and bool(pytest["ok"])
    return {
        "passed": passed,
        "lint": {"tool": "ruff", **ruff},
        "tests": {"tool": "pytest", **pytest},
    }


def _snapshot_workspace_files() -> list[dict[str, Any]]:
    """
    Best-effort inventory of files written to the per-run workspace.

    This is needed because some tools (e.g. ``file_writer``) may not explicitly
    return a structured file list. Downstream phases (QA/DevOps) require a real
    file set to operate like an engineering organization.
    """
    root = get_settings().project.workspace_dir
    base = (get_settings().project.workspace_dir and get_settings().project.workspace_dir) or ""
    _ = base
    p = __import__("pathlib").Path(root).resolve()
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for fp in p.rglob("*"):
        if fp.is_file():
            try:
                rel = fp.relative_to(p).as_posix()
            except ValueError:
                rel = fp.name
            out.append({"path": rel})
    return sorted(out, key=lambda d: d.get("path", ""))


def _guardrail_error_dict(out: dict[str, Any], phase: str) -> dict[str, Any] | None:
    if not out.get("guardrail_terminal"):
        return None
    checks = out.get("guardrail_checks") or []
    last = checks[-1] if checks else {}
    return {
        "phase": phase,
        "message": str(last.get("message") or "Guardrail failed after max retries"),
        "type": "GuardrailError",
        "guardrail": last,
    }


def planning_subgraph_node(
    state: LangGraphProjectState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run planning supervisor (PO + Architect) and merge new messages."""
    desc = (state.get("project_description") or "").strip()
    if not desc:
        return {
            "errors": [
                {
                    "phase": "planning",
                    "message": "Missing project_description",
                    "type": "ValidationError",
                }
            ],
        }
    agents, overrides = _extract_profile_from_state(state)
    sub = _cached_planning(agents, overrides)
    prior = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    seed: list[BaseMessage] = (
        prior + [HumanMessage(content=desc)] if prior else [HumanMessage(content=desc)]
    )
    try:
        out = sub.invoke(
            {**_subgraph_context(state), "messages": seed},
            _nested_config(config, "planning"),
        )
    except Exception as e:
        logger.exception("planning_subgraph_failed", error=str(e))
        return {
            "errors": [
                {
                    "phase": "planning",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ],
            "current_phase": "planning",
        }
    ge = _guardrail_error_dict(out, "planning")
    if ge:
        return {
            "errors": [ge],
            "current_phase": "planning",
        }
    out_msgs = [m for m in (out.get("messages") or []) if isinstance(m, BaseMessage)]
    delta = _message_delta(seed, out_msgs)
    extracted_req: dict[str, Any] = {}
    extracted_arch: dict[str, Any] = {}
    # Prefer explicit keys; otherwise parse structured JSON from the latest delta message.
    if out.get("requirements") or out.get("architecture"):
        extracted_req = out.get("requirements") or {}
        extracted_arch = out.get("architecture") or {}
    else:
        latest_text = ""
        for m in reversed(delta):
            latest_text = getattr(m, "content", "") or ""
            if isinstance(latest_text, str) and latest_text.strip():
                break
        extracted_req, extracted_arch = _parse_structured_planning(latest_text)
    return {
        "messages": delta,
        "current_phase": "planning",
        "requirements": extracted_req,
        "architecture": extracted_arch,
    }


def development_subgraph_node(
    state: LangGraphProjectState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run development supervisor (backend / frontend / fullstack)."""
    desc = (state.get("project_description") or "").strip()
    req = state.get("requirements") or {}
    arch = state.get("architecture") or {}
    prior_tr = state.get("test_results") or {}
    qa_summary = ""
    if prior_tr.get("passed") is False:
        qa_summary = (
            "\n\nPrevious QA failed. Fix the issues below and update the workspace files.\n"
            f"QA result (JSON):\n{json.dumps(prior_tr, default=str)[:12000]}\n"
        )
    ctx = (
        f"Project:\n{desc}\n\nRequirements (JSON):\n{json.dumps(req, default=str)[:8000]}\n\n"
        f"Architecture (JSON):\n{json.dumps(arch, default=str)[:8000]}\n"
        f"{qa_summary}"
    )
    prior = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    seed: list[BaseMessage] = (
        prior + [HumanMessage(content=ctx)] if prior else [HumanMessage(content=ctx)]
    )
    agents, overrides = _extract_profile_from_state(state)
    sub = _cached_development(agents, overrides)
    try:
        out = sub.invoke(
            {**_subgraph_context(state), "messages": seed},
            _nested_config(config, "development"),
        )
    except Exception as e:
        logger.exception("development_subgraph_failed", error=str(e))
        return {
            "errors": [
                {
                    "phase": "development",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ],
            "current_phase": "development",
        }
    ge = _guardrail_error_dict(out, "development")
    if ge:
        return {
            "errors": [ge],
            "current_phase": "development",
        }
    out_msgs = [m for m in (out.get("messages") or []) if isinstance(m, BaseMessage)]
    delta = _message_delta(seed, out_msgs)
    return {
        "messages": delta,
        "current_phase": "development",
        "generated_files": _snapshot_workspace_files(),
        "deployment_config": out.get("deployment_config"),
    }


def testing_subgraph_node(
    state: LangGraphProjectState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run QA ReAct agent."""
    files = state.get("generated_files") or []
    ctx = (
        "Run QA on the following generated files summary:\n"
        f"{json.dumps(files, default=str)[:12000]}\n"
    )
    prior = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    seed: list[BaseMessage] = (
        prior + [HumanMessage(content=ctx)] if prior else [HumanMessage(content=ctx)]
    )
    agents, overrides = _extract_profile_from_state(state)
    sub = _cached_testing(agents, overrides)
    try:
        out = sub.invoke(
            {**_subgraph_context(state), "messages": seed},
            _nested_config(config, "testing"),
        )
    except Exception as e:
        logger.exception("testing_subgraph_failed", error=str(e))
        return {
            "errors": [
                {
                    "phase": "testing",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ],
            "current_phase": "testing",
        }
    ge = _guardrail_error_dict(out, "testing")
    if ge:
        return {
            "errors": [ge],
            "current_phase": "testing",
        }
    out_msgs = [m for m in (out.get("messages") or []) if isinstance(m, BaseMessage)]
    delta = _message_delta(seed, out_msgs)
    tr = _run_real_quality_gate()
    return {
        "messages": delta,
        "current_phase": "testing",
        "test_results": tr,
    }


def deployment_subgraph_node(
    state: LangGraphProjectState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run DevOps then Cloud sequential subgraph."""
    arch = state.get("architecture") or {}
    files = state.get("generated_files") or []
    ctx = (
        "Prepare deployment.\n"
        f"Architecture:\n{json.dumps(arch, default=str)[:6000]}\n"
        f"Files:\n{json.dumps(files, default=str)[:6000]}\n"
    )
    prior = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    seed: list[BaseMessage] = (
        prior + [HumanMessage(content=ctx)] if prior else [HumanMessage(content=ctx)]
    )
    agents, overrides = _extract_profile_from_state(state)
    sub = _cached_deployment(agents, overrides)
    try:
        out = sub.invoke(
            {**_subgraph_context(state), "messages": seed},
            _nested_config(config, "deployment"),
        )
    except Exception as e:
        logger.exception("deployment_subgraph_failed", error=str(e))
        return {
            "errors": [
                {
                    "phase": "deployment",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ],
            "current_phase": "deployment",
        }
    ge = _guardrail_error_dict(out, "deployment")
    if ge:
        return {
            "errors": [ge],
            "current_phase": "deployment",
        }
    out_msgs = [m for m in (out.get("messages") or []) if isinstance(m, BaseMessage)]
    delta = _message_delta(seed, out_msgs)
    return {
        "messages": delta,
        "current_phase": "deployment",
        "deployment_config": state.get("deployment_config") or {"status": "pending"},
    }
