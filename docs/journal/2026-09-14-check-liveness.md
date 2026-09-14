# 2026-09-14 — the checks that could not see, and a surface for the part that is human

**Session:** evening 2026-09-13 → 2026-09-14. Agent-assisted (Claude Opus 5).
**Base:** [`d483e61`](../eval-runs/2026-09-13-langgraph-smoke/README.md) — the live LangGraph smoke.
**Preceded by** [2026-09-13 (eval audit)](2026-09-13-eval-methodology-audit.md),
which left one carry-forward: re-index `output/runs/`, then read thirty traces by hand.

**Neither of those was done today, and that is the honest headline.** What was done is
the thing that turned out to sit underneath both: a measurement of whether the checks can
see anything at all, and a surface for the human step so that reading thirty traces stops
costing what it currently costs. Live next-steps list is §8; it supersedes the
"Next sitting" list in the smoke-run README, whose items 2–4 are carried forward intact.

---

## 1. Verdict

The corpus audit said the eval machinery had never been fed. That was true and it was
not the whole defect. Today's finding is that **feeding it would not have been enough**:
two span types have no producer anywhere in the codebase, so two checks are blind on
every corpus that will ever exist, and nothing in the repo reported that — because
`not_applicable` is absent from every headline, verdict, scorecard cell and incidence row
the harness renders.

## 2. What was found

Folded from the committed Tier A report `evals/results/tierA_4671d49ae035_eb36475d7c/report.json`
(taxonomy 1.2.0, 20 checks, 94 fixture documents):

| | |
| --- | ---: |
| check results | 1880 |
| `not_applicable` | **1435 (76.3%)** |
| `pass` | 263 |
| `fail` | 182 |

The published headline for that run is `FAIL — 182 failed check(s) across suite`. It is
accurate. It also omits that three quarters of the suite declined to answer, and 65 of
those 182 failures are a single check firing on fixtures that were never going to have
artifacts.

| Claim | Verified by | Consequence |
| --- | --- | --- |
| 11 of 20 checks are decided by one fixture pair | fold of the committed report | `1 pass / 1 fail` at 96–98% abstention is a unit test in a coverage table |
| `human_interrupt` has no parser | `evals/trace/` — literal appears only in `models.py`'s `SpanType` union | `CHK-interrupt-latency` (FM-003) cannot fire on any corpus |
| `error` has no parser either | same; `builder.py` maps an `"error"` *status*, which is not a span | `CHK-provider-error-rate` survives only because it reads `llm_call`/`retry` too |
| `guardrail_check` has no LangGraph producer | `langgraph_guardrail_nodes.py:273` logs `route_after_behavioral` to structlog; no `.jsonl` writer | FM-005 invisible on the path where the smoke run actually hit it |
| 5 span types are parsed and read by nobody | no mention outside `evals/trace/` | `qa_verdict`, `regression_check`, `session_start`, `subagent_start`, `subagent_stop` |
| `CHK-evaluator-capitulation` ignores the spans it needs | `verification.py:242–261` | it re-parses `qa_verdicts.jsonl` by hand, then abstains 92 times while typed spans sit unread |
| the fixture corpus double-counts itself | 94 files, **72 distinct `trace_id`** | `tier_a` globs filenames and scores both copies; `TraceStore.write` would refuse the duplicate |
| on the real corpus, 19 of 20 checks are blind | `coverage liveness` over `evals/traces/` | 50 traces, 0 spans, 0 artifacts, 95% abstention |

## 3. The thing worth naming on its own

**The 2026-09-13 smoke run demonstrates FM-003 and FM-005 simultaneously, and both of
their checks would abstain on it.** It ended in LangGraph `interrupt()` → `human_review`
after burning four behavioural-relevance retries at 5%, 0%, 9%, 0% against a 15% floor.

The smoke README already conceded this in prose — *"do not claim CHK-guardrail-fp-budget
'caught' this run"* — and that honesty was doing work instrumentation should have been
doing. A sentence in a handoff does not survive contact with a green CI badge; a row
reading `UNREACHABLE` does.

**Method note.** Found by reading, not by running: cross-referencing each check's
`spans_of()` calls against the span types any parser actually constructs. Nothing failed,
nothing errored, and the suite stayed green throughout. What would have caught it earlier
is the thing built today — any report that prints an abstention count would have shown
76% on day one.

## 4. What was built

| Path | Change | State |
| --- | --- | --- |
| `evals/coverage.py` | liveness fold, signal-chain inventory, `EVIDENCE-STARVED` stamp | committed `f883d75` |
| `evals/cli.py` | `coverage liveness`, `coverage signals`, `annotate bundle` | partly committed; `annotate bundle` uncommitted |
| `evals/ui/workbench.html` | four-stage error-analysis workbench, 1461 lines, no dependencies | **uncommitted** |
| `evals/ui/README.md` | how the loop closes, and what the page deliberately will not do | **uncommitted** |
| `tests/unit/evals/test_coverage.py` | 45 tests | committed `2279e1a` |
| `tests/unit/evals/test_annotate_bundle.py` | 26 tests — bundle shape, export/ingest, mirror parity | **uncommitted** |
| `tests/unit/evals/workbench/smoke.js` + `test_workbench_smoke.py` | 23 headless render assertions | **uncommitted** |
| `.kiro/specs/eval-coverage/` | 14 requirements, 11 phases, 54 tasks | R1–R12 committed; R13, R14, Phase 1b uncommitted |
| `docs/eval-runs/2026-09-13-check-liveness/` | the liveness tables and signal chain | committed `f883d75` |

`uv run ruff check` and `ruff format --check` clean on all five Python files;
`mypy` clean on `coverage.py` and `cli.py`. 73 of my tests pass; 379 pass across
`tests/unit/evals/`.

## 5. The spec, in one paragraph

[`.kiro/specs/eval-coverage/`](../../.kiro/specs/eval-coverage/README.md) — a sibling to
[`eval-harness`](../../.kiro/specs/eval-harness/),
[`harness-alignment`](../../.kiro/specs/harness-alignment/) and
[`eval-methodology-alignment`](../../.kiro/specs/eval-methodology-alignment/), restating
none of them.

The spec exists because the alignment spec fixes the eval system's **inputs** while
nothing fixes its **instruments**. Its fourteen requirements cover machine-readable
evidence declarations per check (R1), a liveness classifier whose `unreachable` verdict
ranks above `blind` because a broken chain is a code defect and a starved corpus is not
(R2), `not_applicable` as a first-class reported outcome (R3), a static signal-chain
inventory carrying the spec's one CI gate (R4), harness-owned guardrail and interrupt
telemetry that unblinds FM-005 and FM-003 (R5–R6), resolution of the five orphan signals
by consumption or deletion (R7), six new failure modes FM-019…FM-024 drawn from the
LangGraph smoke run and filed `origin: hypothesis` with a promotion path only a human
annotation can trigger (R8–R9), harness overhead measured against a bare-provider control
(R10), an `EVIDENCE-STARVED` stamp enforced by the renderer rather than asserted in prose
(R11), test hygiene (R12), per-run `check_results.json` in the run record rendered as
evidence and never as a score (R13), and a feed-forward rule keeping eval verdicts out of
every agent prompt — product-gate results still reach the agent, eval results reach only
the human and the corpus — with unmeasured dimension cells as the one safe automation
(R14).

**State: 8 of 62 tasks across 11 phases are done** — the liveness module and CLI, the
baseline artifact, and all of Phase 1b (workbench, `annotate bundle`, the export/ingest
round trip, mirror parity, the headless smoke test). Phase 5 is explicitly blocked on
`eval-methodology-alignment` Phase 1; everything else is planned and unexecuted.

R13 and R14 were not in the original draft. Both came from questions asked mid-session —
whether check results belong in the run record, and whether they should feed the next run.
The first is a straight yes and closes a real gap. The second is a yes with a boundary,
and the boundary is the more valuable half: it is written down now precisely because the
answer felt obviously affirmative at the time.

## 6. The workbench, and why it is not a dashboard

The first instinct was a coverage dashboard — the liveness numbers are the kind of thing
that looks good on a page. It would have been the wrong build. `eval-methodology-alignment`
R13 already says the annotation friction *is* the reason open coding never happened, and
`evals/annotations/` is still empty. A dashboard displaying how starved the corpus is
would have been one more artifact about the problem instead of a way through it.

So: four stages, gated in the order the source material puts them.

| Stage | Unlocks at |
| --- | --- |
| 1 · open code | always |
| 2 · axial code | 30 unaided records (R7.4) |
| 3 · taxonomy draft | ≥1 accepted category (R9.2) |
| 4 · judge | FM confirmed + 100 labels (R11.1, R12.3) |

The gates are the design. A locked stage says what it is waiting for and why, which puts
the discipline in the affordances rather than in a spec nobody re-reads at 11pm. Stage 4
is honestly empty and says so — nothing in this repo is judge-eligible.

Stage 2 turned out to fill a real hole rather than a cosmetic one: R8.3 requires a human
accept/merge/reject step between the clusterer and the taxonomy, `taxonomy propose` could
already cluster, and **there was nowhere for a human to decide.** The clustering in the
page is arithmetic — the same normalisation `propose.py` applies — not a model.

Stage 1 shows no suggestions of any kind. No slugs, no FM ids, no ranked guesses; reuse
appears only after you have invented a code yourself. `test_annotate_bundle.py` scans the
shipped HTML for FM ids and known slugs so that stays true when someone later decides a
little help would be harmless.

The loop closes through commands that already existed: `annotate bundle` exports a sample,
the page exports JSONL in the shape `run_batch_annotate` already accepts, and
`annotate --sample <id> --batch-file` ingests it. Verified end to end into a temp
annotations root — 3 records, valid `AnnotationRecord` lines, saturation computed.

The page re-implements three pure functions so it can preview what the CLI will compute.
Verified identical: `normalize_tag` on 20 cases including unicode and punctuation-only
input, `wilson_ci` to six decimal places, `saturation_streak` across seven sequences.

## 7. What did not change

- **The corpus.** Still 50 traces, 0 spans, 1 backend, `scenario_id: unknown`. Re-indexing
  `output/runs/` remains task 2.4 of `eval-methodology-alignment` and remains free.
- **Zero traces open-coded.** The workbench makes the sitting cheaper. It does not do it,
  and R7.6 says no affordance may exist that would.
- **`origin: hypothesis` stays out of coverage counts.** FM-019…FM-024 were added from the
  smoke run with evidence pointers and no annotation. A check firing does not promote them;
  only a human annotation does.
- **Judges remain advisory.** `eligible_to_gate: false`, 0 golden labels.
- **Tier A stays `--warn-only`.** Nothing today argues for flipping it; today's finding
  argues against, since a green suite now demonstrably means less than it appeared to.
- **Instrument liveness is not in the source material.** Husain and Shankar write about LLM
  application traces, where the trace *is* the model I/O and exists by construction. This
  is an extension for an agentic harness, recorded as such in the spec README rather than
  borrowing their authority.

## 8. Start next session with

**This list supersedes the "Next sitting" list in the smoke-run README.** Its items 2–4
(backfill, sample, annotate, then harness fixes 1–3 and replay) are carried forward as
items 3–5 below, unchanged in substance and now with a surface to do them on.

1. **Clear the stale git lock.** `rm -f .git/index.lock` — left by a `git stash` during a
   bridge drop. Git reads fine; it will block the next commit. *Done when `git commit`
   succeeds.* **Blocks everything else.**
2. **Commit the uncommitted half.** The workbench, its two test files, `annotate bundle`,
   and the R13/R14/Phase-1b spec additions. *Done when `git status` is clean.*
3. **Re-index `output/runs/`** (alignment task 2.4, $0). *Done when `index stats` shows
   ≥3 backends and a span greater than 69 days.* Until this lands the workbench will mostly
   render its "no spans — run-level only" panel, which is correct and not much use.
4. **Bundle 100 traces and read thirty.** `annotate bundle --sample <id> --out bundle.json`,
   open `evals/ui/workbench.html`, export, ingest. *Done when `evals/annotations/` holds ≥30
   records and stage 2 unlocks.* **Human only — this is the item that has now been carried
   for two sessions.**
5. **Then** harness fixes 1–3 from the smoke README (score the turn not the last-12 history;
   stop marking single-agent graphs as supervisors; stop routing behavioural fails to
   `retry_development`) and replay the same brief.
6. **Decide task 1b.6** — whether the node smoke test joins CI. Node is already present for
   the frontend. *Done when the workflow is edited or the task is closed with a reason.*
7. **Close task 1b.7** — `AnnotationRecord.unaided`. The page emits it, ingest drops it,
   because the field does not exist. The 30-record gate currently counts records rather
   than genuinely-unaided ones. Correct while this page is the only writer; wrong the
   moment anything else writes annotations.

**Owed by Rick:** items 1, 2, 4 and 6. Item 4 is not delegable by design.

## 9. Open questions

- **Does `CHK-listener-self-trigger` belong in the check registry at all?** It inspects
  `ai_team.core.flow_wiring` rather than a Trace, so its verdict is identical for every
  trace and its 83 fixture passes are 83 copies of one fact. R1.3 as written would reject it
  for declaring no evidence. Three options in design §9.6; leaning toward a `static: true`
  flag. **Decide before task 2.3**, which is where the declarations land.
- **Should `thin` suppress a green verdict the way `unreachable` does?** Leaning no while
  the corpus is starved, since that is already stamped. Revisit once the corpus clears its
  floors — a check still `thin` on a representative corpus is an instrument problem after all.
- **Is FM-024 (`harness_overhead_unbounded`) a failure mode or a cost?** 1000× a bare
  provider call on a smoke test feels like a failure of the harness's purpose, but the
  taxonomy is about failures. Left as `origin: hypothesis`, which defers it honestly: if
  open coding never produces it, it ages into `unobserved` and answers itself.
- **How far should "evals as living requirements" go?** Nothing in the four specs re-derives
  a requirement from a confirmed failure mode. Automating it puts the FM-014 problem one
  level up — a system writing its own acceptance criteria from its own measurements.
  Design §9.8. **No date set; not blocking.**

## 10. Two pre-existing defects noticed, not fixed

Both reproduce with this session's work stashed, so neither is new:

- `evals/arms/ablation_store.py:62` — `Incompatible return value type (got "str | None", expected "str")`
- `evals/report.py:407` — `Returning Any from function declared to return "str"`
