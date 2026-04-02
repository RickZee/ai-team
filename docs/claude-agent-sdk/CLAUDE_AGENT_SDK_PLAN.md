# AI-Team: Claude Agent SDK Backend Plan

> Add a **Claude Agent SDK** orchestration backend alongside CrewAI and LangGraph. The SDK's native subagent spawning, session persistence, streaming, and MCP integration make it a natural fit for the multi-agent software development pipeline.

---

## 0. How This Backend Differs

The Claude Agent SDK is fundamentally different from CrewAI and LangGraph. Understanding these differences is critical to a good architecture:

| Dimension | CrewAI | LangGraph | Claude Agent SDK |
|-----------|--------|-----------|-----------------|
| **Orchestration model** | Crews with hierarchical/sequential process | Explicit state graph with nodes and edges | Autonomous agent loop with subagent delegation |
| **Agent definition** | `Agent` class with role/goal/backstory | `create_react_agent()` with prompt + tools | `AgentDefinition` with description + prompt + tools |
| **Multi-agent pattern** | Manager delegates within a Crew | Supervisor node routes between agent nodes | Parent agent spawns subagents via `Agent` tool |
| **State management** | Pydantic `ProjectState` in flow | TypedDict state passed through graph | Session transcript (JSONL) + file system |
| **Persistence** | Manual (ChromaDB + SQLite) | Checkpointer (SQLite/Postgres) | Built-in session persistence (~/.claude/projects/) |
| **Human-in-the-loop** | Flag + polling | `interrupt()` / `Command(resume=...)` | `canUseTool` callback + `AskUserQuestion` tool |
| **Streaming** | Callbacks | `graph.stream()` events | `StreamEvent` messages from `query()` |
| **Tool definition** | CrewAI `@tool` decorator | LangChain `@tool` decorator | MCP server wrapping custom functions |
| **MCP support** | `crewai-tools[mcp]` | `langchain-mcp-adapters` | **Native** — first-class MCP client |
| **Cost tracking** | Manual token counting | Manual | Built-in `total_cost_usd` + `max_budget_usd` |
| **Context management** | Manual | Manual | Automatic compaction + prompt caching |
| **Model per agent** | Via LLM config per agent | Via `ChatOpenAI` per node | `model` field on `AgentDefinition` |
| **Retry/error** | Guardrail retry + tenacity | Conditional edge loops | Agent loop auto-retries; `is_error` on tools |

### Key insight: Session-based, not state-based

CrewAI and LangGraph pass explicit state objects between nodes/crews. The Claude Agent SDK operates differently: it maintains a **conversation transcript** (session) that accumulates across turns. State is implicit in the conversation history, not in a typed data structure.

This means:
- **No explicit `ProjectState` object** flowing through the pipeline
- **File-based handoff**: agents write artifacts to the filesystem; downstream agents read them
- **Session continuation**: later phases can `resume` the same session to access prior context
- **Automatic context management**: the SDK compacts old turns when the context window fills

### Key advantage: Native everything

The SDK natively handles things that require libraries/plugins in other frameworks:
- MCP servers are first-class (no adapter library)
- Streaming is built into `query()`
- Cost tracking is built into `ResultMessage`
- Session persistence is automatic
- Subagent spawning is a built-in tool

---

## 1. Architecture Overview

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                   CLAUDE AGENT SDK BACKEND                                    │
│                                                                              │
│  ClaudeAgentBackend(Backend)                                                 │
│    ├── run(description, profile) → ProjectResult                             │
│    └── stream(description, profile) → AsyncIterator[dict]                    │
│                                                                              │
│  Orchestrator Agent (Claude Opus/Sonnet)                                     │
│    System prompt: "You are an engineering manager..."                         │
│    Tools: [Agent, Read, Glob, Grep, TodoWrite]                               │
│    Subagents:                                                                │
│      ├── planning-agent (sequential: PO → Architect)                         │
│      │     ├── product-owner subagent                                        │
│      │     └── architect subagent                                            │
│      ├── development-agent (parallel: backend + frontend)                    │
│      │     ├── backend-developer subagent                                    │
│      │     ├── frontend-developer subagent                                   │
│      │     └── fullstack-developer subagent                                  │
│      ├── testing-agent                                                       │
│      │     └── qa-engineer subagent                                          │
│      └── deployment-agent (sequential: devops → cloud)                       │
│            ├── devops-engineer subagent                                       │
│            └── cloud-engineer subagent                                        │
│                                                                              │
│  Session: persisted at ~/.claude/projects/<project>/                          │
│  Cost: tracked via ResultMessage.total_cost_usd                              │
└──────────────────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌─────────────────────────────────┐
│ Direct tools    │          │ MCP Servers (native)             │
│ (via SDK MCP)   │          │                                  │
│ - file_tools    │          │  ┌─────────┐  ┌──────────┐     │
│ - code_tools    │          │  │ GitHub   │  │Filesystem│     │
│ - git_tools     │          │  │ MCP Srv  │  │ MCP Srv  │     │
│ - test_tools    │          │  └─────────┘  └──────────┘     │
│ - guardrails    │          │  ┌─────────┐  ┌──────────┐     │
│ (as MCP server) │          │  │ai-team  │  │ Docker   │     │
│                 │          │  │MCP Srv  │  │ MCP Srv  │     │
└─────────────────┘          │  └─────────┘  └──────────┘     │
                             └─────────────────────────────────┘
```

### Orchestration model: Nested subagents

Unlike LangGraph's flat graph or CrewAI's crew-based model, the Claude Agent SDK uses **nested subagent delegation**:

```text
Orchestrator (Manager)
  │
  ├── "Use the planning-agent to create requirements and architecture"
  │     │
  │     ├── planning-agent uses product-owner subagent
  │     └── planning-agent uses architect subagent
  │     └── Returns: requirements.md + architecture.md written to workspace
  │
  ├── "Use the development-agent to implement the architecture"
  │     │
  │     ├── development-agent uses backend-developer subagent
  │     ├── development-agent uses frontend-developer subagent (in parallel)
  │     └── Returns: source files written to workspace
  │
  ├── "Use the testing-agent to run tests and verify quality"
  │     │
  │     └── qa-engineer runs tests, writes test_results.json
  │
  └── "Use the deployment-agent to create deployment artifacts"
        │
        ├── devops-engineer creates Dockerfile, CI pipeline
        └── cloud-engineer creates IaC
```

Each level is a separate `query()` call or a subagent spawned within a session.

---

## 2. Agent Definitions

### 2.1 Agent hierarchy

```text
Level 0: Orchestrator
  └── Level 1: Phase Agents (planning, development, testing, deployment)
        └── Level 2: Specialist Agents (PO, architect, backend dev, etc.)
```

The orchestrator is the only agent that needs all subagent definitions. Phase agents only know about their own specialists.

### 2.2 Orchestrator Agent

```python
ORCHESTRATOR_PROMPT = """You are an Engineering Manager orchestrating a software development team.

Given a project description, you will:
1. Use the planning-agent to analyze requirements and design architecture
2. Review the planning output (requirements.md, architecture.md in workspace)
3. Use the development-agent to implement the architecture
4. Use the testing-agent to run tests and verify quality
5. If tests fail and retries remain, use development-agent again with test feedback
6. Use the deployment-agent to create deployment artifacts
7. Produce a final project report

Rules:
- Always review each phase's output before proceeding to the next
- If any phase produces incomplete or low-quality output, retry (max {max_retries} times)
- Write phase transition logs to workspace/logs/phases.jsonl
- On unrecoverable error, write error report and stop gracefully

Active team profile: {profile_name}
Active agents: {agent_list}
Active phases: {phase_list}
"""

orchestrator_options = ClaudeAgentOptions(
    model="opus",
    allowed_tools=["Agent", "Read", "Glob", "Grep", "Write", "Bash", "TodoWrite"],
    permission_mode="acceptEdits",
    max_turns=50,
    max_budget_usd=20.00,
    agents={
        "planning-agent": planning_agent_def,
        "development-agent": development_agent_def,
        "testing-agent": testing_agent_def,
        "deployment-agent": deployment_agent_def,
    },
    mcp_servers=profile_mcp_servers,
    setting_sources=["project"],  # Load CLAUDE.md for project conventions
)
```

### 2.3 Phase Agent Definitions

Each phase agent is an `AgentDefinition` that itself has sub-agents:

```python
planning_agent_def = AgentDefinition(
    description="Coordinates planning: gathers requirements and designs architecture",
    prompt="""You coordinate the planning phase for a software project.

Step 1: Use the product-owner agent to analyze the project description and produce
        a requirements document. The PO writes to workspace/docs/requirements.md.
Step 2: Read the requirements, then use the architect agent to design the system.
        The architect writes to workspace/docs/architecture.md.
Step 3: Review both documents for completeness and consistency.
        If incomplete, re-invoke the relevant agent with feedback.

Write your planning summary to workspace/docs/planning_summary.md.""",
    tools=["Agent", "Read", "Glob", "Grep", "Write"],
    model="sonnet",
    agents={
        "product-owner": product_owner_def,
        "architect": architect_def,
    },
)

development_agent_def = AgentDefinition(
    description="Coordinates code generation: assigns work to developers",
    prompt="""You coordinate the development phase.

Step 1: Read workspace/docs/requirements.md and workspace/docs/architecture.md.
Step 2: Break the implementation into tasks for your developer agents.
Step 3: Use backend-developer, frontend-developer, or fullstack-developer as needed.
        Agents can run in parallel for independent modules.
Step 4: Review generated code for completeness (all files referenced in architecture exist).

Each developer writes files directly to workspace/src/.
Write a development summary to workspace/docs/development_summary.md.""",
    tools=["Agent", "Read", "Glob", "Grep", "Write", "Edit"],
    model="sonnet",
    agents={
        "backend-developer": backend_dev_def,
        "frontend-developer": frontend_dev_def,
        "fullstack-developer": fullstack_dev_def,
    },
)

testing_agent_def = AgentDefinition(
    description="Runs tests, analyzes coverage, reports quality",
    prompt="""You are a QA engineer. Your job:

1. Read the generated code in workspace/src/ and requirements in workspace/docs/
2. Write test files to workspace/tests/
3. Run tests using Bash (pytest or appropriate runner)
4. Analyze coverage and failures
5. Write test results to workspace/docs/test_results.json (structured)
   and workspace/docs/test_report.md (human-readable)

If tests fail, clearly describe what failed and why so the development
agent can fix it on retry.""",
    tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    model="sonnet",
)

deployment_agent_def = AgentDefinition(
    description="Creates deployment artifacts: Docker, CI/CD, IaC",
    prompt="""You coordinate deployment artifact creation.

Step 1: Read architecture and generated code.
Step 2: Use devops-engineer for Dockerfile, docker-compose, CI/CD pipeline.
Step 3: Use cloud-engineer for infrastructure-as-code (if applicable).
Step 4: Write deployment summary to workspace/docs/deployment_summary.md.""",
    tools=["Agent", "Read", "Write", "Glob", "Grep"],
    model="sonnet",
    agents={
        "devops-engineer": devops_def,
        "cloud-engineer": cloud_def,
    },
)
```

### 2.4 Specialist Agent Definitions

```python
product_owner_def = AgentDefinition(
    description="Requirements analyst: user stories, acceptance criteria, MoSCoW",
    prompt="""You are a Product Owner. Given a project description:

1. Analyze the request and identify target users
2. Write user stories in "As a... I want... So that..." format
3. Add acceptance criteria for each story
4. Prioritize using MoSCoW (Must/Should/Could/Won't)
5. List assumptions and constraints

Write the full requirements document to workspace/docs/requirements.md.
Use structured markdown with clear sections.""",
    tools=["Read", "Write", "Glob", "Grep"],
    model="sonnet",
)

architect_def = AgentDefinition(
    description="Solutions architect: system design, tech selection, ADRs",
    prompt="""You are a Solutions Architect. Given requirements:

1. Read workspace/docs/requirements.md
2. Design the system: components, interfaces, data model
3. Select technology stack with justification
4. Define API contracts and data flows
5. Write Architecture Decision Records (ADRs) for key choices

Write the architecture document to workspace/docs/architecture.md.
Include ASCII diagrams for system overview and data flow.""",
    tools=["Read", "Write", "Glob", "Grep"],
    model="opus",  # Stronger model for architecture decisions
)

backend_dev_def = AgentDefinition(
    description="Backend developer: APIs, services, database schemas",
    prompt="""You are a Backend Developer. Given architecture:

1. Read workspace/docs/architecture.md for your assigned components
2. Implement backend code: APIs, services, models, database schemas
3. Follow best practices: type hints, docstrings, error handling
4. Write files to workspace/src/ following the architecture's directory structure
5. Include requirements.txt or pyproject.toml for dependencies

Write clean, production-quality code. No TODO stubs or placeholder implementations.""",
    tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    model="sonnet",
)

frontend_dev_def = AgentDefinition(
    description="Frontend developer: UI components, state management, styling",
    prompt="""You are a Frontend Developer. Given architecture:

1. Read workspace/docs/architecture.md for UI components
2. Implement frontend: components, pages, state management, API clients
3. Follow modern frontend best practices
4. Write files to workspace/src/ per architecture

Write clean, well-structured code. Include package.json if applicable.""",
    tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    model="sonnet",
)

fullstack_dev_def = AgentDefinition(
    description="Fullstack developer: both backend and frontend",
    prompt="""You are a Fullstack Developer. Implement both backend and frontend:

1. Read workspace/docs/architecture.md
2. Build the complete application (server + client)
3. Ensure frontend-backend integration works end-to-end

Write all code to workspace/src/.""",
    tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    model="sonnet",
)

devops_def = AgentDefinition(
    description="DevOps engineer: Docker, CI/CD, monitoring",
    prompt="""You are a DevOps Engineer:

1. Read workspace/docs/architecture.md and workspace/src/ structure
2. Create Dockerfile (multi-stage, minimal image)
3. Create docker-compose.yml if multi-service
4. Create CI/CD pipeline (.github/workflows/ci.yml)
5. Add health checks and basic monitoring config

Write files to workspace/ root and workspace/.github/.""",
    tools=["Read", "Write", "Glob", "Grep"],
    model="sonnet",
)

cloud_def = AgentDefinition(
    description="Cloud engineer: IaC, cost optimization, security",
    prompt="""You are a Cloud Infrastructure Engineer:

1. Read workspace/docs/architecture.md for deployment requirements
2. Create infrastructure-as-code (Terraform, CloudFormation, or CDK)
3. Consider: cost, security, reliability, scalability
4. Write IaC files to workspace/infrastructure/

Only create IaC if the architecture requires cloud deployment.""",
    tools=["Read", "Write", "Glob", "Grep"],
    model="sonnet",
)
```

### 2.5 Team Profile Filtering

Not all agents are defined for every profile. The backend filters `AgentDefinition` dicts based on `TeamProfile.agents`:

```python
def build_agent_definitions(profile: TeamProfile) -> dict[str, AgentDefinition]:
    """Build only the agents needed for this profile."""
    all_agents = {
        "product-owner": product_owner_def,
        "architect": architect_def,
        "backend-developer": backend_dev_def,
        "frontend-developer": frontend_dev_def,
        "fullstack-developer": fullstack_dev_def,
        "devops-engineer": devops_def,
        "cloud-engineer": cloud_def,
    }
    # Filter based on profile
    active = {k: v for k, v in all_agents.items()
              if k.replace("-", "_") in profile.agents}

    # Build phase agents with only active specialists
    phase_agents = {}
    if "planning" in profile.phases:
        phase_agents["planning-agent"] = build_planning_agent(active)
    if "development" in profile.phases:
        phase_agents["development-agent"] = build_development_agent(active)
    if "testing" in profile.phases:
        phase_agents["testing-agent"] = testing_agent_def
    if "deployment" in profile.phases:
        phase_agents["deployment-agent"] = build_deployment_agent(active)

    return phase_agents
```

---

## 3. State Management: File-Based Handoff

### 3.1 Workspace Convention

Unlike CrewAI/LangGraph where state flows through typed objects, the Claude Agent SDK backend uses the **filesystem as state**:

```text
workspace/
├── docs/
│   ├── requirements.md        # PO output → read by Architect, Developers
│   ├── architecture.md        # Architect output → read by Developers, DevOps
│   ├── planning_summary.md    # Planning agent summary
│   ├── development_summary.md # Development agent summary
│   ├── test_results.json      # QA structured output → read by Orchestrator
│   ├── test_report.md         # QA human-readable report
│   └── deployment_summary.md  # Deployment agent summary
├── src/                       # Generated source code
├── tests/                     # Generated test files
├── infrastructure/            # IaC files (if applicable)
├── Dockerfile                 # DevOps output
├── docker-compose.yml         # DevOps output
├── .github/workflows/ci.yml   # DevOps output
└── logs/
    ├── phases.jsonl           # Phase transition log
    └── costs.jsonl            # Per-agent cost tracking
```

### 3.2 Phase Transition Tracking

The orchestrator writes structured phase logs:

```json
{"phase": "planning", "status": "started", "timestamp": "2026-03-29T10:00:00Z"}
{"phase": "planning", "status": "completed", "timestamp": "2026-03-29T10:05:00Z", "cost_usd": 0.45}
{"phase": "development", "status": "started", "timestamp": "2026-03-29T10:05:01Z"}
```

### 3.3 Mapping to ProjectResult

The backend reads workspace artifacts and maps them to `ProjectResult`:

```python
class ClaudeAgentBackend:
    name = "claude-agent-sdk"

    def run(self, description: str, profile: TeamProfile, **kwargs) -> ProjectResult:
        workspace = setup_workspace(description)

        # Run orchestrator
        result_msg = await run_orchestrator(description, profile, workspace)

        # Collect artifacts from filesystem
        raw = {
            "requirements": read_if_exists(workspace / "docs/requirements.md"),
            "architecture": read_if_exists(workspace / "docs/architecture.md"),
            "generated_files": list_files(workspace / "src"),
            "test_results": read_json_if_exists(workspace / "docs/test_results.json"),
            "deployment_config": collect_deployment_files(workspace),
            "cost_usd": result_msg.total_cost_usd,
            "session_id": result_msg.session_id,
            "phases": read_jsonl(workspace / "logs/phases.jsonl"),
        }

        return ProjectResult(
            backend_name="claude-agent-sdk",
            success=result_msg.subtype == "success",
            raw=raw,
            error=None if result_msg.subtype == "success" else str(result_msg.stop_reason),
            team_profile=profile.name,
        )
```

---

## 4. Tools Strategy

### 4.1 Built-in SDK Tools (no custom code needed)

| Tool | Used by | Purpose |
|------|---------|---------|
| `Read` | All agents | Read workspace files |
| `Write` | Developers, QA, DevOps | Write generated code/config |
| `Edit` | Developers, QA | Modify existing files |
| `Bash` | QA (run tests), Developers (install deps) | Shell commands |
| `Glob` | All agents | Find files by pattern |
| `Grep` | All agents | Search file contents |
| `Agent` | Orchestrator, Phase agents | Spawn subagents |
| `TodoWrite` | Orchestrator | Track progress |
| `WebSearch` | Architect (optional) | Research best practices |

### 4.2 Custom Tools via MCP

Our existing tools (`file_tools.py`, `code_tools.py`, `git_tools.py`, `test_tools.py`) are wrapped as an MCP server and provided to agents:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("run_guardrails", "Run security and quality guardrails on generated code",
      {"file_path": str, "check_types": list})
async def run_guardrails(args: dict) -> dict:
    """Run guardrail checks on a file."""
    from ai_team.guardrails import run_all_checks
    result = run_all_checks(args["file_path"], args["check_types"])
    return {"content": [{"type": "text", "text": json.dumps(result)}]}

@tool("run_project_tests", "Execute the project test suite",
      {"test_path": str, "coverage": bool})
async def run_project_tests(args: dict) -> dict:
    """Run pytest with optional coverage."""
    from ai_team.tools.test_tools import run_tests
    result = run_tests(args["test_path"], coverage=args.get("coverage", False))
    return {"content": [{"type": "text", "text": json.dumps(result)}]}

@tool("validate_code_safety", "Check code for dangerous patterns",
      {"code": str})
async def validate_code_safety(args: dict) -> dict:
    """Security guardrail: check for eval, exec, etc."""
    from ai_team.guardrails.security import code_safety_check
    result = code_safety_check(args["code"])
    if result.status == "fail":
        return {"content": [{"type": "text", "text": f"SECURITY VIOLATION: {result.message}"}],
                "is_error": True}
    return {"content": [{"type": "text", "text": "Code safety check passed"}]}

# Bundle into MCP server
ai_team_tools_server = create_sdk_mcp_server(
    name="ai-team-tools",
    version="1.0.0",
    tools=[run_guardrails, run_project_tests, validate_code_safety]
)
```

### 4.3 Tool Permissions per Agent

Security through scoped tool access:

```python
# Orchestrator: can spawn agents, read files, track progress
orchestrator_tools = ["Agent", "Read", "Glob", "Grep", "Write", "TodoWrite",
                      "mcp__ai-team-tools__run_guardrails"]

# Developers: can read/write/edit code, run shell
developer_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep",
                   "mcp__ai-team-tools__validate_code_safety"]

# QA: can read, write tests, run tests, check coverage
qa_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep",
            "mcp__ai-team-tools__run_project_tests",
            "mcp__ai-team-tools__run_guardrails"]

# Architect: read-only code + web search for research
architect_tools = ["Read", "Glob", "Grep", "Write", "WebSearch"]
```

### 4.4 External MCP Servers

Same configuration as other backends, from `team_profiles.yaml`:

```python
def build_mcp_servers(profile: TeamProfile) -> dict:
    """Build MCP server config for Claude Agent SDK."""
    servers = {}

    # Always include our custom tools
    servers["ai-team-tools"] = ai_team_tools_server

    # Add profile-specific external servers
    mcp_config = profile.metadata.get("mcp_servers", {})
    for name, config in mcp_config.items():
        if config.get("transport") == "stdio":
            servers[name] = {
                "command": config["command"],
                "args": config.get("args", []),
                "env": config.get("env", {}),
            }
        elif config.get("transport") == "http":
            servers[name] = {
                "type": "http",
                "url": config["url"],
                "headers": config.get("headers", {}),
            }

    return servers
```

---

## 5. Guardrails Strategy

### 5.1 Three enforcement layers

| Layer | Mechanism | When |
|-------|-----------|------|
| **Prompt-based** | System prompt instructions (role adherence, output format) | Every agent turn |
| **Tool-based** | `validate_code_safety` and `run_guardrails` MCP tools | On generated code |
| **Hook-based** | `PreToolUse` / `PostToolUse` hooks | Before/after every tool call |

### 5.2 Hooks for Guardrails

```python
async def security_hook(input_data: dict, tool_use_id: str, context: dict) -> dict:
    """Block dangerous operations before they execute."""
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Block writes to sensitive paths
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if any(p in file_path for p in [".env", "credentials", "secrets", "../"]):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Security: blocked write to {file_path}",
                }
            }

    # Block dangerous bash commands
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        dangerous = ["rm -rf /", "eval(", "exec(", "curl | sh", "wget | sh"]
        if any(d in command for d in dangerous):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Security: blocked dangerous command",
                }
            }

    return {}

async def quality_hook(input_data: dict, tool_use_id: str, context: dict) -> dict:
    """Post-tool quality checks on written files."""
    if input_data.get("hook_event_name") != "PostToolUse":
        return {}

    tool_name = input_data.get("tool_name", "")
    if tool_name in ("Write", "Edit"):
        file_path = input_data.get("tool_input", {}).get("file_path", "")
        if file_path.endswith(".py"):
            # Check for placeholder code
            content = input_data.get("tool_output", "")
            placeholders = ["TODO", "FIXME", "NotImplementedError", "pass  # implement"]
            found = [p for p in placeholders if p in content]
            if found:
                return {
                    "systemMessage": f"WARNING: File {file_path} contains placeholders: {found}. "
                                     "Replace them with real implementations.",
                    "continue": True,
                }
    return {}

async def audit_hook(input_data: dict, tool_use_id: str, context: dict) -> dict:
    """Log all tool calls for observability."""
    import json, datetime
    log_entry = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "event": input_data.get("hook_event_name"),
        "tool": input_data.get("tool_name"),
        "session": input_data.get("session_id"),
    }
    # Append to audit log (non-blocking)
    asyncio.create_task(append_jsonl("workspace/logs/audit.jsonl", log_entry))
    return {"async": True}
```

### 5.3 Hook Configuration

```python
hooks = {
    "PreToolUse": [
        HookMatcher(matcher="Write|Edit|Bash", hooks=[security_hook]),
        HookMatcher(hooks=[audit_hook]),  # All tools
    ],
    "PostToolUse": [
        HookMatcher(matcher="Write|Edit", hooks=[quality_hook]),
        HookMatcher(hooks=[audit_hook]),
    ],
}
```

---

## 6. Human-in-the-Loop

### 6.1 Tool Approval Callback

```python
async def human_approval(tool_name: str, input_data: dict, context) -> PermissionResult:
    """Approval callback for the orchestrator."""

    # Auto-approve safe operations
    safe_tools = {"Read", "Glob", "Grep", "Agent", "TodoWrite"}
    if tool_name in safe_tools:
        return PermissionResultAllow(updated_input=input_data)

    # Auto-approve file writes within workspace
    if tool_name in ("Write", "Edit"):
        path = input_data.get("file_path", "")
        if path.startswith("workspace/"):
            return PermissionResultAllow(updated_input=input_data)

    # Ask user for everything else
    approved = await show_ui_approval(tool_name, input_data)
    if approved:
        return PermissionResultAllow(updated_input=input_data)
    return PermissionResultDeny(message="User denied")
```

### 6.2 Planning Review Interrupt

The orchestrator prompt instructs Claude to ask for human review after planning:

```text
After planning completes, use the AskUserQuestion tool to ask the user:
"Planning is complete. Requirements and architecture are in workspace/docs/.
Would you like to: (1) Approve and proceed to development, (2) Request changes,
(3) Abort the project?"
```

The `canUseTool` callback handles `AskUserQuestion`:

```python
if tool_name == "AskUserQuestion":
    questions = input_data.get("questions", [])
    answers = await show_ui_questions(questions)  # Gradio or TUI
    return PermissionResultAllow(updated_input={**input_data, "answers": answers})
```

### 6.3 Test Failure Escalation

If tests fail after max retries, the orchestrator uses `AskUserQuestion` to escalate:

```text
If tests have failed {max_retries} times, ask the user:
"Tests failed after {max_retries} attempts. Failures: {failure_summary}.
Would you like to: (1) Continue trying, (2) Accept current state, (3) Abort?"
```

---

## 7. Cost Tracking & Budget Control

### 7.1 Per-phase budgets

```python
PHASE_BUDGETS = {
    "planning": 3.00,      # Requirements + architecture
    "development": 10.00,  # Code generation (most expensive)
    "testing": 3.00,       # Test generation + execution
    "deployment": 2.00,    # Deployment artifacts
}

# Orchestrator gets total budget
TOTAL_BUDGET = sum(PHASE_BUDGETS.values())  # $18.00
```

### 7.2 Cost tracking in ResultMessage

```python
phase_costs = {}

for phase_name, phase_prompt in phases:
    async for msg in query(prompt=phase_prompt, options=phase_options):
        if isinstance(msg, ResultMessage):
            phase_costs[phase_name] = msg.total_cost_usd or 0

            # Write to cost log
            await append_jsonl("workspace/logs/costs.jsonl", {
                "phase": phase_name,
                "cost_usd": msg.total_cost_usd,
                "input_tokens": msg.usage.get("input_tokens", 0),
                "output_tokens": msg.usage.get("output_tokens", 0),
                "cache_read_tokens": msg.usage.get("cache_read_input_tokens", 0),
            })

total = sum(phase_costs.values())
print(f"Total cost: ${total:.4f}")
```

### 7.3 Model selection for cost optimization

| Agent | Dev model | Prod model | Rationale |
|-------|-----------|------------|-----------|
| Orchestrator | sonnet | opus | Needs strong reasoning for coordination |
| Planning-agent | sonnet | sonnet | Coordination only |
| Product Owner | sonnet | sonnet | Requirements are structured |
| Architect | sonnet | opus | Architecture needs deep reasoning |
| Backend Dev | sonnet | sonnet | Code generation is sonnet's strength |
| Frontend Dev | sonnet | sonnet | Same |
| QA | sonnet | sonnet | Test generation is routine |
| DevOps | haiku | sonnet | Dockerfiles/CI are templated |
| Cloud | haiku | sonnet | IaC is templated |

Configure via `team_profiles.yaml` `model_overrides`.

---

## 8. Streaming & Monitoring

### 8.1 Stream events to TUI

```python
async def stream_to_monitor(description: str, profile: TeamProfile, monitor: TeamMonitor):
    """Run orchestrator with streaming, feeding events to Rich TUI."""

    current_tool = None

    async for message in query(
        prompt=build_orchestrator_prompt(description, profile),
        options=ClaudeAgentOptions(
            include_partial_messages=True,
            **build_options(profile),
        ),
    ):
        if isinstance(message, StreamEvent):
            event = message.event

            # Track tool invocations
            if event.get("type") == "content_block_start":
                cb = event.get("content_block", {})
                if cb.get("type") == "tool_use":
                    current_tool = cb.get("name")
                    if current_tool == "Agent":
                        # Subagent starting
                        monitor.on_agent_start(
                            agent_name=cb.get("input", {}).get("subagent_type", "unknown"),
                            task="Executing...",
                            model="claude",
                        )

            # Stream text to TUI
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    monitor.on_agent_output(delta.get("text", ""))

        elif isinstance(message, ResultMessage):
            monitor.on_phase_complete(cost=message.total_cost_usd)
```

### 8.2 AsyncIterator for Backend.stream()

```python
class ClaudeAgentBackend:
    async def stream(self, description, profile, **kwargs):
        async for message in query(
            prompt=build_orchestrator_prompt(description, profile),
            options=ClaudeAgentOptions(include_partial_messages=True, **build_options(profile)),
        ):
            if isinstance(message, StreamEvent):
                yield {"type": "stream", "event": message.event}
            elif isinstance(message, AssistantMessage):
                yield {"type": "assistant", "content": str(message.content)}
            elif isinstance(message, ResultMessage):
                yield {"type": "result", "success": message.subtype == "success",
                       "cost_usd": message.total_cost_usd, "session_id": message.session_id}
```

---

## 9. Session Persistence & Recovery

### 9.1 Session continuation

If a run is interrupted (budget hit, crash, user abort), resume later:

```python
# Initial run
result = await run_orchestrator(description, profile, workspace)
session_id = result.session_id  # Save this

# Resume later
async for msg in query(
    prompt="Continue from where you left off. Check workspace/logs/phases.jsonl for last phase.",
    options=ClaudeAgentOptions(
        resume=session_id,
        max_budget_usd=remaining_budget,
        **build_options(profile),
    ),
):
    pass
```

### 9.2 Session forking (experiment with alternatives)

```python
# Fork from a planning-complete session to try different architectures
async for msg in query(
    prompt="Re-do the architecture using a microservices approach instead of monolith.",
    options=ClaudeAgentOptions(
        resume=session_id,
        fork_session=True,  # Don't modify original
        **build_options(profile),
    ),
):
    pass
```

### 9.3 Mapping to CLI

```bash
ai-team --backend claude-agent-sdk "Build a REST API"              # New run
ai-team --backend claude-agent-sdk --resume <session_id>           # Resume
ai-team --backend claude-agent-sdk --resume <session_id> --fork    # Fork
```

---

## 10. Advanced Claude Capabilities

These features are unique to the Claude Agent SDK backend and not available in CrewAI or LangGraph. They represent the primary reason to use this backend for high-stakes or cost-sensitive runs.

### 10.1 Extended Thinking (Visible Reasoning)

The Architect and Orchestrator agents benefit enormously from **extended thinking** — Claude shows its reasoning process before producing output. This is critical for architecture decisions, debugging complex test failures, and coordinating multi-agent workflows.

```python
# Architect agent with adaptive thinking
architect_def = AgentDefinition(
    description="Solutions architect with deep reasoning",
    prompt="...",
    tools=["Read", "Write", "Glob", "Grep"],
    model="opus",
    thinking={"type": "adaptive"},           # Claude decides when/how much to think
    output_config={"effort": "high"},         # Encourage deep reasoning
)

# QA agent — skip thinking for speed
qa_def = AgentDefinition(
    description="QA engineer",
    prompt="...",
    tools=["Read", "Write", "Bash", "Glob", "Grep"],
    model="sonnet",
    output_config={"effort": "medium"},       # Balanced — fast test generation
)

# DevOps — minimal thinking, templated work
devops_def = AgentDefinition(
    description="DevOps engineer",
    prompt="...",
    tools=["Read", "Write", "Glob", "Grep"],
    model="haiku",
    output_config={"effort": "low"},          # Dockerfiles are straightforward
)
```

**Per-agent effort levels:**

| Agent | Model | Effort | Thinking | Rationale |
|-------|-------|--------|----------|-----------|
| Orchestrator | opus | high | adaptive | Coordination requires multi-step reasoning |
| Product Owner | sonnet | medium | adaptive | Requirements analysis is structured |
| Architect | opus | high/max | adaptive | Architecture decisions need deep reasoning |
| Backend Dev | sonnet | high | adaptive | Complex code benefits from reasoning |
| Frontend Dev | sonnet | medium | adaptive | Component code is more templated |
| QA | sonnet | medium | off | Test generation is pattern-based |
| DevOps | haiku | low | off | Dockerfiles/CI are highly templated |
| Cloud | haiku | low | off | IaC is templated |

**Interleaved thinking**: On Opus/Sonnet 4.6, thinking happens **between tool calls**. The Architect agent thinks before each decision: "I need to choose between REST and GraphQL for this API. Let me consider the requirements..." → reads requirements → thinks about trade-offs → writes architecture. The reasoning trace is visible in the session transcript for debugging.

**Capturing thinking for audit:**

```python
async for message in query(prompt="...", options=options):
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if hasattr(block, "type") and block.type == "thinking":
                # Log reasoning for audit trail
                await append_jsonl("workspace/logs/reasoning.jsonl", {
                    "agent": current_agent,
                    "thinking": block.thinking,
                    "timestamp": datetime.now(UTC).isoformat(),
                })
```

### 10.2 Prompt Caching (90% Cost Reduction)

The SDK automatically caches system prompts, tool definitions, and CLAUDE.md content. For a multi-agent system with repeated context, this is massive:

**What's cached and reused:**

| Content | Size (tokens) | Cached? | Savings |
|---------|--------------|---------|---------|
| CLAUDE.md (project conventions) | ~2,000 | Yes — loaded once, read by all agents | 90% on reads |
| Tool schemas (10 tools) | ~3,000 | Yes — stable across turns | 90% on reads |
| System prompts | ~500/agent | Yes — stable per agent | 90% on reads |
| Prior conversation history | Grows | Yes — previous turns cached | 90% on reads |
| Thinking blocks | Varies | Cached alongside assistant turns | Indirect savings |

**Cost model for a full run (estimated):**

```text
Without caching:
  9 agents × ~5,000 tokens system context = 45,000 input tokens per turn
  Across ~100 turns total = 4.5M input tokens
  At $5/MTok (Opus) = $22.50 input cost

With caching:
  First turn per agent: full price = ~$0.25
  Subsequent turns: 90% cache read = ~$2.25
  Total input cost ≈ $2.50 (89% savings)
```

**Implementation:**

```python
# Automatic — just load CLAUDE.md via settingSources
options = ClaudeAgentOptions(
    setting_sources=["project"],  # Loads CLAUDE.md, cached automatically
    # Tool schemas are cached automatically after first use
)

# Explicit cache control on stable content
# (Usually not needed — automatic mode handles this)
```

### 10.3 File Checkpointing (Snapshot & Rollback)

Before risky operations (refactoring, development retry after test failure), snapshot the workspace and roll back if validation fails:

```python
from claude_agent_sdk import get_file_checkpoint, rewind_files

async def run_with_rollback(phase_prompt, options, workspace):
    """Run a phase with rollback capability."""

    # Snapshot before the phase
    checkpoint = await get_file_checkpoint()

    async for msg in query(prompt=phase_prompt, options=options):
        if isinstance(msg, ResultMessage):
            if msg.subtype == "success":
                # Validate the output
                valid = await validate_phase_output(workspace)
                if valid:
                    return msg
                else:
                    # Rollback all file changes
                    await rewind_files(checkpoint)
                    # Retry with feedback
                    return await run_with_rollback(
                        f"Previous attempt failed validation. Try again. Issues: {valid.errors}",
                        options, workspace
                    )
```

**Use cases:**
- Development agent produces broken code → rollback, retry with test feedback
- Architect rewrites architecture → rollback if planning agent rejects it
- QA agent modifies source code during debugging → rollback to preserve clean state

**Limitations:** Only tracks `Write`/`Edit` operations. Bash-based file operations (`sed -i`, `mv`, `rm`) are **not tracked**. Instruct agents to use `Write`/`Edit` tools instead of Bash for file modifications.

### 10.4 Vision: QA Agent Screenshot Analysis

The QA agent can analyze UI screenshots for visual regression testing:

```python
qa_with_vision_def = AgentDefinition(
    description="QA engineer with visual testing capabilities",
    prompt="""You are a QA Engineer with visual testing capabilities.

In addition to running code tests, you can:
1. Launch the application (Bash: start dev server)
2. Capture screenshots of key pages
3. Analyze screenshots for: layout issues, missing elements, broken styling
4. Compare before/after screenshots during refactoring
5. Include visual findings in test_report.md

Use the Read tool on image files to analyze them visually.""",
    tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep",
           "mcp__ai-team-tools__run_project_tests"],
    model="sonnet",
    output_config={"effort": "high"},  # Visual analysis needs attention
)
```

**Visual testing workflow:**

```text
1. QA agent starts dev server (Bash: npm run dev)
2. Captures screenshots (Bash: playwright screenshot or curl)
3. Reads screenshots (Read tool supports images natively)
4. Analyzes: "The navbar is missing the logout button described in requirements"
5. Writes findings to test_report.md
```

Cost: ~$4.80 per 1,000 optimized images (Sonnet 4.6). For a typical run analyzing 10-20 screenshots, this adds ~$0.10.

### 10.5 ToolSearch: Deferred Tool Loading

When the system has many MCP servers and custom tools (>10), loading all tool schemas upfront wastes context. ToolSearch loads tools on demand:

```python
options = ClaudeAgentOptions(
    mcp_servers={
        "github": {...},       # ~50 tools
        "filesystem": {...},   # ~10 tools
        "postgres": {...},     # ~20 tools
        "docker": {...},       # ~15 tools
        "ai-team-tools": {...},# ~10 tools
    },
    # Don't list all 105 tools in allowed_tools!
    # Instead, agent uses ToolSearch to find what it needs:
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Agent",
                   "ToolSearch"],  # Agent discovers MCP tools on demand
)
```

**Context savings:**

```text
Without ToolSearch: 105 tools × ~500 tokens/schema = 52,500 tokens in every request
With ToolSearch:    7 core tools + search = ~3,500 tokens + ~2,500 per discovered tool

Savings: ~85% reduction in tool schema overhead
```

**How it works:** Claude calls `ToolSearch` with a query like "I need to create a GitHub issue". The SDK searches available MCP tools, returns the 3-5 most relevant (e.g., `mcp__github__create_issue`), and Claude can then invoke them. Discovered tools are injected inline without breaking prompt cache.

### 10.6 Skills: Reusable Agent Capabilities

Define reusable skills that any agent can invoke automatically:

```text
.claude/skills/
├── code-review/
│   └── SKILL.md          # "Review code for security, performance, and style"
├── test-analysis/
│   └── SKILL.md          # "Analyze test failures and propose fixes"
├── dependency-audit/
│   └── SKILL.md          # "Check dependencies for vulnerabilities"
└── api-design/
    └── SKILL.md          # "Design REST API following OpenAPI best practices"
```

**Example skill file (`.claude/skills/code-review/SKILL.md`):**

```markdown
---
description: "Review code for security vulnerabilities, performance issues, and style violations"
tools: ["Read", "Glob", "Grep"]
---

# Code Review Skill

When asked to review code:
1. Scan for security issues: eval(), exec(), SQL injection, XSS, hardcoded secrets
2. Check performance: N+1 queries, unnecessary loops, missing indexes
3. Verify style: type hints, docstrings, consistent naming
4. Output a structured review with severity levels (critical/warning/info)
```

**Integration:**

```python
# Enable skills for agents that need them
orchestrator_options = ClaudeAgentOptions(
    setting_sources=["project"],  # Loads .claude/skills/*
    allowed_tools=["Agent", "Read", "Glob", "Grep", "Write", "Skill", ...],
)

# Skills are automatically invoked when Claude determines they match the task
# e.g., "Review the generated auth module" → triggers code-review skill
```

### 10.7 Batch API: Bulk Analysis at 50% Cost

For non-urgent tasks (nightly code review, batch testing, retrospective analysis), the Batch API processes requests asynchronously at 50% cost:

```python
from anthropic import Anthropic

client = Anthropic()

# Submit batch of analysis tasks
batch = client.messages.batches.create(
    requests=[
        {
            "custom_id": f"review-{file}",
            "params": {
                "model": "claude-sonnet-4-6-20260329",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": f"Review this code:\n{code}"}],
            },
        }
        for file, code in files_to_review.items()
    ]
)

# Check status later (usually < 1 hour)
result = client.messages.batches.retrieve(batch.id)
```

**Combined with prompt caching: up to 95% savings.**

Use cases:
- Nightly code quality scan across entire codebase
- Batch architecture review of multiple design alternatives
- Parallel test generation for all modules (then collect and merge)

### 10.8 Session Forking: A/B Test Architectures

Fork from a planning-complete session to explore alternatives without losing the original:

```text
Session A: "Build a REST API" → Planning complete (monolith architecture)
  ├── Fork B: "Re-do architecture as microservices" → Development → Testing
  └── Fork C: "Re-do architecture as serverless" → Development → Testing

Compare: which fork produced better code, tests, and deployment config?
```

```python
# Original run completes planning
original_session_id = result.session_id

# Fork A: microservices
async for msg in query(
    prompt="Re-architect as microservices. Keep requirements, redesign architecture.",
    options=ClaudeAgentOptions(resume=original_session_id, fork_session=True, ...),
):
    fork_a_session = msg.session_id

# Fork B: serverless
async for msg in query(
    prompt="Re-architect as serverless (AWS Lambda + API Gateway).",
    options=ClaudeAgentOptions(resume=original_session_id, fork_session=True, ...),
):
    fork_b_session = msg.session_id
```

This is unique to the Claude Agent SDK — neither CrewAI nor LangGraph support session forking natively.

---

## 11. Directory Structure

```text
ai-team/
├── src/ai_team/
│   ├── backends/
│   │   ├── claude_agent_sdk_backend/     # NEW
│   │   │   ├── __init__.py
│   │   │   ├── backend.py               # ClaudeAgentBackend(Backend)
│   │   │   ├── orchestrator.py          # Orchestrator prompt + query loop
│   │   │   ├── agents/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── definitions.py       # All AgentDefinition objects
│   │   │   │   ├── prompts.py           # System prompts per role
│   │   │   │   └── builder.py           # build_agent_definitions(profile)
│   │   │   ├── tools/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── mcp_server.py        # Custom MCP server wrapping ai_team tools
│   │   │   │   └── permissions.py       # Tool permission lists per role
│   │   │   ├── hooks/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── security.py          # PreToolUse security hook
│   │   │   │   ├── quality.py           # PostToolUse quality hook
│   │   │   │   └── audit.py             # Audit logging hook
│   │   │   ├── streaming.py             # StreamEvent → monitor/UI adapter
│   │   │   └── costs.py                 # Per-phase budget management
│   │   │
│   │   ├── crewai_backend/              # Existing
│   │   └── langgraph_backend/           # Existing
│   │
│   ├── core/                            # EXISTING (unchanged)
│   │   ├── backend.py                   # Backend protocol
│   │   ├── team_profile.py              # TeamProfile loader
│   │   └── result.py                    # ProjectResult
│   │
│   ├── tools/                           # SHARED (unchanged)
│   ├── guardrails/                      # SHARED (called from hooks + MCP tools)
│   ├── models/                          # SHARED (unchanged)
│   ├── config/                          # SHARED (add claude-agent-sdk model config)
│   ├── rag/                             # SHARED (knowledge as CLAUDE.md or MCP resources)
│   ├── mcp/                             # SHARED (MCP client config)
│   ├── ui/                              # SHARED: src/ai_team/ui/ (wire to Backend.stream())
│   └── monitor.py                       # SHARED (consume stream events)
│
├── tests/
│   ├── integration/
│   │   ├── test_crewai_backend/
│   │   ├── test_langgraph_backend/
│   │   └── test_claude_agent_sdk_backend/  # NEW
│   └── comparison/                         # Run same demo across all 3 backends
│
├── CLAUDE.md                             # Project conventions loaded by SDK agents
└── .claude/
    └── settings.json                     # Claude Code settings (hooks, permissions)
```

### What's new vs. shared

| Component | Action | Notes |
|-----------|--------|-------|
| `backends/claude_agent_sdk_backend/` | **New** | ~12 files, core implementation |
| `core/` | **Unchanged** | Same Backend protocol, TeamProfile, ProjectResult |
| `backends/registry.py` | **Update** | Add `claude-agent-sdk` case |
| `tools/` | **Unchanged** | Wrapped via custom MCP server |
| `guardrails/` | **Unchanged** | Called from hooks and MCP tools |
| `config/models.py` | **Deferred** | Claude direct API model IDs (optional; SDK uses aliases / full IDs from profile) |
| `config/settings.py` | **Partial** | `ANTHROPIC_API_KEY` documented in `.env.example`; orchestrator reads `os.environ` — not yet on root `Settings` |
| `main.py` | **Update** | Add `claude-agent-sdk` to `--backend` choices |
| `CLAUDE.md` | **New** | Project conventions loaded by all SDK agents |
| `.claude/settings.json` | **New** | Hook configuration for SDK agents |

---

## 12. Implementation Tasks

**Status legend:** `[x]` = delivered in repo (sub-bullets note gaps). `[ ]` = not implemented or only a stub.

### Phase 0: Setup & Dependencies (3 tasks)

- [x] **T0.1** Add `claude-agent-sdk` to `pyproject.toml`:
  - `claude-agent-sdk >= 0.1.0` (or `@anthropic-ai/claude-agent-sdk` for TS)
  - `anthropic >= 0.40.0` (if needed as transitive dep)
  - Add `ANTHROPIC_API_KEY` to `.env.example` and settings
  - *Gap:* `ANTHROPIC_API_KEY` is documented in `.env.example` and read via `os.environ` in the orchestrator; not yet a nested field on root `Settings` in `config/settings.py`.

- [x] **T0.2** Update `backends/registry.py`:
  - Add `claude-agent-sdk` case to `get_backend()`
  - Update CLI `--backend` choices in `main.py`
  - *Note:* Alias `claude-sdk` also resolves to the same backend.

- [x] **T0.3** Create `CLAUDE.md` at project root:
  - Project conventions (code style, testing standards, security rules)
  - Agent behavioral constraints (loaded via `settingSources=["project"]`)
  - This replaces the "system prompt preamble" — all agents inherit it
  - *Note:* Orchestrator also appends a `CLAUDE.md` excerpt into `system_prompt` and uses `add_dirs` to the repo root; not only `setting_sources`.

### Phase 1: Agent Definitions & Prompts (4 tasks)

- [x] **T1.1** Create `backends/claude_agent_sdk_backend/agents/prompts.py`:
  - System prompts for all 9 agent roles (orchestrator + 8 specialists)
  - Include behavioral guardrails directly in prompts (role adherence, output format)
  - Parameterized with `{profile_name}`, `{agent_list}`, `{max_retries}`, etc.

- [x] **T1.2** Create `backends/claude_agent_sdk_backend/agents/definitions.py`:
  - `AgentDefinition` objects for all specialist agents
  - Phase agent definitions (planning, development, testing, deployment)
  - Orchestrator configuration

- [x] **T1.3** Create `backends/claude_agent_sdk_backend/agents/builder.py`:
  - `build_agent_definitions(profile: TeamProfile) -> dict[str, AgentDefinition]`
  - Filter agents by profile
  - Apply model overrides from profile
  - Build phase agents with only active specialists

- [x] **T1.4** Write unit tests for agent builder:
  - Test each profile produces correct agent hierarchy
  - Test model overrides are applied
  - Test missing agents are excluded from phase agents
  - *Gap:* `tests/unit/backends/test_claude_agent_sdk_builder.py` covers representative profiles, not an exhaustive matrix of every `team_profiles.yaml` entry.

### Phase 2: Custom MCP Tools & Permissions (3 tasks)

- [x] **T2.1** Create `backends/claude_agent_sdk_backend/tools/mcp_server.py`:
  - Wrap existing guardrails as MCP tools: `run_guardrails`, `validate_code_safety`
  - Wrap test runner: `run_project_tests`
  - Bundle into `create_sdk_mcp_server()`
  - *Extra:* `search_knowledge` MCP tool (RAG) included.

- [x] **T2.2** Create `backends/claude_agent_sdk_backend/tools/permissions.py`:
  - Tool permission lists per agent role
  - `get_allowed_tools(role: str) -> list[str]`
  - `get_disallowed_tools(role: str) -> list[str]` (e.g., Bash blocked for Architect)
  - *Gap:* `get_disallowed_tools()` not implemented; architect omits Bash via allow-list only.

- [ ] **T2.3** Write unit tests for MCP tool server:
  - Test each tool with mock inputs
  - Test `is_error` returned for guardrail failures
  - Test permission lists are correct per role

### Phase 3: Hooks (Guardrails & Audit) (3 tasks)

- [x] **T3.1** Create `backends/claude_agent_sdk_backend/hooks/security.py`:
  - `PreToolUse` hook: block writes to `.env`, credentials, paths with `..`
  - `PreToolUse` hook: block dangerous Bash commands (eval, exec, rm -rf /)
  - Return `permissionDecision: "deny"` with reason

- [x] **T3.2** Create `backends/claude_agent_sdk_backend/hooks/quality.py`:
  - `PostToolUse` hook: scan written Python files for TODO/FIXME/NotImplementedError
  - Return `systemMessage` warning agent to replace placeholders
  - `PostToolUse` hook: validate generated JSON files are parseable

- [x] **T3.3** Create `backends/claude_agent_sdk_backend/hooks/audit.py`:
  - Log all tool calls to `workspace/logs/audit.jsonl`
  - Track subagent start/stop events
  - Non-blocking (async)
  - *Gap:* Pre/Post tool events only; subagent start/stop not logged here (would need `SubagentStart`/`SubagentStop` hooks).

### Phase 4: Backend Implementation (4 tasks)

- [x] **T4.1** Create `backends/claude_agent_sdk_backend/orchestrator.py`:
  - `run_orchestrator(description, profile, workspace) -> ResultMessage`
  - Build orchestrator prompt from template + profile
  - Configure `ClaudeAgentOptions` with agents, tools, hooks, MCP servers, budget
  - Execute `query()` and collect `ResultMessage`
  - Handle `error_max_turns`, `error_max_budget_usd`, `error_during_execution`
  - *Gap:* No explicit retry/resume loops on those error subtypes; SDK/CLI surfaces failures via `ResultMessage`.

- [x] **T4.2** Create `backends/claude_agent_sdk_backend/backend.py`:
  - `ClaudeAgentBackend(Backend)` with `run()` and `stream()`
  - `run()`: setup workspace → run orchestrator → collect artifacts → return `ProjectResult`
  - `stream()`: yield `StreamEvent` messages from `query(include_partial_messages=True)`

- [x] **T4.3** Create `backends/claude_agent_sdk_backend/costs.py`:
  - Per-phase budget management
  - Cost logging to `workspace/logs/costs.jsonl`
  - Budget remaining calculation for resume scenarios
  - Cost comparison report generation
  - *Gap:* Default phase budget table + `append_cost_log()` after orchestrator; no “remaining budget” calculator or standalone comparison report generator.

- [x] **T4.4** Create `backends/claude_agent_sdk_backend/streaming.py`:
  - `StreamEvent` → monitor/UI event adapter
  - Track subagent invocations from `content_block_start` events
  - Map to `TeamMonitor` API (phase changes, agent starts/finishes)
  - *Gap:* Maps Agent tool starts and text deltas to `on_agent_start` / `on_log`; no dedicated phase/cost widgets in `monitor.py`.

### Phase 4b: Advanced Claude Capabilities (5 tasks)

- [x] **T4b.1** Configure extended thinking per agent:
  - Set `thinking={"type": "adaptive"}` + `output_config={"effort": "high"}` for Orchestrator and Architect
  - Set `output_config={"effort": "medium"}` for PO, Backend Dev, QA
  - Set `output_config={"effort": "low"}` for DevOps, Cloud (templated work)
  - Capture thinking blocks in `workspace/logs/reasoning.jsonl` for audit
  - Make effort levels configurable in `team_profiles.yaml` `model_overrides`
  - *Gap:* Orchestrator uses `thinking` + `effort`; per-agent effort via `AgentDefinition.effort` and `metadata.claude_agent_sdk.effort` — not `model_overrides`. No `reasoning.jsonl` capture.

- [ ] **T4b.2** Enable file checkpointing for rollback:
  - Set `enable_file_checkpointing=True` on orchestrator options
  - Snapshot before each phase (planning, development, testing, deployment)
  - On phase validation failure: `rewind_files(checkpoint)` then retry
  - Instruct agents to use Write/Edit (not Bash) for file modifications (Bash changes aren't tracked)
  - *Note:* `enable_file_checkpointing` exists as a `run()`/`stream()` kwargs passthrough only; no phase snapshots or `rewind_files` orchestration.

- [x] **T4b.3** Create `.claude/skills/` for reusable capabilities:
  - `code-review/SKILL.md` — security, performance, style review
  - `test-analysis/SKILL.md` — analyze test failures, propose fixes
  - `api-design/SKILL.md` — REST API design following OpenAPI patterns
  - `dependency-audit/SKILL.md` — check for vulnerable/outdated dependencies
  - Enable skills via `setting_sources=["project"]` + `Skill` in `allowed_tools`
  - *Gap:* Skills files exist; `Skill` is added to orchestrator `allowed_tools` only when `metadata.claude_agent_sdk.enable_skills` is true — not default `setting_sources`.

- [x] **T4b.4** Enable ToolSearch for deferred MCP tool loading:
  - Add `ToolSearch` to `allowed_tools` for agents using MCP servers
  - Mark MCP tool schemas with `defer_loading: true` when >10 tools per server
  - Test that agents discover and invoke deferred tools correctly
  - *Note:* `ToolSearch` is appended when `metadata.claude_agent_sdk.use_tool_search` is true or when there are ≥3 MCP servers. `defer_loading` on schemas is not applied (SDK `sdk` MCP config shape).

- [x] **T4b.5** Add vision capability to QA agent:
  - Update QA agent definition with multi-modal prompt
  - Add screenshot capture workflow (Bash: playwright/puppeteer screenshot)
  - QA agent reads images via `Read` tool and analyzes UI
  - Visual findings included in `test_report.md`
  - *Gap:* Prompt instructs multimodal use of image paths; automated Playwright screenshot workflow not wired.

### Phase 5: Session Management & Recovery (2 tasks)

- [x] **T5.1** Implement session management:
  - Save `session_id` in `workspace/logs/session.json` after each phase
  - `--resume <session_id>` reads last session and continues
  - `--fork` creates a branch from an existing session
  - Calculate remaining budget on resume
  - *Gap:* `session.json` written after successful orchestrator completion; CLI uses `--resume` + `--fork-session` + `resume_session_id` / `fork_session` kwargs. No per-phase session persistence or remaining-budget math.

- [x] **T5.2** Implement error recovery:
  - On `error_max_turns`: resume with higher limit and feedback
  - On `error_max_budget_usd`: save state, report partial results
  - On `error_during_execution`: log error, retry phase (max 3 times)
  - On unrecoverable: return `ProjectResult(success=False, error=...)`
  - *Note:* `recovery_max_attempts` > 1 uses `run_orchestrator_with_recovery` (wider turns/budget, prompt nudge). Enable via backend kwarg; each attempt logged to `costs.jsonl` as `orchestrator_recovery_attempt`.

### Phase 6: UI & CLI Integration (3 tasks)

- [x] **T6.1** Update `main.py` CLI:
  - Add `claude-agent-sdk` to `--backend` choices
  - Add `--resume <session_id>` and `--fork` flags
  - Add `--budget <usd>` flag for cost limit
  - Display session ID after run for resume capability
  - *Note:* Budget flags: `--claude-budget` and alias `--budget`. `FEEDBACK_DEFAULT_RESPONSE` / human feedback default is passed as `hitl_default_answer` for `AskUserQuestion` auto-answer when set. Reuses `--resume` for Claude session id when using this backend.

- [x] **T6.2** Update Gradio UI (`src/ai_team/ui/app.py`):
  - Wire to `ClaudeAgentBackend.stream()` for real-time progress
  - Show `AskUserQuestion` prompts in UI for HITL
  - Display per-phase cost breakdown
  - Show session ID for resume
  - *Gap:* Streaming JSON log; HITL questions not surfaced as dedicated UI widgets. Run end shows a short **Claude summary** (session_id, cost_usd, stop_reason) after the event log.

- [x] **T6.3** Update Rich TUI (`monitor.py`):
  - Consume `StreamEvent` messages from Claude Agent SDK
  - Map to existing TUI panels (phase progress, agent activity, guardrails)
  - Show real-time cost counter
  - *Note:* `TeamMonitor.on_claude_result` + metrics rows for Claude session id and cost when `ResultMessage` arrives during stream.

### Phase 7: RAG & Knowledge Integration (2 tasks)

- [x] **T7.1** Wire RAG knowledge into Claude Agent SDK:
  - **Option A**: Curate static knowledge into `CLAUDE.md` sections (loaded via `settingSources`)
  - **Option B**: Expose `search_knowledge` as MCP tool (same as LangGraph backend)
  - **Option C**: MCP resource server that serves knowledge documents on demand
  - Implement at least Options A + B

- [x] **T7.2** Configure CLAUDE.md per team profile:
  - Generate profile-specific CLAUDE.md at runtime
  - Include relevant best practices based on profile's `rag.knowledge_topics`
  - Include project conventions, security rules, output format requirements
  - *Note:* `workspace/docs/CLAUDE_PROFILE.md` is generated per run (`write_profile_claude_context`); orchestrator system prompt references it. Repo `CLAUDE.md` excerpt still merged from inferrred repo root.

### Phase 8: Testing & Comparison (4 tasks)

- [x] **T8.1** Write integration tests for Claude Agent SDK backend:
  - Test agent builder with all profiles
  - Test hooks (security block, quality warning, audit logging)
  - Test MCP tool server
  - Test orchestrator with mocked `query()` (mock `ResultMessage` returns)
  - Test session resume and fork
  - *Gap:* No automated resume/fork tests. MCP server config + costs/workspace helpers + subagent audit covered in unit tests.

- [x] **T8.2** Add to backend comparison suite:
  - Add `claude-agent-sdk` to `scripts/compare_backends.py`
  - Run same demos through all 3 backends
  - Compare: output quality, cost, latency, token usage, error rate
  - *Note:* Opt-in via `--with-claude`; `ComparisonReport` includes optional `claude_agent_sdk` snapshot.

- [ ] **T8.3** Run demos against real Anthropic API:
  - `demos/01_hello_world` (all 3 backends)
  - `demos/02_todo_app` (all 3 backends)
  - Test at least 2 team profiles (`full` and `backend-api`)
  - Document cost per backend per demo
  - *Note:* Steps and artifact paths: [RUNBOOK.md](RUNBOOK.md).

- [x] **T8.4** Update documentation:
  - `README.md` — add `claude-agent-sdk` to backend list
  - `docs/ARCHITECTURE.md` — add Claude Agent SDK backend diagram
  - ADR: "Claude Agent SDK backend: session-based vs state-based orchestration"
  - ADR: "Hooks as guardrails: PreToolUse/PostToolUse patterns"
  - Update comparison table with all 3 backends
  - *Note:* `docs/ARCHITECTURE.md` §2.1.1–2.1.2: three-backend table, comparison matrix, Mermaid diagram. **ADR-006** (session + workspace vs typed state), **ADR-007** (hooks + MCP split). README backend table already listed Claude Agent SDK; repo tree line updated to `claude_agent_sdk_backend/`.

---

## 13. Key Design Decisions

### D1: Nested subagents vs. flat agent pool

**Decision**: Use **nested subagent hierarchy** (orchestrator → phase agents → specialists).

**Rationale**: Maps naturally to the existing team structure. Phase agents provide isolation — the development-agent doesn't see the testing-agent's context. The orchestrator has a clean, high-level view. This also matches the SDK's design: subagents have isolated context windows, which prevents context pollution between phases.

### D2: File-based state vs. typed state objects

**Decision**: Use the **filesystem as the state interface** between agents.

**Rationale**: The Claude Agent SDK doesn't have a typed state graph like LangGraph. Instead of fighting this, lean into it: agents write artifacts to well-known paths, downstream agents read them. This is actually closer to how real engineering teams work (shared repo, not shared memory). It also makes debugging trivial — inspect the workspace directory at any point.

### D3: Hooks for guardrails (not just prompt instructions)

**Decision**: Use **SDK hooks** (`PreToolUse` / `PostToolUse`) for security and quality guardrails, in addition to prompt-based behavioral guardrails.

**Rationale**: Prompts are suggestions; hooks are enforcement. A developer agent told "don't write to .env" might still try. A `PreToolUse` hook that blocks the Write tool for `.env` paths is deterministic. Three layers: prompts (behavioral), hooks (security/quality enforcement), MCP tools (on-demand guardrail checks).

### D4: CLAUDE.md as shared knowledge base

**Decision**: Use **`CLAUDE.md`** as the primary mechanism for injecting project conventions and best practices into all agents.

**Rationale**: The SDK automatically loads `CLAUDE.md` via `settingSources=["project"]`. Every agent (including subagents) inherits it. This replaces the need for RAG-based prompt injection for static knowledge. Dynamic/project-specific knowledge still uses the `search_knowledge` MCP tool.

### D5: Session persistence for crash recovery

**Decision**: Rely on the SDK's **built-in session persistence** for crash recovery, instead of building a custom checkpointing solution.

**Rationale**: Sessions are persisted as JSONL files automatically. On crash, resume with the session ID. This is simpler than LangGraph's checkpointer approach and requires zero additional infrastructure. Trade-off: less granular than LangGraph checkpoints (can't time-travel to specific nodes), but sufficient for phase-level recovery.

### D6: Budget per phase, not per agent

**Decision**: Set `max_budget_usd` at the **phase level**, not per individual agent.

**Rationale**: Individual agent costs are unpredictable (depends on task complexity). Phase budgets are more predictable and easier to reason about. The orchestrator tracks cumulative spend and can abort or adjust if a phase exceeds budget.

### D7: Direct Anthropic API, not OpenRouter

**Decision**: Use the **Anthropic API directly** for the Claude Agent SDK backend (requires `ANTHROPIC_API_KEY`).

**Rationale**: The Claude Agent SDK is built for the Anthropic API — it uses Claude-specific features (prompt caching, extended thinking, tool annotations) that may not work through OpenRouter. Other backends continue to use OpenRouter. Users choose which API key to provide based on their backend choice.

### D8: Adaptive thinking over fixed budgets

**Decision**: Use **adaptive thinking** (`thinking: {"type": "adaptive"}`) with effort levels, not fixed `budget_tokens`.

**Rationale**: Fixed budgets require tuning per task. Adaptive mode lets Claude decide when and how much to think based on task complexity. Combined with per-agent effort levels (`high` for Architect, `low` for DevOps), this optimizes cost while preserving reasoning quality where it matters.

### D9: File checkpointing for rollback, not git

**Decision**: Use SDK **file checkpointing** (`get_file_checkpoint()` / `rewind_files()`) instead of git-based rollback.

**Rationale**: File checkpointing is built into the SDK, tracks Write/Edit operations automatically, and doesn't require git setup in the workspace. It's faster and simpler for within-run rollback. Git is still used for the final artifact (commit the workspace after a successful run), but not for mid-run recovery.

### D10: Skills for domain knowledge, CLAUDE.md for conventions

**Decision**: Use **Skills** (`.claude/skills/`) for domain-specific capabilities (code review, API design, test analysis) and **CLAUDE.md** for project conventions.

**Rationale**: Skills are invoked automatically when Claude detects a matching task — no explicit wiring needed. This is cleaner than embedding domain knowledge in system prompts. CLAUDE.md handles the universal conventions that all agents need. Together they provide two levels of knowledge injection without RAG for static content.

### D11: ToolSearch for MCP scaling

**Decision**: Use **deferred tool loading** (ToolSearch) when MCP servers expose >10 tools total.

**Rationale**: Loading all MCP tool schemas upfront consumes ~500 tokens per tool. With 5 MCP servers averaging 20 tools each, that's 50,000 tokens of schema in every request — wasted if the agent only uses 3-4 tools. ToolSearch cuts this by ~85% and improves tool selection accuracy.

---

## 14. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Claude Agent SDK API instability | Medium | Pin version; SDK is post-1.0 |
| Subagent context isolation causes lost information | High | File-based handoff ensures artifacts persist; orchestrator aggregates |
| Cost unpredictability (no graph structure to limit paths) | High | `max_budget_usd` per phase; `max_turns` per agent; cost logging |
| Prompt engineering for orchestrator coordination | High | Detailed system prompts; test with multiple project types; iterate |
| Session storage size on disk | Low | Periodic cleanup; TTL on old sessions |
| No typed state validation between phases | Medium | Orchestrator validates artifacts exist before proceeding; JSON schema for test_results |
| Hook complexity for guardrails | Medium | Keep hooks simple (deny/allow); complex validation in MCP tools |
| Anthropic API rate limits | Medium | Backoff with tenacity; stagger subagent spawning |
| CLAUDE.md size vs context window | Low | Keep CLAUDE.md concise (~2000 tokens); detail goes in knowledge/ MCP resources |

---

## 15. Estimated Effort

| Phase | Tasks | Estimated complexity |
|-------|-------|---------------------|
| Phase 0: Setup & Dependencies | 3 | Small |
| Phase 1: Agent Definitions & Prompts | 4 | Medium — prompt engineering is iterative |
| Phase 2: Custom MCP Tools & Permissions | 3 | Medium |
| Phase 3: Hooks (Guardrails & Audit) | 3 | Medium |
| Phase 4: Backend Implementation | 4 | Large — core orchestration logic |
| Phase 4b: Advanced Claude Capabilities | 5 | Medium — high-value differentiators |
| Phase 5: Session Management & Recovery | 2 | Medium |
| Phase 6: UI & CLI Integration | 3 | Medium |
| Phase 7: RAG & Knowledge | 2 | Small-Medium |
| Phase 8: Testing & Comparison | 4 | Medium-Large |
| **Total** | **33 tasks** | |

Recommended execution order:
1. Phase 0 (dependencies + registry)
2. Phase 1 (prompts — can iterate these throughout)
3. Phases 2-3 in parallel (tools + hooks are independent)
4. Phase 4 (core backend — depends on 1-3)
5. Phase 4b (advanced capabilities — depends on 4, but items can be done incrementally)
6. Phase 5 (session management — depends on 4)
7. Phases 6-7 in parallel (UI + RAG are independent)
8. Phase 8 (testing + comparison — after everything works)

Phase 4b tasks can also be deferred and added incrementally after the core backend is working — they're enhancements, not blockers.

---

## 16. Dependencies & Versions

```toml
[tool.poetry.dependencies]
# New (Claude Agent SDK backend)
claude-agent-sdk = ">=0.1.0"
# anthropic = ">=0.40.0"  # likely transitive dep of claude-agent-sdk

# Existing (all other backends and shared layers unchanged)
# ...
```

New environment variable:
```bash
ANTHROPIC_API_KEY=sk-ant-...   # Required for claude-agent-sdk backend
# OPENROUTER_API_KEY still used for crewai and langgraph backends
```

---

## 17. Three-Backend Comparison Matrix

After all three backends are implemented, the comparison framework captures:

| Metric | CrewAI | LangGraph | Claude Agent SDK |
|--------|--------|-----------|-----------------|
| **Output quality** | File count, test pass rate, code completeness | Same | Same |
| **Cost ($/demo)** | OpenRouter pricing | OpenRouter pricing | Anthropic direct + prompt caching (up to 90% savings) |
| **Latency (seconds)** | Measured | Measured | Measured (prompt caching reduces TTFT) |
| **Token usage** | Input + output | Input + output | Input + output + cache read/write breakdown |
| **Error rate** | % runs with failures | Same | Same |
| **Recovery** | None (restart) | Checkpoint resume | Session resume + file rollback |
| **HITL experience** | Flag polling | interrupt() | canUseTool + AskUserQuestion |
| **Debugging** | Logs only | State inspection + replay | Session transcript + reasoning traces + audit log |
| **Streaming** | Callbacks | graph.stream() events | StreamEvent from query() |
| **MCP support** | Plugin (crewai-tools[mcp]) | Adapter (langchain-mcp-adapters) | Native (first-class) |
| **Setup complexity** | Medium | Medium | Low (fewer deps) |
| **Extended thinking** | ❌ Not available | ❌ Not available | ✅ Adaptive per agent |
| **Prompt caching** | ❌ | ❌ | ✅ Automatic, 90% read savings |
| **File rollback** | ❌ | ❌ | ✅ Built-in checkpointing |
| **Vision (screenshots)** | ❌ | ❌ | ✅ QA agent analyzes UI |
| **Deferred tool loading** | ❌ | ❌ | ✅ ToolSearch, 85% context savings |
| **Skills** | ❌ | ❌ | ✅ Reusable .claude/skills/ |
| **Session forking** | ❌ | ❌ | ✅ A/B test architectures |
| **Batch API (50% off)** | ❌ | ❌ | ✅ Async bulk analysis |
| **Per-agent effort tuning** | ❌ | ❌ | ✅ low/medium/high/max per agent |
| **Reasoning audit trail** | ❌ | ❌ | ✅ Thinking blocks logged |
