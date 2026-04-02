"""Claude Code tool allow-lists per role (plus MCP tool names for ai_team_tools server)."""

from __future__ import annotations

# MCP server registry key must match ``mcp_servers`` dict key in orchestrator options.
MCP_SERVER_KEY = "ai_team_tools"

# Exposed MCP tools (decorator names) — referenced as mcp__{key}__{name}
MCP_RUN_GUARDRAILS = f"mcp__{MCP_SERVER_KEY}__run_guardrails"
MCP_RUN_PROJECT_TESTS = f"mcp__{MCP_SERVER_KEY}__run_project_tests"
MCP_VALIDATE_CODE_SAFETY = f"mcp__{MCP_SERVER_KEY}__validate_code_safety"
MCP_SEARCH_KNOWLEDGE = f"mcp__{MCP_SERVER_KEY}__search_knowledge"


def orchestrator_allowed_tools() -> list[str]:
    return [
        "Agent",
        "Read",
        "Glob",
        "Grep",
        "Write",
        "Edit",
        "Bash",
        "TodoWrite",
        MCP_RUN_GUARDRAILS,
    ]


def specialist_writer_tools() -> list[str]:
    """Read/write search tools for specialists that do not delegate."""
    return ["Read", "Write", "Glob", "Grep"]


def planning_allowed_tools(*, include_mcp: bool) -> list[str]:
    tools = ["Agent", "Read", "Glob", "Grep", "Write"]
    if include_mcp:
        tools.append(MCP_RUN_GUARDRAILS)
    return tools


def architect_allowed_tools() -> list[str]:
    return ["Read", "Write", "Glob", "Grep", MCP_SEARCH_KNOWLEDGE]


def developer_allowed_tools() -> list[str]:
    return [
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Glob",
        "Grep",
        MCP_VALIDATE_CODE_SAFETY,
    ]


def qa_allowed_tools() -> list[str]:
    return [
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Glob",
        "Grep",
        MCP_RUN_PROJECT_TESTS,
        MCP_RUN_GUARDRAILS,
    ]


def devops_allowed_tools() -> list[str]:
    return ["Read", "Write", "Glob", "Grep", MCP_SEARCH_KNOWLEDGE]


def get_disallowed_tools_for_yaml_role(role: str) -> list[str]:
    """
    Tools blocked for a given ``agents.yaml`` role (defense in depth for subagents).

    The allow-list already omits many tools; this blocks risky ones if the model
    attempts them (e.g. shell from a planning-only agent).
    """
    key = role.strip().lower().replace("-", "_")
    if key == "product_owner":
        return ["Bash", "Edit", "MultiEdit"]
    if key == "architect":
        return ["Bash"]
    if key == "manager":
        return []
    return []


def get_allowed_tools_for_yaml_role(role: str) -> list[str]:
    """Map ``agents.yaml``-style role keys to tool lists (for tests / introspection)."""
    key = role.strip().lower()
    if key == "product_owner":
        return specialist_writer_tools()
    if key == "architect":
        return architect_allowed_tools()
    if key in ("backend_developer", "frontend_developer", "fullstack_developer"):
        return developer_allowed_tools()
    if key == "qa_engineer":
        return qa_allowed_tools()
    if key in ("devops_engineer", "cloud_engineer"):
        return devops_allowed_tools()
    if key == "manager":
        return orchestrator_allowed_tools()
    return planning_allowed_tools(include_mcp=True)
