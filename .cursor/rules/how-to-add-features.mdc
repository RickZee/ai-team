---
description: Checklists for adding new agents, tools, guardrails, crews, and flow steps
alwaysApply: true
---

# When creating a new agent

An agent exists once per backend; a role added to only one backend breaks the comparison.

1. Add the persona to `config/agents.yaml` (role, goal, backstory, allow_delegation, max_iter)
2. Map the role to a model in `config/models.py` (`_role(...)` entries per `AI_TEAM_ENV` tier)
3. CrewAI: wire it in `backends/crewai_backend/agents/` via `create_agent(role_name, tools=...)`
4. LangGraph: add prompt + tools in `backends/langgraph_backend/agents/` and a node/subgraph in `graphs/`
5. Claude Agent SDK: add the subagent in `backends/claude_agent_sdk_backend/agents/definitions.py`
6. Add it to the profiles that need it in `config/team_profiles.yaml`
7. Unit test per backend; run `tests/conformance/` to confirm all three still satisfy the protocol

# When creating a new tool

1. Create in `src/ai_team/tools/` with `@tool` decorator
2. Include security wrapper (path validation, content scanning)
3. Add audit logging for all operations
4. Define Pydantic models for structured input/output
5. Add unit test with normal and adversarial inputs
6. Register in the appropriate agent's tool list

# When creating a new guardrail

1. Add to `behavioral.py`, `security.py`, or `quality.py`
2. Return `GuardrailResult` Pydantic model
3. Integrate with CrewAI task `guardrail` parameter
4. Add toggles in `GuardrailConfig` settings
5. Add unit test (passing, failing, edge-case)
6. Add adversarial cases under `tests/unit/guardrails/adversarial/`

# When creating a new crew

1. Create in `src/ai_team/backends/crewai_backend/crews/` with `kickoff()` method
2. Define tasks in `src/ai_team/config/tasks.yaml` and `src/ai_team/backends/crewai_backend/tasks/`
3. Set process (hierarchical or sequential)
4. Configure memory, planning, verbose
5. Add context dependencies between tasks
6. Integrate guardrails at task level
7. Add integration test with mocked LLM

# When adding to the flow

1. Add `@listen` to `AITeamFlow` in `src/ai_team/backends/crewai_backend/flows/main_flow.py`
2. Add `@router` for branching if needed
3. Update `ProjectState` if needed
4. Add phase to `ProjectPhase` enum if new
5. Add error handler in `error_handling.py`
6. Update routing documentation
7. Add integration test for new flow path
