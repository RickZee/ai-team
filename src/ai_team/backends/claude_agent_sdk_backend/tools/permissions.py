"""Claude Code tool allow-lists per role (plus MCP tool names for ai_team_tools server)."""

from __future__ import annotations

# MCP server registry key must match ``mcp_servers`` dict key in orchestrator options.
MCP_SERVER_KEY = "ai_team_tools"

# Exposed MCP tools (decorator names) — referenced as mcp__{key}__{name}
MCP_RUN_GUARDRAILS = f"mcp__{MCP_SERVER_KEY}__run_guardrails"
MCP_RUN_PROJECT_TESTS = f"mcp__{MCP_SERVER_KEY}__run_project_tests"
MCP_RUN_APP_SMOKE = f"mcp__{MCP_SERVER_KEY}__run_app_smoke"
MCP_VALIDATE_CODE_SAFETY = f"mcp__{MCP_SERVER_KEY}__validate_code_safety"
MCP_SEARCH_KNOWLEDGE = f"mcp__{MCP_SERVER_KEY}__search_knowledge"
MCP_ACCEPTANCE_STATUS = f"mcp__{MCP_SERVER_KEY}__acceptance_status"
MCP_ACCEPTANCE_MARK_PASSING = f"mcp__{MCP_SERVER_KEY}__acceptance_mark_passing"
MCP_RUN_UI_SMOKE = f"mcp__{MCP_SERVER_KEY}__run_ui_smoke"

# Native Claude Code tools plus every MCP_* constant defined above.
REGISTERED_TOOL_NAMES = frozenset(
    {
        "Agent",
        "Read",
        "Glob",
        "Grep",
        "Write",
        "Edit",
        "MultiEdit",
        "Bash",
        "TodoWrite",
        MCP_RUN_GUARDRAILS,
        MCP_RUN_PROJECT_TESTS,
        MCP_RUN_APP_SMOKE,
        MCP_VALIDATE_CODE_SAFETY,
        MCP_SEARCH_KNOWLEDGE,
        MCP_ACCEPTANCE_STATUS,
        MCP_ACCEPTANCE_MARK_PASSING,
        MCP_RUN_UI_SMOKE,
    }
)

# Per-role bash allowlists (R14.2). Evaluated only when the component is on.
BASH_ALLOWLIST_BY_ROLE: dict[str, frozenset[str]] = {
    "product_owner": frozenset(),
    "architect": frozenset({"git"}),
    "developer": frozenset(
        {"pytest", "python", "python3", "ruff", "mypy", "black", "git", "ls", "cat"}
    ),
    "backend_developer": frozenset(
        {"pytest", "python", "python3", "ruff", "mypy", "black", "git", "ls", "cat"}
    ),
    "frontend_developer": frozenset(
        {"pytest", "python", "python3", "npm", "npx", "git", "ls", "cat"}
    ),
    "qa_engineer": frozenset({"pytest", "python", "python3", "ruff", "git", "ls", "cat"}),
    "devops_engineer": frozenset({"docker", "git", "ls", "cat"}),
    "cloud_engineer": frozenset({"docker", "git", "ls", "cat"}),
    "manager": frozenset({"git", "ls"}),
}


def bash_allowlist_enabled() -> bool:
    """Allowlist is off until the FP budget holds (R14.6)."""
    import os

    return os.environ.get("AI_TEAM_BASH_ALLOWLIST", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def bash_command_permitted(role: str, command_name: str) -> bool:
    """True when *command_name* is on *role*'s allowlist."""
    key = role.strip().lower().replace("-", "_")
    allowed = BASH_ALLOWLIST_BY_ROLE.get(key, BASH_ALLOWLIST_BY_ROLE["developer"])
    return command_name in allowed


def assert_role_tools_are_registered() -> None:
    """Guard: every role allow-list entry must name a registered tool."""
    for role, tools in {
        "manager": orchestrator_allowed_tools(),
        "product_owner": specialist_writer_tools(),
        "architect": architect_allowed_tools(),
        "developer": developer_allowed_tools(),
        "qa_engineer": qa_allowed_tools(),
        "devops_engineer": devops_allowed_tools(),
    }.items():
        unknown = set(tools) - REGISTERED_TOOL_NAMES
        if unknown:
            raise AssertionError(f"{role} allow-list names unknown tools: {sorted(unknown)}")


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
        MCP_ACCEPTANCE_STATUS,
    ]


def specialist_writer_tools() -> list[str]:
    """Read/write search tools for specialists that do not delegate."""
    return ["Read", "Write", "Glob", "Grep", MCP_ACCEPTANCE_STATUS]


def planning_allowed_tools(*, include_mcp: bool) -> list[str]:
    tools = ["Agent", "Read", "Glob", "Grep", "Write"]
    if include_mcp:
        tools.append(MCP_RUN_GUARDRAILS)
        tools.append(MCP_ACCEPTANCE_STATUS)
    return tools


def architect_allowed_tools() -> list[str]:
    return ["Read", "Write", "Glob", "Grep", MCP_SEARCH_KNOWLEDGE, MCP_ACCEPTANCE_STATUS]


def developer_allowed_tools() -> list[str]:
    return [
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Glob",
        "Grep",
        MCP_VALIDATE_CODE_SAFETY,
        MCP_ACCEPTANCE_STATUS,
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
        MCP_RUN_APP_SMOKE,
        MCP_RUN_GUARDRAILS,
        MCP_ACCEPTANCE_STATUS,
        MCP_ACCEPTANCE_MARK_PASSING,
        MCP_RUN_UI_SMOKE,
    ]


def devops_allowed_tools() -> list[str]:
    return [
        "Read",
        "Write",
        "Glob",
        "Grep",
        MCP_RUN_APP_SMOKE,
        MCP_SEARCH_KNOWLEDGE,
        MCP_ACCEPTANCE_STATUS,
    ]


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
