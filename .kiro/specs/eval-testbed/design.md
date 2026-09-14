# Design — Eval Testbed

**Spec ID:** `eval-testbed`
**Reads with:** [`requirements.md`](./requirements.md). Unprefixed requirement ids are this
spec's; others are named — `alignment R13.4`, `coverage R14`.

---

## 1. The shape of the change

Three deliverables and a repositioning.

```
  DATA       evals/corpus/teaching/           a real, redacted, span-bearing corpus
                                              + manifest.json + VERSION

  SURFACE    src/ai_team/ui/web/              /loop /traces /traces/<id> /annotate /report
             routers/evals.py                 read-only over the corpus + results

  EXTENSION  docs/EXTENDING_EVALS.md          observation → mode → check → fixtures → line
             evals.cli checks new             scaffold with TODOs a human must fill
             evals.cli run --against          the delta

  MANUAL     docs/course/session-*.md         each session gains a "Do this" block
```

No new package, no second framework. Every surface calls the CLI's own functions.

## 2. Where the loop surface lives, and why

Three candidates were considered.

| Option | For | Against |
| --- | --- | --- |
| Extend the React app | A server already reads runs; router + page conventions exist; `ui-refinement` tokens and testids apply; it can read the corpus from disk | Needs a running process; the app currently has **zero** eval surface, so this is new ground |
| Grow `workbench.html` | Zero infrastructure; offline; already gate-aware | A single file cannot list a 100-trace corpus, score a suite, or compute a delta without a server |
| A third surface | Clean slate | Three surfaces for one loop; the fragmentation is the problem |

**Decision: extend the React app, and serve the workbench from it.**

The app becomes the loop surface. The workbench stays exactly one file and gains a second
entry point: served at `/annotate`, hydrated from `GET /api/evals/bundle?sample=<id>`
instead of drag-and-drop, and posting to `POST /api/evals/annotations` instead of a file
download. Same HTML, same gates, same no-model-output test scanning the same shipped file.

This satisfies R5.1 (one action to reach annotation) without giving up R5.6 (the
dependency-free offline path), because the file still opens from `file://` and still accepts
a dragged bundle when no server is there. One file, two entry points, one guarantee.

### 2.1 Why not port annotation into React

It would mean two implementations of the no-suggestions rule, and the test that protects it
scans the shipped HTML. Two implementations of that rule is how the rule eventually gets a
"helpful" exception — which is the FM-014 shape one level up, and the reason the docstring
warning about it exists in `evals/annotate.py`.

## 3. The API

One router, `src/ai_team/ui/web/routers/evals.py`, read-only except the annotation POST.

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/api/evals/loop` | stage states, gates, what each blocked stage waits for |
| GET | `/api/evals/traces` | filtered, sorted trace list + `CorpusProfile` + stamps |
| GET | `/api/evals/traces/{id}` | one trace: timeline, spans, artifacts, test output, **missing** |
| GET | `/api/evals/traces/{id}/checks` | per-trace check results with `na_reason` |
| GET | `/api/evals/bundle` | an annotation bundle for a sample |
| POST | `/api/evals/annotations` | ingest `AnnotationRecord` lines through the existing path |
| GET | `/api/evals/report` | latest `SuiteReport` + coverage + stamps |
| GET | `/api/evals/report/delta` | delta against a named previous result |

Every endpoint delegates to functions already in `evals/` — `TraceStore`, `coverage.py`,
`aggregate.py`, `annotate.run_batch_annotate`. **The router holds no eval logic**, so the
CLI stays the substrate and the two cannot disagree. A test asserts each endpoint's payload
matches the CLI's output for the same inputs.

### 3.1 The one write path

`POST /api/evals/annotations` is the only mutation, and it calls the same ingest the CLI
calls. It refuses to overwrite an existing record without an explicit flag (R8.4), and it
sets nothing itself — `unaided` comes from the client, and the client is the workbench,
which knows whether it showed the annotator anything.

## 4. `unaided` is a prerequisite, not a follow-up

`AnnotationRecord` has no `unaided` field. The workbench emits one; ingest drops it. The
30-record gate therefore counts *records*, which is correct only while the workbench is the
only writer.

**This spec adds a second entry point to that writer, so the field has to land first.**
It is `eval-coverage` task 1b.7, and it is promoted here from a loose end to a Phase 0
blocker. A gate that counts the wrong thing is worse than a gate that is missing, because
it reports a number.

## 5. The teaching corpus

```
evals/corpus/teaching/
  VERSION            semver; appears in every report scored over this corpus
  manifest.json      per trace: backend, scenario, date, status, span types, provenance,
                     redaction pass, and why it was selected
  traces/*.json      ≥100 redacted traces
  README.md          what it is, what it is not, and the floors it clears
```

### 5.1 Selection is a curriculum, and the manifest has to say so

R2.8 requires interesting failures to be over-represented and the manifest to admit it. This
is the sharpest honesty problem in the spec: a curated corpus is the right pedagogy and the
wrong sample. A reader who computes a rate from it gets a number about the curriculum, not
about the system.

Three mechanisms, because prose will not hold:

1. `manifest.json` carries `selection: curated` and a per-trace `selected_because`.
2. Every report scored over it renders **`CURATED`** alongside its corpus kind — a fourth
   stamp, orthogonal to the three in `eval-claim-surfaces`, meaning *the denominator was
   chosen, not sampled*.
3. Rate rendering over a `CURATED` corpus suppresses the percentage and shows counts only.
   A curated corpus can teach you to *see* a failure mode; it can never tell you how often
   one happens, and the renderer should make that impossible rather than discouraged.

Point 3 is the one that costs something and the one worth keeping.

### 5.2 Where the traces come from

`output/runs/` after alignment task 2.4 — 324 run dirs, 4 backends, a 69.8-day span. Two
gaps measured on 2026-09-14:

- **229 of 324 runs carry zero spans.** Only 95 are usable as trace material today. So the
  corpus needs either alignment Phase 1's telemetry landing first and then fresh runs, or
  Phase 4's budgeted runs to fill the gap. This is why Phase 1 is blocked and Phase 4 spends.
- **`extra.final_status` is present in only 94 of 308 `run.json`**, all reading `complete`.
  214 runs never finalised. Any indexer must read one level into `extra` — a top-level-only
  reader concludes the field does not exist, which is exactly how this spec's author
  initially mis-measured it.

### 5.3 Redaction

`fixtures redact --lint` already exists and runs in CI over `evals/fixtures`. It extends to
the teaching root unchanged. A corpus this repo publishes for strangers gets the stricter
read: absolute paths outside the repo, hostnames, usernames and project names go too, not
only secrets.

## 6. Trace rendering: absence is content

R4.3 is the design idea in this spec most likely to be dropped as polish, so the mechanism
is specified rather than the intent.

A trace view has two columns of equal weight:

```
  WHAT HAPPENED                        WHAT IS MISSING
  phase timeline (4 phases)            phases.jsonl        absent
  14 tool spans                        costs.jsonl         absent
  2 guardrail decisions                run record          completed_at: null
  test output: exit 5, 0 collected     writer attribution  no span carries `writer`
```

The right column is built from the trace's own `warnings` plus the `na_reason` codes of
checks that abstained on it. A reader learning to spot a starved trace has to see starvation
rendered with the same typographic weight as content, because in the source material the
absence is the finding.

## 7. The delta, and the distinction that matters

R7.3 requires a delta to separate *the system changed* from *the instrument changed*. Same
arithmetic, opposite meanings:

| Transition | Means | Category |
| --- | --- | --- |
| `fail` → `pass` on a trace | the system under test behaves differently | system |
| `blind` → `live` for a check | the instrument can now see | instrument |
| `na` → `fail` | the instrument can now see, and what it sees is bad | instrument, then system |
| rate moved, `n` moved too | the denominator changed | neither — say so |

The renderer groups by category and labels each group. The fourth row is the one that
silently misleads today: a rate moving because the denominator moved is not a finding, and
it is the most common thing a delta will show while a corpus is being built.

## 8. Docs: two entry points, one for each reader

`docs/GETTING_STARTED.md` opens with an API key because its subject is running the agents.
That is correct for that document and wrong for this spec's reader.

**`docs/EVAL_QUICKSTART.md`** becomes the keyless entry: clone, `uv sync`, one command, the
loop surface on the shipped corpus. It links to `GETTING_STARTED` for the optional paid step
rather than inheriting its prerequisites. `README.md` offers both paths at the same
prominence with the cost of each stated.

`docs/EXTENDING_EVALS.md` is the third document and the cheapest high-value item in the
spec: the extension point of a 13,000-line harness is currently undocumented.

## 9. Order of operations

```
  Phase 0  keyless entry, unaided field, EVAL_QUICKSTART      free, unblocked
  Phase 1  teaching corpus                                    BLOCKED: alignment P1 + 2.4
  Phase 2  EXTENDING_EVALS + checks new + delta                free, unblocked
  Phase 3  trace browser + loop surface + API                 needs a corpus; usable on any
  Phase 4  fill corpus gaps — SPENDS ≤$20, human-triggered
  Phase 5  annotation in the surface                          needs Phase 0's unaided field
  Phase 6  course becomes the lab manual                      needs Phases 1-3
  Phase 7  rebuild and publish the page                       needs everything above
```

Phases 0 and 2 are the minimum that changes a reader's experience, and neither is blocked.

## 10. Open decisions

**10.1 Does the loop surface ship in the existing app or as a separate mode of it?** The
app's current job is watching a run. Adding the loop makes it two products behind one nav.
Leaning one app with two top-level sections, because a reader who runs the agents later
should not meet a second tool. **Decide before task 3.2.**

**10.2 How many traces does the teaching corpus actually need?** R2.1 says ≥100 to match the
methodology's pool. But the reader reads thirty, and 100 redacted traces is a large commit.
Leaning ≥100 indexed with a ~40-trace curated reading set named in the manifest, so the
corpus clears its floors while the reading set stays honest about being curated. **Decide
before task 1.1.**

**10.3 Should the `CURATED` stamp suppress percentages entirely (§5.1 point 3), or only
outside the course?** Leaning entirely. A course that shows percentages over a curated
corpus while telling readers not to trust percentages over curated corpora teaches the
opposite of its content. **Decide before task 1.4** — it changes the renderer.

**10.4 Does the reader path CI job (R12.5) run on every PR or nightly?** Every PR is honest
and adds minutes; nightly risks the keyless path breaking for a day. Leaning every PR, since
it is the requirement the spec rests on. **Decide before task 0.4.**

**10.5 Is `minieval.py` still worth shipping once the loop runs here?** Its role narrows to
"do this on your own logs." That is a real role, and it is also 500 lines to maintain for a
bridge. Leaning keep, because it is the one artifact a reader can use without adopting this
project at all, and that is worth something on its own. **Revisit after Phase 6.**

**10.6 Does the published page get a reader-facing changelog?** A course whose commands are
CI-checked against a versioned corpus will drift visibly. Leaning yes, one line per change,
because a teaching asset that silently changes is the claim-travelling problem again.
**Not blocking.**
