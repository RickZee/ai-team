---
name: course-test
description: >-
  Walk through the course in course/ as a learner would, run every step, compare
  what happens with what the lab says, and write a report with observations and
  prioritised, concrete improvements. Use when asked to test, validate, dry-run,
  QA or review the course ("Agents That Actually Work"), or a single week of it.
---

# Test the course (`course/`)

You are two people at once:

- **The learner** — follows `course/` literally, top to bottom, knows nothing else about this
  repo, and types exactly what the page says. If the page doesn't say it, the learner doesn't
  know it.
- **The reviewer** — a QA lead who writes down what happened, compares it with what the page
  promised, and judges whether each step teaches what it claims to.

Your output is a **report**, not a fixed course. Do not edit `course/` unless the task says
`fix` (see §7).

---

## 1. Read the task, set four parameters

| Parameter | Values | Default |
| --- | --- | --- |
| `scope` | `all`, `week-N`, or a step id like `W3.S2` | `all` |
| `mode` | `stranger` (fresh clone, no data, no keys) · `maintainer` (this checkout, its data) | `stranger` |
| `budget_usd` | a number; `0` means no paid steps | `10` (from `/test-course`); `0` if the task names none |
| `fix` | `no` · `yes` (apply P0/P1 doc fixes after the report, on a branch) | `no` |

State the four values at the top of the report. If the task doesn't say, use the defaults
and say so.

## 2. Hard rules

1. **Never spend money unless `budget_usd > 0`.** Run every command with
   `OPENROUTER_API_KEY= ANTHROPIC_API_KEY=` prefixed unless the step is paid *and* budget
   allows. Paid steps (week 1 step 3, week 2 step 1, week 6 step 3) get
   `AI_TEAM_RUN_BUDGET_USD=<remaining budget>` and are logged with their cost. Otherwise mark
   them `SKIPPED-PAID` and continue.
   Track every paid run in `$REPORT/spend.jsonl` (see §2a) and stop paid work before the
   budget would be exceeded.
2. **Never do the human part.** Week 4 is reading thirty runs *by a human*. You must not
   write open-coding notes, labels or categories as if you were the reader, and must never
   write to `evals/annotations/` or `evals/golden/`. Test the *mechanics* only, with at most
   two notes that start with `SIMULATED:` into the scratch folder, and say so in the report.
3. **Never write outside the scratch area and the report folder.** Scratch is
   `course/.work/` in the test checkout. Don't touch `output/runs/`, `workspace/`,
   `evals/traces/`, `.env`, or git history in the maintainer checkout — except what a lab step
   itself creates (e.g. a dry run adds a run folder; note it).
4. **Type what the page says.** Copy each command verbatim. If it fails, record the failure
   *before* trying anything else. Only then try the smallest fix a learner could plausibly
   find, and record that too. Never silently "correct" a command.
5. **Week 5 step 4 changes code.** Do it on a throwaway branch in the test checkout
   (`git checkout -b course-test/w5`), run it fully, then leave it there — never merge it.
6. **Time-box with `course/testing/run_step.py`, never plain `timeout`** (macOS has none, and
   killing only the shell leaves `run_demo.py` children running and spending). It runs the
   command in the learner's shell (`$SHELL`, zsh on macOS), kills the whole process group at
   the limit, and lists leftover course processes in `<log>.meta`. Any leftover is a **P0**
   finding and must be killed before you continue. A hang is a finding too.

   ```bash
   python3 course/testing/run_step.py --cwd "$TEST" --timeout 900 \
     --log "$REPORT/logs/W1.S3.c1.txt" -- '<the command exactly as the page shows it>'
   ```

## 2a. Spend plan

Costs come from past runs of the smoke brief: LangGraph and CrewAI on the default DeepSeek
tier cost **pennies**; the Claude Agent SDK costs **$0.48–$0.95** a run; the `smoke-claude`
profile puts every backend on Claude, so budget ~$1 per run there.

Run the paid steps in this order, and only while `remaining ≥ projected + $0.50` (reserve):

| Order | Step | Command as written | Projected | Running total |
| --- | --- | --- | --- | --- |
| 1 | W1.S3 | one LangGraph run | ~$0.05 | ~$0.05 |
| 2 | W2.S1 | one run each: langgraph, crewai, claude-agent-sdk | ~$1.10 | ~$1.15 |
| 3 | W6.S3 (optional) | `run_smoke_batch.py --n 3 --backends langgraph` | pennies, ~1 h | ~$1.20 |
| 4 | W6.S3 (optional) | `run_smoke_batch.py --n 3 --team smoke-claude` (9 Claude runs) | ~$9 | **over** |

The Claude SDK backend does **not** read `AI_TEAM_RUN_BUDGET_USD` unless the fix from
2026-09-16 is in your checkout (`grep -n AI_TEAM_RUN_BUDGET_USD
src/ai_team/backends/claude_agent_sdk_backend/backend.py`); without it, a Claude run's ceiling
is the backend's own ~$18. Budget Claude runs at $1 each regardless.

Week 6 asks the learner to fix something first. You don't change system code, so run the
batches as a **baseline** and say so; you're testing that the commands work and that their
output supports the step's *Explain* (intervals, overlap), not that a fix worked.

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

RUN_ID=$(date -u +%Y-%m-%d)-<mode>          # e.g. 2026-09-20-stranger
REPORT=course/testing/runs/$RUN_ID          # always in the ORIGINAL checkout
mkdir -p $REPORT/logs
```

**Stranger mode** — the real test. A new learner has no run history and no keys:

```bash
TEST=$(mktemp -d)/ai-team
git clone --quiet "$(git rev-parse --show-toplevel)" "$TEST"
cd "$TEST"            # everything below runs here
```

Do **not** copy `.env`, `output/` or `workspace/` into it. (If `budget_usd > 0`, copy only
`.env`.) Then follow `course/README.md` → *Start* exactly.

**Maintainer mode** — runs in this checkout against its existing data. Faster, but it can hide
problems a stranger would hit (e.g. week 3 quietly relies on hundreds of existing runs).

Record the environment in the report: OS, `uv --version`, Python version, git SHA, mode.

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
   `$REPORT/observations.jsonl`:

```json
{"id": "W3.S2.c1", "result": "DRIFT", "exit": 0, "seconds": 34,
 "expected": "several backends, ~160 spans across ~330 traces", "actual": "1 trace (langgraph, complete), 0 spans — fresh clone has only the dry run",
 "learner_confusion": "Page shows 338 runs; a new learner has 2. Nothing says why.",
 "severity": "P1", "suggestion": "Add a note: 'your counts will be tiny on a fresh clone — the shape is what matters'",
 "evidence": "logs/W3.S2.c1.txt"}
```

Keep going after failures. A report that stops at the first break hides everything after it.

## 5. Assess

After running, score each week 1–5 on each dimension. Use this rubric, with one sentence of evidence per score.

| Dimension | 5 means | 1 means |
| --- | --- | --- |
| **Runs** | Every command works as written | Learner is stuck |
| **Accurate** | Observe/Explain match reality (drift is fine) | Page teaches something false |
| **Clear** | A newcomer knows what to do and why at every step | Needs repo knowledge the page doesn't give |
| **Teaches** | The Predict → Observe gap makes the point land | Steps are busywork; the point is only asserted |
| **Honest** | Every number carries its kind/`n`/date; limits stated | Overclaims, or unlabeled rates |
| **Fits budget** | Stated time and cost are right (±50%) | Far off |

Also answer, in plain sentences:

- Could a stranger finish this week alone? If not, at which step do they give up?
- What is the single most confusing moment?
- Which lesson landed best, and which one is only asserted?
- Does the course still serve its purpose (`campaign-v2/README.md` → *Purpose*)?

## 6. Write the report

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
- End with **Top 5 improvements**, ordered by learner impact per hour of work.

Then print the path to the report and the Top 5 in chat.

## 7. If `fix: yes`

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

## 8. Known context (don't re-report as new)

- Counts in *Observe* blocks come from the maintainer checkout on 2026-09-16 and will drift.
  Report `DRIFT`, not `MISMATCH`, unless the conclusion changes.
- `failed` traces include runs that never recorded a status (each carries a warning). That's a
  known open issue (journal 2026-09-16 §5), not a new finding — unless a lab misstates it.
- Week 4 and week 6 depend on human work and real spend by design.
