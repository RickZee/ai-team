# Course test report — 2026-09-18-stranger

| | |
| --- | --- |
| **Scope / mode / budget / fix / depth** | **week-4,week-5** · stranger · **$10** · no · **build** (defaults from `/test-course`; skill §9) |
| **Git SHA** | `2cb0a45` on `feat/course-v2` (after `3f5f585` `--min-spans`, `944981b` discovery moved into evals, `3c6cee5` fixture-contract gate) |
| **Environment** | Darwin 27.0.0 · uv 0.10.2 · Python 3.12.7 |
| **Tester** | Cursor agent (Grok 4.6) · 2026-09-18 |
| **Spend** | **$0.022 of $10**. Per step: B5 LangGraph watchdog **$0.022245**. `run_smoke_batch --n 10` not run (~1 h). |
| **Wall time** | ~90 min including four $0 dry runs, B1–B4, and B5's 15 min timeout |
| **Coverage** | **in-scope 7/7 = 100%** (RUN + RUN-PARTIAL) · **overall 7/24 = 29%** (W1–W3 and W6 SKIPPED-SCOPE) |
| **Previous run** | `course/testing/runs/2026-09-17-stranger-4` (SHA `3c6cee5`, scope week-5,week-6) |

## Verdict

Week 5's first pytest now talks: `mine.py` only is **1 failed, 429 passed**, and the message names the import. The gate still fails completeness without fixtures and still fails when a pass fixture is deleted. Ruff on the builder is green. Week 4's new Observe block does **not crash at n=0 or n=4**, and the page clearly dates 355/24/30 as this repo — but `sorted(glob)[-1]` is alphabetical, so after two samples it prints `empty: 0 of 0` for a sample that was actually `4 of 4`. `--min-spans 1` is an honest diagnosis (`n_eligible=0`); `run_smoke_batch --n 10` is an hour, not a dead command. Start still clones GitHub `main` (**F1**).

## Scorecard

| Week | Runs | Accurate | Clear | Teaches | Honest | Fits budget | Stranger can finish alone? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · Build | — | — | — | — | — | — | SKIPPED-SCOPE |
| 2 · Fail | — | — | — | — | — | — | SKIPPED-SCOPE |
| 3 · Observe | — | — | — | — | — | — | SKIPPED-SCOPE |
| 4 · Read | 4 | 5 | 3 | 5 | 5 | 4 | Mechanics yes; thirty human reads no; readable corpus no |
| 5 · Evaluate | 5 | 5 | 5 | 5 | 5 | 5 | Yes without the patch |
| 6 · Improve | — | — | — | — | — | — | SKIPPED-SCOPE |

`Buildable` and `Feeds back` (weeks 5–6, `depth: build` only):

| Week | Buildable | Feeds back |
| --- | --- | --- |
| 5 · Evaluate | 5 | 5 |
| 6 · Improve | — | — |

Week 4 Clear is 3 because the inspect one-liner and the bundle `SAMPLE=` line can point at different files, and after `--min-spans` the newest sample is empty so the workbench bundle is `bundled: 0`. Week 4 Fits budget is 4: the step claims 10 min; the honest off-ramp is ~1 h. Week 5 Clear is 5 because the first pytest is the discovery test.

## Coverage

| Week | Steps | RUN | RUN-PARTIAL | JUDGED | Skipped (reason) | % |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 0 | 0 | 0 | all SKIPPED-SCOPE | 0 |
| 2 | 4 | 0 | 0 | 0 | all SKIPPED-SCOPE | 0 |
| 3 | 5 | 0 | 0 | 0 | all SKIPPED-SCOPE | 0 |
| 4 | 3 | 2 | 1 | 0 | S2 human reads SKIPPED-HUMAN (command still run) | 100 |
| 5 | 4 | 4 | 0 | 0 | — | 100 |
| 6 | 5 | 0 | 0 | 0 | all SKIPPED-SCOPE | 0 |
| **In-scope** | **7** | **6** | **1** | **0** | | **100** |
| **All** | **24** | **6** | **1** | **0** | W1–W3, W6 SKIPPED-SCOPE | **29** |

Under 80% overall because this was a scoped re-test. In-scope coverage is 100%. Four $0 dry runs were a DEVIATION-SCOPE so W4.S1 could be judged at n≈4 (skill §9); the page assumes week 3's corpus.

## Step results

| Step | Block | Result | Exit | Time | Note |
| --- | --- | --- | --- | --- | --- |
| W4.S1 | c1 empty | DRIFT | 0 | 0.9 s | n_selected=0 / n_corpus=0 |
| W4.S1 | c2 empty | MATCH | 0 | 0 s | `empty: 0 of 0` — no crash |
| W4.S1 | c1 n=4 | DRIFT | 0 | 0.2 s | n_selected=4 / n_corpus=4 |
| W4.S1 | c2 n=4 as written | **MISMATCH** | 0 | 0 s | alpha sort reopened the empty sample: `0 of 0` |
| W4.S1 | c2 on 20163a | MATCH | — | — | `[0,0,0,0]` empty **4 of 4** |
| W4.S1 | c3 `--min-spans 1` | MATCH | 0 | 0.2 s | n_eligible=0 n_corpus=4 |
| W4.S1 | c4 bundle | DRIFT | 0 | 0.5 s | `ls -t` → empty min-spans sample; **bundled: 0** |
| W4.S1 | `--n 10` | SKIPPED-TIME | — | — | ~1 h; W1.S3 off-ramp was B5 |
| W4.S2 | c1 | MATCH | 0 | 0.1 s | mechanics; human SKIPPED-HUMAN |
| W4.S3 | c1 | MATCH | 0 | 0.3 s | no Downloads export; empty taxonomy |
| W5.S1 | c1 | MATCH | 0 | 1.6 s | 182 fail; 22 uniqueness warns |
| W5.S2 | c1 | DRIFT | 0 | 0 s | 95 fixtures |
| W5.S3 | c1 | MATCH | 0 | 0 s | spend.py |
| W5.S4 | attempt-0 evals | MATCH | 1 | 11.0 s | **names mine** (was 423 green) |
| W5.S4 | dump+pytest | MATCH | 0 | 9.4 s | 434 passed; 228 fail Tier A |
| W5.S4 | B4 delete pass | MATCH | 1 | 0.9 s | completeness exit 1 |
| W5.S4 | B5 live | MATCH | 124 | 900.3 s | watchdog; $0.022; 1 na after |

Totals (in-scope): **MATCH 12 · DRIFT 4 · MISMATCH 1 · SKIPPED-TIME 1 · SKIPPED-HUMAN 1**.

## W4.S1 — the three §9 questions

1. **Does `python3 -c` produce something sensible at n=4?** On the n=4 sample file: `spans per trace: [0, 0, 0, 0]` / `empty: 4 of 4`. That is the lesson, not a crash. As written, `sorted(glob)[-1]` is alphabetical, so after an earlier empty sample it prints `0 of 0` instead. Later in the same step, `SAMPLE=$(ls -t …)` uses mtime.

2. **Are 355 / 24 of 30 empty / 257/95/3 a promise about the learner's corpus?** No. The Explain names *"On 2026-09-18 this repo's own corpus — 355 real traces"*. The callout at the top of the step says a fresh clone has neither 30 runs nor 30 informative ones. Honest.

3. **Is `run_smoke_batch.py --n 10` an honest off-ramp?** `--min-spans 1` with four dry runs: `n_eligible=0`. That is a corpus problem, as the page says. The first listed off-ramp is week 1 step 3; that command runs (B5: 15 min then watchdog). `--n 10` is pennies and **about an hour**, which the page already says. Not a dead end; not a 10-minute step either. Not executed this run (SKIPPED-TIME).

## Build track

| Task | What I predicted | What I changed | What the numbers did | Attempts | Time |
| --- | --- | --- | --- | --- | --- |
| B1 write the check | evals pytest still green | `mine.py` then wiring | **1 fail names mine** → completeness → 434 pass / 228 fail | 4 | ~20 min |
| B2 make it fail | sabotage caught | always-`passed()` | 4 failed | 2 | ~5 min |
| B3 adjust the eval | 228→257 | require ≥2 spans | **exact**; reverted | 1 | ~3 min |
| B4 baseline + regression | still exit 1 | rm pass json | **exit 1**, readable | 1 | ~2 min |
| B5 live traces | pennies or timeout | LangGraph after unset | watchdog 900 s $0.022; 0/4 then +1 na | 1 | 15 min paid |
| B6 full pipeline | ruff red last time | format check | **green**; unit 1692 passed | 1 | ~1.5 min |

**Wiring points (B1)** — did `pytest` name the missing piece?

| # | File | Message named it? | Attempts |
| --- | --- | --- | --- |
| 1 | `evals/checks/registry.py` | **Yes — first command, `tests/unit/evals`.** | 1 |
| 2 | `evals/coverage.py` | Yes — `missing: ['CHK-trace-has-spans']` | 1 |
| 3 | `tests/unit/evals/trace_fixtures.py` | Yes — ALL_CHECK_IDS | 1 |
| 4 | `tests/unit/evals/test_check_sensitivity.py` | (reached after builder; mutation defined before dump) | 1 |
| 5 | `evals/fixtures/traces/` | **Yes, completeness + committed-fixture tests** | 1 |
| 6 | `evals/baselines/tier_a.json` | N/A until `baseline accept` | 1 |

- Mutation test (B2) catch a never-fail check? **Yes**, four tests, ~6 s.
- Gate (B4) block a deliberate regression? **Yes.** Readable completeness line.
- Week 5 claims 60 minutes. Actual B1–B4 ~25 min.

Full narrative: `build.md`. Diff: `my-check.diff`.

## Concept ledger

See `concepts.md`. This pass: sampler vs readable pool **taught**; taxonomy **asserted** (no thirty notes, and at n=4 empty there is nothing to read).

## Findings

| ID | Sev | Where | What happened | Suggested change | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | P0 | `course/README.md` Start | `origin/main` has no `course/`. Known, not re-derived. | Merge `course/` to `main` or change Start. | (known) |
| F28 | P1 | `course/week-4-read.md:62–70` | Observe uses `sorted(glob.glob(...))[-1]` (alphabetical). After the empty sample (`e3b0c442`) and the n=4 sample (`20163a`), the one-liner prints `empty: 0 of 0` for a selection of 4. The n=4 file is `empty: 4 of 4`. Same step's bundle line uses `ls -t`. | Open the newest file by mtime, or print the path. Same helper as `SAMPLE=$(ls -t …)`. | `logs/W4.S1.c2-rerun-1.txt` |
| F29 | P2 | `course/week-4-read.md:101` | After `--min-spans 1` selects 0, `SAMPLE=$(ls -t …)` is that empty sample. Bundle **bundled: 0**. `--min-spans` also reuses sample id `e3b0c442` and overwrites the first empty sample file. | If `n_selected==0`, do not clobber the previous sample; tell the learner which id to bundle. | `logs/W4.S1.c4.txt` |

**Closed since stranger-4**

| ID | Was | Now |
| --- | --- | --- |
| F24 | first `pytest tests/unit/evals` with `mine.py` only = 423 passed | **1 failed, 429 passed**, names `mine` |
| F27 | `ruff format --check` would reformat `trace_fixtures.py` | **5 files already formatted** |

**Not new:** uniqueness 22; R13 (wiped traces this time); R10 (B5 timeout 900 s; last B5 complete 449 s); F1.

### Repo findings (not course text)

| ID | Where | What | Owner |
| --- | --- | --- | --- |
| R10 | LangGraph | This B5 watchdog 900 s / $0.022 / no `state.json`. Last B5 complete 448.7 s. Variance is the data. | langgraph backend |
| R13 | `trace backfill` | Known. Wiped traces-root between before/after this run. | evals/cli |

## Week notes

### Week 4 · Read
- Predictions: I thought sample would error on an empty folder. It prints zeros. I thought the new one-liner would crash at n=4. It doesn't — unless it opens the wrong file.
- Most confusing moment: watching `n_selected=4` then `empty: 0 of 0`.
- Scores evidence: 355 numbers are labelled as this repo. `--min-spans` is the right question. Taxonomy is asserted; at n=4 empty I could not have read thirty informative runs even if I wanted to.

### Week 5 · Evaluate
- Predictions: first pytest still green. Wrong. B4 still exit 1. Right.
- Most confusing moment: none in the wiring this time — the first failure was the table row.
- Scores evidence: 182 / 0.479 snapshot exact. 228 with my check. Completeness gate MATCH. Ruff MATCH.

## Learner questions

- Could a stranger finish alone? Week 5 on this branch: yes. Week 4 mechanics: yes. Week 4 as intended (thirty informative reads): not from a fresh clone without making runs. Not from GitHub `main` (F1).
- Single most confusing moment: the Observe one-liner lying after a second sample.
- Lesson that landed best: a sampler will always hand you thirty; `--min-spans` asks whether thirty readable runs exist. Lesson only asserted: open-coding thirty traces.
- Purpose (`course/README.md`): weeks 4–5 on this branch do what they claim, with F28 in the way of the new Observe block.
- After the build track: **yes, I could add a check to a system I did not write.** The first pytest starts the conversation.
- Concept I only understood after something went wrong: alphabetical `[-1]` is not "the one I just made". Also: a watchdog kill is `na` on the check I wrote, not a fail.

## Since last run

Previous: `course/testing/runs/2026-09-17-stranger-4` (`3c6cee5`, week-5/week-6).

| Block | Was (`3c6cee5`) | Now (`2cb0a45`) |
| --- | --- | --- |
| W5.S4 mine.py only + evals pytest | MISMATCH 423 passed (F24) | **MATCH exit 1, names mine** |
| B4 delete pass fixture | MATCH exit 1 | MATCH exit 1 (holds) |
| B6 ruff format | would reformat builder (F27) | **already formatted** |
| B5 LangGraph | complete 448.7 s $0.025 | **timeout 900 s $0.022** (R10) |
| W4.S1 Observe one-liner | (old text; not this question) | **MISMATCH** after two samples; MATCH on the n=4 file |
| W4.S1 `--min-spans` | (did not exist) | MATCH n_eligible=0 |

Spend / wall: stranger-4 **$0.025 / ~75 min**. This run **$0.022 / ~90 min**.

## Top 5 improvements

Ordered by learner impact per hour of work.

1. **Open the newest sample by mtime in W4.S1's Observe one-liner (F28).** Same rule as `SAMPLE=$(ls -t …)`. Print the path so a mismatch is visible.
2. **Keep Start honest (F1):** merge `course/` to `main` or change the clone line.
3. **Don't let `--min-spans` with n_selected=0 become the bundle input (F29).** Keep the previous sample id; say "you have 0 readable traces — that is the finding, skip the workbench."
4. **Stop backfill from minting duplicate `n` (R13)** — still open; wipe is a workaround, not a lesson.
5. **Uniqueness 22** — still the open decision, not a new finding.

## Appendix

- Observations: `observations.jsonl`
- Steps and ids: `steps.json`
- Build log: `build.md` · check diff: `my-check.diff`
- Concept ledger: `concepts.md`
- Logs: `logs/`
- Spend: `spend.jsonl`
- Build branch left in the test checkout: `course-test/2026-09-18-stranger` @ `a4bc571` in `/var/folders/7f/trms0d492gsf9j9ydv6kp1q00000gn/T/tmp.fn4luThPNO/ai-team`
- Steps not run, and why: W1–W3 and W6 SKIPPED-SCOPE; W4.S2 human reads SKIPPED-HUMAN; W4.S1 `run_smoke_batch --n 10` SKIPPED-TIME
- Deviations: four $0 dry runs + workspace backfill so W4.S1 could be judged at n≈4; W5 branch name `course-test/$RUN_ID` not `my-first-check`; two `SIMULATED:` notes in TEST `course/.work` only; B3 tighten reverted; B5 used as the week 4 off-ramp's first option
- Leftovers at end: none
