# Handoff — 1 Oct 2026

**The October notes were checked against the repo, then the problems that were still open were fixed one at a time on `feature/field-notes-sequel`, each with a field note.** The branch is local. It is not pushed. The live next-steps list is §7. Nothing else in this file is a task list.

**Author:** Rick Zakharov (with agent assist)
**Preceded by:** [2026-09-30 repo audit](2026-09-30-repo-audit.md). That entry's 14 open items stand. This document does not supersede any section of it.
**This document supersedes nothing.** There is no earlier `docs/HANDOFF-*.md` in this repo. Session records live in this journal.
**Branch:** `feature/field-notes-sequel`, on `1701918` (`main` at the time of the branch): seven commits from the first pass, then the pre-merge pass in §9. Not pushed.

A placeholder dry run was executed on 2026-09-30, before these fixes, and confirmed an empty `logs/`. After the fixes, the claims below rest on the unit tests named in §3, not on a second `run_demo`. The full unit suite was not re-run after the last commit.

Decisions recorded in: [docs/FRAMEWORKS.md](../FRAMEWORKS.md), and §9 below. The six field notes were folded into the October series the same day (§9); their drafts live with the campaign, outside git.

**Current verdict:** Six October gaps are fixed on the branch and each has a note. The 30-run re-measure is not one of them. Publish a note only after its proof file is on `main`.

---

## 1. Verdict

The October campaign's numbers that were checked held. The sequel branch fixes the gaps those notes were still waiting on, except a new finish rate, which would require a paid batch and is not claimed.

## 2. What was decided / what was found

| Claim | Verified how | Consequence |
| --- | --- | --- |
| 17 failure modes are 11 harness, 4 model, 1 framework, 1 provider | Count of `layer:` in `evals/taxonomy/failure_modes.yaml` | October LinkedIn 1 can say this |
| Sep 13 smoke: 1.528 s / $0.0000716 bare call, 1,600 s wall, relevance 5/0/9/0 vs 0.15 | That run's README | One run. The posts already say so |
| Old relevance scoring fails correct QA code at 8% | Re-ran the regression fixture: message says 8% below 15% | The journal figure is the test, not a rounded memory |
| 30-run batch: 22 complete, 7 timeout, 1 failed; Wilson 55.6–85.8%; median spend $0.0214; median wall 12.4 min | The batch JSON in `.archive/…/n30-batch-2026-09-18.json` | October posts 7 and 9 Version B match |
| Per-role split on 19 accounted runs: QA 89.6%, developer 10.1%, architect 0.3% | Re-summed `token_usage` in those `state.json` files | Same numbers. There was no command that printed them |
| 369 run records, 240 without `completed_at`, 241 without `costs.jsonl` | Directories that contain `run.json` | A raw directory count is 385. Sixteen folders have no `run.json`. Do not "correct" 369 |
| Placeholder dry run, model off: exit 0, `completed_at` set, `logs/` empty | Ran `scripts/run_demo.py … --graph-mode placeholder` into a temp dir on 2026-09-30. Run-record span was 0.14 s; the command was about 3 s | "Four seconds" in LinkedIn 4 is still a fair description of the command. The empty log was the bug |
| CrewAI's 93,284 loop and the 78-minute GIL hang are two incidents | `docs/posts/failure-taxonomy.md` §2 and `docs/troubleshooting/gil-starvation-hitl-delay.md` | October LinkedIn 5 had fused them. The paste text in `.archive` was split. The image still fuses them on one red line |
| Seven September timeouts have no `state.json` | Listed the seven timeout run dirs; each has `logs/costs.jsonl` only | The cause cannot be read from phase history. No after-rate was invented |
| `.archive/` is gitignored | `.gitignore` line 212 | October posts, including the LinkedIn 5 sentence edit, are not on this branch |
| `eval-methodology-alignment` tasks 1.1–1.6 are not done | Spec DoD still wants `session.json`, one writer module, and a backend wrapper that emits telemetry even if the backend calls nothing | `TelemetryWriter` is a start. Those boxes stay unchecked |

Targeted tests that passed while landing the branch: telemetry and results-bundle (12), phase-log and main-graph (18), acceptance sign-off plus existing acceptance tests (12), fixture contract (20), role-cost (2). `mypy` on `acceptance.py` was clean after the literal annotation. That is not a full-suite claim.

## 3. What changed in the repo

All of this is committed on `feature/field-notes-sequel`. `git diff --stat main...HEAD`: 47 files, +817 / −1,197.

| Commit | Decision |
| --- | --- |
| `cc684de` | A finished run always writes `logs/costs.jsonl`. No model calls is `spent_usd: 0`, `writer: harness`. The closer used to skip the file when `calls` was 0, which is every mocked run |
| `e8973e6` | LangGraph appends `phase_history` on the placeholder nodes and writes `phases.jsonl` from that list. The orchestrator prompt no longer asks the model to write the file. Week 3 step 5 of the course now says the line is gone |
| `7e5d177` | A passing quality gate calls `mark_passing`. Verifier role is `_harness`. A failing gate leaves `passes` false. The September 153 items stay false; they are the old record |
| `eeaa9fb` | `verified_by` is a literal `test` or `smoke`, so mypy accepts the call |
| `160796c` | Deleted 22 `__fixture.json` files that were byte-identical to the sibling already in the corpus. 72 trace ids, 72 files. A test fails if an id appears twice |
| `be661e0` | `scripts/role_cost.py` sums tokens by role from `state.json`. Dollars per role are that role's share of the run total, by tokens, and the report says so |
| `2c4cb28` | `docs/FRAMEWORKS.md` states the listener loop and the GIL hang as two fixes. `ARCHITECTURE.md` §2.1.1 links to it |

The six notes were drafted in `docs/field-notes/2026-11/`, each 152–218 words with a receipt. §9 folds them into the October series and removes the folder from the branch.

## 4. The thing worth naming on its own

**A missing cost file was treated as "this run did not happen," and a mocked run never created one.** `run_demo` passed `spend=None` whenever `calls` was 0, and `finalize` wrote `costs.jsonl` only when that argument was truthy. The 2026-09-30 dry run finished, set `completed_at`, and left `logs/` empty. Charts that skip absent files then drop the free runs, which are the runs you use to test the instrument.

Found by running the week-1 command into a temp directory and listing `logs/`, then reading `scripts/run_demo.py` and `ResultsBundle.finalize`. A test that finalizes with no spend and asserts the file is absent would have locked the bug in. That assertion was the old test. It now requires a zero row.

The phase log had the same shape: the writer was a sentence in a prompt. Deleting the sentence without a harness writer would have made the file rarer. The prompt line came out in the same commit that writes the file from `phase_history`.

## 5. What did not change

- The 2026-09-30 audit's 14 open items. None of them were this session.
- October Version A (the finale and Substack 4). No second 30-run batch. No new finish rate. No interval. The seven timeout directories still have no `state.json` (§9 makes future stopped runs keep one).
- `.kiro/specs/eval-methodology-alignment/tasks.md` Phase 1. `TelemetryWriter` does not satisfy "grep `phases.jsonl` under `src/` returns only `telemetry.py`," does not write `session.json`, and is not installed by a `Backend` wrapper. `emit_phase_end` in `context_pressure.py` still writes `phases.jsonl` on the CrewAI and Claude paths.
- Strands and Microsoft Agent Framework. Still not running.
- The October frameworks image. It still said the listener hit 93,284 and "now its own process" on one line (redrawn with two lines in §9).
- The bracket in the 28-engineers post. That sentence is Rick's. It was not written.

## 6. Repo surface

Start at [docs/FRAMEWORKS.md](../FRAMEWORKS.md) and [course/week-1-build.md](../../course/week-1-build.md). The campaign calendar and receipts live outside git; the canonical copy is the campaign folder Rick keeps outside the repo, and `.archive/Campaign - Oct 2026/` is an older copy of it. Proof files the posts link to:

- `src/ai_team/harness/telemetry.py`
- `src/ai_team/backends/common/acceptance.py`
- `evals/fixtures/traces/`
- `scripts/role_cost.py`
- `docs/FRAMEWORKS.md`

## 7. Start next session with

**This is the only live list.** Rewritten in the §9 pass; it replaces the first pass's list.

1. **Push `feature/field-notes-sequel`, open a PR into `main`, merge by Fri Oct 9.** Done when CI is green and these resolve on `main`: `course/week-1-build.md` (with the after card), `src/ai_team/harness/telemetry.py`, `docs/FRAMEWORKS.md`, `scripts/role_cost.py`, `src/ai_team/backends/common/acceptance.py`, `evals/fixtures/traces/`. Owner: Rick. Posts 4 to 9 link to these.
2. **Batch A, the weekend of Oct 10–11 (spend approved by Rick on Oct 1).** `uv run python scripts/run_smoke_batch.py --n 30 --backends langgraph --team smoke` from `main`. The September batch cost $0.90 and ran 7.3 hours. Done when the bundle is in `output/` and every timeout has a `state.json` with `stopped_by` and `stopped_in`.
3. **Read before fixing (Oct 12–19).** List where the timeouts stopped (`stopped_in`), split their tokens with `scripts/role_cost.py`, and write the cause down before looking at a fix. Then one fix, with a test that fails on the old code, merged by Fri Oct 23.
4. **Batch B, the weekend of Oct 24–25.** Same command, same team, same brief. Fill the finale's Version A from batch A and batch B (compare B with A: same instrument), by Mon Nov 2. If B is not in by then, the finale posts Version B. Whoever runs the batch does not write the after-number first.
5. **Before Thu Oct 29, replace the bracket in the 28-engineers post.** One sentence, past tense, no employer-internal material, and the post stays at or under 250 words. Owner: Rick. The agent does not invent it.
6. **Leave `eval-methodology-alignment` Phase 1 unchecked** until its own definition of done is true (`session.json`, a single writer, the wrapper test). `TelemetryWriter` is not that phase.

**Decisions still owed by Rick:** the 28-engineers sentence, and whether the `.archive/Campaign - Oct 2026/` copy should go. The 2026-09-30 audit list is still owed too.

## 8. Open questions

- **Do weeks 1 and 3 of the course still teach the right labs?** Week 3 step 5 was updated in `e8973e6`; week 1 in §9. Neither has had a stranger run since. Run `/test-course` on both before the next course push, or the labs and the pages will drift again.
- **Are dollar shares in `role_cost.py` too easy to quote as a provider invoice?** The report labels them as a token share of the run total. If a note ever drops that clause, the number is no longer the one the script prints.

## 9. Same day, second pass: pre-merge fixes and the campaign re-plan

Rick read §7 and asked for the campaign to follow the fixes. Three decisions, his: put each fix next to the finding it answers, re-measure the 30 runs (two batches), and make the branch mergeable first.

**Found while making the branch mergeable.** The full unit suite had not been run on the first pass, and two repo tests failed on the branch before any change here:

- `test_no_unreferenced_images_outside_publication`: `e8973e6` removed week 3's only reference to `docs/images/eval-telemetry-writers.png`. The image is back as the "before" picture, with the term *self-reported telemetry* it introduced.
- `test_ignore_errors_loc_within_budget`: 12,305 LOC under `ignore_errors` against a floor of 12,241, from code added to `langgraph_backend` (an untyped package).
- `test_annotate_three_resume_skips`: it checked for the `__fixture.json` files `160796c` deleted.

And one content gap: course week 1, which posts 4 and the Substack issue link to, still taught that the model-off run leaves `logs/` empty. After `cc684de` and `e8973e6` it does not.

| Commit | Decision |
| --- | --- |
| `5637bfa` | `role_cost.py` takes many runs (`--batch <smoke_batch.json>`), keeps runs whose message tokens reach 90% of the cost log's total, and lists every skipped run with its reason. On the September batch it prints the 19-run split the drafts quoted by hand: QA 89.6%, in:out 43.4 |
| `d7e0bf2` | A placeholder run leaves an empty `audit.jsonl`, through the bus's own path. Placeholder only: no node there can call a tool, so zero is known. A full run still leaves the file to the bus, so a run whose tools bypassed it cannot show a false zero |
| `a53b385` | A stopped LangGraph run keeps its last checkpoint. `DemoTimeoutError` unwinds out of `graph.invoke`; the backend now writes the checkpointer's state with `stopped_by` and `stopped_in`, writes `phases.jsonl` from it, and re-raises. Checked with a real SIGALRM: stopped in `testing`, three phases recorded. The batch runner never counts a stopped run as green |
| `7a49cc1` | That writer moved to `ai_team.harness.stopped_run` (typed), and the `crewai_backend.callbacks` override is retired with one cast. 11,867 LOC under `ignore_errors`; the ratchet moves down |
| `6bf2e8c` | Week 1 shows the after card first and the September card as the before; the student's card asks for `spent_usd` and audit rows; the stop rule says a stopped LangGraph run keeps its checkpoint. Week 3 gets its image back |
| `e2d3d55` | `test_annotate` looks fixtures up by the one file left per trace id |

**The re-plan.** The October series grows to ten posts and ends Thu Nov 5, with Substack 4 on Fri Nov 6 (Tue Nov 3 is Election Day). A new Thu Oct 15 post tells the logging fix two days after the post that found it (field notes 1 and 2). Notes 3 to 6 are folded into the posts they repeat: 3 into the 28-engineers post, 4 into the baseline post, 5 into the cost post (now proven by `role_cost.py --batch`), 6 into the frameworks post, whose text and image now keep the two CrewAI failures apart. `docs/field-notes/` is removed from the branch; the drafts are kept with the campaign.

Checked after the last commit: the full unit suite (1,784 passed with the venv's `pytest` and `ruff` on `PATH`; without it, ten gate and smoke tests fail on `/usr/bin/python`), `tests/conformance` and `tests/integration`, `ruff check`, `ruff format --check`, `mypy src/` and `mypy evals/`.

**Still open from this pass.** Unit tests that run a backend without `workspace_dir`, and a `run_demo` without `PROJECT_WORKSPACE_DIR`, still write into `./workspace/` (the audit's hard-coded-workspace item). The stopped-run writer covers LangGraph only; CrewAI and the Claude SDK still leave no state when the watchdog stops them.
