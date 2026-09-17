# Course test report — <RUN_ID>

| | |
| --- | --- |
| **Scope / mode / budget / fix / depth** | all · stranger · $10 · no · build |
| **Git SHA** | |
| **Environment** | OS · uv · Python |
| **Tester** | Cursor agent (model) · date |
| **Spend** | $0.00 of $<budget> · per step: W1 $ · W2 $ · W6 $ · projected vs actual |
| **Wall time** | total · of which build track |
| **Coverage** | <RUN+RUN-PARTIAL+JUDGED>/<total> steps = <n>% · per week below |

## Verdict

<Three sentences: can a stranger finish the course alone? where do they get stuck? is it ready to share?>

## Scorecard

| Week | Runs | Accurate | Clear | Teaches | Honest | Fits budget | Stranger can finish alone? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · Build | | | | | | | |
| 2 · Fail | | | | | | | |
| 3 · Observe | | | | | | | |
| 4 · Read | | | | | | | |
| 5 · Evaluate | | | | | | | |
| 6 · Improve | | | | | | | |

`Buildable` and `Feeds back` (weeks 5–6, `depth: build` only):

| Week | Buildable | Feeds back |
| --- | --- | --- |
| 5 · Evaluate | | |
| 6 · Improve | | |

One line of evidence per score goes in the week sections below.

## Coverage

| Week | Steps | RUN | RUN-PARTIAL | JUDGED | Skipped (reason) | % |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |
| 6 | | | | | | |
| **All** | | | | | | |

Every skip names its reason from the closed list in the skill, §4a.

## Step results

| Step | Block | Result | Exit | Time | Note |
| --- | --- | --- | --- | --- | --- |
| W1.S2 | c1 | MATCH | 0 | 5 s | |

Totals: MATCH · DRIFT · MISMATCH · BROKEN · SKIPPED

## Build track

<`depth: build` only. Delete this section for a walk-through.>

| Task | What I predicted | What I changed | What the numbers did | Attempts | Time |
| --- | --- | --- | --- | --- | --- |
| B1 write the check | | | | | |
| B2 make it fail | | | | | |
| B3 adjust the eval | | | | | |
| B4 baseline + regression | | | | | |
| B5 live traces | | | | | |
| B6 full pipeline | | | | | |

**Wiring points (B1)** — did `pytest` name the missing piece, or did I have to read the test?

| # | File | Message named it? | Attempts |
| --- | --- | --- | --- |
| 1 | `evals/checks/registry.py` | | |
| 2 | `evals/coverage.py` | | |
| 3 | `tests/unit/evals/trace_fixtures.py` | | |
| 4 | `tests/unit/evals/test_check_sensitivity.py` | | |
| 5 | `evals/fixtures/traces/` | | |
| 6 | `evals/baselines/tier_a.json` | | |

- Did the mutation test (B2) catch a check that can never fail? Which test, how fast?
- Did the gate (B4) block a deliberate regression? Was the message readable?
- Re-runs where a wider scope caught something a narrower one missed:
- Week 5 claims 60 minutes for "write your own check". Actual:

## Concept ledger

| Concept | Verdict | What I could explain afterwards |
| --- | --- | --- |

Verdict: **taught** · **asserted** · **missing**. A headline lesson marked *asserted* is a P1.

## Findings

| ID | Sev | Where | What happened | Suggested change | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | P0 | `course/week-…md:LINE` | | exact replacement text or command | `logs/…` |

Severity: **P0** blocks the learner · **P1** misleads · **P2** friction · **P3** polish.

### Repo findings (not course text)

| ID | Where | What | Owner (spec / file) |
| --- | --- | --- | --- |

## Week notes

### Week 1 · Build
- Predictions a newcomer would make, and whether the step corrected them:
- Most confusing moment:
- Scores evidence:

<!-- repeat for weeks 2–6 -->

## Learner questions

- Could a stranger finish alone? Where would they give up?
- Single most confusing moment in the course:
- Lesson that landed best / lesson that is only asserted:
- Does the course still serve the purpose in `campaign-v2/README.md`?
- After the build track: could you now add a check to a system you didn't write? What would
  have to change for the answer to be yes?
- Which concept did you only understand after something went wrong?

## Top 5 improvements

Ordered by learner impact per hour of work.

1.
2.
3.
4.
5.

## Appendix

- Observations: `observations.jsonl`
- Steps and ids: `steps.json`
- Build log: `build.md` · check diff: `my-check.diff`
- Concept ledger: `concepts.md`
- Logs: `logs/` (re-runs carry a `-rerun-N` suffix)
- Spend: `spend.jsonl`
- Build branch left in the test checkout:
- Steps not run, and why:
