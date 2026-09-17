# Week 2 · Fail — run it fresh, see it break

**By the end:** you've watched the same brief break on different frameworks and put a layer —
model, framework, harness or provider — next to every failure. Most of the breaking now lives
in the recorded case and the git history rather than in your own live run — which is what
"we fixed it" is supposed to look like, and why every claim here carries its date and its `n`.
**Time:** ~2 hours · **Cost:** ≈ $1 with keys, $0 with the recorded case · [← Course home](./README.md)

---

## Step 1 — The race (30 min)

**Optional, and it will probably work.** That is the point. Four days ago this step was the
centrepiece: on a fresh clone (2026-09-16) only the Claude SDK run finished — 170 s, $0.71 —
while LangGraph and CrewAI were still going at 15 minutes. Four harness fixes later, all three
finish. You are running the *after*; step 2 is the *before*, fully recorded, and it is still
where the lesson is. If you have no keys, skip straight there.

**Predict.** Same brief, same tools, same guardrails. Which framework finishes fastest? Which
one fails? Write it down **before** you look at the table below — the interesting part is
where your intuition about "fastest" is wrong.

**Run** — one line per backend you have a key for. Same **stop rule** as week 1: Ctrl-C at
minute 15, then `ps aux | grep run_demo` and kill leftovers. Note: the `$1` cap is enforced by
the harness for LangGraph and CrewAI; Claude runs cost ≈ $0.50–$1.

```bash
for B in langgraph crewai claude-agent-sdk; do
  AI_TEAM_ENV=dev AI_TEAM_RUN_BUDGET_USD=1 \
    uv run python scripts/run_demo.py demos/00_smoke_test \
    --backend $B --skip-estimate --timeout 900
done
```

Prefer to watch? Start the dashboard and use the **Compare** tab, which races them live:

```bash
uv run ai-team-web &                                        # API on :8421
(cd src/ai_team/ui/web/frontend && npm install && npm run dev)  # open localhost:5173/compare
```

**Observe.** One row per run:

| | langgraph | crewai | claude-agent-sdk |
| --- | --- | --- | --- |
| Finished? how? | | | |
| Wall time | | | |
| `retry_count` | | | |
| Test file in `workspace/<id>/`? | | | |
| Files in `output/runs/<id>/logs/` | | | |

```bash
ls -t output/runs | head -3          # your three newest run ids
```

**What this looked like on 2026-09-17**, same brief, same day, four commits apart:

| | langgraph | crewai | claude-agent-sdk |
| --- | --- | --- | --- |
| Morning (`396a348`) | complete, 12.4 min, `$0.054`, **retry 3 of 3** | **failed** at 14 min on deployment guardrails, no tests | complete, 3.6 min, `$0.90` |
| Evening (`8db7448`) | complete, **3.8 min**, `$0.008`, **retry 0** | complete, 9.8 min, 5 tests pass | complete, 3.8 min, `$0.86` |

Two things to take from that. The morning LangGraph run *finished* and still burned every
retry it had on code that was correct the first time — "it completed" is not the same as "it
worked". And one fix moved two backends, because both shared the same piece of glue.

A failed row is still a result, not a broken lab. Fill in what you actually see; your row may
differ from both of these, and that is data.

## Step 2 — Study a recorded failure (45 min, $0)

No key? This step is for you too. It's the same brief, run on 2026-09-13, with every log kept:
[`docs/eval-runs/2026-09-13-langgraph-smoke/`](../docs/eval-runs/2026-09-13-langgraph-smoke/README.md).

**Predict.** A bare model call writes this module in 1.5 seconds for $0.00007. How long did the
nine-role team take?

**Observe.**

![1.5 seconds versus 26 minutes on the same brief](./images/smoke-timeline.png)

Read the *Timeline* table in that README top to bottom, then open the evidence:

```bash
ls docs/eval-runs/2026-09-13-langgraph-smoke/evidence/
```

**Explain.** The files were correct by minute two. Everything after that was the harness:

- a relevance guardrail scored the QA agent against the **last 12 chat messages** — not the
  files it wrote — and got 0–9% against a 15% floor, so it retried;
- the router sent **every** testing-phase error back to development;
- the test run collected **0 tests**, with the test file sitting right there.

A better model would not have helped.

**Change.** Before reading on, write down what you'd change to stop the loop. Then read what
was actually changed (2026-09-16):

```bash
LOOPFIX=$(git log --format=%h -1 --grep="stop the LangGraph guardrail loop")
git show --stat $LOOPFIX
git show $LOOPFIX -- src/ai_team/backends/langgraph_backend/graphs/guardrail_hooks.py src/ai_team/backends/langgraph_backend/graphs/routing.py
```

Four small changes, none of them to a prompt or a model:

1. **Score the current turn.** Guardrails now read only what this phase's agents said —
   everything after the phase's own task message — not the whole run history.
2. **A single agent isn't a supervisor.** Single-agent planning and development were
   filtering on a supervisor that didn't exist, so their guardrail never checked anything.
3. **A guardrail complaint about QA goes to a human,** not back to development.
4. **Use the run's own folder.** The QA agent was told the parent `./workspace` path, which
   is where the sandbox error and the nested folders came from.

How close was your guess? The regression test rebuilds the exact 09-13 situation and shows the
old scoring failing correct test code at 8%:

```bash
uv run pytest tests/unit/backends/langgraph_backend/test_guardrail_loop_regression.py -v
```

**Then the next layer showed up.** The first live run after that fix had no guardrail
failures — and still didn't finish in 15 minutes. The log showed why: every file the agents
wrote was only a *draft* ("call commit_write to promote"), and no agent was ever given
`commit_write`. Nothing was saved, so pytest never saw a test. On top of that, the QA agent's
prompt told it to use `file_writer`, a tool it didn't have. The unit tests never noticed,
because the test setup switches drafts off.

```bash
DRAFTFIX=$(git log --format=%h -1 --grep="save agent writes")
git show --stat $DRAFTFIX
uv run pytest tests/unit/backends/langgraph_backend/test_pipeline_writes_reach_disk.py -v
```

That last test runs the whole pipeline offline, drafts on, with scripted agents: it completes
with passing tests and no retries.

**Then a live run finished.** 2026-09-17 morning: twelve and a half minutes, five cents, tests
passing — the first LangGraph smoke in this repo's history to complete on its own. Read the
next sentence before you celebrate. It retried the entire development phase **three times out
of a maximum of three**, on code that was already correct on the first attempt. One more bad
round and it would have been another failure.

The log says why, and it is a third layer. The brief asks for `calc.py` and `test_calc.py`
only. The agent wrote exactly that. The harness had **two write paths that disagreed**: one
silently rewrote a root-level `test_calc.py` to `tests/test_calc.py`, the other wrote it where
the agent asked. Both files existed, with the same module name, so pytest refused to collect
either. The agent spent four rounds deleting a file it had never created. Its closing message:
*"All 74 tests pass (37 from root `test_calc.py` + 37 from `tests/test_calc.py`)."*

Two smaller ones underneath. The gate linted the generated project with **ai-team's own house
style**, failing it on a rule the brief never mentioned. And the QA agent, whose prompt tells
it to "inspect source files", had no tool that could read one — it called `read_file` three
times, was told that is not a valid tool, and rewrote the source from memory.

```bash
PATHFIX=$(git log --format=%h -1 --grep="write what was asked")
git show --stat $PATHFIX
uv run pytest tests/unit/tools/test_write_path_fidelity.py -v
```

> **The pattern:** fixing the loudest failure uncovers the quiet one behind it. A test suite
> that runs with a production switch flipped off is testing a different program. And a harness
> that silently "helps" — relocating a file, renaming a path — makes the agent spend its turns
> fighting a ghost.

Fixing those three took an afternoon. The same brief that evening: **3.8 minutes, $0.008,
`retry_count: 0`**, two files at the paths the brief asked for — and CrewAI, which shared the
same write path, went from failing at 14 minutes to passing in 9.8.

**Two live runs are not a rate.** n=1 before, n=1 after. Every number in this section is a
single observation, and the interval around a single observation is enormous. Turning "it's
faster now" into a claim you could defend is week 6.

## Step 3 — Whose failure is it? (30 min)

Put a layer next to every failure from steps 1 and 2:

| Layer | Means | Example from this repo |
| --- | --- | --- |
| **Model** | The LLM did something dumb | Wrote code as prose and asked permission instead of calling the tool |
| **Framework** | The orchestrator's rules bit you | An event listener that re-triggers itself forever |
| **Harness** | Your own glue code | The guardrail reading chat history instead of files |
| **Provider** | The API or router | The same model id behaving differently depending on who serves it |

![Where multi-agent failures actually sat: mostly the harness](../docs/images/failure-stack.svg)

Check yourself against the full catalogue:
[*Seventeen Ways Multi-Agent Systems Actually Fail*](../docs/posts/failure-taxonomy.md).
(The chart above was drawn when it had ten entries; the catalogue now has seventeen, and the
harness still dominates.)

## Step 4 — Don't rank anything yet (15 min)

**Predict.** Framework A went green 5 of 5, framework B 1 of 5. Is A better?

**Observe.** Two traps:

1. **The models differ.** By default CrewAI and LangGraph run a DeepSeek model and the Claude
   SDK runs Claude, so each row is a *framework + model* bundle. Holding the model constant
   changes the story:

   ![Same framework, only the model changed](../docs/images/same-model-matrix.svg)

2. **n=5 is too small.** 1/5 has a 95% interval of 4–62%; 5/5 has 57–100%. They overlap. We'll
   do this properly in week 6.

**Explain.** Write down *what* failed, not *who won*.

## ✅ Checkpoint

- [ ] A comparison table — your runs or the recorded case
- [ ] A layer next to every failure
- [ ] The minute the recorded task was actually done, and what kept it running

**For testers:** this is root-cause classification in a defect tracker, with four new
component names.

**Exercise:** find a failure where two layers are both plausible. What evidence would settle
it — and was that evidence recorded? That's next week.

**Next:** [Week 3 · Observe →](./week-3-observe.md)
