# Flows

Orchestration can run on **CrewAI** (`AITeamFlow`) or **LangGraph** (`compile_main_graph`). Both follow the same product phases: intake → planning → development → testing → deployment (and optional human review / retry).

## CrewAI flow (default)

- Main flow: `AITeamFlow` with `@start`, `@listen`, `@router` on `ProjectState`.
- Conditional routing and human-in-the-loop map to flow methods and `ProjectState` fields (`awaiting_human_input`, `human_feedback`, etc.).
- See `src/ai_team/flows/main_flow.py` and [ARCHITECTURE.md](ARCHITECTURE.md) §2.1.

## LangGraph backend

- **Graph:** `StateGraph` built in `src/ai_team/backends/langgraph_backend/graphs/main_graph.py`.
- **Entry:** `START → intake → …` with **conditional edges** implemented in `graphs/routing.py` (`route_after_intake`, `route_after_planning`, `route_after_development`, `route_after_testing`, `route_after_deployment`, `route_after_human_review`).
- **Modes:**
  - `placeholder` — lightweight nodes (no subgraph LLM calls); suitable for fast tests and smoke runs.
  - `full` — planning/development/testing/deployment nodes delegate to compiled subgraphs.
- **Persistence:** SQLite checkpointer by default; optional Postgres via `AI_TEAM_LANGGRAPH_POSTGRES_URI`.
- **HITL:** In `full` mode, `human_review` may call `interrupt()`; resume with `Command(resume=...)` and the same `thread_id` (see CLI `--resume` / Gradio resume fields).

```text
START → intake → [rag_context?] → planning ⇄ human_review → development
  → testing → (retry_development ↺) → deployment → complete → END
  → error → END
```

Error and retry paths are driven by `errors`, `test_results`, `retry_count`, and `metadata` flags (`planning_needs_human`, `testing_needs_human`) as documented in `routing.py`.
