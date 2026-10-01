# The gate marks the work done

**Status:** Ready after this branch is on `main`.
**Proof:** `src/ai_team/backends/common/acceptance.py`

---

Across 19 runs in September, 153 acceptance criteria were written down before any code. Not one was ever marked done, including runs whose tests passed. The only function that could set `passes` to true was a tool on the Claude path. LangGraph and CrewAI were told to sign the work and had no such tool, so the list stayed false.

The quality gate already knew the answer: tests, lint, smoke. It wrote that answer to a side file and left the list alone. It now updates the list. A passing gate marks each criterion, with the gate file as the evidence, and the verifier is `_harness`. A failing gate leaves `passes` false. The agent that wrote the code does not grade it.

The September rows stay false. They are the record of the old writer. New runs take the new one.

Takeaway: the definition of done is a file the harness updates from the gate, not a tool you hope the QA agent calls.

The code:
src/ai_team/backends/common/acceptance.py

Who is allowed to mark a task done on your agent team?

#AgenticAI #AIEngineering #LLMOps

---

**Receipts**
- 153 items, 19 files, 0 with `passes: true`, counted 2026-09-30 from `workspace/2026-09-*/logs/acceptance.jsonl`.
- `mark_passing` was reachable from `backends/claude_agent_sdk_backend/tools/mcp_server.py` only.
- `tests/unit/backends/test_acceptance_signoff.py`: a passing gate sets `passes` and `agent_role == "_harness"`; a failing gate does not.
