# Adopting "Agentic Code Quality" (Addy Osmani) into ai-team

Source: <https://addyo.substack.com/p/agentic-code-quality>
Read 2026-08-19. Analysis against the repo as of this date.

## The article in one paragraph

Human code review does not scale to agent-generated change volume, so quality
stops being a property of the review step and becomes a property of the
*environment the agent works in*. "Software quality now depends on the
constraints you set around your agents." Constraints must sit at three points —
**before** work (shaping the proposal), **during** work (back-pressure the agent
can act on), and at the **production boundary** (the gate) — and must be
trustworthy enough that a human is only pulled in when a guardrail breaks.
Quality is not one number: correctness, maintainability, performance, security,
efficiency, comprehensibility. When change volume outruns verification capacity,
you have exactly three moves: scale verification, slow the agents, or lower the
bar. Humans retreat to "taste, intent, and architecture."

Notably the article offers **no measurement framework**. It names the problem and
stops. That gap is where ai-team is interesting.

---

## What ai-team already does (don't rebuild these)

The three-stage constraint model is already implemented on the Claude Agent SDK
backend, and the article gives it a vocabulary rather than new work:

| Article's stage | ai-team's implementation |
|---|---|
| Pre-work constraint | `hooks/security.py` — PreToolUse; `tools/permissions.py` per-agent tool allowlists |
| Runtime feedback | `hooks/quality.py` — PostToolUse on Write/Edit |
| Production boundary | `evals/gate.py` + `baselines/`, wired into `ci.yml` (`eval-tier-a`) and `eval-nightly.yml` |
| Audit trail | `hooks/audit.py` → `logs/audit.jsonl` |

Other alignments worth naming explicitly:

- **Constraint types.** `guardrails/quality.py` (complexity, file/function length,
  naming, coverage, docs, architecture compliance, dependency pinning),
  `guardrails/security.py` (code safety, secrets, PII, prompt injection, path
  traversal), `guardrails/behavioral.py` (role adherence, **scope control**,
  delegation, iteration limits). The article's list of constraint types is close
  to a subset of this. Scope control in particular is the article's "scope
  validation ensuring proposals stay within agent authority" — already built.
- **Mutation testing.** The article recommends it; ai-team already applies it one
  level up, mutating the *check suite's* passing fixtures
  (`design.md` §7.2, `tests/unit/evals/test_check_sensitivity.py`).
- **Constraint placement discipline.** `ci.yml` runs the Tier A gate in
  `--warn-only` soak with an explicit "do not flip until a week of green
  nightlies" comment. That is the article's calibration argument, done.
- **Low-damage failure modes.** Per-run `./workspace/<id>/` isolation,
  `workspace_snapshots.py`, path-boundary validation.
- **The comprehensibility mitigation.** `docs/journal/` is a written record of
  *why*, which is precisely the antidote to the article's "humans lose their
  mental model because they stopped reading the diffs" trap.

**Do not adopt Sonar.** It is the article's one product recommendation, and it
conflicts with the $0-per-PR eval tier and duplicates ruff + mypy + bandit +
`guardrails/quality.py`.

---

## The five things worth adopting

### 1. Replace the substring scan in the quality hook with real tooling — *highest leverage*

`hooks/quality.py` currently greps written `.py` files for `TODO`, `FIXME`,
`NotImplementedError`, `pass  # implement`, and validates `.json` with
`json.loads`. That's the runtime back-pressure slot — the single most valuable
position in the article's model — occupied by a substring match.

The article's argument for compiler-level rejection applies directly: the agent
should learn a file is broken from the tool that actually knows, not from a
keyword list.

Proposed hook chain on PostToolUse for `.py` writes, cheapest first:

1. `ast.parse` — syntax. Fail fast, return the `SyntaxError` message verbatim.
2. `ruff check --output-format=json` on the single file — returns rule codes and
   line numbers, which is exactly the agent-readable feedback the article asks for.
3. `mypy` on the file (only when the workspace has a config) — type errors.
4. Keep the placeholder scan as a fourth, lowest-priority signal.

Return the tool's own diagnostics in `systemMessage`. Cost is a few hundred ms
per write, entirely local, no tokens. This turns `guardrails/quality.py`'s
regex-approximated cyclomatic complexity (`_cyclomatic_complexity_approx`) into a
fallback rather than the primary measurement.

### 2. Score generated *tests* by mutation, not by coverage

`coverage_guardrail` measures whether generated tests execute lines. That is the
metric the article implicitly criticizes — it cannot distinguish a test suite that
asserts from one that merely imports. ai-team already owns the machinery to do
this properly, applied to its own check suite.

Extend it to the generated workspace: mutate `workspace/<id>/src/`, re-run
`workspace/<id>/tests/`, report the kill rate. A generated suite with 90% coverage
and a 20% mutation score is a *finding* — arguably the most publishable finding
this repo could produce about agent-written tests.

Fits as a Tier B/C check (`evals/checks/verification.py`), bound to a new failure
mode. Budget-aware: mutation runs are CPU, not tokens, so this stays inside the
$0 PR tier if scoped to a small mutant sample.

### 3. Give the eval report a quality-*dimension* axis

The article's six dimensions — correctness, maintainability, performance,
security, efficiency, comprehensibility — map cleanly onto ai-team's existing
check registry, which already carries a `failure_mode_id` and (via the taxonomy)
a `layer` attribution.

Add `dimension` alongside them. `evals/report.py` then produces a per-dimension
breakdown instead of a single pass rate, and `gate.py` can hold different
baselines per dimension — a security regression should block where a
maintainability regression warns. This is a small schema change
(`checks/registry.py`, `checks/base.py`, `taxonomy/failure_modes.yaml`) with
disproportionate reporting value, and it directly answers "quality isn't a single
metric."

Note that ai-team measures dimensions the article omits entirely: **cost** and
**trajectory efficiency** (`evals/cost.py`, `checks/spend.py`,
`checks/trajectory.py`). Worth keeping those as first-class dimensions rather than
flattening to the article's list.

### 4. Measure constraint economics — the article's unanswered question

The article says apply strong constraints where they serve both quality and
delivery, and "don't support them if they're not serving one or both" — then gives
no way to tell which is which. ai-team has a trace corpus, so it can.

Per guardrail, over the corpus:

- **Fire rate** — how often it triggers.
- **Precision** — of the firings, how many corresponded to a real defect
  downstream (needs the human labels Phase 5 already produces).
- **Cost of the retry loop** — tokens and wall-clock spent because the guardrail
  sent the agent back, from `logs/costs.jsonl`.

A guardrail that never fires is dead weight. One that fires constantly and is
always worked around is *verification debt* — it taxes throughput and buys
nothing. This is a genuinely novel measurement, it reuses the taxonomy and
labeling infrastructure already built, and it's the natural sequel to the
failure-taxonomy essay.

### 5. Track architectural drift across runs, not within one

`architecture_compliance_guardrail` evaluates a single output. The article's
sharpest observation is that individual changes can each satisfy every constraint
while the system collectively drifts somewhere nobody chose.

`evals/gate.py` + `baselines/` is already a cross-run comparison mechanism, so the
missing piece is drift *metrics* in the baseline: module count, import-graph
depth and fan-out, cross-layer import violations, average file length. Ratchet
them the way coverage is ratcheted. Cheap to compute (AST walk over the generated
workspace), and it closes the one failure class in the article that none of the
current guardrails can see.

---

## Positioning note

The article is a well-circulated statement of a thesis that this repo is a
working implementation of — with the notable omission of any measurement
framework. The natural post is *"Osmani says quality lives in the constraints.
Here's what happens when you measure the constraints themselves"* — grounded in
the failure taxonomy, judge-alignment numbers (TPR/TNR/κ), and the constraint
economics from item 4. That's the argument the article sets up and doesn't make.

## Suggested order

1. **#1** — hours, not days; improves every SDK-backend run immediately.
2. **#3** — schema change, unblocks better reporting for everything after it.
3. **#5** — reuses `gate.py`/`baselines/` wholesale.
4. **#4** — depends on Phase 5 labels; highest novelty.
5. **#2** — largest build, best headline finding.
