---
description: CrewAI agent, crew, and flow patterns
globs: ["src/ai_team/backends/crewai_backend/agents/**/*.py", "src/ai_team/backends/crewai_backend/crews/**/*.py", "src/ai_team/backends/crewai_backend/flows/**/*.py"]
alwaysApply: false
---

# Agent Definition

Personas live in `src/ai_team/config/agents.yaml`; the role → model map lives in
`src/ai_team/config/models.py`. CrewAI agents are built by the factory, not by subclassing:

```python
from ai_team.backends.crewai_backend.agents.base import create_agent

architect = create_agent("architect", tools=[...])  # key in agents.yaml
```

The LLM comes from `config/llm_factory.create_llm_for_role(role, settings)` (OpenRouter).

# Crew Composition

```python
crew = Crew(
    agents=[...], tasks=[...], process=Process.hierarchical,
    manager_agent=self.manager, memory=True, verbose=True, planning=True,
)
return crew.kickoff(inputs=inputs)
```

# Flow Orchestration

`AITeamFlow(Flow[ProjectState])`: use `@start()`, `@listen(previous)`, `@router(previous)` for branching.

```python
@router(run_planning_crew)
def route_after_planning(self):
    if self.state.requirements and self.state.architecture:
        return "run_development"
    return "request_human_feedback"
```

# Task with Guardrail

`Task(description=..., expected_output=..., output_pydantic=..., guardrail=fn)`. Guardrail receives `TaskOutput`, returns it or raises `GuardrailFailure` to trigger retry.
