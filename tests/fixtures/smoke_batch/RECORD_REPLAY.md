# Record / replay for the comparison batch

The backend comparison costs real money to run — metered API calls across three
backends, n≥5 each. That makes it hard for a contributor to validate a change to the
*harness* (the parsing, the confidence-interval math, the verdict rendering) without
paying to exercise it. Replay mode fixes that.

## Replay (zero cost)

```bash
uv run python scripts/run_smoke_batch.py --replay example_mixed_model_n5
```

This reads a recorded bundle and runs the entire report pipeline — Wilson intervals,
median bootstrap, pairwise verdicts, the confounded/canary banners — against the
recorded rows. No backend runs, no API calls, $0. Use it to check that a change to
`scripts/batch_stats.py` or the reporting still produces the expected table.

`--replay` accepts a bare fixture name (resolved under `tests/fixtures/smoke_batch/`),
or a path.

## Record (costs money — you provide the runs)

A recorded bundle is just the normal output of a live batch. Run one for real:

```bash
uv run python scripts/run_smoke_batch.py --n 5 --team smoke-claude --demo demos/02_todo_app
```

That writes `output/smoke_batch_<timestamp>.json`. To turn it into a replay fixture,
copy it into this directory under a descriptive name:

```bash
cp output/smoke_batch_<timestamp>.json \
   tests/fixtures/smoke_batch/my_same_model_todo_n5.json
```

Then anyone can replay it at no cost. Keep fixtures honest: they carry their own
provenance (`same_model`, `demo`, `is_canary`, `generated_at_utc`), and the report
banners are driven by those fields, so a mislabeled fixture will announce itself.

## What replay does and does not prove

- **Proves:** the harness parses rows correctly, the statistics are right, and the
  verdict rule ("no ranking when intervals overlap") fires as intended.
- **Does not prove:** anything about a live backend's real behavior — that still needs
  a recorded (paid) run. Replay validates the *measurement*, not the *measured*.

Live `output/smoke_batch_*.json` files are working artifacts and are git-ignored.
Fixtures in this directory are committed on purpose — they are the shared, free way to
test the harness.
