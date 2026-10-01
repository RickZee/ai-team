# Frameworks

Where LangGraph, CrewAI, and the Claude Agent SDK keep state, wait for a human, and fail. Strands on Amazon Bedrock AgentCore and Microsoft Agent Framework on Microsoft Foundry are being built against the same `Backend` contract. Neither runs yet ([CLOUD_NATIVE.md](CLOUD_NATIVE.md), [ADR-001](adr/ADR-001-cloud-native-backends.md)).

The tables below are the orchestration comparison in [ARCHITECTURE.md](ARCHITECTURE.md) §2.1.1. The failure notes are separate incidents. They are not one story.

## State, resume, human, guardrails

| | CrewAI | LangGraph | Claude Agent SDK |
| --- | --- | --- | --- |
| Primary state | `ProjectState` on the flow | Checkpointed graph state | Session transcript plus workspace files |
| Resume | Rerun the flow, or start a new run | Thread id and `Command(resume=...)` | `session_id`, optional fork |
| Human | Flow flags / `human_feedback` | `interrupt()`, then resume | `AskUserQuestion`, optional `can_use_tool` |
| Guardrails | Task validators | Graph nodes and shared helpers | Hooks before and after tool calls |

## What broke, and the fix that belongs to it

**LangGraph, routing.** Retries are edges. On the 2026-09-13 smoke run, `route_after_testing` sent a QA-phase error back to development, and that loop stacked on a guardrail retry. The files were already on disk. The edge now sends a guardrail complaint about QA to a human. Receipt: [docs/eval-runs/2026-09-13-langgraph-smoke/](eval-runs/2026-09-13-langgraph-smoke/).

**CrewAI, a listener that re-triggered itself.** In CrewAI Flows a completed method emits its own name, and a method that listens for that name runs again. One retry handler reached 93,284 iterations in 15 minutes. The fix is the listener names: `on_<trigger>`, plus a test that fails if a method listens to itself. That fix is not the process boundary. Receipt: [docs/posts/failure-taxonomy.md](posts/failure-taxonomy.md) §2, `tests/unit/flows/test_flow_wiring.py`.

**CrewAI, a hung thread.** A different run pinned a thread at about 95% CPU inside the same process as the other backends. LangGraph's interrupt was done, and the API still reported `running` for 78 minutes, because the spinning thread held the GIL. The fix is a process boundary: CrewAI runs in its own process, with `terminate()` and then `kill()` at the deadline. Receipt: [docs/troubleshooting/gil-starvation-hitl-delay.md](troubleshooting/gil-starvation-hitl-delay.md).

**Claude Agent SDK.** State is the session and the files. Guardrails are hooks. At n=5 it finished 5/5 and cost $0.48 to $0.95 a run, and it was the only row on Claude. Those intervals overlap the other rows. The table does not rank frameworks. Receipt: the results table in the README.

## What this page will not say

A demo of the happy path looks the same on all three. The choice is which failure you want to debug. Five runs are not a ranking.
