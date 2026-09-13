# Handoff — LangGraph smoke as the first real eval case

**Date:** 2026-09-13
**Run id:** `2026-09-13_182650_write-a-single-python-module_01`
**Intent:** production-hardening task 9.1 (live benchmark, $25 cap)
**What it actually is:** a cheap `demos/00_smoke_test` LangGraph/`prototype` run
that should have finished in a couple of minutes and did not.

This note is a **handoff**, not a published rate. Corpus kind stays
`FIXTURE-ONLY` until this run is indexed, open-coded by a human, and the
floors in [`EVAL_GATE_STATUS.md`](../../campaign/EVAL_GATE_STATUS.md) move.
The campaign sequel — *what traces read by hand actually found* — starts here.

Frozen mid-run **2026-09-13T18:52:46Z**; the process then exited **14:53:26 EDT**
(wall **1600 s**, CLI exit **1**). Terminal state: LangGraph
`interrupt()` → `human_review` (`hitl_source=testing`).
`run.json.completed_at` stayed **null** — CLI never calls `ResultsBundle.finalize()`.
Evidence in [`evidence/`](./evidence/) (including `terminal-state.json`,
`scorecard.json`). Screenshots taken in flight:
[`.kiro/specs/production-hardening/screenshots/9.1/`](../../../.kiro/specs/production-hardening/screenshots/9.1/README.md).

---

## Why this run is the eval use case

The starved-harness audit
([`posts/the-starved-harness.md`](../../posts/the-starved-harness.md),
[`journal/2026-09-13-eval-methodology-audit.md`](../../journal/2026-09-13-eval-methodology-audit.md))
said:

1. The methodology is Husain & Shankar (traces → open coding → taxonomy →
   checks). See [`resources.md`](../../resources.md) and
   [`EVAL_METHODOLOGY.md`](../../EVAL_METHODOLOGY.md).
2. The machinery exists. **Zero production traces have been open-coded.**
3. Backfill pointed at `./workspace` (generated code). Run records live in
   `./output/runs/`.
4. `phases.jsonl` is requested from the model, not written by the harness.

This smoke run is the opposite of the August fixture dump: one live
LangGraph execution, a known brief, a known profile, a receipt directory,
and enough logs to **debug a real failure** the way the essays claim we do.

It is also a 9.1 problem. A “minimum token spend” setup validator
([`DEMOS.md`](../../DEMOS.md)) ran **1600 s** past a 900 s watchdog, ended in
HITL, and still has no `completed_at` / `costs.jsonl`. Do not publish wall-clock
or cost from this run as a benchmark.

---

## Reproduce

```bash
# Same command used 2026-09-13. Cap is the spec $25; default $5 would also
# have been enough if the run had finished.
set -a && source .env && set +a
export AI_TEAM_ENV=dev
export AI_TEAM_RUN_BUDGET_USD=25
uv run python scripts/run_demo.py demos/00_smoke_test \
  --backend langgraph --skip-estimate --timeout 900
```

**Hardware (this machine):** Apple M3 Pro, Darwin 25.6.0 arm64, Python 3.12.7.
**Models (dev tier, every role):** `openrouter/deepseek/deepseek-v4-flash`.
**Bare OpenRouter control (same brief, max_tokens=256):** 1.528 s, 332 tokens,
**$0.0000716**. Harness wall for this smoke: **1600 s**, ~1000× the control,
then HITL. That ratio is a harness-overhead anecdote (`n=1`), not a 9.1 table.

**Do not** start a second web run against the same budget to get Dashboard
shots. CLI runs are invisible on Home (in-memory `GET /api/runs` only).
See problem 8 below.

---

## Timeline (from structlog + ToolBus journal)

Times are local EDT (UTC−4). Source: `evidence/structlog-excerpt.txt`
(from `/tmp/ai-team-bench-9.1/harness.out`) and `evidence/journal.jsonl`.

| t | Event |
| --- | --- |
| 14:26:50 | `spend_guard_reset budget_usd=25.0`. Graph compiled. Planning = architect only. |
| 14:27:10 | Development = fullstack_developer. First `write_file` **drafts** `calc.py` + `test_calc.py`. |
| 14:27:54 | Testing subgraph = qa_engineer. |
| 14:28:38 | **`testing_subgraph_failed`**: `Path must be under workspace: …/ai-team/workspace` (the **parent** tree, not the run dir). |
| 14:28:44 | Salvage: `code_block_extracted_to_workspace` commits `calc.py` and `test_calc.py`. `testing_exception_fallback count=2`. |
| 14:32:20 | Behavioral scope fail: relevance **5%** vs floor **15%**. Retry 1/3. |
| 14:35:39 | Same guardrail: **0%**. Retry 2/3. |
| 14:40:12 | Same guardrail: **9%**. Retry 3/3. |
| 14:46:27 | Same guardrail: **0%** (past max_retries; still in the graph). |
| 14:46:38 | More drafts (`calc.py`, `tests/test_calc.py`). |
| 14:48:52 | Drafts aimed at **nested** `workspace/<id>/workspace/<id>/calc.py`. |
| 14:49:19 | A later `route_after_behavioral` **pass**. |
| (graph) | `phase_history` then shows **development again** (files 274 → 283 → 288) and two more testing `passed: false` — `route_after_testing` mapped a testing-phase error to `retry_development` (`retry_count` hit 3). |
| 14:53:26 | `failure_records_persisted`. Graph `interrupt()` → `human_review`. CLI exit 1. `completed_at` still null. |

`state.json` `phase_history` (see `evidence/terminal-state.json`):

```
planning complete
development complete (files: 260)   ← inventory of the unscope tree, not 260 source files
testing recovered, passed: false
development complete (files: 274)
development complete (files: 283)
testing complete, passed: false
development complete (files: 288)
testing complete, passed: false
→ human_review
```

Quality-gate artifact at exit: ruff ok, pytest **exit 5** (`collected 0 items`)
even though `calc.py` and `test_calc.py` exist at the run root. Nested copies
also poisoned collection (`import file mismatch` on
`workspace/<id>/workspace/<id>/test_calc.py` in structlog).

### Why relevance failed after files existed

The scorer **never looks at disk.** LangGraph `concat_recent_ai_content`
(`guardrail_hooks.py`) concatenates the **last 12 AI messages** in the seeded
history. Planning and development wrap with
`behavioral_only_message_names={*_supervisor}` even in single-agent mode, so
those subgraphs skip or vacuously pass scope. Testing does **not** filter
names, so QA is scored against leftover architect ADR + fullstack chatter.
Fences in that window make `had_code` true; leftover prose is ≥8 words, so
the “entirely / mostly code” escapes do not fire. Overlap 0–9% vs the
LangGraph code-role floor **0.15** is expected. Asking the model to “be more
relevant” adds more generic vocabulary and fails again.

Two retry loops, no shared “files already shipped” signal:

1. In-subgraph: `MAX_SUBGRAPH_GUARDRAIL_RETRIES = 3` (`langgraph_guardrail_nodes.py`).
2. Graph-level: `_guardrail_error_dict` emits `{phase: "testing"}`;
   `route_after_testing` treats any testing-phase error as `retry_development`
   (`routing.py`).

Watchdog: `DemoTimeoutError` is a catchable `Exception`. Every subgraph wraps
`sub.invoke` in `except Exception`, so SIGALRM is one-shot and then swallowed.
CrewAI already moved to subprocess + OS kill; LangGraph CLI did not.
`BudgetExceededError` is a `BaseException` on purpose so those handlers cannot
retry it — the wall-clock watchdog was not given the same treatment.

---

## Trace inventory (honest)

| Artifact | Present? | Notes |
| --- | --- | --- |
| `output/runs/<id>/run.json` | yes | backend `langgraph`, profile `prototype`, `completed_at: null` |
| `output/runs/<id>/state.json` | **yes (after exit)** | `retry_count=3`, HITL not persisted as `__interrupt__` here |
| `output/runs/<id>/reports/scorecard.json` | yes | `status: partial`, `test_passed: false`, `phases: {}` |
| `output/runs/<id>/logs/costs.jsonl` | **no** | CLI never `finalize()`; spend is in-memory only |
| `workspace/<id>/logs/phases.jsonl` | **no** | LangGraph never calls `emit_phase_end()` |
| `workspace/<id>/logs/journal.jsonl` | 22 lines | `run_id` / `backend` always **null** |
| `workspace/<id>/logs/audit.jsonl` | 22 lines | ToolBus drafts/commits |
| `workspace/<id>/calc.py` | yes (813 B) | four arithmetic ops + ZeroDivisionError |
| `workspace/<id>/test_calc.py` | yes (2127 B) | pytest classes for add/sub/mul/div |
| Nested `workspace/<id>/workspace/<id>/workspace/<id>/` | **yes (3 levels)** | QA prompt used unscope `settings.workspace_dir` (`./workspace`) |
| Dashboard Home row | **no** | CLI run never entered in-memory `state.runs` |

If you backfill from `./workspace` default, you get generated files and
almost no spans. If you backfill from `output/runs/` you get `run.json`
and still **no** `phases.jsonl` / `costs.jsonl`. Either way, several
Tier A checks will return `na` for missing span types — which is itself
the starved-harness story, now on a live LangGraph id.

---

## How this maps to what we already published

Do **not** treat the right-hand column as golden labels. It is axial-coding
**hypotheses** after reading the logs. Open coding in
`evals/annotate.py` must stay unguided (R3.7): no FM ids in the TUI.

| Published mechanism | Where | What this run shows |
| --- | --- | --- |
| Traces before scores | Husain & Shankar / `EVAL_METHODOLOGY.md` | We have a run id and logs. We do **not** yet have a Trace with spans. |
| Cheap detection first | same | `CHK-guardrail-fp-budget` (FM-005) needs `guardrail_check` spans. Today the fails live only in structlog. Parser gap. |
| FM-005 lexical guardrail FP | `failure-taxonomy.md` §5, `behavioral.py` | Last-12 AI window, not disk files. Planning/dev skip scope via a fake supervisor-name filter; QA is scored on leftover ADR prose. |
| FM-008 dashboard / metric drift | taxonomy §8 | Home empty; CLI never `finalize()` so no `costs.jsonl`; journal `run_id=null`. |
| FM-010 gate environment / layout | `langgraph-reliability-investigation.md` | Testing crashed on parent `./workspace`; nested three levels; pytest exit 5 despite root `test_calc.py`. |
| FM-001 salvage | taxonomy §1 | `code_block_extracted_to_workspace` after the testing exception — salvage worked; retries then ignored it. |
| FM-002 retry loop | taxonomy §2 | Two loops: in-subgraph ×3 then `retry_development` ×3 → HITL. |
| FM-007 spend | taxonomy §7 | Guard *reset* to $25; no `costs.jsonl`, so we cannot prove the ceiling saw real `usage.cost`. |
| Seven-layer bar | Weng / `HARNESS.md` / `resources.md` | Guardrails fired; observability and routing did not close the loop. |
| “tests green ≠ app works” | ClaudeDevs / FM-006 | Files existed; the quality-gate pytest collected **0** items (`exit 5`). |
| Stencil: views as projections | `posts/harness-map.md` | Dashboard is a projection of in-memory runs. CLI truth never projected. |
| Watchdog | `GUARDRAILS.md` / CrewAI subprocess kill | `DemoTimeoutError` is `Exception`; subgraphs swallow SIGALRM. |

The 2026-07-01 comment in `scope_control_guardrail` already admits the
relevance floor was documented as fixed and still burns QA-shaped output.
This run is a **receipt** that the live path still does it.

---

## What we can publish from this (and what we cannot)

This is the sequel setup for
[`posts/the-starved-harness.md`](../../posts/the-starved-harness.md) and L4
in [`campaign/2026-09-eval-audit-campaign.md`](../../campaign/2026-09-eval-audit-campaign.md).
The method we already describe:

```
workspace / output/runs logs  →  Trace  →  human open coding (no FM hints)
                              →  axial coding → taxonomy YAML
                              →  cheap check (CHK-*) if the mode is mechanical
                              →  harness fix  →  replay the same brief
```

is exactly how this smoke gets debugged. The interesting finding is not
"DeepSeek failed calc.py." Files landed in ~90 s. The interesting finding
is **retry amplification after a successful write**: the relevance scorer
reads conversation prose, not disk; a testing-phase GuardrailError rewinds
**development**; SIGALRM is swallowed; Home never lists the CLI run.

**May say (after this doc, with n=1, no rate):** we ran a live LangGraph
smoke, preserved the logs, and the first read already shows those
harness defects. The annotation TUI is the next sitting.

**Must not say:** a pass rate, that FM-005 is "confirmed," that 9.1 is
published, that the eval gate now scores real runs, or that
`CHK-guardrail-fp-budget` caught this (it cannot see these spans yet).

---

## Debug loop (do this, in order)

This is the loop we describe in publications. Do not skip to “add a check”
or “lower the threshold” before the human annotation.

### 0. Freeze the tree

Leave `workspace/<run_id>` and `output/runs/<run_id>` on disk. Copy
`/tmp/ai-team-bench-9.1/harness.out` next to the run if the process is
still writing:

```bash
cp /tmp/ai-team-bench-9.1/harness.out \
  output/runs/2026-09-13_182650_write-a-single-python-module_01/logs/harness.structlog.txt
```

When the process exits, snapshot `run.json` (expect `completed_at` or a
timeout/error). Kill only with a process-group kill if it is still up
past the intended 900 s — SIGALRM already failed.

### 1. Index the run-record tree (free)

Default backfill is the known bug (`evals/cli.py` `--workspace-root`
defaults to `./workspace`). Point it at records:

```bash
uv run python -m evals.cli trace backfill \
  --workspace-root ./output/runs \
  --limit 20
uv run python -m evals.cli index rebuild
uv run python -m evals.cli index stats
```

Expect: this id present; `span_count` still low; warnings `missing:
…/logs/phases.jsonl`. Record the stats in this folder (`stats.txt`) —
that is a `CORPUS` building block, not a publishable rate.

### 2. Sample unlabeled (still $0)

```bash
uv run python -m evals.cli sample --strategy unlabeled -n 20 --seed 1
# or failed-only / this backend:
uv run python -m evals.cli sample --strategy stratified -n 20 --seed 1 --backend langgraph
```

### 3. Open-code as a human (R3.7)

```bash
uv run python -m evals.cli annotate --sample <sample_id>
```

Rules from `EVAL_METHODOLOGY.md` / `evals/annotate.py`:

- No LLM suggestions, no FM ids in the UI, no “is this FM-005?” prompts.
- Note what you see: path error, relevance retries, nested dirs, empty Home.
- Tags are **invented** in this session (`qa-relevance-retry`,
  `workspace-parent-path`, `cli-not-in-session`, …).

### 4. Axial coding → taxonomy (only after 3)

```bash
uv run python -m evals.cli taxonomy propose --from-annotations
```

Then decide whether this is a new mode or a new **example** on FM-005 /
FM-008 / FM-010. Update `evals/taxonomy/failure_modes.yaml` only with a
human `trace_id` that exists in the index — not a fixture id.

### 5. Make the existing check able to see this run

Today `CHK-guardrail-fp-budget` looks for `spans_of("guardrail_check")`.
This run’s fails are `route_after_behavioral` lines in structlog. Work:

- Parse `journal.jsonl` / a harness-owned `guardrails.jsonl` into
  `guardrail_check` spans (`evals/trace/parsers.py`).
- Fill `run_id`, `backend`, `phase` on every ToolBus journal line.
- Write `phases.jsonl` from subgraph enter/exit in
  `src/ai_team/harness/telemetry.py` (eval-methodology-alignment Phase 1).
- Write `costs.jsonl` from the same OpenRouter `usage.cost` the spend
  guard already reads.

Until those land, **do not** claim CHK-guardrail-fp-budget “caught” this
run. It would `na` (no spans) or `na` (status ≠ complete).

### 6. Fix the harness, then replay

Fixes that this receipt justifies (smallest first):

1. **Score this turn, not last-12 history** — pass the subgraph *delta* into
   `concat_recent_ai_content`. Architect ADR + fullstack confirm + “wrote
   test_calc.py” must not fail QA scope.
2. **Don’t mark single-agent graphs as supervisors** —
   `planning.py` / `development.py` must not pass `behavioral_only_message_names`
   unless `create_supervisor` was used.
3. **Don’t treat behavioral fails as `retry_development`** — if `calc.py` +
   `test_*.py` exist, run the quality gate and route on pytest. A GuardrailError
   after a green (or even “files present”) gate should complete, not rewind.
4. **Testing path sandbox + one workspace root** — snapshot and QA prompt must
   use `get_workspace_dir()`, not `get_settings().project.workspace_dir`.
   Reject a leading `workspace/` segment on writes.
5. **Watchdog as `BaseException` or OS kill** — same pattern as
   `BudgetExceededError` / CrewAI subprocess kill. `except Exception` around
   `sub.invoke` must not eat it.
6. **LangGraph CLI `finalize()` + `emit_phase_end()`** — `costs.jsonl` and
   `phases.jsonl` on the same path the eval parsers already read.
7. **Home lists disk runs** — `useUnifiedRuns()` / `GET /api/registry/runs`.
8. **Backfill default** → `./output/runs`.

Replay the same smoke after (1)–(3). If it finishes under a few minutes
with `completed_at` set and pytest on `test_calc.py` green, 9.1 can use
*that* receipt. This run stays in the corpus as the **failure** example.

---

## What this run is not

- Not a 9.1 published benchmark (no cost log, `completed_at` null, HITL, 1600 s).
- Not a `CORPUS` pass rate (`n=1`, not indexed, not annotated).
- Not proof that DeepSeek is “bad at calc.py” — files were written in ~90 s.
- Not a reason to flip CI off `--warn-only`.

Claim rules remain [`EVAL_GATE_STATUS.md`](../../campaign/EVAL_GATE_STATUS.md):
every rate needs `n` and corpus kind. The publishable sentence is: **we
finally have a live LangGraph smoke with a path-sandbox crash and a
lexical guardrail retry storm, and the eval loop we already described
is how we will label and fix it.**

---

## Next sitting (human)

1. Process is **dead** (exit 1 at 14:53:26). Do not re-run against the same
   budget to get Dashboard shots.
2. Run debug-loop steps 1–3 (backfill `output/runs`, sample unlabeled, annotate).
   Budget: $0.
3. Only after an annotation line exists in `evals/annotations/` may we
   attach this `trace_id` to FM-005 (or a new tag) in the taxonomy YAML.
4. Then implement harness fixes 1–3, replay smoke, compare wall-clock to
   the 1.5 s bare call.
