# Corpus batch — 2026-09-18

Not a course test. LangGraph smoke, n=30, default `smoke` profile (pennies, mixed-model canary). SHA `e533c79` on `feat/course-v2`.

| | |
| --- | --- |
| **Runs attempted / completed / timed out / errored** | **30 / 22 / 7 / 1** |
| **Finish rate (95% Wilson)** | **22/30 = 73% [56–86]** — `final_status=complete`. Same as `tests_ok=True`. |
| **Wall min / median / max** | **1m34s / 12m22s / 30m00s** (script table). Raw: 93.7 / 742.4 / 1800.4 s. |
| **Spend** | **$0.897 total** of $3. Per run $0.002–$0.129, median $0.021. `logs/costs.jsonl` `spent_usd` **matches** `output/smoke_batch_20260918_225130.json` to the cent. |
| **`n_eligible` `--min-spans 1`** | **before 98 / after 128** (n_corpus 355 → 385). G3 unblocked. |
| **Spans per trace** | Whole corpus: min 0 / median 0 / max 28; **128 with ≥1 span, still 3 with ≥2**. This batch: **30/30 have exactly 1 span.** |
| **`retry_count`** | Of 23 runs with `state.json`: **19×0, 3×1, 1×2**. Seven timeouts have no `state.json`. |

Wall clock of the batch: **7 h 16 min** (15:35:59Z–22:51:30Z). Per-run ceiling in `run_smoke_batch.py` is **1800 s**, not the labs' 900 s. Timeouts are the 30-minute watchdog.

Raw: `output/smoke_batch_20260918_225130.json` (copy in this folder). Log: `batch.log`.

---

## The variance table

```
**MIXED-MODEL (confounded)** — CANARY demo (not a verdict), team=smoke, n=30, 2026-09-18

| Backend | Green | Green 95% CI | Wall min/median/max | Median 95% CI | Spend range |
|---|---|---|---|---|---|
| langgraph | 22/30 | 73% [56–86] | 1m33s / 12m22s / 30m00s | 7m26s–17m28s | $0.002–$0.129 |
```

---

## What surprised me

I thought we were buying thirty *readable* traces. `--min-spans 1` says we did: n_eligible went 98 → 128, and this batch alone is 30/30 eligible. Then I counted spans. **Every new trace has exactly one span.** The corpus still has **three** traces with two or more. Week 4 already told me 95 ones and 3 real reads; I just added 30 more ones.

I thought a timeout was a cheap abort. The seven 30-minute kills cost **$0.056–$0.129** each — more than most completes. The one `exit=1` (`failed`, 21m46s, $0.053) sits in the middle.

I thought retry 0 was "the" LangGraph result because week 2's evening row said so. On completes with a state file it is the **mode** (19/23), not a promise: one complete used 2 of 3 retries and still finished in 15.7 min.

The four anecdotes we had (226 s, 449 s, 518 s, 900 s timeout) were not a bad sample of the *shape* — the range is real — they were a bad sample of the **rate**. 7/30 hit the ceiling. That is not a freak.

n_eligible was already 98 before I spent a cent. G3 at `--min-spans 1` did not need this batch. G3 as "thirty traces with enough in them to open-code" still does.

---

## What this says about week 2's live table

The page currently shows **one morning row and one evening row**, each n=1, as if the evening 3.8 min / $0.008 / retry 0 were an after-state. On this SHA, the same brief, n=30:

| | langgraph (n=30, `e533c79`, 2026-09-18, canary, mixed-model) |
| --- | --- |
| Finished? | **22 complete / 7 timeout (30 min) / 1 failed** |
| Finish rate | **73% [56–86]** |
| Wall | 1.6 / **12.4** / 30.0 min |
| Spend | $0.002–$0.129 a run; **$0.90 the batch**; median $0.021 |
| `retry_count` | 0 on 19 of 23 completes that wrote `state.json`; 1 on three; 2 on one |
| Tests | `tests_ok=True` on every complete; missing on timeout/fail |

Keep the dated n=1 rows — they are what a learner will actually type. Add this as the variance row so "3.8 min, retry 0" is visibly one draw from a 73% [56–86] finish rate, not the after.

G3 (`--min-spans 1`, thirty traces): **unblocked** (128 eligible). Thirty *informative* traces (the week 4 sentence about "enough in them to read"): **still 3**. A second batch would buy more one-span files, not that.

No second batch. n_eligible is not under 30.
