"""In-process MCP tools wrapping shared ai-team guardrails, tests, and RAG."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
from ai_team.backends.claude_agent_sdk_backend.tools.permissions import MCP_SERVER_KEY
from ai_team.guardrails import code_safety_guardrail
from ai_team.guardrails.security import path_security_guardrail
from ai_team.tools.test_tools import run_pytest
from claude_agent_sdk import create_sdk_mcp_server, tool

logger = structlog.get_logger(__name__)


def _resolve_under_workspace(workspace: Path, file_path: str) -> Path:
    """Resolve a path; must stay under workspace (after resolve)."""
    raw = (file_path or "").strip()
    candidate = (workspace / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    workspace_r = workspace.resolve()
    try:
        candidate.relative_to(workspace_r)
    except ValueError as e:
        raise ValueError(f"Path escapes workspace: {file_path}") from e
    return candidate


def build_ai_team_mcp_tools(workspace: Path) -> list[Any]:
    """Create SdkMcpTool instances bound to ``workspace``."""

    @tool(
        "run_guardrails",
        "Run path security and (for .py) code safety checks on a workspace file.",
        {"file_path": str, "check_types": list},
    )
    async def run_guardrails(args: dict[str, Any]) -> dict[str, Any]:
        check_types = list(args.get("check_types") or ["path", "code_safety"])
        rel = str(args.get("file_path") or "").strip()
        try:
            path = _resolve_under_workspace(workspace, rel)
        except ValueError as e:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "is_error": True,
            }
        results: dict[str, Any] = {}
        if "path" in check_types:
            pr = path_security_guardrail(str(path))
            results["path_security"] = pr.model_dump()
        if "code_safety" in check_types and path.suffix == ".py":
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                return {
                    "content": [{"type": "text", "text": f"Cannot read file: {e}"}],
                    "is_error": True,
                }
            cs = code_safety_guardrail(text)
            results["code_safety"] = cs.model_dump()
        fail = any(
            isinstance(v, dict) and v.get("status") == "fail"
            for v in results.values()
            if isinstance(v, dict)
        )
        payload = json.dumps(results, default=str)
        return {
            "content": [{"type": "text", "text": payload}],
            "is_error": bool(fail),
        }

    @tool(
        "run_project_tests",
        "Run pytest with coverage for a path relative to the process cwd (usually repo root).",
        {
            "test_path": str,
            "source_path": str,
        },
    )
    async def run_project_tests(args: dict[str, Any]) -> dict[str, Any]:
        test_path = str(args.get("test_path") or "tests").strip()
        source_path = str(args.get("source_path") or "src").strip()
        try:
            result = run_pytest(test_path, source_path)
            payload = result.model_dump()
        except Exception as e:
            logger.warning("mcp_run_project_tests_failed", error=str(e))
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "is_error": True,
            }
        return {
            "content": [{"type": "text", "text": json.dumps(payload, default=str)}],
            "is_error": not bool(payload.get("success")),
        }

    @tool(
        "validate_code_safety",
        "Check a code string for dangerous patterns (eval, exec, etc.).",
        {"code": str},
    )
    async def validate_code_safety(args: dict[str, Any]) -> dict[str, Any]:
        code = str(args.get("code") or "")
        r = code_safety_guardrail(code)
        body = r.model_dump()
        if r.status == "fail":
            return {
                "content": [{"type": "text", "text": json.dumps(body, default=str)}],
                "is_error": True,
            }
        return {"content": [{"type": "text", "text": json.dumps(body, default=str)}]}

    @tool(
        "search_knowledge",
        "Search ingested markdown knowledge (RAG). Disabled when RAG is off.",
        {"query": str, "top_k": int},
    )
    async def search_knowledge(args: dict[str, Any]) -> dict[str, Any]:
        q = str(args.get("query") or "").strip()
        top_k = int(args.get("top_k") or 5)
        try:
            from ai_team.rag.config import get_rag_config
            from ai_team.rag.pipeline import get_rag_pipeline

            cfg = get_rag_config()
            if not cfg.enabled:
                text = "RAG is disabled; set RAG_ENABLED=true and ingest knowledge."
            elif not q:
                text = "Provide a non-empty query."
            else:
                pipe = get_rag_pipeline()
                hits = pipe.retrieve(q, top_k=top_k if top_k > 0 else cfg.top_k)
                text = pipe.format_context(hits) if hits else "No matching snippets found."
        except Exception as e:
            logger.warning("mcp_search_knowledge_failed", error=str(e))
            text = f"Knowledge search failed: {e}"
        return {"content": [{"type": "text", "text": text}]}

    return [run_guardrails, run_project_tests, validate_code_safety, search_knowledge]


def build_ai_team_mcp_server(workspace: Path) -> Any:
    """Return :class:`McpSdkServerConfig` for ``ClaudeAgentOptions.mcp_servers``."""
    tools = build_ai_team_mcp_tools(workspace)
    return create_sdk_mcp_server(name=MCP_SERVER_KEY, version="1.0.0", tools=tools)
