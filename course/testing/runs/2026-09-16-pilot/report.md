# Course test report — 2026-09-16-pilot

| | |
| --- | --- |
| **Scope / mode / budget / fix** | W1.S2, W3.S1–S4, W4.S1 · stranger · $0 · yes (docs only) |
| **Git SHA** | `d266025` |
| **Environment** | Linux VM · uv 0.12.13 · Python 3.13 |
| **Tester** | Claude (pilot of the `course-test` procedure) · 2026-09-16 |
| **Spend** | $0.00 |

## Verdict

A stranger can do week 1 and the first half of week 3 on a fresh clone at $0, and the core
week 3 lesson (wrong folder → nothing; right folder → correct labels) still lands. The
"two readers disagree" lesson is weak with one run, and **week 4 cannot be done by a
stranger** without real runs or an existing history. The course needs a small committed
teaching corpus before it is shared widely.

## Step results

| Step | Result | Note |
| --- | --- | --- |
| W1.S2.c1 | MATCH | 5 s, $0 |
| W1.S2.c2 | MATCH | empty `logs/`, phase `complete` |
| W3.S1.c1 | MISMATCH → fixed | page showed pre-fix `crewai` |
| W3.S2.c1 | DRIFT | 1 trace, correct labels, 0 spans |
| W3.S3.c1 | DRIFT | readers barely disagree with n=1 |
| W3.S4.c1 | DRIFT | 0 live / 17 blind over 1 trace |
| W4.S1 | BROKEN | needs ≥30 real runs |

## Findings

| ID | Sev | Where | What happened | Suggested change | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | P0 | `week-4-read.md` Step 1 | A fresh clone has 1 trace; 30 can't be sampled; dry runs are identical | Say so up front; ship a teaching corpus | note added; corpus open |
| F2 | P1 | `week-3-observe.md` Step 1 | Observe block still showed pre-fix `crewai` | Show `unknown … failed` | fixed |
| F3 | P1 | `week-3-observe.md` intro | Counts come from a 340-run checkout; strangers see n=1 with no explanation | "Fresh clone?" note: compare shape, not counts | fixed |
| F4 | P1 | `week-3-observe.md` Step 3 | With one run the two readers barely disagree, so the lesson is only asserted | Commit a snapshot of both readers' output on the maintainer corpus, or the teaching corpus | open |
| F5 | P2 | `week-3-observe.md` Step 1 | Predict assumed "hundreds of runs" | Reword | fixed |

### Repo findings

| ID | Where | What | Owner |
| --- | --- | --- | --- |
| R1 | `course/` + `evals/` | No committed teaching corpus, so weeks 3–4 depend on local history | `.kiro/specs/eval-testbed/` Phase 1 |

## Top 5 improvements

1. Build the committed, redacted teaching corpus (eval-testbed Phase 1) — unblocks week 4 for strangers and makes week 3's numbers reproducible.
2. Until then, commit a dated snapshot of week 3's maintainer outputs (`index stats`, `minieval stats`, `liveness`) so strangers can compare against real files, not prose.
3. Run the full `course-test` in stranger mode with `budget_usd: 3` to cover the paid steps.
4. Add a Predict beat to W3.S5 and an Explain beat to W2.S1 (flagged by `extract_steps.py`).
5. Re-run this test after every change to `evals/trace/` — the W3.S1 regression shows lab text drifts silently when the tool changes.
