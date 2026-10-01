# The phase log is written by the harness

**Status:** Ready after this branch is on `main`.
**Proof:** `src/ai_team/harness/telemetry.py`

---

The log that says which phase an agent run is in used to be a line in a prompt. Item 7 told the model to append `logs/phases.jsonl`. When it didn't, the file was absent, and every check that needed a phase abstained. Nothing errored.

That line is gone. The LangGraph run writes the log itself, from the phases the graph recorded, including a run with the model switched off. Each row is `phase_start` or `phase_end`, and `writer` is `harness`, set inside the writer so the caller cannot stamp it as the agent.

A mocked run now leaves planning, development, testing, and complete in that file. `context_pressure` is null on purpose: there is no token window to divide by, and a guessed window would be a fake number.

Takeaway: a phase log is a write in the harness, on the path the graph already took.

The code:
src/ai_team/harness/telemetry.py

Which of your agent logs is still a sentence in a prompt?

#AgenticAI #AIEngineering #LLMOps

---

**Receipts**
- The instruction was `agents/prompts.py` item 7. `course/week-3-observe.md` step 5 taught that line. It is deleted, and a test refuses to let it back in.
- Placeholder nodes now append `phase_history`. `LangGraphBackend` calls `TelemetryWriter.phases_from_history` after the graph returns. `tests/unit/backends/test_langgraph_backend.py` runs the mocked graph and requires `planning` and `complete` with `writer: harness`.
