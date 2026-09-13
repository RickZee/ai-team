# The corpus audit — three specs of eval machinery, fed nothing

Triggered by [Hamel Husain & Shreya Shankar on Lenny's Podcast](https://www.lennysnewsletter.com/p/why-ai-evals-are-the-hottest-new-skill)
(*Why AI evals are the hottest new skill for product builders*) and Hamel's
[AI Evals FAQ](https://hamel.dev/blog/posts/evals-faq/). The plan was a
routine alignment pass: read the source, compare it to
[`EVAL_METHODOLOGY.md`](../EVAL_METHODOLOGY.md), note the deltas.

The methodology matched. The data did not exist.

## What the audit ran

```bash
python3 - <<'PY'   # against evals/traces/index.db
select status, count(*)        -> [('failed', 50)]
select scenario_id, count(*)   -> [('unknown', 50)]
select backend, count(*)       -> [('crewai', 50)]
select min(started_at), max(started_at)
    -> 2026-08-16T19:29:23.668979Z .. 2026-08-16T19:29:25.639385Z
select sum(span_count), sum(label_count) -> (0, 0)
PY
```

Fifty traces. One backend. One scenario id, and that one is `unknown`. One status.
**Zero spans between all fifty.** Created inside a **1.97-second window**.

Then the workspaces:

| | |
| --- | --- |
| Run workspaces under `workspace/` | **440** |
| Empty directories | **221** |
| Containing only `src/` and `tests/` | **219** |
| Containing any `logs/*.jsonl` | **0** |

And the annotations:

```
$ ls -A evals/annotations/
$
```

Empty. Zero traces have ever been open-coded. Which means the seventeen-mode
taxonomy — FM-001 through FM-017, every check bound to it, the coverage table,
the essay it cites — came from
[`docs/posts/failure-taxonomy.md`](../posts/failure-taxonomy.md), written from
memory in July, and **not one entry traces to a trace.**

## Root cause, part one: the corpus reads the wrong tree

Every one of those 50 traces carries the same warning block:

```
"missing: .../workspace/2026-07-06_201201_full_01/logs/phases.jsonl",
"missing: .../logs/costs.jsonl",
"missing: .../logs/audit.jsonl",
"missing: .../logs/session.json",
"no audit log for backend=crewai; tool-level checks skipped"
```

The builder is not broken. It looked in `workspace/` and the files were not there.
They were never going to be there. `workspace/<run_id>/` is where the **agents'
generated code** lands — `src/`, `tests/`, nothing else.

The **harness's own records** go somewhere else:

```
$ ls output/runs | grep -c '^20'
211
$ find output/runs -maxdepth 2 -name 'run.json' | wc -l
210
$ find output/runs -maxdepth 2 -name 'state.json' | wc -l
141
$ find output/runs -path '*/logs/*' -type f | sed 's|.*/logs/||' | sort | uniq -c
  60 costs.jsonl
$ find output/runs -maxdepth 2 -name 'receipt.json' | wc -l
8
```

And what is in them:

| | |
| --- | --- |
| Backends recorded | `langgraph` 148 · `crewai` 1 · `claude-agent-sdk` 1 · unset 60 |
| Date range | 2026-07-06 → 2026-09-13 — **69 days** |
| `run.json` carries | `backend`, `workspace_dir`, `completed_at`, `extra.final_status` |
| `state.json` carries | `actual_cost_usd`, `total_tokens`, `monitor_snapshot` |

And the default:

```
evals/cli.py:547
  backfill.add_argument("--workspace-root", default="./workspace")
```

So the corpus that indexed as **one backend over 1.97 seconds** could have been
**three backends over 69 days**, for **$0.00**, on the day the backfill was
written. Four of the five diversity floors were reachable from disk the entire
time. It read the directory where the generated code lands instead of the
directory where the run records live.

## Root cause, part two: phase telemetry is asked for, not written

`phases.jsonl` is the file that yields the phase and retry spans every trajectory
check reasons over. Its only writer in code is:

```
src/ai_team/harness/context_pressure.py:78
  with (logs / "phases.jsonl").open("a", encoding="utf-8") as f:
```

— added on 2026-09-12, and it appends a single `phase_end` row when it records
context pressure. Otherwise the file is requested:

```
src/ai_team/backends/claude_agent_sdk_backend/agents/prompts.py:23
  7. Write phase transition entries to workspace/logs/phases.jsonl
    (JSON lines: phase, status, timestamp).
```

**Zero `phases.jsonl` files exist under `workspace/` or `output/runs/`.** Not one,
in 440 runs.

Worth being precise about the contrast, because it makes the defect specific
rather than general: `audit.jsonl` has a real code writer (`tools/bus.py`,
best-effort, "for TraceBuilder"). `costs.jsonl` has two
(`core/results/writer.py`, `claude_agent_sdk_backend/costs.py`) and 60 of them
exist. Most of the telemetry in this system is written by code. **Phase telemetry
is the one signal left to a prompt, and it happens to be the one every trajectory
check depends on.**

## The uncomfortable framing

The honest version of this is not *"we haven't done error analysis yet."* It is:

> **The eval harness has been pointed at the wrong directory since it was
> written, and three specs were built on top of the empty result.**

`eval-harness` (Aug 16) built the Trace boundary, sampling, the annotation TUI,
golden sets, judge alignment, bias correction, the $0 Tier A gate.
`harness-alignment` (Sep 12) built arms, the ladder, four new failure modes,
ablation storage. Both are real, typed, tested — 13,223 lines of Python under `evals/`, vendor
excluded. Both assumed the corpus was reading from the right place.

What Tier A actually scores is **94 synthetic `__pass` / `__fail` / `__na`
fixtures** across 21 checks. A green Tier A proves the check code behaves as
written. It has never once said anything about whether `ai-team` works. The repo
says so, in [`evals/golden/README.md`](../../evals/golden/README.md) and in
`EVAL_METHODOLOGY.md` — but the disclosure lived in a README while the numbers
travelled without it.

## What the source material actually said

Not "look at your data" as a slogan. Two operational claims:

- *"Error analysis is the most important activity in evals"* — and it is upstream
  of every artifact this repo has built. We built the downstream and skipped the
  upstream.
- *"A working pool of roughly 100 diverse traces is a useful guardrail"* — the
  word doing the work is **diverse**. Fifty traces from one backend, one scenario,
  one status, one two-second batch is `n=1` wearing `n=50`'s clothes. Exactly the
  mistake [Jul 23](journey.md) caught in the defense layer, repeated one layer up.

There is a third, and it is the one that stings:

- *"We've spent 60–80% of our development time on error analysis and evaluation."*
  This project has spent close to 100% of its eval time on **evaluation
  infrastructure** and 0% on **error analysis**. Those are not the same activity,
  and building the first is a very comfortable way to avoid the second.

## What changed today

Nothing in `src/`. A spec:
[`.kiro/specs/eval-methodology-alignment/`](../../.kiro/specs/eval-methodology-alignment/)
— 16 requirements, 9 phases, 38 tasks. The shape of it:

1. **The corpus reads `output/runs/`.** One argument, $0.00, and the highest-value
   task in the spec: ~210 traces, three backends, a 69-day span, with `backend` and
   `final_status` read from run records instead of guessed from directory names.
   `--workspace-root` survives as a secondary source for runs with no record.
2. **Phase telemetry becomes harness-owned.** New `src/ai_team/harness/telemetry.py`,
   constructed by the `Backend` wrapper so a new backend inherits it, writing beside
   `run.json` rather than into a tree nobody reads. `prompts.py:23` is **deleted**,
   not supplemented — leaving it would give one file two writers and make provenance
   unresolvable at the exact moment it matters.
3. **FM-018 `self_reported_telemetry`.** A run whose records were written by the
   model rather than the harness. Deterministic, Tier A, $0.00. It marks all 50
   existing traces, and that is recorded as a **baseline**, not a regression.
   Distinct from FM-016 (`self_graded_verification`): FM-016 produces a bad answer
   you can argue with, FM-018 produces a clean-looking dataset, which is worse.
4. **`unindexable` as a trace state.** A run the builder could not read is not a
   failed run. Today's 50 are recorded as `failed` and are polluting every
   denominator they touch.
5. **A corpus diversity floor** — ≥100 indexable, ≥3 backends, ≥4 scenarios, ≥2
   statuses, ≥14 days — with a `NON-REPRESENTATIVE` stamp rendered by the renderer,
   never asserted in prose. Today's corpus fails all five.
6. **Taxonomy `origin`**: `essay` | `open_coding` | `reference` | `hypothesis`,
   with `evidence_annotations` required for `open_coding`. The migration stamps
   FM-001…013 `essay` and FM-014…017 `reference`, which makes the current state
   legible in one line: **0 of 17 failure modes have been observed.**
7. **Three refusals that cannot be flagged past**: `taxonomy propose` under 30
   unaided annotations, `judge validate` under 100 labels, re-runs above ceiling.
   The loop was skippable because nothing refused.

Phase 4 — annotate 100 traces — is marked human-only, with an explicit instruction
that an agent reading the task list must stop and say so. That is not ceremony.
A model-labeled golden set makes every number downstream meaningless, and this
repo now has 13k lines that would happily consume one.

## Honest state after today

| | |
| --- | --- |
| Traces with usable telemetry | **0** |
| Traces open-coded by a human | **0** |
| Failure modes derived from observation | **0 of 17** |
| Judges with a validated TPR/TNR | **0** (one prompt exists; alignment reports `n: 0`) |
| Tier A corpus kind | **FIXTURE-ONLY** |
| Run records never read by the corpus | **210**, spanning 69 days |
| Instrumentation to fix it | **specced, not built** |

The minimum slice that changes any row: task 2.4 (re-index `output/runs/`, free)
plus task 4.2 (annotate 30 by hand). Thirty traces read personally will say more about what to
build next than the remaining eight phases combined — which is, in the end, the
entire content of the podcast.
