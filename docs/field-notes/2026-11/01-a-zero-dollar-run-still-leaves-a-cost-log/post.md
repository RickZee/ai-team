# A zero-dollar run still leaves a cost log

**Status:** Ready after this branch is on `main`. The proof is the file below; do not publish the GitHub link until that file is on `main`.
**Proof:** `src/ai_team/harness/telemetry.py`

---

I ran the agent team with the model switched off. The run finished. The record said when. The cost log was not there.

Every spend chart I have reads `logs/costs.jsonl`. A run with no row does not show up as free. It drops out. The same hole hid months of CLI runs: the closer skipped the file whenever the model had not been called, and a mocked run calls the model zero times.

The closer now writes the row anyway. No calls, no tokens, `spent_usd: 0`, and the line is stamped `writer: harness`, from the module, not from a field the caller can set. Zero is a measurement. A missing file was a gap in the instrument.

Takeaway: if a run can finish without spending, the cost log still has to say zero.

The code:
src/ai_team/harness/telemetry.py

What does your cost chart do with a run that spent nothing?

#AgenticAI #AIEngineering #LLMOps

---

**Receipts**
- Dry run on 2026-09-30: exit 0, `completed_at` set, `logs/` empty. `scripts/run_demo.py` passed `spend=None` when `calls` was 0, and `ResultsBundle.finalize` wrote `costs.jsonl` only when `spend` was truthy.
- After this change, `tests/unit/core/test_results_bundle.py` and `tests/unit/harness/test_telemetry.py` require a zero `run_total` row with `writer: harness`.
