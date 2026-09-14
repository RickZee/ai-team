# Design — Eval Claim Surfaces

**Spec ID:** `eval-claim-surfaces`
**Reads with:** [`requirements.md`](./requirements.md). Requirement ids below are this spec's
unless prefixed — `alignment R15.1`, `coverage R3.2`.

---

## 1. The shape of the change

Three surfaces, three mechanisms, no new module.

```
  surface        mechanism                                     files
  ─────────────────────────────────────────────────────────────────────────────────────
  quickstart     caveat now, corrected command after 2.4,      README.md, evals/README.md,
                 CI audit forever                              scripts/audit_doc_commands.py

  report         SuiteReport gains coverage + stamps;          evals/aggregate.py,
                 four renderers learn to show a denominator    evals/report.py,
                 and three orthogonal stamps                   evals/checks/base.py

  clock          index stats gains staleness + floor           evals/store.py, evals/cli.py,
                 shortfall; docs gain a dated rhythm           docs/EVAL_METHODOLOGY.md
```

The report is where nearly all the code is. The other two are a markdown edit with a test and
a SQL query with a formatter.

## 2. The one-stamp rule (R2)

`evals/coverage.py` already owns both vocabularies as of `f883d75`:

```python
CorpusKind = Literal["FIXTURE-ONLY", "CORPUS", "LIVE"]   # coverage.py:82
EVIDENCE_STARVED_THRESHOLD = 0.50                         # coverage.py:77
class CoverageReport(BaseModel):
    corpus_kind: CorpusKind                               # coverage.py:346
    def stamps(self) -> list[str]: ...                    # coverage.py:366
```

`SuiteReport` imports them. It does not define a parallel enum, and `evals/report.py` never
writes the string `"FIXTURE-ONLY"` itself — it renders `report.stamps`.

**Why this is worth a requirement.** `alignment R15.1` says every rate renders its corpus
kind. `coverage R11.2` says the `EVIDENCE-STARVED` stamp is renderer-enforced. Executed
independently, each is satisfied by a local implementation in the file its author was editing,
and the failure mode is not that one is wrong — it is that they drift and a reader has no way
to know which one they are looking at. One import is cheaper than one reconciliation.

The enforcement is a test, not a review convention:

```python
def test_no_second_corpus_kind_literal() -> None:
    """R2.2 — the vocabulary lives in coverage.py and is imported."""
    offenders = [
        p for p in Path("evals").rglob("*.py")
        if p.name != "coverage.py"
        and not p.match("*/tests/*")
        and "FIXTURE-ONLY" in p.read_text()
    ]
    assert offenders == []
```

### 2.1 Three stamps, composed

| Stamp | Owner | Answers | Computed from |
| --- | --- | --- | --- |
| `FIXTURE-ONLY` / `CORPUS` / `LIVE` | alignment R15 | what are the traces? | which root was scored |
| `NON-REPRESENTATIVE` | alignment R4 | is the corpus wide enough? | `CorpusProfile` vs R4 floors |
| `EVIDENCE-STARVED` | coverage R11 | could the instruments see? | `na` share excluding `not_in_scope` |

`SuiteReport.stamps` is the sorted union of whichever apply. A Tier A run today earns all
three; the renderer shows all three. The order is fixed (corpus kind, then representativeness,
then evidence) so the field is deterministic per R10.2.

## 3. `SuiteReport` v2 (R2.3, R10.1)

Additive only. Five new fields, one bumped version:

```python
class SuiteReport(BaseModel):
    schema_version: int = 2                    # was 1 (R10.1)
    ...
    coverage: CoverageReport | None = None     # folded liveness for the scored corpus
    stamps: list[str] = Field(default_factory=list)
    n_files: int = 0                           # R4.2
    n_distinct_traces: int = 0                 # R4.2
    abstention: AbstentionSummary | None = None
```

```python
class AbstentionSummary(BaseModel):
    """R3.6 / R6.1 — why the suite declined to answer."""
    n_results: int
    n_na: int
    n_na_in_scope: int                  # the EVIDENCE-STARVED denominator
    share_in_scope: float
    top_abstainers: list[TopAbstainer]  # exactly three, or fewer if fewer checks abstained

class TopAbstainer(BaseModel):
    check_id: str
    na_count: int
    dominant_reason: NaReason
```

`ScorecardCell` and `FailureModeIncidence` each gain `na_count: int` and `n_decided: int`
(coverage R3.2). `n_decided` is `pass + fail` and is the only denominator any renderer is
permitted to divide by.

A version-1 report loads because every added field has a default. `schema_version` is bumped
so a consumer can branch, not so a loader can refuse.

## 4. `na_reason` as a closed vocabulary (R5)

Today `CheckResult` carries `evidence_text: str` and nothing structured, and
`evals/coverage.py:465` clusters those strings with `Counter.most_common(3)`. That works until
someone rewords a message, at which point one cause silently becomes two.

```python
NaReason = Literal[
    "missing_span_type",   # the trace has no spans of a type the check requires
    "missing_artifact",    # a required file is absent from the workspace
    "missing_raw_key",     # raw_result lacks a key the check reads
    "missing_scalar",      # a cost/duration/count field is None
    "not_in_scope",        # this check was never meant to score this trace
]
```

`not_in_scope` carries the design weight. It is the difference between *blind* and *not
asked*, and conflating them is how `CHK-required-artifacts` contributed 65 of 182 headline
failures by firing on fixtures that were never going to have artifacts. Per R5.3 and
coverage R11.1 it is excluded from the `EVIDENCE-STARVED` denominator — hence
`n_na` and `n_na_in_scope` as separate fields rather than one number.

**Migration.** `evals/checks/base.py:82` already centralizes the `na(...)` constructor
alongside `passed(...)`. The parameter becomes required there, and the twenty registered checks
are updated call site by call site. R5.5's guard is the safety net: an outcome-for-outcome diff against
`evals/results/tierA_4671d49ae035_eb36475d7c/report.json` must be empty. This change is
allowed to add a field; it is not allowed to change a verdict.

## 5. Renderer rules (R3, R6)

One function, four formats. The rules are properties of the data, not of the output:

1. **No bare rate.** A rate renders as `value (n_decided=<k>, na=<m>)`. `evals/report.py`
   gets a `_rate_cell(rate, n_decided, na_count)` helper and no format string bypasses it.
2. **Suppress under ten.** `n_decided < 10` renders `n=<k>` with no percentage and no CI
   (R3.3). This is the rule that removes **eleven of the current seventeen** incidence
   percentages — more once task 2.3's distinct-id collapse halves the duplicated denominators —
   and that removal is the point: eleven of twenty checks are decided by one fixture pair.
3. **Every active FM gets a row.** Built from the taxonomy loader, not from observed results,
   so a mode nothing could see is a row reading `liveness: unreachable` rather than an absence
   (R3.4). `origin: hypothesis` modes are filtered out before this step and rendered, if at
   all, in a separate unpromoted section (R3.5).
4. **Headline names the blind.** `FAIL — 182 failed, 1435 abstained (76.3%), 2 checks
   unreachable` replaces `FAIL — 182 failed check(s) across suite`. The verdict downgrades to
   `pass (instruments incomplete)` when any check is `unreachable` (R6.3).

### 5.1 The HTML renderer

It is the format a human opens and the only one with no test (R11.4). Three changes beyond
the shared rules: a stamp row directly under the headline; `not_applicable` as a column in
both tables; and the existing light-only palette gains a `prefers-color-scheme` block, since
the report is read at 11pm more often than at 11am. No new dependency — the template stays
inline Jinja2 with inline SVG, per `eval-harness` R13.

## 6. The doc-command audit (R1.5)

A twenty-line script, not a linter plugin:

```python
# scripts/audit_doc_commands.py
EXEMPT = ("docs/journal/", "docs/eval-runs/", "docs/posts/",
          "docs/showcase/", "docs/campaign/", ".archive/")
PATTERN = re.compile(r"trace\s+backfill[^\n]*--workspace-root\s+\./workspace")
```

Tracked `*.md` files outside `EXEMPT` are scanned; a match is an error naming the file, the
line, and the owning task. Runs in the existing lint job — no new workflow.

**Why a gate here and nowhere else.** Every other signal in this spec describes a state of the
data, and gating on data states is how a team learns to ignore a gate. This one fires on a
string in a tracked file that the repo has already documented as wrong in three places. It can
only be tripped by adding the defect back.

The exemption list is the interesting half. `docs/showcase/starved-harness.html:657` quotes
the wrong command *as the finding*. Rewriting it would destroy the artifact. The rule is by
path rather than by content because content-based exemption drifts into argument.

## 7. The clock (R8, R9)

`index stats` currently renders `store.stats()` — a four-column `GROUP BY`. It gains a header
block above the existing table:

```
corpus    50 traces (72 distinct ids in 94 fixture files)
span      2026-08-16 → 2026-08-16  (1.97 seconds)
floors    UNMET: traces 50/100 · backends 1/3 · scenarios 0/4 · statuses 1/2 · span 0/14d
annots    NONE — evals/annotations/ is empty; 50 traces created since
next      open coding overdue (no anchor date recorded)
```

Two new store methods — `corpus_profile()` and `annotation_staleness()`. The first already has
a home in alignment design §4.2 as `CorpusProfile`; this spec consumes it if it exists and
computes the four floor counts inline if it does not, which keeps the task unblocked either way.

R8.3 is a small thing that matters: empty annotations render as `NONE`, never `0 days`. A zero
next to a date format reads as recent, and the state this command exists to expose is exactly
the one where nothing has happened.

### 7.1 The cadence, anchored

R9.5 rejects "every 2–4 weeks" without an anchor. `EVAL_METHODOLOGY.md` gains:

```markdown
## Cadence

| Pass | Period | Trigger |
| --- | --- | --- |
| Open coding | ≥100 fresh traces every 2–4 weeks | calendar |
| Outlier review | 10–20 traces weekly between passes | calendar |
| Forced review | regardless of calendar | default model changes · backend added · harness component toggled |

**Anchor:** no pass has occurred. First pass due on the first date the corpus clears its R4
floors. `index stats` reports the shortfall.
```

The honest anchor is the absence of one. Writing "first pass due 2026-10-01" would be a
schedule invented to fill a table; writing what the anchor depends on is checkable and puts
the dependency where the reader can see it.

## 8. Order of operations

Phases 2 and 3 are independent. Phase 1 is independent of both. The only internal ordering
constraint is within Phase 2: `na_reason` (R5) before the abstention summary (R3.6, R6.1),
because the summary groups by the code.

```
  Phase 1  quickstart + audit          ── independent, ~1 hour
  Phase 2  na_reason → fields → renderers → stamps   ── sequential internally
  Phase 3  index stats + cadence docs  ── independent
  Phase 4  baseline, determinism, coverage-of-coverage  ── after 2
```

## 9. Open decisions

**9.1 Does `n_decided < 10` suppress the CI summary line too, or only the report?** Leaning
report-and-summary both, because `summary.txt` is what gets pasted into a PR comment and a
suppressed number that reappears one surface over is not suppressed. Decide before task 2.4.

**9.2 Should `EVIDENCE-STARVED` suppress the verdict the way `unreachable` does?** Leaning no,
matching the 2026-09-14 journal's reasoning on `thin`: a starved corpus is already stamped and
the stamp is the signal. An unreachable check is a code defect and gets the stronger treatment.
Revisit once the corpus clears its floors — a suite still `EVIDENCE-STARVED` on a
representative corpus means something different.

**9.3 Where does `CHK-listener-self-trigger` land?** It inspects `ai_team.core.flow_wiring`
rather than a Trace, so its 83 fixture passes are 83 copies of one fact and R4's distinct-id
collapse will not fix that. Carried from the 2026-09-14 journal §9 and `eval-coverage` design
§9.6 — leaning `static: true`, which would exclude it from denominators here. **This spec does
not decide it**, but R3's denominators change meaning depending on the answer, so the flag must
exist before task 2.2 even if its value is provisional.

**9.4 Does the HTML dark-mode block belong in this spec at all?** It is a real improvement to
the surface a human reads, and it is also scope creep into `ui-refinement`'s token system,
which the eval report does not use. Leaning yes because the report is standalone by design
(`eval-harness` R13: no CDN, no build) and borrowing the app's tokens would couple them.
Cheap to drop from task 2.5 if it slows the phase.
