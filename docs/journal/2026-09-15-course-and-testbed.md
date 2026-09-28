# 2026-09-15 — the course that could not be written, and why that was the finding

**Session:** 2026-09-14 evening → 2026-09-16. Agent-assisted (Claude Opus 5).
**Base:** [`ffb9bbf`](https://github.com/) — after the workbench landed.
**Preceded by** [2026-09-14 (check liveness)](2026-09-14-check-liveness.md), whose
carry-forward was: re-index `output/runs/`, then read thirty traces.

**Neither was done, again — third session running.** What happened instead started as a
teaching document and turned into an audit of whether this repo can be used by anyone who
did not write it. The answer was no, in seven places, and that is the entry.

Live next-steps list is §8.

---

## 1. Verdict

A course was drafted for `docs/course/` and a page published from it. Reviewing both
against the repo produced a finding that invalidated the approach rather than the prose:

> **The course had to hand readers a 250-line toy harness, because the reader cannot run
> the loop on this project.**

Not "it is undocumented." The path breaks in seven places, four of them before the reader
reaches an eval at all. A course that routes people *away* from the testbed is an
admission the testbed is not usable, and no amount of better writing fixes that.

Two specs came out of it. The page is withheld.

## 2. What was asked, and what the answer turned out to be

The session opened with two questions: do we have good UI/UX and a good system for people
to learn the eval methodology, and do we need LangSmith to collect and analyse traces.

**LangSmith: no, and it would mask the defect.** The problem is not trace storage or
viewing — those are built. Nothing *writes* spans. A trace backend with nothing to ingest
stays empty, and it would only see the LangGraph arm, fragmenting the cross-backend
comparison that is the whole thesis. Three of the four live specs already name it in their
no-vendor constraint.

Housekeeping from the same look: **`langsmith>=0.8.18` is a direct dependency in
`pyproject.toml` with zero imports anywhere** in `src/`, `evals/` or `tests/`. It arrives
transitively via `langchain-core`/`langgraph` regardless (resolved 0.9.3). The direct pin
is a CVE-style floor, not usage — but as written it reads like an adopted vendor, which
contradicts four specs. Not fixed.

**UI/UX: three surfaces exist and none of them is the loop.** The workbench (good, and
was uncommitted at session start). The Tier A report (light-mode only, no abstention
column, no corpus stamp, no drill-down). `coverage liveness` (honest, and not wired into
CI). The React app has **zero** eval surface — no `/api/traces`, and not one reference to
traces, checks or FM ids in any component.

## 3. The stranger's path — the table this session exists for

Every row verified against the working tree.

| # | What they try | What happens |
| --- | --- | --- |
| 0 | Install and run once | **Needs an OpenRouter key and real credit.** `GETTING_STARTED.md:9` puts it in the prerequisites checklist; no keyless or replay gate exists in `config/settings.py` or `main.py` |
| 1 | Build a corpus | `trace backfill` defaults to `./workspace` → 0 spans |
| 2 | Expect spans | Pointed at the right tree, **229 of 324 runs still carry zero spans** |
| 3 | Look at a trace | **No trace viewer.** Nothing in the app |
| 4 | Open-code thirty | Workbench is reached by `sample` → `annotate bundle` → drag a file → export → a fifth command |
| 5 | Add or tweak a check | **Zero documentation.** No scaffold, no worked example, nothing in `docs/` or `evals/README.md` |
| 6 | Re-run and see the change | No delta; the report still hides 76% abstention |
| 7 | Know where they are | Nothing reports loop state |

Row 0 is the one that matters most: the funnel's first paid arrow arrives third, before
the reader has seen anything this project is good at.

Row 5 is the cheapest and the most damning. The extension point of a 13,000-line eval
harness is undocumented.

## 4. What the page got wrong, measured against our own standard

The published page opened with *"a 13,000-line eval system that had never measured
anything."* Our own writing guide sets the test — *"would this still be worth reading by
someone who does not care whose repo it is?"* — and the rule that the personal material
"moves from headline to evidence… never the hero."

The page made the confession the hero. It is in the **Reads as confession** column of a
table we wrote ourselves.

## 5. What was built

| Path | What | State |
| --- | --- | --- |
| `.kiro/specs/eval-claim-surfaces/` | 11 reqs, 4 phases, 26 tasks, $0 — the quickstart, the report, the clock | committed `e40331a` |
| `.kiro/specs/eval-testbed/` | 12 reqs, 8 phases, 39 tasks, ≤$20 — keyless entry, teaching corpus, loop surface, extension path | committed `e40331a` |
| `.kiro/specs/README.md` | specs index **and** the cross-spec execution order: 7 audience milestones, ownership table | committed `e40331a` |
| `docs/course/` | 6 sessions, `lessons.md`, `minieval.py` | committed `e40331a` |
| `docs/EVALS.md` | course linked | committed `e40331a` |

`eval-claim-surfaces` is a **slice spec**: almost every fix in it already had a requirement
home in alignment R14/R15 or coverage R3/R11, so it references and sequences rather than
restating. It owns exactly two things nothing else owned — that no tracked document may
present a command the repo knows is wrong, and that corpus kind and `EVIDENCE-STARVED` get
**one** implementation, in `evals/coverage.py`, rather than one per spec that executes.

## 6. Findings the repo did not have before

Produced by running `minieval.py` against this repo's own two trees, then verifying each
claim against the files.

**Re-indexing `output/runs/` clears all five R4 floors, not four.** 324 run dirs, 4 sources
(langgraph 213, unset 109, crewai 1, claude-agent-sdk 1), 2 statuses, 69.8-day span.
Alignment task 2.4's expectation is understated.

**But `final_status` is nested at `extra.final_status`, present in only 94 of 308
`run.json`** — and every one of those 94 reads `complete`. A top-level-only reader sees
zero statuses and concludes the field does not exist. **Any indexer for task 2.4 must read
one level into `extra`**, or it reproduces the original defect in a new place.

**FM-021 `run_record_incomplete` is real at n=308, not n=1.** 214 of 308 run records have
`completed_at: null` and no final status — `finalize()` never runs on ~69% of runs.
`eval-coverage` filed FM-021 as `origin: hypothesis` from a single smoke run; there is now
population-scale evidence. It still needs a human annotation to promote — that rule does
not bend — but `CHK-run-record-complete` will fire on two thirds of the corpus the day it
lands, which makes it the right worked example for `EXTENDING_EVALS.md`.

**229 of 324 runs carry zero spans.** So the corpus will clear its diversity floors while
staying span-starved, and `CHK-writer-is-code` stays blind. That is `eval-coverage`'s
thesis — fixing the inputs does not fix the instruments — now demonstrated rather than
argued.

## 7. The mistake worth keeping

The first run of `minieval.py` against `output/runs/` reported **308 of 308 records missing
a status field and every diversity floor unmet.** Both published, briefly, on the page.

Wrong. The field was there the whole time, one level down. A four-line change to the
reader turned *"all floors unmet, 308 failures"* into *"all floors met, 214 failures"* on
identical data, same afternoon.

Which is the two-trees defect arriving uninvited: a reader and a writer disagreeing about
where a value lives, producing confident numbers about a system that was fine. The tell
was that the numbers were *too* damning — a field this repo's own notes said existed,
absent from every single record. **When a measurement indicts everything, suspect the
measurement.**

`minieval.py` now looks one level into `extra`, `meta` and `metadata`, with a comment
saying why. The episode is written up in `session-6` and on the page, because it happened
while writing a course about exactly that failure.

## 8. Start next session with

**This supersedes the list in [2026-09-14](2026-09-14-check-liveness.md) §8.** Items 3–5
there are carried forward as 2–4 below, unchanged in substance.

1. **Read the path before picking work.** `.kiro/specs/README.md` — seven milestones, and
   an **ownership table** for the five pieces of work that now appear in two specs each.
   Executing a *referenced* id instead of the *owning* one is the likeliest way to waste a
   week. *Done when the table has been read once.*
2. **M3 — alignment Phase 1 + 2.4 + 2.6 + 3.1–3.2.** 13 tasks, $0, unblocked, and **the
   critical path**: no telemetry writer → no spans → nothing to browse, annotate or check.
   Carries the `extra.final_status` nesting from §6. *Done when `index stats` reports ≥300
   traces, ≥3 backends, a ≥60-day span, and `phases.jsonl` exists on disk stamped
   `writer: harness` with the prompt line at `prompts.py:23` deleted.*
3. **Read thirty traces.** Alignment 4.2–4.4. **Human only, third session carried.** The
   workbench exists, is committed, and the friction excuse is gone. *Done when
   `evals/annotations/` holds ≥30 records with `unaided: true` — which needs item 5.*
4. **Then the harness fixes** from the smoke README (score the turn not the last-12
   history; stop marking single-agent graphs as supervisors; stop routing behavioural
   fails to `retry_development`) and replay the same brief.
5. **`AnnotationRecord.unaided`** — testbed 0.1, promoted from coverage 1b.7 because the
   testbed adds a second writer to the annotation path. The 30-record gate currently counts
   records, not unaided ones. *Done when a record from any other path defaults to `false`
   and a test asserts it.* **Blocks item 3's Definition of done.**
6. **If you want one cheap task instead:** testbed **2.1**, write
   `docs/EXTENDING_EVALS.md`. One markdown file; the extension point of the whole harness
   is currently undocumented.
7. **Drop or comment the `langsmith` pin** (§2). *Done when `pyproject.toml` either omits
   it or carries a comment naming it a CVE floor.*

**Owed by Rick:** items 3 and 4. Item 3 is not delegable by design.

## 9. What did not change

- **The corpus.** Still built from the wrong tree. Item 2 is still free.
- **Zero traces open-coded.** `evals/annotations/` empty after three sessions.
- **Judges advisory**, `eligible_to_gate: false`, 0 golden labels.
- **Tier A `--warn-only`.** Nothing this session argues for flipping it.
- **The page stays private and unshared.** Testbed Phase 7 gates rebuilding it on the loop
  actually running. Publishing a course that promises a loop the project cannot deliver is
  this repo's signature defect performed on purpose — the claim travelling without the
  label.
- **`docs/course/` is retained, not deleted.** Testbed Phase 6 turns it into the lab manual:
  each session gains a CI-checked "Do this" block against the shipped corpus, and
  `minieval.py` narrows to session 6's bridge to the reader's own logs.

## 10. Open questions

- **Does the loop surface ship inside the existing app or as a second section of it?**
  The app's current job is watching a run. Adding the loop makes it two products behind one
  nav. Leaning one app, two top-level sections. Testbed design §10.1 — **decide before
  task 3.2.**
- **Does the `CURATED` stamp suppress percentages entirely?** A teaching corpus must
  over-represent interesting failures, which makes it a chosen denominator rather than a
  sample. Leaning absolute suppression: a course showing percentages over a curated corpus
  while telling readers not to trust them teaches the opposite of its content. Testbed
  §10.3 — **decide before task 1.4.**
- **How many traces does the teaching corpus need?** ≥100 to match the methodology's pool,
  but the reader reads thirty and 100 redacted traces is a large commit. Leaning ≥100
  indexed with a ~40-trace curated reading set named in the manifest. Testbed §10.2.
- **Is `minieval.py` worth maintaining once the loop runs here?** Its role narrows to "do
  this on your own logs." Leaning keep — it is the one artifact a reader can use without
  adopting this project at all. Testbed §10.5, **revisit after Phase 6.**
- **Does `CHK-listener-self-trigger` belong in the registry?** Unchanged from
  [2026-09-14](2026-09-14-check-liveness.md) §9 and now blocking: claim-surfaces R3's
  denominators change meaning depending on the answer, so the `static` flag must exist
  before task 2.2 even if its value is provisional.

## 11. Method note

Every task count in `.kiro/specs/README.md` was produced by parsing the six `tasks.md`
files. **Three counts in the first draft were wrong** (M3, M6, and the free total), and the
cadence work had been left off the path entirely. Re-derive from the files rather than
trusting the numbers in prose — including the ones in this entry.
