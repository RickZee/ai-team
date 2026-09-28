# Course test report — 2026-09-16-stranger

| | |
| --- | --- |
| **Scope / mode / budget / fix** | all · stranger · $10 · no |
| **Git SHA** | `72d49e1` (local `feat/course-v2` tree; test checkout later moved to `my-first-check` `4fde1aa` for week 5 only) |
| **Environment** | Darwin 27.0.0 · uv 0.10.2 · Python 3.12.7 |
| **Tester** | Cursor agent (Grok 4.6) · 2026-09-16 |
| **Spend** | **$1.54 recorded + $0.10 projected = $1.64 counted** of $10. W1 LangGraph $null (count $0.05) · W2 CrewAI $null (count $0.05) · W2 Claude **$0.71** · W6 Claude n=1 **$0.83**. Plan was ~$5.65 with `--n 5`, then `--n 1 --team smoke-claude` (~$3). Those live batches were not run (time). Two orphan LangGraph processes kept spending after `--timeout 900` until killed; their USD is unknown. |
| **Wall time** | ~80 min tester time including two 15-min hangs. Not the advertised 12 hours of learner work (week 4 reading and week 6 `--n 5` skipped). |

## Verdict

A stranger who follows `course/README.md` → *Start* and clones GitHub **never gets `course/`** — it is not on `origin/main`. Inside this local tree the $0 spine (dry run, recorded 2026-09-13 case, weeks 3–5) teaches the instrument lesson hard, but macOS zsh and copy-paste placeholders break several fences, and the paid LangGraph/CrewAI path does not stop when the page says it will. It is not ready to share as “clone the repo and go.”

## Scorecard

| Week | Runs | Accurate | Clear | Teaches | Honest | Fits budget | Stranger can finish alone? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 · Build | 2 | 4 | 3 | 5 | 4 | 2 | No — zsh grep, then a hang with no `state.json` |
| 2 · Fail | 3 | 5 | 4 | 5 | 4 | 2 | Yes **if** they use the recorded case and skip the live race |
| 3 · Observe | 3 | 3 | 4 | 5 | 4 | 5 | Yes after quoting globs and substituting the commit SHA |
| 4 · Read | 3 | 5 | 4 | 3 | 5 | 4 | No — n=5 not 30; human reading skipped by design |
| 5 · Evaluate | 4 | 4 | 3 | 5 | 5 | 5 | Yes if they apply the documented patch |
| 6 · Improve | 2 | 4 | 2 | 3 | 2 | 1 | No — `--n 5` is an evening, not 90 minutes |

One line of evidence per score goes in the week sections below.

## Step results

| Step | Block | Result | Exit | Time | Note |
| --- | --- | --- | --- | --- | --- |
| W1.S2 | c1 | MATCH | 0 | 8.6 s | placeholder dry run |
| W1.S2 | c2 | MATCH | 0 | 0.1 s | `completed_at` null, empty `logs/` |
| W1.S2 | c3 | BROKEN | 1 | 0.0 s | zsh `NOMATCH` on `--include=*.py` |
| W1.S3 | c1 | BROKEN | 124 | 900 s | `--timeout 900` did not kill; orphans spent |
| W1.S3 | c2 | BROKEN | 0 | 0.1 s | no `state.json` |
| W2.S1 | c1 langgraph | SKIPPED-PAID | — | — | reused W1 hang (DEVIATION-TIMEBOX) |
| W2.S1 | c1 crewai | BROKEN | 124 | 900 s | still `testing`; test file exists |
| W2.S1 | c1 claude | MATCH | 0 | 170 s | $0.71, `completed_at` set |
| W2.S1 | c2 | SKIPPED-SCOPE | — | — | immortal dashboard servers |
| W2.S1 | c3 | MATCH | 0 | 0 s | three newest ids |
| W2.S2 | c1 | MATCH | 0 | 0 s | recorded evidence dir |
| W2.S2 | c2 | MATCH | 0 | 0 s | guardrail + `retry_development` |
| W3.S1 | c1 | MISMATCH | 0 | 1.3 s | not empty after paid runs |
| W3.S1 | c3 | MISMATCH | 0 | 0 s | 87 spans, not zero |
| W3.S2 | c1 | DRIFT | 0 | 1.0 s | shape ok, n=5 |
| W3.S2 | c3 | DRIFT | 0 | 0.1 s | newest is Claude; no “no final status” |
| W3.S2 | c4 | BROKEN | 1 | 0 s | `git show <that commit>` |
| W3.S2 | c5 | MATCH | 0 | 1.0 s | forced `crewai` |
| W3.S3 | c1 | DRIFT | 0 | 0.2 s | floors UNMET; 2 vs 87 spans |
| W3.S4 | c1 | DRIFT | 0 | 1.5 s | 0 live / na 91% on n=5 |
| W3.S5 | c1 | BROKEN | 1 | 0 s | zsh glob again |
| W4.S1 | c1 | DRIFT | 0 | 0.5 s | n_selected=5 |
| W4.S2 | c1 | BROKEN | 1 | 0 s | `ID=<run id …>` |
| W4.S3 | c1 | BROKEN | 0 | 0.5 s | missing `~/Downloads/annotations.jsonl` |
| W5.S1 | c1 | MATCH | 0 | 1.1 s | 182 failed; `head -3` misses layer lines |
| W5.S2 | c1 | DRIFT | 0 | 0 s | 95 fixture files |
| W5.S3 | c1 | MATCH | 0 | 0 s | pass/fail/na |
| W5.S4 | c2 | MATCH | 0 | 20 s | patch + baseline; CORPUS n=5 |
| W6.S2 | c1 | BROKEN | 1 | 1.3 s | `grep "<your check id>"` |
| W6.S3 | c1 | MATCH | 0 | 82 s | 1619 passed |
| W6.S3 | c2 | SKIPPED-PAID | — | 203 s* | *`--n 1` Claude only; `--n 5` not run |
| W6.S4 | c1 | MATCH | 0 | 0.1 s | `(0.0, 0.2425)` |
| W6.S5 | c1 | BROKEN | 2 | 0.1 s | `/path/to/your/runs` |
| README | Start | BROKEN | — | — | `course/` not on `origin/main` |

Totals: **MATCH 16 · DRIFT 6 · MISMATCH 2 · BROKEN 11 · SKIPPED-PAID 2 · SKIPPED-SCOPE 1** (plus week-4 human reading SKIPPED-HUMAN).

## Findings

| ID | Sev | Where | What happened | Suggested change | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | P0 | `course/README.md:18` | `git clone https://github.com/RickZee/ai-team.git` checks out `main`. `origin/main` has no `course/`. | Merge this tree to `main` before sharing, or change Start to the branch that contains `course/`. | `git cat-file -e origin/main:course/README.md` |
| F2 | P0 | `course/week-1-build.md:70` same pattern in week 3 step 5 | On macOS zsh, `grep … --include=*.py` never runs (`NOMATCH`). | `grep -rn --include='*.py' "finalize(" src/ai_team scripts` | W1.S2.c3, W3.S5.c1 |
| F3 | P0 | `course/week-1-build.md:87` | `--timeout 900` armed a watchdog that did not stop LangGraph. Killing the shell left `run_demo.py` orphans (PPID 1) still spending. No `state.json`, no `costs.jsonl`. Workspace already had `calc.py` + `test_calc.py`; guardrail retried at 8% then 5% relevance. | After minute 15: Ctrl-C, then use `docs/eval-runs/2026-09-13-langgraph-smoke/`. Do not claim the flag stops the process. Observe must `ls $RUN` first. | `logs/W1.S3.c1.meta.txt` |
| F4 | P0 | `course/week-2-fail.md:16` | Live race: CrewAI still in `testing` at 900s; LangGraph same as F3. Only Claude finished (170s, $0.71). Step billed as 30 min / ≈$1. | Default the comparison table to the recorded case. Live backends optional. | `logs/W2.S1.c1-crewai.meta.txt` |
| F5 | P0 | `course/week-3-observe.md:103` | `git show <that commit>` is zsh redirection. Same class: week 4 `ID=<run id…>`, week 6 `grep "<your check id>"`. | Never put `<placeholders>` inside copy-paste fences. Give a command that substitutes. | `logs/W3.S2.c4.txt` |
| F6 | P0 | `course/week-6-improve.md:52` | `--n 5` uses per-run ceilings of 1800s / 1500s / 900s. Fifteen live runs are hours, not 90 min / $1–5. `--replay example_mixed_model_n5` already prints the overlap lesson at $0 and is **not in the lab**. | Make `--replay` the lab command. Live `--n 5` as an evening optional. | `scripts/run_smoke_batch.py` `TIMEOUTS`; `logs/W6.S3.replay.txt` |
| F7 | P1 | `course/week-3-observe.md:56` | After paid weeks 1–2, default backfill is not empty (5 traces, 87 spans). Punchline “zero spans / empty corpus” is only true for dry-run-only. | Split Observe: dry-run vs after paid runs. Paid-path punchline is **unknown backend**, not emptiness. | `logs/W3.S1.c1.txt` |
| F8 | P1 | `course/week-5-evals.md:21` | `head -3 summary.txt` does not include `layer[harness] fails=102 0.479 (n=213, …)` (line 14). | `grep layer course/.work/tier-a/summary.txt` | `course/.work/tier-a/summary.txt` in the test checkout |
| F9 | P1 | `course/week-5-evals.md:148` | “On this repo's 334 real traces it fails 236” is maintainer-only. Stranger CORPUS is n=5, thin. | Fresh-clone Observe with n=5; lead with `git apply course/solutions/week-5-check.patch`. | `logs/W5.S4.c2.txt` |
| F10 | P1 | `course/week-2-fail.md` / Claude backend | `claude_recovery_attempt max_budget_usd=18.0` while the lab sets `AI_TEAM_RUN_BUDGET_USD=1`. Week 6 batch sets neither. | Honor the lab cap in recovery and in `run_smoke_batch.py`. | `logs/W2.S1.c1-claude.txt` |

Severity: **P0** blocks the learner · **P1** misleads · **P2** friction · **P3** polish.

### Repo findings (not course text)

| ID | Where | What | Owner (spec / file) |
| --- | --- | --- | --- |
| R1 | `scripts/run_demo.py` watchdog | `--timeout 900` does not kill LangGraph; SIGALRM / child process group not torn down. Ctrl-C of the shell leaves orphans spending. | harness / run_demo |
| R2 | CLI path vs `finalize()` | Confirmed: only web + Claude SDK call `finalize()`. LangGraph/CrewAI CLI runs have `completed_at: null` and often no `state.json` if killed. | `core/results/writer.py` — this is the week 1 lesson, still true |
| R3 | `guardrail_hooks.py` / `routing.py` | Last-12 chat relevance + `retry_development` on every testing error. Files were correct by minute ~2; loop continued. | LangGraph graphs — week 2 recorded case still reproduces |
| R4 | Claude recovery budget | `max_budget_usd=18.0` ignores `AI_TEAM_RUN_BUDGET_USD=1`. | claude-agent-sdk backend |
| R5 | Cost writers | Paid LangGraph/CrewAI wrote no `output/runs/.../logs/costs.jsonl`. Claude did (`spent_usd`). Missing cost is the week 1 lesson on live runs. | harness CLI path |
| R6 | `evals.cli` default `--workspace-root ./workspace` | Still the starved-harness default. After real runs it is not empty — it is **mislabelled**. | evals CLI — week 3 |

## Week notes

### Week 1 · Build
- Predictions a newcomer would make: all four of end time, status, phase log, cost log exist. The dry run corrects that.
- Most confusing moment: the paid run “finishes” the brief (`calc.py` / `test_calc.py` in the workspace) while the process will not die and the Observe card cannot be filled.
- Scores: dry run is excellent teaching. Live run is a trap unless the recorded case is offered here, not only in week 2.

### Week 2 · Fail
- Live race is not a 30-minute lab. The recorded 2026-09-13 case is the actual product and it is excellent (timeline, last-12 messages, `retry_development`, 0 tests collected).
- Claude is the only backend that writes `completed_at` — which quietly proves week 1.
- Lesson that landed best: harness vs model. Lesson only asserted if they never open the recorded README.

### Week 3 · Observe
- Fresh-clone note is good. Unconditional “Zero” spans is not, after the paid path.
- Two readers disagreeing (evals default 87 spans vs minieval 2 spans) is the best moment in the course.
- `git show <that commit>` blocks a copy-paste learner on zsh.

### Week 4 · Read
- Mechanics work: stratified sample returns 5, bundle writes, `evals/ui/workbench.html` exists.
- Human reading SKIPPED-HUMAN (two `SIMULATED:` notes in `course/.work/annotations/` only; nothing under `evals/annotations/`).
- Without a teaching corpus this week cannot be finished as specified.

### Week 5 · Evaluate
- Tier A red / 182 / $0 matches. FIXTURE-ONLY vs CORPUS is the best explicit teaching in the course.
- Wiring table is six files; the patch is what a stranger will actually use, and it works (408 eval unit tests, baseline accept, fail count 182→228).
- `head -3` vs quoted Observe is a small but real miss.

### Week 6 · Improve
- `wilson_ci(0, 12)` matches.
- Live `--n 5` was not run. `--replay example_mixed_model_n5` prints 5/5 vs 1/5 with overlapping CIs and “no significant difference” — that **is** the Explain, and the lab does not mention it.
- DEVIATION-TIMEBOX: `run_smoke_batch.py --n 1 --backends claude-agent-sdk` → 0/1 green, $0.83, CI 0–79%. Script works. Cost/time as written do not.

## Learner questions

- Could a stranger finish alone? Not from GitHub `main`. From this tree: weeks 3 and 5 yes; weeks 1–2 only via the recorded case; week 4 no (no 30 runs); week 6 no (live batch).
- Single most confusing moment: LangGraph still retrying after the files exist, while `--timeout 900` lies and `state.json` is missing.
- Lesson that landed best: the instrument can be empty, mislabelled, or disagree with a second reader — and green FIXTURE-ONLY proves nothing about agents.
- Lesson only asserted: “fix it, prove it with n” (week 6 live loop).
- Does the course still serve the purpose in `course/README.md`? The $0 labs would, if they were on the default branch and the copy-paste fences ran on zsh. As Start is written, a stranger who doesn't care whose repo this is **cannot run it**.

## Top 5 improvements

Ordered by learner impact per hour of work.

1. **Put `course/` on the branch Start clones** (merge to `main`, or change the clone line). Until then the course is private to this checkout.
2. **Quote every grep glob** (`--include='*.py'`) and **remove `<placeholders>` from bash fences** (commit SHA, run id, check id).
3. **Week 1–2 stop rule:** if it is still running at minute 15, Ctrl-C and open `docs/eval-runs/2026-09-13-langgraph-smoke/`. State that `--timeout` may not kill, and that Observe must survive a missing `state.json`.
4. **Week 6 default to `--replay example_mixed_model_n5`.** Keep live `--n 5` as an optional evening with honest time/cost. Do not set `TIMEOUTS` of 1800s in a 90-minute lab.
5. **Teaching corpus (or split Observe).** Week 3 “zero spans” is false after paid runs; week 4 needs 30 real traces; week 5’s “236 of 334” is maintainer-only.

## Appendix

- Observations: `observations.jsonl`
- Logs: `logs/`
- Spend: `spend.jsonl`
- Test checkout: `/var/folders/7f/trms0d492gsf9j9ydv6kp1q00000gn/T/tmp.8HIBka0rLK/ai-team` (throwaway; week 5 left on `my-first-check`, not merged)
- Steps not run, and why:
  - W2.S1.c2 dashboard — immortal servers, optional
  - W2.S1 for-loop langgraph iteration — DEVIATION-TIMEBOX, reused W1.S3
  - W4 step 2 human open-coding — SKIPPED-HUMAN
  - W6.S3 `--n 5` and `--n 5 --team smoke-claude` — SKIPPED-PAID / DEVIATION-TIMEBOX (hours, not 15 min); `--n 1` Claude and `--replay` run instead
  - W6.S3 smoke-claude `--n 1` (~$3) — DEVIATION-BUDGET/TIMEBOX, likely LangGraph hang
- Deviations: quoted grep globs; process-group killer for paid runs (macOS has no `timeout(1)`); week 5 used `course/solutions/week-5-check.patch`; two `SIMULATED:` notes in scratch only

## Resolution (added after review, 2026-09-16)

Findings were checked against the code before fixing. Commits are on `feat/course-v2`.

| ID | Status | What changed |
| --- | --- | --- |
| F1 | open — launch gate | Push and merge `feat/course-v2` (launch gate). Not a course-text defect. |
| F2 | fixed | Globs quoted: `--include='*.py'` (weeks 1, 3) |
| F3 | fixed (docs + code) | Week 1 stop rule at minute 15, `ps` check for leftovers, Observe survives a missing `state.json`; watchdog fixed (R1) |
| F4 | fixed | Week 2 live race marked optional with the 2026-09-16 result; stop rule; recorded case is the default |
| F5 | fixed | No `<placeholders>` left in runnable fences (`FIX=$(git log …)`, `ID=$(ls -t …)`, `CHECK=…`, `NOTES=…`, `RUNS=…`) |
| F6 | fixed | Week 6 defaults to `run_smoke_batch.py --replay example_mixed_model_n5` ($0); live batches optional with honest time/cost |
| F7 | fixed | Week 3 step 1 Observe split: dry runs only / real runs / maintainer checkout |
| F8 | fixed | `head -1` + `grep layer` |
| F9 | fixed | Week 5 quotes your own corpus first; 236/334 labelled as the maintainer's |
| F10 | fixed (code) | See R4 |
| R1 | fixed | `DemoTimeoutError` is now a `BaseException`; a second alarm 30 s later finalizes the record as `timeout` and hard-exits 124 |
| R2 / R5 | fixed | `run_demo.py` finalizes its own run record on every exit path (`complete` / `failed` / `awaiting_human` / `timeout` / `error`), with backend and spend |
| R3 | fixed (unit-tested, not yet live) | Current-turn guardrail scoring; testing `GuardrailError` → human review; single-agent subgraphs really checked; run-scoped workspace in the testing prompt and file inventory. Regression test rebuilds the 09-13 case |
| R4 | fixed | Claude SDK ceiling now honours `AI_TEAM_RUN_BUDGET_USD` (min of cap and phase sum) |
| R6 | by design | The `./workspace` default is the week 3 lesson |

Test harness: `course/testing/run_step.py` replaces plain `timeout` (absent on macOS) — runs in
`$SHELL`, kills the process group, reports leftovers. The tester's `run_paid.py` was removed in
its favour.
