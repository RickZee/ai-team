# Spec: `eval-claim-surfaces`

Kiro-style three-document spec for the three free fixes that stop this repo teaching its own
defects. Read in order:

1. **[`requirements.md`](./requirements.md)** — 11 requirements with EARS acceptance criteria,
   constraints, and non-goals.
2. **[`design.md`](./design.md)** — where each field lands, the one-stamp rule, the
   `na_reason` vocabulary, schema/baseline compatibility, and four open decisions (§9).
3. **[`tasks.md`](./tasks.md)** — 4 phases, 26 tasks, each with a definition of done and
   requirement traceability.

## What this spec owns, and what it only sequences

This is a **slice spec**. Almost every fix in it already has a requirement home:

| Fix | Owning requirement | Owning task |
| --- | --- | --- |
| Corpus source is the run-record tree | `eval-methodology-alignment` R5 | alignment 2.4 |
| Corpus-kind on every rate | `eval-methodology-alignment` R15.1–R15.2 | alignment 8.3 |
| Generic metrics demoted | `eval-methodology-alignment` R15.3 | alignment 8.4 |
| Dated tables + 30-day CI warning | `eval-methodology-alignment` R15.4 | alignment 8.5 |
| Staleness in `index stats` | `eval-methodology-alignment` R14.3–R14.4 | alignment 8.1 |
| Cadence written down | `eval-methodology-alignment` R14.1–R14.2 | alignment 8.2 |
| `not_applicable` first-class | `eval-coverage` R3 | coverage 4.1–4.3b |
| `EVIDENCE-STARVED`, verdict suppression | `eval-coverage` R11, R2.4–R2.6 | coverage 4.4–4.6 |

**None of those are restated.** This spec references them and puts them in one executable
order. It owns exactly two things nothing else owns:

- **R1** — that no tracked document may present a command whose result the repo already knows
  to be wrong. `README.md:337` and `evals/README.md:12` both still tell a new reader to run
  `trace backfill --workspace-root ./workspace`, which is the exact invocation the
  2026-09-13 audit identified as the root cause. The quickstart reproduces the bug.
- **R2** — that `FIXTURE-ONLY` / `CORPUS` / `LIVE` and `EVIDENCE-STARVED` get **one**
  implementation, in `evals/coverage.py`, consumed by `evals/report.py`. Both already exist
  there as of `f883d75`. Alignment 8.3 and coverage R11.2 would each satisfy independently by
  writing their own, and two stamp implementations that disagree is worse than none.

## The one-line version

`eval-methodology-alignment` fixes the inputs. `eval-coverage` fixes the instruments. This
fixes the **surfaces** — the three places a human meets the eval system and currently learns
something false from it: the quickstart, the report, and the absence of a clock.

## Why these three, and why now

All three are **$0.00**, none is blocked on `harness/telemetry.py`, and each one removes a
specific false lesson that survives every future improvement:

| Surface | What it teaches today | Evidence |
| --- | --- | --- |
| Quickstart | "point backfill at `./workspace`" | `README.md:337`, `evals/README.md:12` — the audited root cause, still the documented path |
| Report | "FM-006 occurs at 0.976 (n=84)" | `evals/results/tierA_4671d49ae035_eb36475d7c/report.md` §4 — fixture arithmetic rendered with a Wilson CI and no corpus stamp |
| Cadence | nothing; there is no clock | `index stats` prints `backend/scenario/status/count` and nothing else; `EVAL_METHODOLOGY.md` describes a loop with no rhythm |

The report is the sharpest. A reader — including the author six months out — sees seventeen
failure-mode rates with confidence intervals and reasonably concludes the system has been
measured. What the table actually reports is that 20 checks behaved as written against 94
synthetic fixture documents carrying 72 distinct ids, with 76.3% of results abstaining. Every
number is correct. The composition is a claim nobody made on purpose.

## The asymmetry that makes this worth doing before the corpus lands

Fixing the corpus makes the numbers *true*. It does not make them *readable*, and a true
number rendered the current way is more dangerous than a false one, because the corpus stamp
is the only thing that would have told a reader which they were looking at.

```
  today          FIXTURE-ONLY data  →  unstamped renderer  →  reader infers a measurement
  after 2.4      CORPUS data        →  unstamped renderer  →  reader infers a measurement
                                                              and is right for the wrong reason
```

The renderer has to learn to say which corpus it read before the corpus changes underneath it,
or the change is invisible at exactly the moment it matters most.

## Scope decision (2026-09-14)

Asked and answered: **full honest renderer**, not the minimal stamp. That means all of
`eval-coverage` Phase 4 — `na_count`, `n_decided`, all 17 FM rows carrying `liveness`,
distinct-`trace_id` counting, `EVIDENCE-STARVED` at the 50% threshold, headline
blind/unreachable counts, verdict suppression, and the liveness table printed in CI — plus
alignment 8.3 and 8.4. Rationale: the stamp alone tells a reader the corpus is fixtures while
still showing them `0.976 (n=84)` over a corpus of 72 distinct traces. The denominator defect
and the stamp defect are the same defect seen twice; splitting them ships half a fix and
leaves the more misleading half in place.

## Constraints baked in

| | |
| --- | --- |
| Location | extends `evals/aggregate.py`, `evals/report.py`, `evals/coverage.py`, `evals/cli.py`, `evals/store.py`, `docs/`; no new package |
| Cost | **$0.00.** Every task is offline, deterministic, and runs on the corpus already on disk. |
| One implementation per stamp | corpus kind and `EVIDENCE-STARVED` live in `evals/coverage.py` and are imported, never re-derived (R2) |
| No vendor | no Braintrust / LangSmith / Arize / DeepEval, consistent with the other four specs |
| Renderer-enforced, never prose | every stamp is a computed field with a test, not a sentence in a markdown file (R2.5) |
| Determinism preserved | `tests/integration/evals/test_tier_a_integration.py` compares two runs to each other; every field added here SHALL be deterministic (R10.2) |
| Staleness never gates | R8.4, following alignment R14.4. The one CI gate is R1.5's doc-command audit, and it fails on a known-wrong command, not on a data state. |
| Evals never reach agents | unchanged from `eval-coverage` R14 — nothing here puts a rate, stamp or FM id into an agent-facing path |
| Out of scope | the telemetry writers, the re-index implementation, the human annotation pass — see Non-goals |

## Dependencies

**Nothing here is blocked.** Two soft couplings:

- **R1's end state** wants alignment task 2.4 (make `output/runs/` the primary source). Until
  that lands, R1 is satisfied by the caveat path (R1.3): the quickstart carries a one-line
  warning naming the defect and the task, rather than a command the repo knows returns
  shells. Task 1.1 delivers the caveat; task 1.4 removes it and closes R1 when 2.4 lands.
- **R6's `unreachable` counts** consume `evals/coverage.py`, which is committed (`f883d75`).
  No dependency on the uncommitted workbench.

`evals/ui/` is still untracked as of this writing, which is a separate carry-forward
(2026-09-14 journal §8 item 2) and not this spec's business.

## Minimum defensible slice

**Phase 1, plus tasks 2.1, 2.2 and 3.1.** The quickstart stops teaching the bug, every rate
carries its corpus kind and its decided denominator, and `index stats` reports how stale the
corpus is. Three files, no schema migration, about half a day.

If even that is too long: **task 1.1 alone.** Two lines of markdown in two files. It is the
only item in any of the five eval specs where the cost is measured in minutes and the thing
being prevented is a new reader reproducing a defect that took two months to find.

## Executing this with Cursor

```
Read .kiro/specs/eval-claim-surfaces/requirements.md and design.md for context.
Implement task 2.1 from .kiro/specs/eval-claim-surfaces/tasks.md.
Do not start any other task. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

All four phases are free and safe to run unattended. **No task in this spec spends money, and
no task in this spec writes to `evals/annotations/`, `evals/golden/` or `evals/traces/`.**
