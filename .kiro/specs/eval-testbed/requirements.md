# Requirements — Eval Testbed

**Spec ID:** `eval-testbed`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target repo:** `ai-team` (extends `src/ai_team/ui/web/`, `evals/`, `docs/course/`, `docs/`)
**Created:** 2026-09-14
**Budget:** ≤ **$20.00**, human-triggered, Phase 4 only — the teaching corpus. Every other
phase is $0.00.

**Depends on:** [`../eval-harness/`](../eval-harness/) — Trace boundary (R1), check registry
(R5), tiers (R11). [`../eval-methodology-alignment/`](../eval-methodology-alignment/) —
harness-owned telemetry (R1), corpus source (R5), human-and-unaided open coding (R7),
annotation ergonomics (R13). [`../eval-coverage/`](../eval-coverage/) — liveness (R2),
abstention (R3), feed-forward discipline (R14).
[`../eval-claim-surfaces/`](../eval-claim-surfaces/) — corpus-kind stamps (R2), staleness
(R8). [`../ui-refinement/`](../ui-refinement/) — token system, frozen testids.
**None of those are restated here.**

---

## Introduction

This repo describes itself as a live testbed for agentic harnesses. It is a testbed for one
person. The machinery is real — 13,000 lines of trace store, sampling, annotation,
clustering, alignment statistics and a $0 gate — and none of it is reachable by someone who
did not write it.

That was established by drafting a course for `docs/course/` and then auditing the course
against the repo. The finding was not that the writing was weak. It was that **the course
had to hand readers a 250-line toy harness, because the loop it teaches cannot be run on
this project.** The stranger's-path table in [`README.md`](./README.md) lists eight steps
and seven breaks, four of them before the reader reaches an eval.

### The funnel, as it exists

```
  clone  →  install uv  →  get an OpenRouter key  →  put credit on it  →  configure .env
         →  run a demo (~20 min, real money)  →  backfill the wrong tree  →  0 spans
         →  no viewer  →  no docs for adding a check  →  no delta  →  give up
```

Every arrow is a drop-off. The first paid arrow is the third one, and it arrives before the
reader has seen anything this project is good at.

### What this spec changes

```
  clone  →  install uv  →  run the loop on the corpus that shipped with it  →  $0.00
         →  browse traces  →  read thirty  →  cluster your codes  →  draft a mode
         →  write a check  →  re-run  →  see your number move
         →  (optional, later) produce a run of your own
```

The paid step moves to the end and becomes optional. That reordering is the spec.

### One decision carries most of the value

**Commit a real teaching corpus.** Not the 94 synthetic fixture files — those carry 72
distinct ids, roughly two spans each, and are named for the check each one exists to
trigger, so open-coding them teaches nothing about a real system. A corpus of redacted
traces from real runs, clearing the diversity floors this repo already defined, is what
makes every other requirement here reachable offline and for nothing.

---

## R1 — The whole loop runs with no API key and no spend

**User story.** As someone evaluating this project, I want to complete the error-analysis
loop before I am asked for a credit card, because the entry toll is where I currently stop.

### Acceptance criteria

1. A reader with a clone, `uv`, and **no API key** SHALL be able to complete every stage of
   the loop: build a corpus, browse traces, open-code, cluster, draft a failure mode, write
   a check, re-run the suite, and see the delta.
2. The documented first command SHALL NOT require a key, a network call, or spend. The
   current `docs/GETTING_STARTED.md` prerequisites checklist puts an OpenRouter key at step
   one; the eval path SHALL have its own entry that does not.
3. `AI_TEAM_OFFLINE=1` (or equivalent) SHALL make every eval-path command fail loudly rather
   than silently attempting a network call, so a keyless reader gets an explanation instead
   of a timeout.
4. Producing a run of one's own SHALL be documented as an optional later step, not a
   prerequisite, and its cost SHALL be stated before the command.
5. No requirement here SHALL weaken the existing spend guards or budget ceilings.

## R2 — A real teaching corpus ships with the repo

**User story.** As a reader, I want a corpus worth reading, because thirty synthetic
fixtures authored to trigger one check each teach me nothing about how agents fail.

### Acceptance criteria

1. The repo SHALL commit a teaching corpus of **≥100 traces** from real runs, distinct from
   `evals/fixtures/traces`, under its own root with its own manifest.
2. It SHALL clear the diversity floors already defined in `eval-methodology-alignment` R4:
   ≥3 backends, ≥4 scenario ids, ≥2 statuses, ≥14-day span.
3. It SHALL carry real spans of at least the types the loop's stages read: phase, tool,
   guardrail and interrupt. A corpus that clears the diversity floors while carrying no
   spans satisfies nothing — that is the state measured on 2026-09-14, where 229 of 324
   real runs had zero spans.
4. It SHALL be redacted by `evals/cli.py fixtures redact --lint` and SHALL pass that lint in
   CI. No key, token, path outside the repo, hostname, or customer string.
5. The manifest SHALL record, per trace, its provenance: which backend, which scenario,
   which date, and whether the run was real or reconstructed.
6. It SHALL be versioned, and its version SHALL appear in every report scored over it, so a
   reader can tell which corpus a number in a course or post came from.
7. It SHALL be stamped `CORPUS`, never `FIXTURE-ONLY` — and WHERE it does not clear a floor,
   the `NON-REPRESENTATIVE` stamp SHALL say which. The teaching corpus is held to the
   standard the repo publishes, not a lower one.
8. Traces whose runs ended in interesting failures SHALL be over-represented relative to
   their natural frequency, and the manifest SHALL say so. A teaching corpus is a curriculum,
   not a sample — and a reader who is told it is a sample would compute rates from it.

## R3 — One surface shows the loop as a loop

**User story.** As a reader, I want to see where I am in the process and what the next step
is, because a loop described in a document and executed through nine CLI commands is not a
loop I can follow.

### Acceptance criteria

1. There SHALL be one local surface presenting the loop's stages in order, showing for each:
   done, available, or blocked — and for blocked, **what it is waiting for and why**.
2. Stage gates SHALL be the ones already defined, not new ones: 30 unaided annotations before
   clustering, ≥1 accepted category before drafting a mode, a confirmed mode plus 100 labels
   before a judge. The workbench already implements these; this surface SHALL read the same
   thresholds from the same place rather than re-encode them.
3. It SHALL run locally with no key (R1) and SHALL start with one documented command.
4. It SHALL show loop state, not system health: days since the last annotation, floors met
   and unmet, judge eligibility, corpus kind. Reported, never gating.
5. It SHALL NOT display model output anywhere in the annotation path — `eval-harness` R3.7
   and `eval-methodology-alignment` R7.3 are unchanged and apply to every surface added here.
6. WHERE a stage is blocked on human work, the surface SHALL say that plainly rather than
   offering an automated alternative. The absence of a shortcut is a feature.

## R4 — Traces are browsable and readable

**User story.** As a reader, I want to open a trace and understand what happened, because
that is the activity the entire methodology rests on.

### Acceptance criteria

1. A trace list SHALL support filtering and sorting by backend, scenario, status, duration,
   span count, and whether it has been annotated.
2. A single trace view SHALL render, in a form suited to this domain rather than as a JSON
   dump: the phase timeline, the span sequence, generated artifacts, test output, and the
   run record. This restates the *form* requirement of `eval-methodology-alignment` R13.4
   for a browsing surface rather than an annotating one.
3. It SHALL show what the trace is **missing** — absent logs, absent spans, absent run-record
   fields — with the same prominence as what it has. A reader learning to spot a starved
   trace needs to see starvation rendered.
4. It SHALL show which checks decided on this trace, which abstained, and the abstention
   reason, per `eval-coverage` R13.4.
5. It SHALL be read-only. Nothing in the browsing path SHALL write to `evals/traces/`,
   `evals/annotations/` or `evals/golden/`.
6. Every trace SHALL be addressable by a stable local URL so a reader can cite one in a
   question, a post, or a bug report.

## R5 — Annotation costs one click to reach

**User story.** As the annotator — the reader or the owner — I want to start reading traces
without a five-command round trip, because the friction is the documented reason the
annotation directory is empty.

### Acceptance criteria

1. Reaching the annotation surface with a live sample SHALL take at most one action from the
   loop surface. The current path is `sample` → `annotate bundle` → drag a file → export →
   `annotate --batch-file`.
2. Exported annotations SHALL land in `evals/annotations/` as valid `AnnotationRecord` lines
   through the existing ingest path, without the reader running a separate command.
3. The no-model-output guarantee SHALL survive the change, and the test that scans the
   shipped HTML for failure-mode ids and taxonomy slugs SHALL still pass.
4. `AnnotationRecord` SHALL carry `unaided`, and the 30-record gate SHALL count genuinely
   unaided records rather than records — closing `eval-coverage` task 1b.7, which is correct
   only while the workbench is the sole writer and wrong the moment a second surface exists.
   **This spec creates that second surface, so the field is a prerequisite, not a follow-up.**
5. An interrupted sitting SHALL resume without losing work, and the record of record SHALL
   remain the repo, never browser storage.
6. Offline annotation SHALL remain possible. Whatever the loop surface adds, the
   dependency-free single-file path SHALL keep working.

## R6 — Adding a check is documented and scaffolded

**User story.** As a reader, I want to add my own check and watch it change a number,
because that is the moment I stop reading about the harness and start using it.

### Acceptance criteria

1. `docs/EXTENDING_EVALS.md` SHALL exist and SHALL carry a worked, runnable example from an
   observation to a merged check: the observation, the failure mode entry, the check, its
   three fixtures, and the report line it produces. **There is currently no documentation
   anywhere on how to add a check.**
2. `evals.cli checks new <slug>` SHALL scaffold a check module, a registry entry, and
   `__pass` / `__fail` / `__na` fixtures, each with a `TODO` a human must fill.
3. The scaffold SHALL set `origin: hypothesis` on any failure mode it creates and SHALL NOT
   offer a flag to set `open_coding`. Promotion requires an annotation record —
   `eval-coverage` R9, unchanged.
4. The scaffolded check SHALL declare the evidence it requires per `eval-coverage` R1, and
   the scaffold SHALL fail WHEN the declared span type has no parser, with the message
   explaining that a check reading a signal nothing writes can never fire.
5. The same document SHALL cover adding a failure mode without a check, and removing one.
6. It SHALL state plainly that a check is preferred to a judge wherever code can decide, and
   link the judge-validation bar rather than restating it.

## R7 — A change produces a visible, attributable delta

**User story.** As a reader, I want to see what my edit did, because "iterate" without a
before-and-after is just re-running.

### Acceptance criteria

1. `evals.cli run` SHALL support comparing a result against a named previous result and
   SHALL render the delta: checks whose outcome changed, rates that moved with both `n`s,
   liveness transitions, and stamps gained or lost.
2. The delta SHALL name **which** traces changed outcome, not only how many.
3. A delta SHALL distinguish "the system changed" from "the instrument changed" — a check
   moving from `blind` to `live` is not an improvement in the system under test, and
   rendering the two identically is the confusion this repo exists to name.
4. Re-running the same corpus with no edits SHALL produce an empty delta. This is the test
   that the delta means anything.
5. The delta SHALL be visible on the loop surface and in the CLI, from one computation.

## R8 — The loop is re-runnable and resettable

**User story.** As a reader, I want to get back to a known state after I break something,
because I will break something.

### Acceptance criteria

1. Every stage command SHALL be idempotent, or SHALL refuse and say what to remove.
2. A documented reset SHALL restore the corpus, annotations and results to the shipped state
   without touching `.env`, the reader's own runs, or anything under `output/runs/`.
3. Reset SHALL be explicit and SHALL NOT be a side effect of any other command.
4. WHERE a command would overwrite reader work — annotations especially — it SHALL refuse
   by default and require an explicit flag.

## R9 — The course becomes the lab manual

**User story.** As a reader, I want each idea followed immediately by the command that
demonstrates it on real data, because reading about error analysis is the failure mode this
whole project documents.

### Acceptance criteria

1. Each of the six sessions in `docs/course/` SHALL carry a **Do this** block: the command,
   the expected output against the shipped teaching corpus, and what to look at in it.
2. Expected outputs SHALL be generated from the shipped corpus and checked by CI, so a
   session cannot drift from what the command actually prints.
3. Session 3 SHALL walk the reader into the annotation surface on the teaching corpus and
   SHALL NOT substitute anything for the reading.
4. Session 6 SHALL reposition `minieval.py` as the bridge to the reader's **own** logs,
   after they have done the loop here — not as the takeaway in place of this project.
5. No session SHALL claim a capability the repo does not have on the day it is written. CI
   SHALL fail on a session whose **Do this** command exits non-zero.
6. The published page SHALL be rebuilt from the sessions only after R1–R7 are satisfied, and
   SHALL lead with what a reader can do rather than with what this project got wrong. The
   audit narrative SHALL appear as evidence, in one section, not as the opening.

## R10 — The testbed's own claims stay honest

**User story.** As a reader, I want the numbers this testbed shows me to be labelled,
because I am here to learn how to label numbers.

### Acceptance criteria

1. Every rate rendered on any surface added here SHALL carry its `n`, its corpus kind, and
   its stamps, per `eval-claim-surfaces` R2 and R3 — imported, never re-implemented.
2. The loop surface SHALL render abstention and liveness wherever it renders a rate.
3. No surface SHALL describe a failure mode as covered on the strength of a registered
   check; coverage claims cite liveness, per `eval-coverage` R11.5.
4. The teaching corpus's own state — what it clears, what it does not — SHALL be visible
   from the loop surface without a command.

## R11 — Evals never reach the agents

**User story.** As the owner, I want the new surfaces to be unable to leak eval results into
an agent's context, because a measurement that becomes a target stops measuring.

### Acceptance criteria

1. Nothing added here SHALL place a check result, liveness verdict, stamp or failure-mode id
   into any agent-facing path. `eval-coverage` R14 is unchanged and extends to every API
   endpoint, template and fixture added by this spec.
2. Product-gate results — pytest, ruff, runtime smoke — SHALL be unaffected.
3. CI SHALL fail WHEN eval vocabulary appears in an agent prompt, per `eval-coverage` R14.2.

## R12 — Test hygiene

**User story.** As a maintainer, I want a reader-facing surface tested at least as well as
the internals it exposes.

### Acceptance criteria

1. No test SHALL write to `evals/annotations/`, `evals/golden/`, `evals/traces/`, or the
   teaching corpus root. Tests SHALL use `tmp_path`.
2. Every refusal path added here SHALL reach 100% branch coverage: the offline guard, the
   overwrite refusals, the parser-less scaffold rejection, and each stage gate.
3. The loop surface SHALL have end-to-end coverage of the full path on the teaching corpus:
   browse → annotate → ingest → propose → scaffold → run → delta.
4. Frontend additions SHALL follow `ui-refinement`'s token system and SHALL register testids
   in `TESTIDS.txt`.
5. A CI job SHALL run the documented reader path start to finish on a clean checkout with
   **no API key set**, and SHALL fail if any step needs one. This is the only test that
   verifies R1, and R1 is the requirement the whole spec rests on.

---

## Constraints

| | |
| --- | --- |
| Location | `src/ai_team/ui/web/` (routers + frontend), `evals/`, `docs/`, `docs/course/`; one new corpus root; no new package |
| Cost | **$0.00 except Phase 4** (≤$20, human-triggered) to produce the teaching corpus |
| Keyless | the reader path never needs a key; CI proves it with no key set (R12.5) |
| No vendor | no Braintrust / LangSmith / Arize / DeepEval, consistent with the other four specs |
| One implementation per stamp | imported from `evals/coverage.py` per `eval-claim-surfaces` R2 |
| No model output in annotation | `eval-harness` R3.7, strengthened, never relaxed, on every surface |
| Evals never reach agents | `eval-coverage` R14, extended to new endpoints |
| Human work stays human | no surface offers to generate annotations, labels, or a taxonomy |
| Gates unchanged | stage thresholds are read from existing code, never re-encoded (R3.2) |
| Blocked | Phase 1 needs alignment Phase 1 + task 2.4 and claim-surfaces Phase 2 |

## Non-goals

- **Hosting it.** Local-first. A deployed multi-tenant version is a product, not a testbed,
  and it would put reader traces on someone else's disk.
- **Making the agents better.** This spec touches measurement and its surfaces. Harness
  fixes live in their own specs and are what the reader might contribute *after*.
- **A new eval framework.** The machinery exists; this is a finishing job. Adopting a second
  framework before the first has run on real data is the mistake the register in
  `docs/resources.md` and the external-tooling review already rejected twice.
- **Replacing the CLI.** The CLI stays the substrate and the scriptable path. The surface
  calls the same code.
- **Multi-annotator agreement.** A standing deviation, recorded in `eval-coverage`.
- **Doing the reading.** The reader's afternoon, and the owner's, remain theirs.
