# Design — Eval Methodology Alignment

**Spec ID:** `eval-methodology-alignment`
**Requirements:** [`requirements.md`](./requirements.md) · **Plan:** [`tasks.md`](./tasks.md)

---

## 1. Design intent

One sentence: **move the boundary of what the harness owns upstream, from scoring to
observation.**

`eval-harness` drew a boundary at the Trace — left of it billed and flaky, right of it free
and deterministic — and then built everything to the right of that line. What it assumed
was that the left side produces traces where the right side looks for them. It does not.
The harness writes run records into `output/runs/` — 210 of them, three backends, 69 days —
and the corpus builder reads `workspace/`, which holds only the code the agents generated.
The one signal that is genuinely missing, phase telemetry, is the one still requested from
the model in a prompt; in 440 runs it was never produced.

So this spec extends the same idea one step left:

```
   execution        observation            scoring
  ┌──────────┐   ┌───────────────┐   ┌──────────────────┐
  │ backend  │ → │ harness-owned │ → │ Trace → checks   │
  │  runs    │   │  telemetry    │   │  judges → report │
  └──────────┘   └───────────────┘   └──────────────────┘
    billed          free, ours          free, ours
    flaky           deterministic       deterministic
                    ↑ NEW
```

Observation belongs with scoring, not with execution. A backend may be swapped, ablated,
vendored, or written by someone else; the record of what it did must not be.

Everything downstream of this — sampling, annotation, clustering, golden sets, alignment —
is already built and needs no design work. §4 through §7 are therefore short: they describe
how existing components behave once they are fed, and the few places where a refusal path
has to be added so the loop cannot be skipped.

## 2. Telemetry

### 2.1 Module

`src/ai_team/harness/telemetry.py` — the only writer of `<run_record>/logs/*`, co-located
with `run.json` under `output/runs/<run_id>/` so the corpus and the telemetry share a tree.

```python
class TelemetryWriter:
    """Harness-owned run telemetry. The agent never writes here."""

    def __init__(self, workspace: Path, run_id: str, backend: str, arm: str | None) -> None: ...
    def session_start(self, scenario_id: str, model_ids: Mapping[str, str], git_sha: str) -> None: ...
    def phase_start(self, phase: str) -> None: ...
    def phase_end(self, phase: str, end_status: str, used_tokens: int | None) -> None: ...
    def cost(self, model_id: str, input_tokens: int, output_tokens: int, source: CostSource) -> None: ...
    def tool_call(self, name: str, args_digest: str, outcome: str) -> None: ...
```

Every record carries `writer: "harness"`. The field is written by the module, not passed in,
so there is no call site that can forge it.

### 2.2 Placement

The writer is constructed by the `Backend` protocol wrapper, not by individual backends.
`run_backend(...)` opens the writer, hands it to the backend as an opaque callback object,
and closes it. A backend that ignores the callback still gets `session.json`, `phase_start`
for the run as a whole, and `phase_end` with a terminal status — degraded telemetry rather
than none. A new backend inherits the floor for free (R1.3).

### 2.3 Failure is soft

`TelemetryWriter` catches `OSError` on every write, records the first failure on the run's
warning list, and sets `degraded: true` in `session.json`. A run never fails because its
logging failed (R1.4) — but the trace built from it carries the degradation, so the number
is discounted rather than silently trusted.

### 2.4 The prompt line goes away

`src/ai_team/backends/claude_agent_sdk_backend/agents/prompts.py:23` is deleted (R1.5).
Keeping it alongside harness telemetry would produce two writers for one file and make
`writer` unresolvable at exactly the moment it matters. The prompt line is not a fallback;
it is the defect.

## 3. Provenance and FM-018

### 3.1 The check

```
CHK-telemetry-provenance
  fail  ← any span derives from a record with writer != "harness"
  pass  ← every contributing record has writer == "harness"
  na    ← the trace has no telemetry records at all
```

`na` rather than `pass` on the empty case (R2.6) is the whole point. The current corpus
would otherwise score 50/50 clean on a check about record-keeping, having kept no records.

### 3.2 Why FM-018 is not FM-016

| | FM-016 `self_graded_verification` | FM-018 `self_reported_telemetry` |
| --- | --- | --- |
| What the agent does | grades its own output | records its own behavior |
| Failure is | visible — a wrong verdict | invisible — a missing or flattering row |
| Blast radius | one run's gate decision | every statistic built on the corpus |
| Detection | compare verifier identity to producer | inspect record `writer` |

FM-016 produces a bad answer you can argue with. FM-018 produces a clean-looking dataset,
which is worse, because nothing downstream has any way to know.

### 3.3 Retroactive scoring

FM-018 runs over the corpus as it stands and marks all 50 traces. That is recorded as the
**baseline**, stamped with the date and taxonomy version (R2.5). A later drop in the FM-018
rate is then attributable to Phase 1 landing, which is the cleanest before/after this repo
will ever get for a harness change — and worth capturing as a result rather than quietly
fixing.

## 4. Corpus

### 4.1 States

| State | Meaning | Counts toward rates | Eligible for open coding | Eligible for golden labels |
| --- | --- | --- | --- | --- |
| `complete` | full telemetry present | yes | yes | yes |
| `partial` | run record present, phase telemetry absent | yes, flagged | yes | **no** (R5.5) |
| `unindexable` | nothing recoverable | **no** (R3.2) | no | no |
| *(skipped)* | empty workspace, no trace created | — | — | — |

The migration (R3.4) reclassifies today's 50 traces. They have no spans and no logs, so they
land as `unindexable` and are then superseded by the re-index of `output/runs/`, where most
of the same runs reappear as `partial` with a real backend, status, cost and duration.

### 4.2 Profile and stamp

```python
class CorpusProfile(BaseModel):
    n_total: int
    n_indexable: int
    n_partial: int
    n_unindexable: int
    backends: dict[str, int]
    scenarios: dict[str, int]      # "unknown" excluded from the distinct count (R4.5)
    statuses: dict[str, int]
    arms: dict[str, int]
    day_span: int
    representative: bool
    unmet_floors: list[str]
```

Floors: `n_indexable ≥ 100`, backends ≥ 3, scenarios ≥ 4, statuses ≥ 2, day span ≥ 14.

Today's profile — built from `workspace/` — fails all five and renders:

```
NON-REPRESENTATIVE — n_indexable=0 (<100), backends=1 (<3),
scenarios=0 (<4), statuses=1 (<2), day_span=0 (<14)
```

The stamp is produced by the renderer (R4.4). Prose cannot opt out of it, and prose that
states a rate without it is a defect — which is how `docs/EVAL_METHODOLOGY.md` came to
describe a "backfilled live corpus" of 50 traces that contain nothing, while 210 usable run
records sat one directory over.

### 4.3 Filling the floors

Order of preference, cheapest first:

1. **Re-index `output/runs/`** under the R5 rules — not `workspace/`. Free. Expected to
   yield ~210 traces across three backends over a 69-day span, which clears the count,
   backend and day-span floors immediately and likely the status floor. This single change
   is the highest-value task in the spec and costs nothing.
2. **Re-run** only the cells still empty after (1), under the $10 ceiling (R5.4), chosen to
   fill backend and scenario cells rather than to add volume.
3. **Generate** scenarios from dimension tuples (§5) for cells no existing scenario covers.

The report in R5.3 prints the shortfall per floor *before* any spend is authorized, so the
$10 buys named cells rather than another batch of the same run.

## 5. Scenario dimensions

`evals/scenarios/dimensions.yaml` enumerates axes; generation is two-step (R6.2) — tuples
first, prose second — because a model asked for "20 varied scenarios" produces 20 rewordings
of one scenario, and a model asked to render a specified tuple produces the tuple.

| Axis | Values |
| --- | --- |
| `task_size` | `single_file`, `small_service`, `full_stack` |
| `spec_completeness` | `thin` (1–4 sentences), `normal`, `over_specified` |
| `stack_familiarity` | `mainstream`, `niche` |
| `existing_codebase` | `greenfield`, `brownfield` |
| `expected_surface` | `tooling`, `runtime`, `integration`, `spec_ambiguity` |

`spec_completeness: thin` closes the limitation `harness-alignment` §9.4 left open: every
arm today receives a full contract, so planner over-specification risk has never been
exercised. It arrives here as a corpus dimension rather than as a new arm, which costs
nothing extra.

Coverage is reported per cell, and an unvisited cell renders `never measured` — distinct
from a cell measured at zero (R6.5), the same distinction `harness-alignment` R15 draws for
stale ablations.

## 6. The error-analysis session

### 6.1 Protocol

```
sample (stratified, n=100, seed recorded)
   ↓
annotate  ─ 30 unaided, no tooling assist  ─┐
   ↓                                        │  unaided: true
annotate  ─ continue to saturation ─────────┘
   ↓
saturation test: 20 consecutive traces, no new tag  →  stop
   ↓
taxonomy propose --from-annotations   (clusters only; never writes)
   ↓
human accept / merge / reject  →  failure_modes.yaml v2.0.0
   ↓
frequency table with Wilson CIs, stamped with sample_id and corpus profile
```

### 6.2 The refusals that make it real

The loop has been skippable because nothing refused. Three refusals are added:

| Refusal | Trigger | Requirement |
| --- | --- | --- |
| `taxonomy propose` exits non-zero | < 30 records with `unaided: true` | R7.4 |
| `judge validate` exits non-zero | < 100 human labels for the FM | R12.3 |
| re-run resolver exits non-zero | resolved cost > ceiling | R5.4 |

Each refusal names what is missing and what would satisfy it. None of them is overridable by
a flag, because a flag is how a refusal becomes a formality.

### 6.3 What the tooling may and may not do

Permitted (per the source material): first-pass axial clustering, mapping annotations to
existing FM ids *after* they exist, summarizing annotation patterns, drafting judge prompts
from confirmed categories.

Refused: initial open coding, validating the taxonomy, producing golden labels, deciding
root cause. `evals/annotate.py`'s module docstring already states this and instructs future
agents not to "helpfully" add AI assistance. That docstring is load-bearing and is extended,
not softened (R7.3).

### 6.4 Saturation is operationalized

"Stop when you stop learning" is unfalsifiable as written, so: **20 consecutive annotated
traces producing no new open-coding tag**, or 100 traces, whichever comes first, with the
terminating condition recorded in the session manifest (R7.5). The running distinct-tag
count is shown live in the TUI (R13.2) so the annotator can watch the curve flatten rather
than guess.

## 7. Taxonomy provenance

```yaml
- id: FM-001
  slug: tool_call_omission
  origin: essay                 # essay | open_coding | reference | hypothesis
  status: active                # active | unobserved | retired
  detection: check
  evidence_annotations: []
```

The migration (R9.3) stamps FM-001…FM-013 as `essay` and FM-014…FM-017 as `reference`. No
entry is promoted to `open_coding` without annotation ids behind it (R9.5). The share by
origin appears in `SuiteReport`, so a reader can see at a glance that a 17-mode taxonomy is
currently 100% un-observed — which is true today and should be uncomfortable to look at
until it changes.

`status: unobserved` (R10.2) exists so that the first pass can be honest without being
destructive. A mode the data did not show is not thereby wrong; it is unconfirmed, and
deleting it would discard a real hypothesis while pretending to be rigorous.

## 8. Claim discipline

Three corpus kinds, rendered on every rate (R15.1):

| Kind | Source | What a pass rate means |
| --- | --- | --- |
| `FIXTURE-ONLY` | `evals/fixtures/traces/` | the check code behaves as written |
| `CORPUS` | indexed traces from real runs | the system behaved this way on this sample |
| `LIVE` | a budgeted tier run just executed | the system behaves this way now |

Today every green number in this repo is `FIXTURE-ONLY`. Nothing about that is dishonest —
`evals/golden/README.md` says so plainly — but the label has lived in a README while the
numbers travelled without it. Attaching the kind at render time is what stops a fixture
pass rate from arriving in a post as a quality claim (R15.5).

Generic metrics stay demoted to a sampling signal (R15.3): useful for deciding which trace
to read next, never reported as quality. This is the one place the source material is
bluntest, and the repo's existing `metrics.py` scorecard is close enough to a generic
dashboard that the rule needs writing down.

R15.6 closes the concrete instance already in the tree: `docs/campaign/EVAL_GATE_STATUS.md`
is referenced twice and does not exist.

## 9. Error handling

| Condition | Behavior |
| --- | --- |
| Telemetry write fails | warning, `degraded: true`, run continues (R1.4) |
| Workspace empty | skipped, no trace (R3.3) |
| Workspace has no logs but has artifacts | `partial` trace with recovered sources (R5.1) |
| Annotation session interrupted | resumable from the sample manifest (R13.3) |
| `taxonomy propose` under 30 unaided | exit 2, names the shortfall (R7.4) |
| `judge validate` under 100 labels | exit 2, names the count (R12.3) |
| Re-run resolves above ceiling | exit 2, prints the resolved plan and cost (R5.4) |
| Corpus below a floor | `NON-REPRESENTATIVE` stamp, never a CI failure (R4.6) |

## 10. Testing strategy

- **Telemetry:** unit tests per record type; a read-only logs dir test for the degraded path
  (R16.3); a test asserting no backend module writes to `logs/` (grep-style guard, so the
  defect cannot return).
- **FM-018 check:** `pass` / `fail` / `na` fixtures (R16.4), plus a retroactive run over a
  frozen copy of the current corpus asserting 50 marks.
- **Backfill states:** table-driven over synthetic workspace shapes — empty, artifacts-only,
  logs-only, complete.
- **Refusal paths:** 100% branch coverage on all three refusals (R16.2).
- **Isolation:** no test writes to `evals/annotations/`, `evals/golden/`, `evals/traces/`
  (R16.1). This repo has already been bitten by golden-file writes in tests; the guard is a
  conftest fixture that fails on any write under those roots.

## 11. Open decisions

1. **Does `partial` earn a judge label after Phase 1 lands?** A trace re-created with full
   telemetry supersedes its `partial` predecessor; whether the old annotation carries forward
   is unresolved. Proposal: annotations carry forward, golden labels do not.
2. **Annotation UI: TUI or local web?** R13 is satisfiable either way. The source material
   favors building it yourself in hours over adopting a vendor; the repo already has a web UI
   under `src/ai_team/ui/web/` that could host it, at the cost of coupling the eval loop to a
   frontend build.
3. **How much of the 219 `partial` set is worth annotating?** Reading artifacts without a
   phase timeline is slow and low-yield. Proposal: annotate 30 `partial` traces to calibrate,
   then decide whether to wait for post-Phase-1 runs before the full 100.
4. **FM-018 on `reference` and `solo` arms.** The vendored reference harness writes its own
   progress files. Whether those count as `writer: agent` is a judgement call with a real
   consequence for the ladder comparison. Proposal: vendored-harness records are
   `writer: vendor`, reported separately, and excluded from FM-018 rather than failed by it.
5. **Whether the frequency table is published.** The first honest failure-rate table this
   repo produces will be worse-looking than the fixture numbers it replaces. That is the
   point, and it is still a decision.
