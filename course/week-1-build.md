# Week 1 · Build — the easy part

**By the end:** you've run a nine-agent team twice — once with no model, once for real — and
you know where everything it did was written down.
**Time:** ~90 min · **Cost:** $0, then cents · [← Course home](./README.md)

---

## Step 1 — Meet the team (20 min)

One brief goes in. Agents plan it, write code, test it, and hand back a workspace. The same
team runs on **three frameworks** behind one interface:

![Same phases, three frameworks: CrewAI, LangGraph, Claude Agent SDK](../docs/images/inter-agent-overview.svg)

**Read** `src/ai_team/core/backend.py`. It's about 30 lines: every framework implements
`run(description, profile)` and `stream(...)`. Same tools, same guardrails, same folders.
That's what makes the question behind this course answerable:

> **When it fails, whose failure is it — the model's, the framework's, or yours?**

Our brief lives in `demos/00_smoke_test/` — open `input.json`. It uses the small `prototype`
team: architect → developer → QA.

## Step 2 — Run it with the model switched off (15 min, $0)

**Predict.** The pipeline will "run" with every model call stubbed. When it finishes, which
of these will exist? An end time in the run record · a final status · a phase log · a cost log.

**Run.** The empty key variables guarantee this can't spend, even if `.env` has keys.

```bash
OPENROUTER_API_KEY= ANTHROPIC_API_KEY= \
  uv run python scripts/run_demo.py demos/00_smoke_test \
  --backend langgraph --graph-mode placeholder --skip-estimate --timeout 120
```

**Observe.** Now look at what was written:

```bash
RUN=output/runs/$(cat output/latest)
ls $RUN $RUN/logs
python3 -m json.tool $RUN/run.json
grep -m1 '"current_phase"' $RUN/state.json
```

Fill in this card from what you see:

| Field | Value |
| --- | --- |
| backend (`run.json`) | |
| current_phase (`state.json`) | |
| completed_at (`run.json`) | |
| final status (`run.json` → `extra`) | |
| files in `logs/` | |

On this repo it looked like this:

![The run finished; the record says it never ended](./images/run-card.png)

**Explain.** The run finished — `state.json` says `complete` — but the run record never got an
end time or a final status, and no phase, cost or audit log exists. Nothing errored.

Every dashboard, eval and report reads the right-hand side. A run with no end time silently
drops out of "average duration"; a run with no phase log gives every path-based check nothing
to look at. **Missing data doesn't fail loudly. It makes every number above it a bit fictional.**

**Change.** Find out who is supposed to close the run record. The method is `finalize()`:

```bash
grep -rn "finalize(" src/ai_team scripts --include=*.py
```

On this repo it's defined in `core/results/writer.py` and called from the web server and the
Claude Agent SDK backend — **not** from the command-line path you just used. Which of your
runs will ever get an end time? Keep the answer; it's a candidate fix for week 6.

## Step 3 — Run it for real (30 min, cents)

Needs `OPENROUTER_API_KEY` in `.env` (or `ANTHROPIC_API_KEY` for `claude-agent-sdk`).

**Predict.** The brief: *write `add(a, b)` and one pytest.* A single model call does this in
about two seconds. How long will the team take? Will it pass?

**Run.**

```bash
AI_TEAM_ENV=dev AI_TEAM_RUN_BUDGET_USD=1 \
  uv run python scripts/run_demo.py demos/00_smoke_test \
  --backend langgraph --skip-estimate --timeout 900
```

**Observe.** Fill in the same card for this run, plus: wall time, `retry_count`, and whether
`workspace/<run_id>/` contains a test file.

```bash
RUN=output/runs/$(cat output/latest); ID=$(cat output/latest)
grep -E '"(current_phase|retry_count)"' $RUN/state.json | head
ls workspace/$ID
```

**Explain.** It may succeed, hang, or end asking a human for review. **All three are useful.**
Don't re-run it yet — whatever happened is next week's material.

## Where things went

| Path | Holds | Written by |
| --- | --- | --- |
| `output/runs/<id>/` | the **run record**: `run.json`, `state.json`, `logs/`, `reports/` | the harness |
| `workspace/<id>/` | the **code the agents wrote** | the agents |

Remember this table. In week 3 it's the whole story.

## ✅ Checkpoint

- [ ] Two filled-in cards: dry run and real run
- [ ] One sentence on why the dry-run card is suspicious
- [ ] Your answer to "which runs ever get an end time?"

**For testers:** a dry run with the model mocked is a smoke test of your *test
infrastructure*. Before trusting a report, check the harness wrote one.

**Next:** [Week 2 · Fail →](./week-2-fail.md)
