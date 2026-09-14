# Tasks — Eval Testbed

**Spec ID:** `eval-testbed`
**Read first:** [`requirements.md`](./requirements.md), then [`design.md`](./design.md).

Living checklist. Check a box only when its Definition of done is literally true. **Leave
Phase 4 open** — it spends and is human-triggered. **Leave Phase 1 open** until its
cross-spec blockers land.

---

## How to execute this plan

One task per session, then:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ evals/
uv run pytest tests/unit tests/integration/evals -q
```

**Phases 0 and 2 are free and unblocked — start there.** Phase 1 is blocked on
`eval-methodology-alignment` Phase 1 and task 2.4, plus `eval-claim-surfaces` Phase 2.
Phase 4 spends ≤$20.00. Phase 7 publishes and is gated on everything.

---

## Phase 0 — The keyless entry (free, unblocked)

- [ ] **0.1 `AnnotationRecord.unaided`**
  - Add the field; ingest preserves it; the 30-record gate counts `unaided: true` records.
    Closes `eval-coverage` task 1b.7, promoted here per design §4.
  - **Definition of done:** the workbench's emitted `unaided` survives ingest; the gate
    counts unaided records; a record written by any other path defaults to `false` and a
    test asserts it. **Blocks 5.1.**
  - _Requirements: R5.4_

- [ ] **0.2 `docs/EVAL_QUICKSTART.md` — clone to loop with no key**
  - Per design §8. Clone, `uv sync`, one command, the loop on whatever corpus exists. Links
    to `GETTING_STARTED` for the optional paid step with its cost stated.
  - **Definition of done:** a reader with no `.env` follows it start to finish without an
    error mentioning a key; `README.md` offers both paths at equal prominence.
  - _Requirements: R1.1, R1.2, R1.4_

- [ ] **0.3 `AI_TEAM_OFFLINE=1` guard on the eval path**
  - Every eval-path command fails loudly with an explanation rather than attempting a
    network call.
  - **Definition of done:** with the flag set and no key, every command in
    `EVAL_QUICKSTART` either succeeds offline or explains precisely what it wanted; none
    times out. Existing spend guards untouched.
  - _Requirements: R1.3, R1.5_

- [ ] **0.4 Reader-path CI job, no key set**
  - Runs the documented reader path on a clean checkout with **no** secrets. Resolve design
    §10.4 (per-PR vs nightly) in this task.
  - **Definition of done:** the job passes with no secrets configured and fails if any step
    needs one. This is the only test of R1 and the spec rests on it.
  - _Requirements: R12.5, R1.1_

- [ ] **0.5 Reset**
  - Documented, explicit, never a side effect. Restores corpus, annotations and results to
    the shipped state; touches neither `.env` nor `output/runs/`.
  - **Definition of done:** reset restores shipped state; a command that would overwrite
    annotations refuses without an explicit flag.
  - _Requirements: R8.2, R8.3, R8.4_

---

## Phase 1 — The teaching corpus — BLOCKED

**Blocked on:** `eval-methodology-alignment` Phase 1 (telemetry writer) and task 2.4
(corpus source); `eval-claim-surfaces` Phase 2 (stamps and abstention rendering). Without
the first, there are no spans to teach from — 229 of 324 runs measured empty on 2026-09-14.

- [ ] **1.1 Corpus root, manifest schema, VERSION**
  - `evals/corpus/teaching/` per design §5. Resolve design §10.2 (size and reading-set
    split) in this task.
  - **Definition of done:** schema documented; `VERSION` appears in every report scored over
    the corpus; §10.2 answered in the task record.
  - _Requirements: R2.1, R2.5, R2.6_

- [ ] **1.2 Build it from `output/runs/`**
  - Indexer reads one level into `extra` per design §5.2 — a top-level-only reader concludes
    `final_status` does not exist, which is how it was first mis-measured here.
  - **Definition of done:** ≥100 traces; ≥3 backends, ≥4 scenarios, ≥2 statuses, ≥14-day
    span; phase, tool, guardrail and interrupt spans all present; every floor stated in the
    README as met or unmet.
  - _Requirements: R2.1, R2.2, R2.3_

- [ ] **1.3 Redact and lint the teaching root**
  - `fixtures redact --lint` extended to the new root, with the stricter read of design §5.3.
  - **Definition of done:** lint clean in CI; no key, token, absolute external path,
    hostname, username or customer string survives; a deliberately seeded secret is caught.
  - _Requirements: R2.4_

- [ ] **1.4 The `CURATED` stamp, and percentage suppression**
  - Per design §5.1. Fourth stamp, orthogonal to the three in `eval-claim-surfaces`,
    imported from `evals/coverage.py` — never a second implementation. Resolve §10.3.
  - **Definition of done:** a report over the teaching corpus renders `CURATED` and shows
    counts without percentages; a test asserts a percentage cannot render over a curated
    corpus; §10.3 answered.
  - _Requirements: R2.7, R2.8, R10.1_

- [ ] **1.5 `selected_because` per trace**
  - **Definition of done:** every trace in the manifest names why it is in the curriculum;
    `selection: curated` is set; the README states plainly that no rate may be computed
    from this corpus.
  - _Requirements: R2.5, R2.8_

---

## Phase 2 — The extension path (free, unblocked)

- [ ] **2.1 `docs/EXTENDING_EVALS.md` — the cheapest high-value task in the spec**
  - One worked, runnable example: observation → failure mode → check → three fixtures →
    the report line it produces. Plus adding a mode without a check, and removing one.
  - **Definition of done:** a reader who has never opened `evals/checks/` lands a working
    check by following it; every command in it is exercised by 2.5. **There is currently no
    documentation anywhere on how to add a check.**
  - _Requirements: R6.1, R6.5, R6.6_

- [ ] **2.2 `evals.cli checks new <slug>`**
  - Scaffolds module, registry entry, and `__pass`/`__fail`/`__na` fixtures with `TODO`s a
    human must fill. Declares required evidence per `eval-coverage` R1.
  - **Definition of done:** the scaffold runs, the new check is registered, Tier A scores it,
    and the fixtures fail until filled in.
  - _Requirements: R6.2, R6.4_

- [ ] **2.3 Scaffold refuses a signal nothing writes**
  - **Definition of done:** scaffolding a check whose mandatory span type has no parser fails
    with a message explaining that such a check can never fire on any corpus.
  - _Requirements: R6.4_

- [ ] **2.4 `origin: hypothesis` only**
  - **Definition of done:** the scaffold cannot set `open_coding`; no flag exists to; a test
    asserts it. Promotion needs an annotation record.
  - _Requirements: R6.3_

- [ ] **2.5 `run --against <result>` — the delta**
  - Per design §7: outcome changes with trace ids, rates with both `n`s, liveness
    transitions, stamps gained or lost, grouped by system / instrument / denominator.
  - **Definition of done:** re-running an unedited corpus produces an empty delta; a
    `blind → live` transition renders as an instrument change, never as an improvement; a
    rate that moved only because `n` moved is labelled as neither.
  - _Requirements: R7.1, R7.2, R7.3, R7.4_

- [ ] **2.6 Idempotence audit**
  - **Definition of done:** every stage command is idempotent or refuses with the reason and
    what to remove.
  - _Requirements: R8.1_

---

## Phase 3 — The loop surface

- [ ] **3.1 `routers/evals.py`, read-only endpoints**
  - Per design §3. The router holds **no** eval logic; it delegates to `evals/`.
  - **Definition of done:** each endpoint's payload matches CLI output for the same inputs,
    asserted by test; nothing in the browsing path writes to `evals/`.
  - _Requirements: R4.5, R10.1_

- [ ] **3.2 Trace list**
  - Filter and sort by backend, scenario, status, duration, span count, annotated. Resolve
    design §10.1 (one app, two sections vs separate) in this task.
  - **Definition of done:** the teaching corpus is navigable in under three clicks from the
    landing view; corpus profile and stamps visible without a command; §10.1 answered.
  - _Requirements: R4.1, R10.4_

- [ ] **3.3 Single trace view, with absence given equal weight**
  - Two columns per design §6: what happened, what is missing. Stable local URL per trace.
  - **Definition of done:** a starved trace renders its absences with the same typographic
    weight as its content; the 2026-09-13 smoke run shows
    `CHK-guardrail-fp-budget: na — no guardrail_check spans` without opening a log.
  - _Requirements: R4.2, R4.3, R4.4, R4.6_

- [ ] **3.4 Loop view**
  - Stages in order with done / available / blocked, and for blocked, what it waits for.
    Thresholds read from existing code, never re-encoded.
  - **Definition of done:** every gate matches the workbench's; a blocked stage names its
    blocker; loop state shows staleness, floors, judge eligibility and corpus kind; nothing
    here gates anything.
  - _Requirements: R3.1, R3.2, R3.3, R3.4, R3.6_

- [ ] **3.5 Report view with abstention and liveness**
  - **Definition of done:** every rate carries `n`, corpus kind and stamps; abstention and
    liveness render beside every rate; no surface calls a mode covered on the strength of a
    registered check.
  - _Requirements: R10.1, R10.2, R10.3_

- [ ] **3.6 Frontend hygiene**
  - **Definition of done:** `ui-refinement` tokens used throughout; new testids registered
    in `TESTIDS.txt`; both themes legible; phone width holds.
  - _Requirements: R12.4_

---

## Phase 4 — Fill the corpus gaps — SPENDS ≤ $20.00, human-triggered

- [ ] **4.1 Shortfall report before any spend**
  - Which backend / scenario / status cells the teaching corpus is short of, and what each
    would cost.
  - **Definition of done:** runs free; read before 4.2 is started; 4.2 refuses without it.
  - _Requirements: R2.2_

- [ ] **4.2 Run the missing cells — SPENDS**
  - `--dry-run` first, sequentially, every dollar attributable to a named empty cell.
  - **Definition of done:** the corpus clears every floor; total spend ≤ $20.00 and recorded;
    the resolver refuses above ceiling.
  - _Requirements: R2.1, R2.2, R2.3_

---

## Phase 5 — Annotation in one action

**Blocked on task 0.1.**

- [ ] **5.1 Workbench served from the app**
  - `/annotate` serves the same single file, hydrated from `GET /api/evals/bundle`. The
    `file://` drag-and-drop path keeps working.
  - **Definition of done:** one action from the loop view reaches a live sample; the file
    still opens offline; the no-model-output test still scans the shipped HTML and passes.
  - _Requirements: R5.1, R5.3, R5.6_

- [ ] **5.2 Export posts through the existing ingest**
  - **Definition of done:** annotations land in `evals/annotations/` as valid records with no
    separate command; an existing record is not overwritten without an explicit flag.
  - _Requirements: R5.2, R8.4_

- [ ] **5.3 Resume an interrupted sitting**
  - **Definition of done:** a reload resumes; the repo remains the record of record and the
    surface says so.
  - _Requirements: R5.5_

- [ ] **5.4 No model output, asserted on every new surface**
  - **Definition of done:** a test scans every template, endpoint payload and fixture added
    by this spec for failure-mode ids and taxonomy slugs, and fails on any.
  - _Requirements: R3.5, R5.3_

---

## Phase 6 — The course becomes the lab manual

- [ ] **6.1 "Do this" blocks in all six sessions**
  - Command, expected output against the shipped corpus, and what to look at.
  - **Definition of done:** every session has one; each command exits zero on a clean
    keyless checkout.
  - _Requirements: R9.1, R9.5_

- [ ] **6.2 CI checks the expected outputs**
  - **Definition of done:** a session whose output drifts from what the command prints fails
    CI; a session whose command exits non-zero fails CI.
  - _Requirements: R9.2, R9.5_

- [ ] **6.3 Session 3 walks into the annotation surface**
  - **Definition of done:** the reader reaches a live sample of the teaching corpus from the
    session; nothing is offered as a substitute for the reading.
  - _Requirements: R9.3_

- [ ] **6.4 Reposition `minieval.py`**
  - Session 6 frames it as the bridge to the reader's own logs, after the loop has been run
    here. Revisit design §10.5.
  - **Definition of done:** it is no longer presented as the takeaway in place of this
    project; §10.5 answered in the task record.
  - _Requirements: R9.4_

- [ ] **6.5 Evals never reach agents — audit the new surfaces**
  - **Definition of done:** no check result, liveness verdict, stamp or FM id appears in any
    agent-facing path; CI fails on eval vocabulary in an agent prompt; product gates
    unaffected.
  - _Requirements: R11.1, R11.2, R11.3_

- [ ] **6.6 Branch coverage on every refusal added here**
  - **Definition of done:** 100% on the offline guard, the overwrite refusals, the
    parser-less scaffold rejection, and each stage gate; no test writes to
    `evals/annotations/`, `evals/golden/`, `evals/traces/` or the teaching root.
  - _Requirements: R12.1, R12.2_

- [ ] **6.7 End-to-end reader path test**
  - **Definition of done:** browse → annotate → ingest → propose → scaffold → run → delta
    passes on the teaching corpus in one test, keyless.
  - _Requirements: R12.3_

---

## Phase 7 — Rebuild and publish the page — GATED

**Do not start until R1–R7 are satisfied.** Publishing a course that promises a loop the
project cannot deliver is this repo's signature defect performed deliberately.

- [ ] **7.1 Rebuild the page from the sessions**
  - Leads with what a reader can do. The audit narrative appears as evidence in one section,
    never as the opening — the campaign's own test is *"would this still be worth reading by
    someone who does not care whose repo it is?"*
  - **Definition of done:** the page's first screen is the loop and the command that starts
    it; the audit is one section below it; every number carries `n`, corpus kind and stamps.
  - _Requirements: R9.6, R10.1_

- [ ] **7.2 Verify every claim on the page against a clean checkout**
  - **Definition of done:** each capability the page claims is demonstrated on a keyless
    clean clone, by the CI job from 0.4. A claim that cannot be demonstrated is cut, not
    softened.
  - _Requirements: R9.5, R9.6_

- [ ] **7.3 Publish, and wire the campaign**
  - **Definition of done:** URL recorded in the campaign header and `docs/course/README.md`;
    L3's `[link]` destination points at it; the claim rules in
    `docs/campaign/EVAL_GATE_STATUS.md` are satisfied by every figure on the page.
  - _Requirements: R9.6_

- [ ] **7.4 Journal entry**
  - **Definition of done:** house style; states what the testbed can and cannot do on the
    day it shipped, and that the course was withheld until the loop ran.
  - _Requirements: —_

---

## Minimum defensible slice

**Phase 0, Phase 2, and tasks 3.1–3.4.** A keyless entry, a documented and scaffolded way to
add a check, a delta that shows what your edit did, and a surface to browse traces and see
the loop. Neither phase is blocked, and together they are the difference between reading
about the loop and running it.

If even that is too long: **task 2.1.** The extension point of a 13,000-line eval harness is
undocumented, and one markdown file is what stands between this repo and someone else
extending it.
