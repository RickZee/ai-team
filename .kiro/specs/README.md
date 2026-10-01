# Eval specs — what they are, and the order to execute them

Seven specs now describe the eval system. Together they hold roughly 250 tasks, and they are
organised by **what is broken**, which is the right way to write a spec and the wrong way to
plan a quarter. This file is the missing half: one execution order, sequenced by **what the
audience can do after each milestone**.

Read a spec for *why* and *what*. Read this for *next*.

---

## The seven specs

| Spec | Owns | State |
| --- | --- | --- |
| [`eval-harness`](./eval-harness/) | Trace boundary, taxonomy, check registry, tiers, the $0 gate | **47/47 done** |
| [`harness-alignment`](./harness-alignment/) | Arms, ladder, ablations, FM-014…017 | **50/54** |
| [`seven-layer-harness`](./seven-layer-harness/) | The harness bar, pinned constraints, context | **39/39 done** |
| [`eval-methodology-alignment`](./eval-methodology-alignment/) | **The inputs** — telemetry, corpus source, human open coding | 0/47 |
| [`eval-coverage`](./eval-coverage/) | **The instruments** — liveness, abstention, the signal chain | 9/62 |
| [`eval-claim-surfaces`](./eval-claim-surfaces/) | **The surfaces** — quickstart, report, cadence | 0/26 |
| [`eval-testbed`](./eval-testbed/) | **Someone else using it** — keyless entry, corpus, loop UI, extension | 0/39 |

The last four are the live ones and they are layered, not parallel:

```
  inputs        →  instruments      →  surfaces        →  someone else
  alignment        coverage            claim-surfaces     testbed
  ────────────────────────────────────────────────────────────────────
  can the         can the checks      does the report    can a stranger
  system record   see what was        say what it        run the loop
  what it did?    recorded?           actually means?    at all?
```

Fixing an inner layer never fixes an outer one. That is why they are separate specs, and
why the order below crosses all four rather than finishing one at a time.

## Execution ownership — read this before starting anything

Five pieces of work appear in two specs each. **One id owns execution**; the other
references it. Doing both is the most likely way to waste a week.

| Work | Owned by | Referenced from |
| --- | --- | --- |
| `NaReason` on `CheckResult` | **claim-surfaces 2.1** | coverage 2.4 |
| Report rendering: `na_count`, stamps, verdict suppression | **claim-surfaces 2.2–2.9** | coverage 4.1–4.6 |
| Staleness, cadence, dated tables | **claim-surfaces Phase 3** | alignment 8.1–8.5 |
| `AnnotationRecord.unaided` | **testbed 0.1** | coverage 1b.7 |
| `CorpusProfile` + `NON-REPRESENTATIVE` | **alignment 2.6** | claim-surfaces 3.1 consumes it |

---

## The path

Seven milestones. Each ends in a capability someone outside this repo can use, and each has
a demo gate — a command whose output proves it landed. **Four of the first five are free and
unblocked today.**

### M1 · A front door that works without a credit card

**Audience can:** clone, run one command with no API key, and read a Tier A report that
states what it asserts.

| | |
| --- | --- |
| Tasks | claim-surfaces 1.1–1.3, 1.5 · testbed 0.2–0.5 |
| Count | 8 |
| Cost | $0.00 |
| Blocked by | nothing |
| Demo gate | On a clean clone with no `.env`: the documented first command exits zero, and CI proves it with no secrets configured (testbed 0.4). |

**Smallest version:** claim-surfaces **1.1** alone — two lines of markdown so `README.md:337`
and `evals/README.md:12` stop telling a new reader to run the audited defect.

Do this first not because it is the most valuable but because every later milestone's value
is delivered *through* this door, and right now the door asks for money on step three.

### M2 · Numbers that state what they are

**Audience can:** read any report and know the corpus kind, the decided denominator, how much
of the suite abstained, and which checks have never decided anything.

| | |
| --- | --- |
| Tasks | claim-surfaces 2.1–2.11, 4.1–4.2 · coverage 2.1–2.6, 3.1–3.4 |
| Count | 23 — the biggest milestone here |
| Cost | $0.00 |
| Blocked by | nothing |
| Demo gate | A Tier A run renders `FIXTURE-ONLY · NON-REPRESENTATIVE · EVIDENCE-STARVED`, names 1435 abstentions and 2 unreachable checks in the headline, and cannot render a percentage without its denominator. |

**Minimum to unlock M4:** claim-surfaces 2.1–2.2 (the `NaReason` vocabulary and the
`na_count` / `n_decided` fields) plus coverage 2.1–2.3 (evidence declarations). The rest of
M2 is the renderer, which can follow.

This milestone is the honesty precondition for everything audience-facing. A testbed that
ships misleading reports teaches the defect it exists to name.

### M3 · The system records what it does — the unblocker

**Audience can:** run the system and get traces with real spans; build a corpus from the
tree the records are actually in.

| | |
| --- | --- |
| Tasks | alignment 1.1–1.6, 2.1–2.4, 2.6, 3.1–3.2 |
| Count | 13 |
| Cost | $0.00 |
| Blocked by | nothing |
| Demo gate | `index stats` reports ≥300 traces, ≥3 backends and a ≥60-day span; `phases.jsonl` exists on disk with every record stamped `writer: harness`; the agent logging instruction at `prompts.py:23` is **deleted**, not supplemented. |

**This is the critical path.** M4 and M6 are capped by it, and today 229 of 324 real runs
carry zero spans, so there is nothing to browse, annotate or check. It is free, unblocked,
and nothing else here changes that number.

Two measured facts to carry into task 2.4: `extra.final_status` is nested and present in only
94 of 308 `run.json` — a top-level-only reader concludes the field does not exist. And 214
runs never finalised, so `completed_at` is null on two thirds of the corpus.

### M4 · Traces you can actually look at

**Audience can:** browse the corpus, open a trace, see what happened *and what is missing*,
and see which checks decided on it, which abstained, and why.

| | |
| --- | --- |
| Tasks | testbed 3.1–3.3, 3.5–3.6 · coverage 4c.1–4c.4 |
| Count | 9 |
| Cost | $0.00 |
| Blocked by | M3 (spans), M2 minimum (abstention reasons) |
| Demo gate | The 2026-09-13 LangGraph smoke run displays `CHK-guardrail-fp-budget: na — no guardrail_check spans` in the UI without opening a log file. |

The design decision that matters: absence gets the same typographic weight as content. A
reader learning to spot a starved trace has to see starvation rendered.

### M5 · Extend it, and watch your own change move a number

**Audience can:** write a check from an observation, re-run, and see a delta attributed to
their edit.

| | |
| --- | --- |
| Tasks | testbed 2.1–2.6 · coverage 6.1–6.3 |
| Count | 9 |
| Cost | $0.00 |
| Blocked by | nothing — can run in parallel with M2 or M3 |
| Demo gate | A stranger follows `docs/EXTENDING_EVALS.md`, lands a working check, and `run --against` shows the delta with the changed trace ids named. Re-running unedited produces an empty delta. |

**Smallest version:** testbed **2.1** — write `docs/EXTENDING_EVALS.md`. The extension point
of a 13,000-line eval harness is currently undocumented, and this is the single cheapest
item in any of the seven specs.

Pair it with coverage **6.3** (`CHK-run-record-complete`): it is the worked example that
document needs, and it fires on 214 of 308 records today, so the reader's first check produces
a real finding rather than a green row.

### M6 · The whole loop, on shipped data, for nothing

**Audience can:** clone and, with no key and no spend, read thirty traces, cluster their own
codes, draft a failure mode, write a check, re-run, and see it fire.

| | |
| --- | --- |
| Tasks | testbed 0.1, Phase 1 (1.1–1.5), Phase 4 (4.1–4.2), Phase 5 (5.1–5.4), 3.4 · alignment 4.1–4.5 · claim-surfaces 3.1–3.4 |
| Count | 22 |
| Cost | **≤ $30** — testbed Phase 4 (≤$20) plus alignment 2.5 if cells remain empty (≤$10) |
| Blocked by | M3, M4, M5 |
| Demo gate | A clean clone with no key completes browse → annotate → ingest → propose → scaffold → run → delta in one test (testbed 6.7). |

Two things in here are **not delegable**: alignment 4.2–4.4 is Rick reading thirty traces
unaided, and it is the item that has now been carried across three sessions. And the teaching
corpus has to be built *after* M3, or it curates span-less traces and locks the starvation
into the thing strangers learn from.

The `CURATED` stamp and percentage suppression (testbed 1.4) are the honesty mechanism for a
corpus that is deliberately a curriculum rather than a sample.

### M7 · Publish

**Audience can:** find it.

| | |
| --- | --- |
| Tasks | testbed Phase 6 (6.1–6.7), Phase 7 (7.1–7.4) · claim-surfaces 4.4–4.6 |
| Count | 14 |
| Cost | $0.00 |
| Blocked by | M1–M6, all of them |
| Demo gate | Every capability the page claims is demonstrated by the keyless CI job from testbed 0.4. A claim that cannot be demonstrated is cut, not softened. |

The drafted page stays private until here. `docs/course/` becomes the lab manual: each
session gains a CI-checked *Do this* block against the shipped corpus.

---

## What to do this week

```
  M1  ██        8 tasks   free   the door
  M3  ████     13 tasks   free   the unblocker        ← start here if you pick one
  M5  ██        9 tasks   free   the testbed feeling
  M2  ███████  23 tasks   free   the honesty layer
  ──────────────────────────────────────────────────
  M4  ███       9 tasks   free   needs M3 + M2-min
  M6  ███████  22 tasks   ≤$30   needs M3, M4, M5
  M7  ████     14 tasks   free   needs everything
```

**M1, M2, M3 and M5 are all free and all unblocked.** 53 tasks with no dependency on anything
outside the repo and no spend. The recommended order is **M1 → M3 → M5 → M2 → M4 → M6 → M7**:
the door first because it is eight tasks, then the unblocker because everything is capped by
it, then the two that make the repo feel like a testbed, then the gated work.

If you want one task today: **testbed 2.1**, `docs/EXTENDING_EVALS.md`.
If you want one milestone: **M3**.

## What the path deliberately leaves out

98 of the 165 open tasks across the four live specs are on it. The other 67 are real work,
and none of it is on the audience's path:

| Left out | Why |
| --- | --- |
| coverage Phase 5 (guardrail + interrupt telemetry) | unblinds FM-003/FM-005; blocked on M3 and worth doing, but after |
| coverage Phases 4d, 7, 8 | feed-forward discipline, orphan signals, harness overhead — internal correctness |
| coverage 6.4–6.9 | the remaining hypothesis checks; 6.3 is the one that earns its place in M5 |
| alignment Phases 5–7 | taxonomy re-derivation, ergonomics, judges — all downstream of the reading in M6 |
| harness-alignment's 4 open | ladder spends, unrelated to the loop |

Judges are the largest omission and it is deliberate: they need 100 human labels, which means
they are downstream of M6, and every one of them is advisory until validated anyway.

## Traps, each one already paid for once

- **Do not build the teaching corpus before M3.** You would curate traces with no spans and
  ship the starvation to strangers as the thing they learn from.
- **Do not publish before M6.** A course promising a loop the project cannot run is this
  repo's signature defect performed on purpose — the claim travelling without the label.
- **Do not let an agent do alignment Phase 4.** Model-labelled ground truth invalidates every
  number downstream, and 13,000 lines here would cheerfully generate a golden set.
- **Do not adopt a second eval framework** before the first has run on real data. Reviewed and
  rejected twice; see `docs/resources.md` and the external-tooling register.
- **Do not flip Tier A off `--warn-only`** until a week of green nightlies on a real corpus.
  Today's liveness finding argues against it, not for it: a green suite now demonstrably
  means less than it appeared to.
- **Do not execute a referenced task id.** Check the ownership table above first.

## Cost, all in

| | |
| --- | --- |
| M1–M5, M7 | **$0.00** |
| M6 | ≤ $30 (≤$20 teaching corpus, ≤$10 corpus cells) |
| Already budgeted elsewhere | $5 live suite, $25 ladder, $15 judge alignment, $1 coverage controls |

The expensive resource is not money. It is the two afternoons of reading in M6 that nobody
else can do.


---

## Cloud-native backends (added 2026-09-28)

Two new orchestration backends on each cloud's own agent stack, plus the shared foundation
they both depend on. Separate from the eval path above. They run under the Cursor
command `/cloud-backends`.

| Spec | Owns | Budget |
| --- | --- | --- |
| [`cloud-backend-foundation`](./cloud-backend-foundation/) | Conformance suite, tool bridge, harness-owned acceptance, local Docker + OTel stack, OTel ingest, Terraform conventions | $0 |
| [`azure-agent-framework`](./azure-agent-framework/) | Microsoft Agent Framework on Microsoft Foundry, Entra ID, Prompt Shields, App Insights, Container Apps Job, Terraform | ≤ $20 |
| [`aws-strands-agentcore`](./aws-strands-agentcore/) | Strands Agents on Amazon Bedrock AgentCore, Bedrock Guardrails, AgentCore Memory, CloudWatch, Terraform | ≤ $20 |

**Order:**

1. Foundation Phases 0–3 (blocking).
2. Azure Phases 0–1 and AWS Phases 0–1, both local and $0. They can interleave.
3. Azure Phases 2–5, then AWS Phases 2–5. Azure goes first.
4. Foundation Phases 4–7 run alongside step 2, since the local stack is needed there.

Every phase is **local first**: in-process with Ollama, then the same container locally,
then cloud models, then Terraform-deployed cloud. Each step must pass the same thin-slice
smoke test before the next one adds a cloud dependency.
