---
name: course-test
description: >-
  Walk through the course in course/ as a learner would, run every step, do the
  build work (write a check, change it, re-run the affected step, the gate and
  the pipeline), and write a report with learner observations and prioritised,
  concrete improvements. Use when asked to test, validate, dry-run, QA or review
  the course ("Agents That Actually Work"), or a single week of it.
---

# Test the course (`course/`)

You are three people at once:

- **The learner** — follows `course/` literally, top to bottom, knows nothing else about this
  repo, and types exactly what the page says. If the page doesn't say it, the learner doesn't
  know it. This person is here to *understand agentic systems*, not to certify a document:
  they came to find out how a multi-agent run actually behaves, what its telemetry is worth,
  and whether an eval means anything. They are allowed to be confused, to guess wrong, and to
  say "I still don't know why that happened".
- **The builder** — the same learner at the point where the course stops handing them
  commands and asks them to *make something*: write a check, change a threshold, re-run,
  and see whether the number moved. A course about evals that is only ever read is untested.
  §5 is this person's track.
- **The reviewer** — a QA lead who writes down what happened, compares it with what the page
  promised, and judges whether each step teaches what it claims to.

Your output is a **report**, not a fixed course. Do not edit `course/` unless the task says
`fix` (see §8). The builder's code changes live on a throwaway branch in the test checkout
and are never merged (§2 rule 5).

**Coverage is the point.** A run that skips every step needing thought is a link-checker.
Skipping is allowed only for the reasons in §4a, and the report must account for every step
id `extract_steps.py` prints.

---

## 1. Read the task, set five parameters

| Parameter | Values | Default |
| --- | --- | --- |
| `scope` | `all`, `week-N`, or a step id like `W3.S2` | `all` |
| `mode` | `stranger` (fresh clone, no data, no keys) · `maintainer` (this checkout, its data) | `stranger` |
| `budget_usd` | a number; `0` means no paid steps | `10` (from `/test-course`); `0` if the task names none |
| `fix` | `no` · `yes` (apply P0/P1 doc fixes after the report, on a branch; see §8) | `no` |
| `depth` | `walk` (type the commands) · `build` (also do §5: author a check, change it, re-run) | `build` |

State all five values at the top of the report. If the task doesn't say, use the defaults
and say so. `depth: walk` is for a quick regression pass after a doc edit; `depth: build` is
the real test and is what `/test-course` sends.

## 2. Hard rules

1. **Never spend money unless `budget_usd > 0`.** Run every command with
   `OPENROUTER_API_KEY= ANTHROPIC_API_KEY=` prefixed unless the step is paid *and* budget
   allows. Paid steps (week 1 step 3, week 2 step 1, week 6 step 3) get
   `AI_TEAM_RUN_BUDGET_USD=<remaining budget>` and are logged with their cost. Otherwise mark
   them `SKIPPED-PAID` and continue.
   Track every paid run in `$REPORT/spend.jsonl` (see §2a) and stop paid work before the
   budget would be exceeded.
2. **Never do the human part — and never use it as cover for skipping the build part.**
   Week 4 is reading thirty runs *by a human*: you must not write open-coding notes, labels or
   categories as if you were the reader, and must never write to `evals/annotations/` or
   `evals/golden/`. Test the *mechanics* only, with at most two notes that start with
   `SIMULATED:` into the scratch folder, and say so in the report.
   Week 5 step 4 and week 6 step 3 are **not** human steps. They are code, they are
   deterministic, and they are the two places the course stops being a tour. Do them (§5).
3. **Never write outside the scratch area and the report folder.** Scratch is
   `course/.work/` in the test checkout. Don't touch `output/runs/`, `workspace/`,
   `evals/traces/`, `.env`, or git history in the maintainer checkout — except what a lab step
   itself creates (e.g. a dry run adds a run folder; note it).
4. **Type what the page says.** Copy each command verbatim. If it fails, record the failure
   *before* trying anything else. Only then try the smallest fix a learner could plausibly
   find, and record that too. Never silently "correct" a command.
5. **The build work changes code.** All of it happens on one throwaway branch in the test
   checkout (`git checkout -b course-test/$RUN_ID`), runs fully, and is left there — never
   merged, never pushed. Commit after each build task so `git log --oneline` is the record of
   what you tried, and so `baseline accept` (which refuses a dirty tree) works.
6. **Time-box with `course/testing/run_step.py`, never plain `timeout`** (macOS has none, and
   killing only the shell leaves `run_demo.py` children running and spending). It runs the
   command in the learner's shell (`$SHELL`, zsh on macOS), kills the whole process group at
   the limit, and lists leftover course processes in `<log>.meta`. For a lab command that
   sets its own `--timeout N`, give `run_step.py` **N + 60** (the default 960 covers
   `--timeout 900`), so you observe whether the harness watchdog stops the run — record
   `exit=124` from the run itself vs. `timed_out=True` from `run_step.py` separately. Any leftover is a **P0**
   finding and must be killed before you continue. A hang is a finding too.

   ```bash
   python3 course/testing/run_step.py --cwd "$TEST" --timeout 960 \
     --log "$REPORT/logs/W1.S3.c1.txt" -- '<the command exactly as the page shows it>'
   ```

7. **Account for every step.** `extract_steps.py` prints the full list of step ids. Every one
   of them gets a row in the report's coverage table with a result or a reason from the closed
   list in §4a. "Ran out of time" is a reason; "seemed hard" and "no runnable blocks" are not —
   a step with no commands still has a *Predict* and an *Explain* to judge.

## 2a. Spend plan

Costs come from past runs of the smoke brief: LangGraph and CrewAI on the default DeepSeek
tier cost **pennies**; the Claude Agent SDK costs **$0.48–$0.95** a run; the `smoke-claude`
profile puts every backend on Claude, so budget ~$1 per run there.

Run the paid steps in this order, and only while `remaining ≥ projected + $0.50` (reserve):

| Order | Step | Command as written | Projected | Running total |
| --- | --- | --- | --- | --- |
| 1 | W1.S3 | one LangGraph run | ~$0.05 | ~$0.05 |
| 2 | W2.S1 | one run each: langgraph, crewai, claude-agent-sdk | ~$1.10 | ~$1.15 |
| 2b | B5 | one LangGraph run, so the corpus grows under your own check | ~$0.05 | ~$1.20 |
| 3 | W6.S3 (optional) | `run_smoke_batch.py --n 3 --backends langgraph` | pennies, ~1 h | ~$1.20 |
| 4 | W6.S3 (optional) | `run_smoke_batch.py --n 3 --team smoke-claude` (9 Claude runs) | ~$9 | **over** |

The Claude SDK backend does **not** read `AI_TEAM_RUN_BUDGET_USD` unless the fix from
2026-09-16 is in your checkout (`grep -n AI_TEAM_RUN_BUDGET_USD
src/ai_team/backends/claude_agent_sdk_backend/backend.py`); without it, a Claude run's ceiling
is the backend's own ~$18. Budget Claude runs at $1 each regardless.

Week 6 asks the learner to fix something first. Under `depth: build` you **have** made a
change — the check from B1–B3 — so week 6's before/after is real: measure with your check on
the corpus as it stands, then again after B5's fresh run, and report both with their `n`.
Under `depth: walk`, run the batches as a **baseline** and say so; you are then testing that
the commands work and that their output supports the step's *Explain* (intervals, overlap),
not that a fix worked.

Step 4 doesn't fit $10. Run it as `--n 1` (~$3) only if time allows, and record the result
as `DEVIATION-BUDGET` with the exact command you ran; do not scale up to spend what's left.
With a smaller budget, stop at the last row that fits and mark the rest `SKIPPED-PAID`
with their projected cost.

Rules for every paid command:

- Prefix `AI_TEAM_ENV=dev AI_TEAM_RUN_BUDGET_USD=1` (the labs' own cap) unless the step
  sets its own.
- After it finishes, read the actual cost from each new run's `state.json`
  (`actual_cost_usd`) or `logs/costs.jsonl`, and append one line per run:
  `{"step": "W2.S1", "backend": "claude-agent-sdk", "run_id": "...", "usd": 0.71, "source": "state.json"}`.
  If no cost was recorded, log `"usd": null` and count the **projected** cost against the
  budget — a missing cost is itself a finding (week 1's lesson).
- A run the spend guard aborts (`budget_abort`) is a result, not a test failure. If a Claude
  run hits the $1 lab cap, that is a **P1 finding** against the labs' cap, not a reason to
  raise it.
- Report total spend, spend per step, and projected vs actual in the report header.
- Week 6's live batches are optional in the lab (the replay is the default). Run them only if
  the budget and a 2-hour time box allow; otherwise `SKIPPED-PAID` with the projection.
- Before writing the report, check nothing is still running:
  `ps -axo pid,etime,command | grep -E 'run_demo|run_smoke_batch|ai-team-web' | grep -v grep`.
  Kill leftovers and record them.

## 3. Prepare

```bash
# the plan: every step and code block, with stable ids (W3.S2.c1 = week 3, step 2, block 1)
python3 course/testing/extract_steps.py
python3 course/testing/extract_steps.py --json > /tmp/course-steps.json

MODE=stranger                               # or maintainer
RUN_ID=$(date -u +%Y-%m-%d)-$MODE
n=2; while [ -e course/testing/runs/$RUN_ID ]; do RUN_ID=$(date -u +%Y-%m-%d)-$MODE-$n; n=$((n+1)); done
REPORT=course/testing/runs/$RUN_ID          # always in the ORIGINAL checkout
PREV=$(ls -d course/testing/runs/*-$MODE* 2>/dev/null | grep -v "$RUN_ID" | tail -1)  # last run to compare with
mkdir -p $REPORT/logs
```

**Stranger mode** — the real test. A new learner has no run history and no keys:

```bash
TEST=$(mktemp -d)/ai-team
git clone --quiet "$(git rev-parse --show-toplevel)" "$TEST"
cd "$TEST"            # everything below runs here
```

This clones the branch that is **checked out here**, so unpushed fixes are tested. Record the
branch and SHA. `course/README.md` → *Start* clones GitHub instead; until the course is on
`main`, treat that as the known finding **F1** (don't re-derive it) and continue in this clone.

Do **not** copy `.env`, `output/` or `workspace/` into it. (If `budget_usd > 0`, copy only
`.env`.) Then follow `course/README.md` → *Start* exactly.

**Maintainer mode** — runs in this checkout against its existing data. Faster, but it can hide
problems a stranger would hit (e.g. week 3 quietly relies on hundreds of existing runs).

Record the environment in the report: OS, `uv --version`, Python version, git SHA, mode.

**Time box.** `depth: walk` over `scope: all` is about 90 minutes of wall time. `depth: build`
adds roughly two hours, most of it in B1 and B5. If you are going to run out of time, drop
work from the **end** of the build track (B6, then B5) rather than skipping steps in weeks 1–4,
and record what you dropped as `SKIPPED-TIME`. Coverage of the course beats depth on one task.

## 4. Run each step

Work through the steps from the plan in order. For every step:

1. **Read** the whole step first, as the learner.
2. **Predict** — if the step has a *Predict* beat, write down the answer a newcomer would
   plausibly give, *before* running. This tests whether the prediction is answerable and
   whether the lesson lands.
3. **Run** each runnable block verbatim through `run_step.py` (rule 6), log to
   `$REPORT/logs/<block-id>.txt`. Exit code and wall time land in `<log>.meta`.
4. **Compare** with the step's *Observe* section and assign one result per block:

   | Result | Meaning |
   | --- | --- |
   | `MATCH` | Output has the same shape and the same conclusion |
   | `DRIFT` | Same conclusion, different numbers (run counts change — expected) |
   | `MISMATCH` | Output leads to a different conclusion than the page states |
   | `BROKEN` | Command fails, hangs, or needs something the page never mentioned |
   | `SKIPPED-PAID` / `SKIPPED-HUMAN` / `SKIPPED-SCOPE` | Not run, with reason |

5. **Check the non-command parts**: every link and image in the step resolves; each
   *Explain* claim is true for what you saw; each *Change* task is doable with what's on the
   page; the stated time and cost are realistic.
6. **Append one observation** per block (and one per non-command issue) to
   `$REPORT/observations.jsonl`. Write it **in the learner's voice, in the first person**,
   before you put on the reviewer hat:

```json
{"id": "W3.S2.c1", "result": "DRIFT", "exit": 0, "seconds": 34,
 "predicted": "I guessed the two readers would disagree by a handful of runs",
 "expected": "several backends, ~160 spans across ~330 traces",
 "actual": "1 trace (langgraph, complete), 0 spans — fresh clone has only the dry run",
 "surprised_me": "The default command reads ./workspace, not output/runs. I'd have trusted that number.",
 "still_dont_understand": "Why a trace can exist with zero spans at all — is that a bug or a shape?",
 "concept": "observability",
 "could_i_explain_it": "yes — the writer and the reader disagree about where runs live",
 "learner_confusion": "Page shows 338 runs; a new learner has 2. Nothing says why.",
 "severity": "P1", "suggestion": "Add a note: 'your counts will be tiny on a fresh clone — the shape is what matters'",
 "evidence": "logs/W3.S2.c1.txt"}
```

`predicted`, `surprised_me`, `still_dont_understand` and `could_i_explain_it` are not
decoration: they are the measurement. A step where nothing surprised you and you could
already explain it taught you nothing — say so, and score **Teaches** accordingly. A step
where you still can't explain it afterwards is either a gap in the page or a genuinely hard
idea; decide which, and say which.

Keep going after failures. A report that stops at the first break hides everything after it.

## 4a. Coverage and skip reasons

Build the coverage table from `extract_steps.py`, not from memory:

```bash
python3 course/testing/extract_steps.py --json > $REPORT/steps.json
```

Every step id gets one of these. The first three are results; the rest are skips and each
needs a one-line reason:

| Disposition | When |
| --- | --- |
| `RUN` | Every runnable block executed; prose beats judged |
| `RUN-PARTIAL` | Some blocks ran; say which didn't and why |
| `JUDGED` | Step has no runnable blocks — you still read it, predicted, and judged the Explain |
| `SKIPPED-PAID` | Budget would be exceeded. Give the projected cost |
| `SKIPPED-HUMAN` | Genuinely a human reading task (week 4 step 2 only) |
| `SKIPPED-SCOPE` | Outside the `scope` parameter |
| `SKIPPED-TIME` | Ran out of the time box. Say what remained |
| `BLOCKED` | An earlier failure made it impossible. Name the blocker |

Report **coverage = (RUN + RUN-PARTIAL + JUDGED) / total steps**, per week and overall, in the
header. Anything under 80% on a `scope: all` run needs a sentence explaining why.

## 4b. The concept ledger

The learner is here to understand agentic systems, so the report tracks ideas, not only
commands. Keep one row per concept in `$REPORT/concepts.md`, filled in as you go:

| Concept | Where the course teaches it | What I could explain afterwards | Verdict |
| --- | --- | --- | --- |
| A team of agents is mostly glue | W1.S1, W2.S2 | | taught / asserted / missing |
| Tool calls are the only thing that changes the world | W1.S2, W2.S2 | | |
| Writes are staged, not saved (draft → commit) | W2.S2 | | |
| Guardrails can fail correct work | W2.S2 | | |
| Retries are a cost multiplier, not a safety net | W1.S3, W2.S1 | | |
| Telemetry has a writer and a reader, and they disagree | W3.S1–S3 | | |
| A check that can't see anything abstains, it doesn't pass | W3.S4, W5.S3 | | |
| Failure modes are a taxonomy you build, not a list you're given | W4 | | |
| A pass rate means nothing without its corpus kind and `n` | W5.S1–S2, W6.S4 | | |
| Deterministic checks before LLM judges | W5.S3 | | |
| A fix is a claim until you measure it twice | W6.S2–S4 | | |
| Monitoring is the same eval on a cadence | W6.S5 | | |

**Verdict** is one of: **taught** (the step made me able to explain it to someone else),
**asserted** (the page says it; nothing I ran demonstrated it), **missing** (I hit the idea in
practice but no step names it). A concept marked *asserted* that the course claims as a
headline lesson is a **P1** finding.

## 5. Build track (`depth: build`)

Six tasks, in order. They are where the course stops being a tour of somebody else's system
and starts being yours. Each one ends with the **re-run matrix** (§5a) — that is the part
most people skip, and skipping it is how a broken eval ships green.

Work on the throwaway branch (§2 rule 5). Record every task in `$REPORT/build.md` with:
what I predicted, what I changed, what the numbers did, how many attempts it took, and what
the failure messages taught me. Attempts matter: a check that takes six tries because the
error message is unhelpful is a **P1** finding against week 5.

### B1 — Write the check yourself (W5.S4, ~60 min, $0)

Do **not** apply `course/solutions/week-5-check.patch` first. Type `evals/checks/mine.py` from
the page, then find the other five wiring points yourself, one `pytest` failure at a time.
The page claims *"The test suite enforces each of these, so if you skip one, `pytest` tells
you which."* That is a testable claim — **test it**:

```bash
git checkout -b course-test/$RUN_ID
# write evals/checks/mine.py only, then:
uv run pytest tests/unit/evals -q
```

Record, for each of the six wiring points, whether the failure message actually named the
missing piece or whether you had to go read the test. Then add them one at a time, re-running
`pytest tests/unit/evals -q` after each, and log the attempt count. **Only after** you are
done (or genuinely stuck for more than 20 minutes) diff your version against the solution
patch and record what you got wrong:

```bash
git diff > $REPORT/my-check.diff
git apply --check course/solutions/week-5-check.patch   # does the published solution still apply?
```

A solution patch that no longer applies to the current tree is a **P0** finding.

### B2 — Make it fail on purpose (~20 min, $0)

A check nobody has seen fail is not a check. Prove yours has teeth in two directions:

```bash
# 1. a trace it SHOULD fail: the fixture builder already makes one
uv run pytest tests/unit/evals -q -k has_spans
# 2. break the check so it can never fail (return passed() always), re-run the suite
#    -> the sensitivity test must catch it. If the suite still passes, that is a P0 repo finding.
# 3. revert the sabotage
git checkout evals/checks/mine.py
```

This is the mutation test for the eval harness itself. Record whether step 2 was caught, by
which test, and how long it took to notice. The course never asks the learner to do this —
if it was valuable, that is a **P2 suggestion** to add a *Change* beat to W5.S4.

### B3 — Adjust the eval and watch the number move (~30 min, $0)

Now change the check's *meaning*, not its wiring, and re-measure. Pick one:

- tighten it — fail a trace with fewer than **two** spans, not zero;
- loosen it — abstain (`na`) instead of failing when `status == "failed"`;
- re-aim it — fail when no span is a `tool_use`, which is the stronger version of the same idea.

Before you run anything, **predict the new numbers**: how many fixtures flip, what Tier A's
fail count becomes, what the corpus rate does. Then:

```bash
uv run python -m evals.cli run --tier A --warn-only --out course/.work/tier-a-after
diff <(head -20 course/.work/tier-a/summary.txt) <(head -20 course/.work/tier-a-after/summary.txt)
```

Record predicted vs actual. **A change you can't see in any number is the finding** — it
means the corpus has no trace that exercises the difference, which is exactly what week 5's
`FIXTURE-ONLY` vs `CORPUS` distinction is about. Say so in those words.

### B4 — Re-accept the baseline, and try to sneak a regression past it (~20 min, $0)

```bash
git commit -am "Tighten CHK-trace-has-spans"
uv run python -m evals.cli baseline accept --tier A --reason "tighten CHK-trace-has-spans" \
  --report course/.work/tier-a-after/report.json
git commit -am "Accept baseline"
```

Then make a change the gate *should* refuse (delete a passing fixture, or make a second check
fail), re-run `--tier A` **without** `--warn-only`, and record whether the gate blocked it and
what the message said. Revert. A gate that accepts a regression silently is a **P0 repo
finding**; a gate that blocks it with an unreadable message is a **P1**.

### B5 — Re-run the pipeline and see your check meet real traces (~30 min, pennies)

Fixtures are not evidence. Take the check to live data:

```bash
# $0 first: rebuild traces from whatever runs this checkout has
uv run python -m evals.cli trace backfill --workspace-root output/runs --traces-root course/.work/traces
uv run python -m evals.cli coverage liveness --traces-root course/.work/traces --out course/.work/liveness.md
grep trace-has-spans course/.work/liveness.md
```

Then, **if budget allows** (§2a), make one fresh run so the corpus grows under you, and do it
again:

```bash
AI_TEAM_ENV=dev AI_TEAM_RUN_BUDGET_USD=1 \
  uv run python scripts/run_demo.py demos/00_smoke_test --backend langgraph --skip-estimate --timeout 900
uv run python -m evals.cli trace backfill --workspace-root output/runs --traces-root course/.work/traces
uv run python -m evals.cli coverage liveness --traces-root course/.work/traces --out course/.work/liveness-after.md
```

Record `n` before and after, the rate before and after, and — the point of the exercise —
whether one more run changed the rate enough to notice. Put the two rates through week 6
step 4's interval command and say whether they overlap. They will. Say it anyway.

### B6 — Full-pipeline regression (~15 min, $0)

Last, run everything the repo runs, as a maintainer would before pushing:

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy src
uv run pytest tests/unit -q
uv run python -m evals.cli run --tier A --warn-only --out course/.work/tier-a-final
uv run pytest tests/unit/repo -q
```

Everything green means your check is a real part of the system, not a file in a folder.
Anything red that your changes caused is a finding against the course's wiring instructions.
Record the wall time of the whole loop: if "write a check" really takes 60 minutes as W5.S4
claims, say what your actual number was.

## 5a. The re-run matrix

After **every** change in §5 — and any time `fix: yes` edits a lab — re-run at three scopes
and record all three. This is the habit the course is trying to teach, so the test must
demonstrate it:

| Scope | Command | Answers |
| --- | --- | --- |
| **The step** | the lab's own block, via `run_step.py` | did the thing I just changed do what I meant? |
| **The gate** | `uv run python -m evals.cli run --tier A --warn-only` + `pytest tests/unit/evals -q` | did I break a neighbour? |
| **The pipeline** | `pytest tests/unit -q`, and a live `run_demo.py` if budget allows | does the system still run end to end? |

Log each as its own block id with a `-rerun-N` suffix (`W5.S4.c1-rerun-2`) so the report shows
the loop, not just the final state. Put before/after numbers side by side; "it passed" is not
a record, "182 fail → 183 fail, the new one is mine" is.

If a re-run at a wider scope fails because of a change you made at a narrower one, that is the
most valuable finding in the report. Write it up in full: what you changed, what broke, how
long before you noticed, and whether any step in the course would have told you.

## 6. Assess

After running, score each week 1–5 on each dimension. Use this rubric, with one sentence of evidence per score.

| Dimension | 5 means | 1 means |
| --- | --- | --- |
| **Runs** | Every command works as written | Learner is stuck |
| **Accurate** | Observe/Explain match reality (drift is fine) | Page teaches something false |
| **Clear** | A newcomer knows what to do and why at every step | Needs repo knowledge the page doesn't give |
| **Teaches** | The Predict → Observe gap makes the point land | Steps are busywork; the point is only asserted |
| **Honest** | Every number carries its kind/`n`/date; limits stated | Overclaims, or unlabeled rates |
| **Fits budget** | Stated time and cost are right (±50%) | Far off |
| **Buildable** | The generative steps (W5.S4, W6.S1–S3) can be done from the page alone | Only the solution patch works |
| **Feeds back** | Changing something produces a number that visibly moves | Nothing the learner does shows up anywhere |

`Buildable` and `Feeds back` are scored only for weeks that have build work (5 and 6) and only
when `depth: build`. Mark them `—` elsewhere.

Also answer, in plain sentences:

- Could a stranger finish this week alone? If not, at which step do they give up?
- What is the single most confusing moment?
- Which lesson landed best, and which one is only asserted?
- Does the course still serve its purpose (`campaign-v2/README.md` → *Purpose*)?
- **After doing the build track: could you now add a check to a system you didn't write?**
  That is the course's real promise. Answer yes or no and say what would have to change.
- **Which concept did you only understand after something went wrong?** Those are the
  course's best candidates for a deliberate failure exercise.

## 7. Write the report

Copy `course/testing/report-template.md` to `$REPORT/report.md` and fill it in. The rules
for feedback:

- **Severity:** `P0` blocks the learner · `P1` misleads or teaches something wrong ·
  `P2` friction or confusion · `P3` polish.
- **Every finding has evidence** (a log path, a line in a lab, a number) **and a concrete
  suggestion** — the replacement text, the command, or the diff. "Could be clearer" is not a
  finding.
- **Separate course problems from repo problems.** A bug in `evals/` that a lab exposes is a
  repo finding; say which spec or file owns it.
- **Don't pad.** If a week is fine, say so in one line.
- Include the **coverage table** (§4a), the **concept ledger** (§4b) and, for `depth: build`,
  a **Build track** section summarising B1–B6: attempts per wiring point, predicted vs actual
  numbers, what the mutation test caught, and the wall time of the whole write-a-check loop
  against the page's claimed 60 minutes.
- End with **Top 5 improvements**, ordered by learner impact per hour of work.

Then print the path to the report and the Top 5 in chat.

## 8. If `fix: yes`

Only after the report is written:

```bash
git checkout -b course-fixes/$RUN_ID       # in the ORIGINAL checkout
```

Apply P0 and P1 **documentation** fixes to `course/` only. Code bugs go in the report, not in
this branch. Re-run the affected steps, add `"fixed": true` plus the re-run result to their
observations, run `python3 course/testing/extract_steps.py` and the link check below, and
commit with a message that lists the finding ids. Never push.

```bash
python3 - <<'PY'
import re, os, glob
bad = []
for f in glob.glob("course/*.md"):
    for m in re.finditer(r"\]\(([^)#\s]+)", open(f).read()):
        u = m.group(1)
        if not u.startswith("http") and not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), u))):
            bad.append((f, u))
print(bad or "links ok")
PY
```

## 8a. Compare with the previous run

If `$PREV` exists, add a **Since last run** section to the report: for every block id in both
`observations.jsonl` files, list result changes (e.g. `W1.S3.c1 BROKEN → MATCH`), findings from
`$PREV/report.md`'s resolution table that are marked fixed but still reproduce (**regressions —
P0**), and new findings. Spend and wall time side by side.

## 9. What changed since the last run (target these)

As of `3f5f585` on `feat/course-v2`, three commits landed after `-stranger-4`. Everything
below is untested by a stranger; the rest of the course has now been walked five times.

**Week 4 step 1 was rewritten and is the newest, least-tested text in the course.** It gained
an Observe block that opens the sample manifest and counts spans per trace, and a Change beat
that re-samples with a new `--min-spans` flag. The commands were verified verbatim against a
355-trace corpus. **They have never been run on a fresh clone**, where the corpus is about
four traces and several of them are dry runs. Specifically worth finding out:

- does the inline `python3 -c` block produce something sensible at n=4, or something that
  reads like a bug?
- the page quotes this repo's numbers (355 traces, 24 of 30 empty, 257/95/3). At n=4 those
  numbers will look nothing like the learner's. Is the page clear that they are *this repo's*
  corpus, or does it read as a promise about theirs?
- the Change beat sends a learner with a thin corpus off to `run_smoke_batch.py`. Is that an
  honest off-ramp or a dead end mid-lab?

**Week 5's first pytest changed.** `test_check_discovery.py` moved from `tests/unit/repo/`
into `tests/unit/evals/`, so `uv run pytest tests/unit/evals -q` with only `mine.py` written
should now go red and name the file. Last run it was 423 green. Re-run B1 from scratch and
confirm the first command talks.

**The Tier A gate can now fail** (`evals/fixture_contract.py`). B4 confirmed the headline —
delete a pass fixture, exit 1 — but nobody has walked the *whole* of W5.S4 with the new gate
in place. A new check with no fixtures yet should now fail completeness; make sure the page's
command order still produces a green gate at the end, and that a learner who runs Tier A
mid-wiring gets an error they can act on rather than a wall.

**The solution patch was reformatted** so `ruff format --check` passes on the learner's
builder. `git apply --check` was verified; applying it for real inside the lab was not.

Suggested scope if time is short: `week-4,week-5`, `depth: build`, `mode: stranger`. The $0
spine in weeks 1–3 and 6 has been stable across three runs.

## 10. Known context (don't re-report as new)

- Counts in *Observe* blocks come from the maintainer checkout on 2026-09-16 and will drift.
  Report `DRIFT`, not `MISMATCH`, unless the conclusion changes.
- `failed` traces include runs that never recorded a status (each carries a warning). That's a
  known open issue (journal 2026-09-16 §5), not a new finding — unless a lab misstates it.
- Week 4 step 2 depends on human reading by design. Week 6's *live* batches depend on real
  spend by design; its replay path does not.
- A fresh clone has almost no runs, so every corpus number in weeks 3–6 will be tiny. That is
  `DRIFT`, and the interesting question is whether the *shape* of the lesson survives at n=1.
- The build track deliberately leaves a branch behind in the test checkout. That is not a
  leftover to report.
- **F1** (Start clones GitHub `main`, which has no `course/`) is open and known. The branch is
  not pushed, so a stranger still cannot run the real Start command — clone locally as §3 says
  and do not re-derive it.
- **22 uniqueness warnings** from the Tier A gate are expected and are an open decision about
  deleting duplicate fixture files, not a new finding.
- **R13**: `trace backfill` mints a new trace id per invocation, so re-running it inflates `n`
  with duplicates of the same run. Known, unfixed. Wipe the traces root between before/after.
- **R10**: LangGraph wall time on the smoke brief has been 226 s, 518 s and a 900 s timeout on
  the same brief. Variance is the finding, not a regression — record the number and move on.
