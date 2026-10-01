# Two CrewAI failures, one page

**Status:** Ready after this branch is on `main`.
**Proof:** `docs/FRAMEWORKS.md`

---

Same nine agents, three frameworks. The comparison that was supposed to carry that sentence did not exist, so the link pointed at an architecture section that says where each one keeps state and waits for a human. The failure stories were somewhere else, and they got told as one.

CrewAI had two. A listener re-triggered itself 93,284 times in 15 minutes, because a completed method emits its own name. That one was fixed by renaming the listeners. Separately, a hung thread in the same process starved every other backend for 78 minutes. That one is why CrewAI now runs in its own process, with a hard kill. The process boundary did not rename the listeners. The rename did not create the process boundary.

LangGraph's failure in the September smoke run was a routing edge: every QA complaint went back to development. The Claude Agent SDK keeps state in the session and in files, and its guardrails are hooks. At five runs it was the most expensive, and it was also the only one on Claude, so that row does not rank the framework.

Takeaway: pick a framework by the failure you can name. Write the two incidents on two lines.

The page:
docs/FRAMEWORKS.md

Which failure would you rather have a name for at 2am?

#AgenticAI #AIEngineering #LLMOps

---

**Receipts**
- State, resume, human, and guardrail rows: `docs/ARCHITECTURE.md` §2.1.1.
- 93,284 iterations: `docs/posts/failure-taxonomy.md` §2 and `tests/unit/flows/test_flow_wiring.py`.
- 78 minutes, GIL, subprocess kill: `docs/troubleshooting/gil-starvation-hitl-delay.md`. The next run's 93,284 loop is described there as a second finding, after the process boundary was already the fix under test.
- Claude 5/5, $0.48–$0.95, overlapping Wilson intervals at n=5: README results table.
