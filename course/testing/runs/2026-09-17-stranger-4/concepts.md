# Concept ledger — 2026-09-17-stranger-4

Scoped run (weeks 5–6). Weeks 1–4 not re-taught here; verdicts below are from what this pass ran.

| Concept | Where the course teaches it | What I could explain afterwards | Verdict |
| --- | --- | --- | --- |
| A team of agents is mostly glue | W1.S1, W2.S2 | Not re-run. | — (SKIPPED-SCOPE) |
| Tool calls are the only thing that changes the world | W1.S2, W2.S2 | Not re-run. | — (SKIPPED-SCOPE) |
| Writes are staged, not saved (draft → commit) | W2.S2 | Not re-run. | — (SKIPPED-SCOPE) |
| Guardrails can fail correct work | W2.S2 | Not re-run. | — (SKIPPED-SCOPE) |
| Retries are a cost multiplier, not a safety net | W1.S3, W2.S1 | Not re-run. B5 completed retry=0 in 7.5 min. | — (SKIPPED-SCOPE) |
| Telemetry has a writer and a reader, and they disagree | W3.S1–S3 | Backfill still mints a new hashed file per invocation (R13). Killed 25 s preflights labelled `failed`. | taught (reproduced) |
| A check that can't see anything abstains, it doesn't pass | W3.S4, W5.S3 | `spend.py` still na when there is no cost. Killed preflights: 0 pass / 2 fail on my check. One complete run produced the first CORPUS pass. | taught |
| Failure modes are a taxonomy you build, not a list you're given | W4 | Not re-run. | — (SKIPPED-SCOPE) |
| A pass rate means nothing without its corpus kind and `n` | W5.S1–S2, W6.S4 | FIXTURE-ONLY 182 fail, then 228 with my check. CORPUS 0/2 thin → 1/5 after one complete LangGraph. Uniqueness 22 warnings do not change the FAIL. | taught |
| Deterministic checks before LLM judges | W5.S3 | 20 checks, then 21. I wrote one. The suite is the teacher once the check is imported *and* you run `tests/unit/repo`. | taught |
| A fix is a claim until you measure it twice | W6.S2–S4 | Tighten ≥2 spans: 228→257 fails (same 29-flip as last run). CORPUS: 0% (n=2) then 20% (1 pass / 4 fail, n=5). Intervals still overlap. | taught |
| Monitoring is the same eval on a cadence | W6.S5 | Audit on 2 killed preflights (before B5 finished): floors unmet. | taught |
| A baseline answers "did this change?"; fixtures answer "is this right?" | W5.S4 (new copy) | I deleted the pass fixture. Gate exit 1, names the missing pass file. Last SHA this was exit 0. | taught |
| Empty env vars beat `.env` | W1 (preflight this run) | Empty prefix: all three backends fail immediately with "set but empty… unset…". After `unset`, Claude starts (Watchdog armed, `claude_recovery_attempt`). | taught (was missing last run) |
