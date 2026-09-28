# Build the reading corpus (and measure the finish rate)

Not a course test. This is a long unattended job that produces four things the project has
never had, from one batch of runs:

1. **thirty readable traces** for week 4's open-coding pass (gate G3, currently 0 of 30);
2. **a finish rate with an interval** — how often a LangGraph smoke actually completes. Four
   observations so far on the same brief: 226 s, 449 s, 518 s, and a 900 s watchdog timeout.
   Every one of them is an anecdote. This turns them into a number;
3. **week 2's variance row**, which currently presents a single lucky run as an after-state;
4. **the before half of G4's before/after.**

## Parameters

- `n`: 30 · `backends`: langgraph only · profile: default (pennies, not `smoke-claude`)
- `budget_usd`: **$3 total.** Per-run cap `AI_TEAM_RUN_BUDGET_USD=1`. Measured cost has been
  $0.008–$0.054 a run, so $3 is roughly 10x headroom. Stop and report if you reach it.
- Wall time: **2–8 hours.** Each run is 4–15 min and the watchdog kills at 900 s. Start it and
  let it go; do not babysit.
- Do **not** edit `course/` or anything under `src/`. This job only makes data.

## Run

```bash
export AI_TEAM_ENV=dev
unset OPENROUTER_API_KEY ANTHROPIC_API_KEY     # an empty value beats .env, on purpose
uv run python scripts/run_smoke_batch.py --n 30 --backends langgraph 2>&1 | tee /tmp/batch.log
```

The script writes `output/smoke_batch_<timestamp>.json` and prints a markdown variance table
with Wilson intervals. Keep both.

**Timeouts are data, not failures.** A run killed at 900 s is one of the outcomes being
measured. Record it and carry on. If the whole batch dies, report how far it got — a partial
batch is still evidence.

## Then rebuild the corpus and check it

`trace backfill` mints a new trace id per invocation (R13, open), so wipe first or you will
count the same run twice:

```bash
rm -rf course/.work/traces
uv run python -m evals.cli trace backfill --workspace-root output/runs \
  --traces-root course/.work/traces

uv run python -m evals.cli sample --strategy stratified -n 30 --seed 1 --min-spans 1 \
  --traces-root course/.work/traces --samples-root course/.work/samples
```

`n_eligible` is the answer to "can Rick read thirty?". **If it is under 30, say so and say by
how many** — then run a second batch sized to the shortfall plus a third for the expected
timeout rate. Do not round up to "close enough": the whole point of week 4 is that thirty
readable runs is a real threshold, not a vibe.

## Report

Write `course/testing/runs/<date>-corpus/report.md`. Short. No rubric, no coverage table —
this is not a course test. Cover:

| | |
| --- | --- |
| Runs attempted / completed / timed out / errored | |
| Finish rate with its 95% Wilson interval | the number the course has never had |
| Wall time: min / median / max | against the page's "30 min, cents" claim |
| Spend: total, per run, and which file you read it from | `logs/costs.jsonl` vs the log |
| `n_eligible` at `--min-spans 1`, before and after | is G3 unblocked? |
| Spans per trace: min / median / max | is there anything in them to read? |
| `retry_count` distribution | week 2 claims retry 0; is that typical or was it one draw? |

Then three short sections:

- **The variance table** the script printed, verbatim.
- **What surprised you.** Same first-person rule as the course-test skill.
- **What this says about week 2's live table**, which currently shows one run per backend as
  though it were a result. Write the row you think the page should carry now, with its `n`.

Paste the finish rate and `n_eligible` into chat at the end. Those two numbers decide what
happens next.
