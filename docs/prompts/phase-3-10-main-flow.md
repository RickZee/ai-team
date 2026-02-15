# Prompt 3.10: Generate Main Flow

**Source:** PROJECT_PLAN_OPUS_4_5.md — Phase 3 (Task & Flow Design)

---

Create the main AITeamFlow orchestration with:
1. Pydantic state model (ProjectState)
2. @start() for intake_request
3. @listen() for each crew execution
4. @router() for conditional branching
5. @human_feedback for escalation
6. State persistence between steps
7. Guardrail integration at each step
8. Error handling with retry logic

Include flow visualization with plot() method.
