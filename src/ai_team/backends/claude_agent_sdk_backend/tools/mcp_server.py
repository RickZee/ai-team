"""In-process MCP tools wrapping shared ai-team guardrails and tests."""

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
        "run_app_smoke",
        (
            "Boot the generated app from the workspace and probe it over HTTP "
            "(docker compose or a Flask app module). Catches runtime breakage "
            "that passing unit tests miss (app won't boot, every request 500s). "
            "Writes docs/smoke_results.json. Run after pytest, before declaring "
            "the run complete."
        ),
        {},
    )
    async def run_app_smoke(_args: dict[str, Any]) -> dict[str, Any]:
        from ai_team.tools.smoke_tools import run_app_smoke as _run_smoke

        try:
            result = _run_smoke(workspace)
        except Exception as e:  # noqa: BLE001 - report, don't crash the agent
            logger.warning("mcp_run_app_smoke_failed", error=str(e))
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "is_error": True,
            }
        payload = json.dumps(result.model_dump(), default=str)
        # A run that booted but failed probes is a real failure the agent must
        # fix; a skipped smoke (no Docker / no entrypoint) is not an error.
        is_error = bool(result.ran and not result.success)
        return {
            "content": [{"type": "text", "text": payload}],
            "is_error": is_error,
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
        "write_workspace_file",
        "Write a file through the shared ToolBus (draft-then-commit). Path relative to workspace.",
        {"path": str, "content": str},
    )
    async def write_workspace_file(args: dict[str, Any]) -> dict[str, Any]:
        from ai_team.tools.bus import get_bus, observation_to_agent_text
        from ai_team.tools.kinds import ToolRequest

        obs = get_bus().invoke(
            ToolRequest(
                tool="write_file",
                args={
                    "path": str(args.get("path") or ""),
                    "content": str(args.get("content") or ""),
                },
                backend="claude-agent-sdk",
            )
        )
        return {
            "content": [{"type": "text", "text": observation_to_agent_text(obs)}],
            "is_error": not obs.ok,
        }

    @tool(
        "acceptance_status",
        "Read-only acceptance list status: counts and the next unsatisfied item.",
        {},
    )
    async def acceptance_status(_args: dict[str, Any]) -> dict[str, Any]:
        from ai_team.harness.acceptance import AcceptanceError
        from ai_team.harness.acceptance import status as acc_status

        try:
            st = acc_status(workspace)
        except AcceptanceError as e:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "is_error": True,
            }
        payload = {
            "total": st.total,
            "passing": st.passing,
            "unsatisfied": st.unsatisfied,
            "next_item": st.next_item.model_dump(mode="json") if st.next_item else None,
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, default=str)}]}

    @tool(
        "acceptance_mark_passing",
        "Mark one acceptance item passing with evidence paths (QA only).",
        {
            "item_id": str,
            "evidence": list,
            "verified_by": str,
            "agent_role": str,
            "session_id": str,
            "subagent_id": str,
        },
    )
    async def acceptance_mark_passing(args: dict[str, Any]) -> dict[str, Any]:
        from ai_team.harness.acceptance import (
            AcceptanceError,
            VerifierIdentity,
            mark_passing,
        )

        item_id = str(args.get("item_id") or "").strip()
        evidence = [str(p) for p in (args.get("evidence") or [])]
        verified_by = str(args.get("verified_by") or "qa_agent")
        identity = VerifierIdentity(
            agent_role=str(args.get("agent_role") or "qa_engineer"),
            session_id=str(args.get("session_id") or ""),
            subagent_id=str(args.get("subagent_id") or "") or None,
        )
        if verified_by not in {"smoke", "ui_smoke", "test", "qa_agent"}:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": f"invalid verified_by: {verified_by}"}),
                    }
                ],
                "is_error": True,
            }
        try:
            doc = mark_passing(
                workspace,
                item_id,
                evidence=evidence,
                verified_by=verified_by,  # type: ignore[arg-type]
                identity=identity,
            )
        except AcceptanceError as e:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "is_error": True,
            }
        item = next((i for i in doc.items if i.id == item_id), None)
        payload = {
            "ok": True,
            "item": item.model_dump(mode="json") if item else None,
            "identity": identity.model_dump(mode="json"),
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, default=str)}]}

    @tool(
        "run_ui_smoke",
        (
            "Playwright UI smoke against the local app declared in scenario.ui. "
            "Never probes a foreign host. Writes docs/ui_smoke_results.json. QA only."
        ),
        {"item_id": str},
    )
    async def run_ui_smoke(args: dict[str, Any]) -> dict[str, Any]:
        from ai_team.tools.ui_smoke_tools import run_ui_smoke as _run_ui

        item_id = str(args.get("item_id") or "ui")
        scenario: dict[str, Any] = {}
        scenario_path = workspace / "docs" / "scenario.json"
        if scenario_path.is_file():
            try:
                loaded = json.loads(scenario_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    scenario = loaded
            except (OSError, ValueError):
                scenario = {}
        try:
            result = _run_ui(workspace, scenario=scenario, item_id=item_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("mcp_run_ui_smoke_failed", error=str(e))
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)})}],
                "is_error": True,
            }
        payload = json.dumps(result.model_dump(mode="json"), default=str)
        is_error = result.status == "fail"
        return {"content": [{"type": "text", "text": payload}], "is_error": is_error}

    return [
        run_guardrails,
        run_project_tests,
        run_app_smoke,
        validate_code_safety,
        write_workspace_file,
        acceptance_status,
        acceptance_mark_passing,
        run_ui_smoke,
    ]


def build_ai_team_mcp_server(workspace: Path) -> Any:
    """Return :class:`McpSdkServerConfig` for ``ClaudeAgentOptions.mcp_servers``."""
    tools = build_ai_team_mcp_tools(workspace)
    return create_sdk_mcp_server(name=MCP_SERVER_KEY, version="1.0.0", tools=tools)
