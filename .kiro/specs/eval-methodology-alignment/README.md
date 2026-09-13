# Spec: `eval-methodology-alignment`

Kiro-style three-document spec for closing the gap between the eval machinery this repo
has built and the error-analysis methodology it claims to follow. Read in order:

1. **[`requirements.md`](./requirements.md)** — 16 requirements with EARS acceptance
   criteria, one new failure mode (FM-018), constraints, and non-goals.
2. **[`design.md`](./design.md)** — harness-owned telemetry, honest backfill states,
   corpus diversity floors, the error-analysis session protocol, taxonomy provenance,
   and claim discipline (§8).
3. **[`tasks.md`](./tasks.md)** — 9 phases, 47 tasks, each with a definition of done and
   requirement traceability.

Builds on [`../eval-harness/`](../eval-harness/) (Trace boundary, check registry,
taxonomy, tiers, provenance) and [`../harness-alignment/`](../harness-alignment/) (arms,
ablation, FM-014…FM-017). Neither is restated here.

## The one-line version

Every stage of the error-analysis loop downstream of "look at your data" is implemented,
and **not one of them has ever seen real data**. Fix the source: make runs emit telemetry
the harness owns, build a corpus that is actually diverse, and do the human open coding
the taxonomy was supposed to come from.

## What the audit found

| Claim in the docs | What the repo actually holds |
| --- | --- |
| "Backfilled live corpus — 50 traces indexed" | 50 traces, **0 spans between them**, all `crewai`, all `scenario_id: unknown`, all `status: failed`, all created inside a **1.97-second window** on 2026-08-16 |
| "Error-analysis-first methodology" | `evals/annotations/` is **empty**. Zero traces open-coded. |
| Taxonomy FM-001…FM-017 | Derived from [`docs/posts/failure-taxonomy.md`](../../../docs/posts/failure-taxonomy.md), written from memory. **No FM traces to an annotation.** |
| "Judges … validated against human labels" | 1 judge prompt for 17 failure modes; golden set empty; alignment report `n: 0`, `eligible_to_gate: false` |
| Tier A "$0.00 per PR, checks green" | Scores **94 synthetic `__pass`/`__fail`/`__na` fixtures**. A green Tier A proves the check code works, not that `ai-team` works. |

## Root cause: two parts, neither of them in `evals/`

### 1. The corpus is built from the wrong tree

`trace backfill` defaults to `--workspace-root ./workspace`. That tree holds what the
**agents wrote** — 440 directories, 221 of them empty, the other 219 containing
generated `src/` and `tests/` and no telemetry at all.

What the **harness** wrote went somewhere else entirely:

| `./output/runs/` | count |
| --- | --- |
| dated run directories | **211** |
| `run.json` (backend, workspace_dir, completed_at, final_status) | **210** |
| `state.json` (actual cost, total tokens, monitor snapshot) | **141** |
| `logs/costs.jsonl` | **60** |
| `receipt.json` + `receipt.md` | **8** |

Backends recorded there: `langgraph` 148, `crewai` 1, `claude-agent-sdk` 1, unset 60.
Date range **2026-07-06 → 2026-09-13 — a 69-day span.**

So the corpus that was indexed as *50 traces, one backend, one scenario, one status,
1.97 seconds* could have been ~210 runs across three backends spanning 69 days, for
**$0.00**, on day one. Four of the five diversity floors in R4 were reachable from
disk the entire time. The eval harness has been reading the directory where the
generated code lands instead of the directory where the run records live.

### 2. Phase telemetry is requested from the model, not written by the harness

`phases.jsonl` is the file that yields the phase and retry spans the checks reason
over. Its only code writer is `src/ai_team/harness/context_pressure.py`, added
2026-09-12, which appends a single `phase_end` row when it records context pressure.
Otherwise it is asked for:

```
src/ai_team/backends/claude_agent_sdk_backend/agents/prompts.py:23
  7. Write phase transition entries to workspace/logs/phases.jsonl
```

**Zero `phases.jsonl` files exist under `workspace/` or `output/runs/`.** So even
pointed at the right tree, the corpus would be run-level only — statuses, costs and
durations, no trajectory. Note the contrast: `audit.jsonl` and `costs.jsonl` *do* have
real code writers (`tools/bus.py`, `core/results/writer.py`,
`claude_agent_sdk_backend/costs.py`). Phase telemetry is the one signal left to a
prompt, and it is the one every trajectory check depends on.

The honest statement of the gap is therefore not "we haven't done error analysis yet,"
and not "we logged nothing." It is: **the harness logged plenty, into a tree the eval
corpus never looks at, and left the one signal the checks need to an instruction the
model was free to ignore.**

## Sources it aligns with

| Source | What it supplies |
| --- | --- |
| [Why AI evals are the hottest new skill for product builders](https://www.lennysnewsletter.com/p/why-ai-evals-are-the-hottest-new-skill) — Hamel Husain & Shreya Shankar, Lenny's Podcast | The loop: traces → open coding → axial coding → count → judge. The benevolent dictator. Theoretical saturation. Binary verdicts. "LLMs can't replace humans in the initial error analysis." |
| [Hamel Husain, *AI Evals FAQ*](https://hamel.dev/blog/posts/evals-faq/) | ~100 diverse traces as the working pool; ≥30 annotated unaided before agent assist; 100–200 labeled examples per judged failure mode; TPR **and** TNR, never accuracy; generic metrics as a sampling signal and never a quality claim; build the annotation tool yourself; re-run analysis every 2–4 weeks; "60–80% of development time on error analysis and evaluation." |

The methodology is not new to this repo — `docs/EVAL_METHODOLOGY.md` already cites it and
`evals/annotate.py` already refuses to show LLM suggestions (R3.7). This spec is not a
change of direction. It is the part that was deferred, and the instrumentation work that
turns out to gate it.

## Why instrumentation is phase zero

```
  harness owns the logs →  corpus reads the right tree →  human open-codes 100  →  axial
        (Phase 1)                  (Phase 2)                    (Phase 4)        (Phase 5)
                                                                             ↓
   judges earn their FMs  ←  labels reach 100–200/FM  ←  taxonomy re-derived
        (Phase 7)                  (Phase 6)                 (Phase 5)
```

Everything to the right of Phase 1 is already built. `evals/sampling.py`,
`evals/annotate.py`, `evals/taxonomy/propose.py`, `evals/golden.py`, `evals/alignment.py`,
`judge align`, `judge validate`, split discipline, bias correction, Wilson intervals — all
of it exists, is typed, and is tested. It has been starved, not missing.

Which makes this the cheapest spec of the three: **most of the work is deleting the
excuse, not building the tool.** Task 2.4 alone — re-index `output/runs/` instead of
`workspace/` — is a one-argument change that takes the corpus from 1 backend and a
1.97-second span to 3 backends and 69 days, for nothing.

## New failure mode

| ID | Slug | Layer | Check |
| --- | --- | --- | --- |
| FM-018 | `self_reported_telemetry` | harness | `CHK-telemetry-provenance` |

A run whose phase, cost, or tool records were written by the agent rather than by the
harness. Deterministic, Tier A, $0.00, and scoreable retroactively over every trace the
corpus already holds — which will mark all 50 of them.

FM-018 is the reason FM-016 (`self_graded_verification`) does not go far enough. FM-016
catches an agent grading its own work. FM-018 catches an agent *reporting* its own work —
the weaker and more corrosive version, because it silently degrades every measurement
built on top of it rather than producing a visibly wrong verdict.

## Constraints baked in

| | |
| --- | --- |
| Location | extends `src/ai_team/harness/`, `evals/trace/`, `evals/annotate.py`; no new package |
| Telemetry | **harness-owned**: written by harness code on the call path, never by agent instruction; the prompt line is deleted, not supplemented |
| Corpus source | run records under `output/runs/`, joined to `workspace/<run_id>/` for artifacts — never the workspace tree alone |
| Backfill | a trace with zero spans is `unindexable`, never `failed` — absence of evidence is not evidence of failure |
| Corpus floor | ≥100 traces, ≥3 backends, ≥4 scenario ids, ≥2 statuses, spanning ≥14 days; below any floor the corpus is stamped `NON-REPRESENTATIVE` |
| Open coding | human, single annotator, ≥30 unaided before any agent assist; `taxonomy propose` may cluster, never label |
| Judges | an FM earns a judge only after it survives a prompt fix and reaches ≥100 labels; below that it stays `detection: check` or `manual` |
| Claim discipline | fixture pass rates render as `FIXTURE-ONLY`; corpus rates carry `n`, Wilson CI, and the diversity stamp |
| Spend | ≤ **$15.00** total: ≤$10 to re-run scenarios for a diverse corpus, ≤$5 for judge align/validate. Additive to the eval-harness $5 and the ladder $25. |
| Out of scope | multi-annotator κ, online/production monitoring, vendor eval platforms, RAG evals, changing any existing check's semantics |

## Minimum defensible slice

**Phases 1, 2, and 4.** Harness-owned telemetry, a corpus that clears the diversity floor,
and 100 traces open-coded by a human. That alone converts the project's central claim —
"we measure our failures" — from scaffolding into a number.

If even that is too long: **Phase 1 plus task 4.2**. Instrument the runs, then annotate 30
of them yourself. Thirty traces read by hand will tell you more about what to build next
than the other eight phases combined, and that is the finding the source material is
actually about.

## Executing this with Cursor

```
Read .kiro/specs/eval-methodology-alignment/requirements.md and design.md for context.
Implement task 1.2 from .kiro/specs/eval-methodology-alignment/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

Phases 0–3 and 5–8 are free and safe to run unattended. **Phase 2.5 (corpus re-runs) and
Phase 7 (judge align/validate) spend money** and are human-triggered with ceilings.
**Phase 4 cannot be delegated to an agent at all** — that is the entire point.
