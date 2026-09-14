# Spec: `eval-testbed`

Kiro-style three-document spec for making this repo a testbed **someone else** can run.
Read in order:

1. **[`requirements.md`](./requirements.md)** — 12 requirements with EARS acceptance criteria,
   the stranger's-path audit, constraints and non-goals.
2. **[`design.md`](./design.md)** — where the loop surface lives, the corpus package, the
   annotation-without-round-trip decision, and six open decisions (§10).
3. **[`tasks.md`](./tasks.md)** — 8 phases (0–7), 39 tasks, each with a definition of done
   and requirement traceability.

Builds on [`../eval-harness/`](../eval-harness/) (Trace boundary, checks, tiers),
[`../eval-methodology-alignment/`](../eval-methodology-alignment/) (telemetry writer, corpus
source, human open coding), [`../eval-coverage/`](../eval-coverage/) (liveness, abstention),
[`../eval-claim-surfaces/`](../eval-claim-surfaces/) (corpus-kind stamps, staleness) and
[`../ui-refinement/`](../ui-refinement/) (tokens, testids). **None are restated.**

## The one-line version

The repo calls itself a live testbed for agentic harnesses. It is a testbed **for its
author, on his machine, with his data.** This spec is the difference.

## Why this spec exists

A course was drafted for `docs/course/` and a page published from it. Reviewing both
against the repo produced a finding that invalidates the approach rather than the prose:

> The course teaches the loop and then hands the reader a 250-line toy, because **the
> reader cannot run the loop on this project.** Not "it is undocumented" — the path is
> broken in seven places, four of them before the reader reaches an eval.

A course that routes people *away* from the testbed is an admission the testbed is not
usable. The fix is not better writing. It is the seven fixes below.

## The stranger's path, audited 2026-09-14

Every row verified against the working tree, not inferred.

| # | What they try | What happens | Evidence |
| --- | --- | --- | --- |
| 0 | Install and run once | **Needs an OpenRouter key and real credit.** No keyless or replay mode exists at the app level. | `docs/GETTING_STARTED.md:9` puts the key in the prerequisites checklist; no mock/replay gate in `config/settings.py` or `main.py` |
| 1 | Build a corpus | `trace backfill` defaults to `./workspace` → traces with **0 spans** | `evals/cli.py`; the 2026-09-13 audit |
| 2 | Expect spans in it | Pointed at the right tree, **229 of 324 runs still carry zero spans**; `CHK-writer-is-code` is BLIND | measured 2026-09-14 over `output/runs/` |
| 3 | Look at a trace | **There is no trace viewer.** The React app has no eval surface at all — no `/api/traces`, and zero references to traces, checks or FM ids in any component | `src/ai_team/ui/web/routers/`, `frontend/src/` |
| 4 | Open-code thirty | Workbench exists and is good, but reaching it is `sample` → `annotate bundle` → drag a JSON file → export → a fifth CLI command to ingest | `evals/ui/README.md` |
| 5 | Add or tweak a check | **Zero documentation.** No scaffold, no worked example, no "how to add a check" anywhere in `docs/` or `evals/README.md` | grep across `docs/*.md`, `evals/README.md` |
| 6 | Re-run and see what changed | Tier A runs, but nothing shows a **delta**, and the report still hides 76% abstention | `evals/report.py`; [`../eval-claim-surfaces/`](../eval-claim-surfaces/) |
| 7 | Know where they are in the loop | Nothing reports loop state. `index stats` prints four columns of counts | `evals/cli.py:79` |

Four of the eight breaks happen **before the reader reaches an eval at all**. The one that
matters most is row 0: the funnel opens with "get an API key and put money on it."

## What "usable by someone else" actually requires

Three things, in dependency order. Everything else is polish.

```
  1. DATA        a real, diverse, span-bearing corpus ships with the repo
                 → the whole loop runs at $0 with no key, on day one

  2. SURFACE     one local app that shows the loop as a loop:
                 browse traces → annotate → propose → check → re-run → see the delta

  3. EXTENSION   a documented, scaffolded way to add a check or a failure mode
                 and watch your own change move a number
```

Today the repo has none of the three. It has the *machinery* underneath all three, which
is why this is a finishing job rather than a rebuild.

## The keyless corpus is the whole unlock

One decision carries most of the value: **commit a real teaching corpus.**

Not `evals/fixtures/traces` — that is 94 synthetic files carrying 72 distinct ids, about
two spans each, named `__pass` / `__fail` / `__na`. Open-coding them teaches nothing about
a real system, because each one was authored to make exactly one check fire.

A teaching corpus is redacted traces from **real runs**: ≥100 traces, ≥3 backends, ≥4
scenarios, ≥2 statuses, ≥14-day span, with phase, tool, guardrail and interrupt spans. With
that committed, a stranger clones the repo and does the entire error-analysis loop —
including the afternoon of reading that the methodology says is the point — for **$0.00,
with no key, offline**. Producing a run of their own becomes an optional later step rather
than the entry toll.

This also fixes the credibility problem in one move. The repo currently ships a starved
corpus and a spec explaining why. It would ship a corpus that clears its own floors.

## Dependencies — this spec is genuinely blocked

Unlike the other four, this one cannot be front-loaded:

| Needs | From | Why |
| --- | --- | --- |
| Harness-owned telemetry | `eval-methodology-alignment` Phase 1 | no writer → no spans → nothing to browse, annotate or check |
| `output/runs/` as corpus source | `eval-methodology-alignment` task 2.4 | the corpus has to come from the tree the records are in |
| Corpus-kind + abstention rendering | `eval-claim-surfaces` Phase 2 | a teaching testbed that ships misleading reports teaches the defect |

**Phase 1 of this spec is blocked on all three.** Phases 0, 2 and 6 are free and can start
now. The honest sequencing is in [`tasks.md`](./tasks.md).

## Minimum defensible slice

**Phase 0 plus Phase 2 plus tasks 3.1–3.4.** A keyless replay path, the check-authoring
docs and scaffold, and a trace browser over whatever corpus exists. That alone turns "read
about the loop" into "run the loop," and none of it needs the teaching corpus to be perfect.

If even that is too long: **task 2.1** — write `docs/EXTENDING_EVALS.md`. The extension
point of a 13,000-line eval harness is currently undocumented, and that is the single
cheapest thing standing between this repo and someone else using it.

## What this does to the course

`docs/course/` stops being a course *about* evals and becomes the **lab manual for this
testbed**: each session keeps its idea and its receipt, and gains a command to run against
the shipped corpus plus the output to expect. `minieval.py` changes role — it is no longer
the takeaway prize, it is session 6's bridge to the reader's own logs, which is where a
250-line file belongs.

**Nothing is published until the loop runs.** The drafted page stays private. Publishing a
course that promises a loop the project cannot deliver would be this repo's signature
defect performed on purpose: the claim travelling without the label.

## Executing this with Cursor

```
Read .kiro/specs/eval-testbed/requirements.md and design.md for context.
Implement task 2.1 from .kiro/specs/eval-testbed/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

Phases 0, 2, 6 and 7 are free. Phase 1 is blocked. Phase 4 spends (≤$20, human-triggered)
and is the only task set in any of the five specs whose output is meant for strangers.
