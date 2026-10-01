# What a run costs, per role

**Status:** Ready after this branch is on `main`. The September batch this note cites is local run output, not a new spend.
**Proof:** `scripts/role_cost.py`

---

I had the tokens. I did not have a command. The September batch, 30 runs of the same tiny brief on LangGraph, three agents, one model, sat in run records. Splitting it by hand is how the number got into a draft, and a draft is not something you can re-run.

`scripts/role_cost.py` reads one run directory. Input and output tokens come off each message. Dollars per role are that role's share of the run's `spent_usd`, by tokens, and the report says so. It is not a provider invoice broken out by agent.

On the 19 finished runs whose messages accounted for at least 90% of the cost-log tokens, QA held 89.6%, the developer 10.1%, the architect 0.3%. QA read about 43 tokens for every one it wrote. That is a retry loop on a bill.

Takeaway: attribute tokens per role before you tune a prompt. The developer was a tenth of this bill.

The command:
uv run python scripts/role_cost.py output/runs/<run_id>

Which role would you have optimized first?

#AgenticAI #AIEngineering #LLMOps

---

**Receipts**
- Same 30-run batch as the October notes (`output/smoke_batch_20260918_225130.json`): QA 16,997,089 in / 391,473 out, developer 1,846,937 / 106,229, architect 26,708 / 30,381, on 19 complete runs at or above 90% of `run_total.total_tokens`. Recomputed 2026-09-30 from `state.json`.
- `tests/unit/harness/test_role_cost.py` covers the stored message shape and a structured `usage_metadata` message. The dollar column is labeled as a token share.
