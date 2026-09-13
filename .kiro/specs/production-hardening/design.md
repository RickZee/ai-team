# Design — Production Hardening

**Spec ID:** `production-hardening`
**Requirements:** [`requirements.md`](./requirements.md)
**Tasks:** [`tasks.md`](./tasks.md)

---

## 1. Overview

### 1.1 What is actually wrong

Nothing here is a rewrite. The audit found no architectural mistake in the harness, the
taxonomy, the trace boundary, or the check registry — those are the parts worth showing.
What it found is **drift between what the repository asserts and what it wires**, in four
places, each with the same shape: something was built, something was written about it, and
then the wiring moved without the writing moving.

```
   CLAIMED                              ACTUAL
   ───────                              ──────
   HARNESS.md: Feedback closed-loop  →  lessons_loop.py imported by its own test only
   README: "the harness is the        →  harness/ absent from the README's own
            real deliverable"             project-structure tree
   pyproject: mypy gate               →  ignore_errors over ~half the Python
   CI: frontend job                   →  builds, never lints or tests (110 cases idle)
   Dockerfile: "FastAPI + React"      →  no Node stage; container serves no UI
   SECURITY.md: full threat model     →  no row for the unauthenticated control plane
```

Every one of those is a one-line fix to the claim or a one-day fix to the wiring. What
makes them worth a spec is that they are exactly the checks a senior reviewer runs, in the
order they run them.

### 1.2 Design principles

1. **Delete before you refactor.** ~1,600 LOC (orphans + uncollected tests) can leave in
   Phase 1. Every later phase is cheaper for it.
2. **A claim without a check is a liability.** The repository's credibility comes from its
   claims being verifiable. Each claim this spec keeps gets a test (R20); each claim it
   cannot check gets downgraded (R2.3).
3. **Move, don't redesign.** R10 relocates 6,772 LOC without changing a line of logic. A
   relocation with an opportunistic refactor inside it is unreviewable.
4. **The boundary is the default, not the exception.** Loopback binding and a required
   token are what the server does unless told otherwise (R15.4–15.5).
5. **Enforcement lives in the cheap job.** All guards run in `lint`, add < 30 s, and print
   the fix in the failure message (R20.5, R9.5).
6. **Honesty is the differentiator.** `SECURITY.md`, the "Honest gaps" paragraph in
   `HARNESS.md`, the `fail_under` history comment, and `performance_report.md`'s admission
   that its numbers were meaningless are the most senior-looking artifacts in the repo.
   This spec extends that voice; it never trims it.

### 1.3 What this deliberately does not change

The failure taxonomy and its IDs. The `Trace` boundary and schema. Check IDs and tier
definitions. Backend orchestration behaviour. Agent prompts and personas. The journal.
Route paths, response shapes, and `data-testid` values.

---

## 2. The wire-or-delete decision table (R1)

Five modules, ~800 LOC, imported only by their own tests. Each needs a recorded decision
before any of them is touched. The recommendation column is the audit's reading; the
decision is the owner's.

| Module | LOC | Evidence | Recommended | **Decision (2026-09-13)** | Why |
| --- | --- | --- | --- | --- | --- |
| `harness/lessons_loop.py` | 161 | Only `tests/unit/harness/test_lessons.py`. Named `closed-loop` in `HARNESS.md`; `SELF_IMPROVEMENT.md` says lessons write through it. Its name appears as an ablation *string* in `evals/arms/base.py`. | **wire** | **wire** | Closed-loop is the most valuable harness-table claim; `ResultsBundle` is the default-path hook. |
| `harness/session_loop.py` | 315 | Only its own test. Phase 8 of `harness-alignment`, explicitly "off by default until its ablation shows it earns its place". | **dormant** | **dormant** | Behind `AI_TEAM_SESSION_LOOP=1` until an ablation earns a default-on place. |
| `harness/qa_verdicts.py` | 75 | Only a test. The *reader* side exists and is wired (`evals/trace/parsers.py` → `parse_qa_verdicts_jsonl`, `evals/checks/verification.py`), but nothing writes `docs/qa_verdicts.jsonl`. | **wire** | **wire** | Without a producer, `CHK-evaluator-capitulation` can only return `inconclusive`. |
| `harness/verifiers.py` | 25 | Only `tests/unit/harness/test_router.py`. Cited in the `enforced` Verification row. | **wire or downgrade** | **wire** | Cheap-path routing is called from `run_app_smoke` on the default path; smoke itself remains the enforcement. |
| `evals/ladder_report.py` | 228 | Only its own test. | **dormant** | **dormant** | Activated by `python -m evals.cli ladder report`; not on a default run. |

The general rule that comes out of this table, and that R9.2 encodes: **a dormant module
is one you can turn on in one documented step.** Anything else is an orphan wearing a
plan.

---

## 3. Machine-checkable status definitions (R2.2)

`HARNESS.md`'s three status words become testable predicates:

| Status | Predicate | Test shape |
| --- | --- | --- |
| `instrumented` | The named module is imported on a default run path. | Reachability graph (R9.1) contains it from an entry point. |
| `enforced` | Bypassing the layer makes the default path fail or block. | A test disables/stubs the layer and asserts the run raises, blocks, or records a guardrail failure. |
| `closed-loop` | Output of run *n* changes input of run *n+1*. | A test writes an artifact in run 1 and asserts run 2 loads it and behaves differently. |

Applying these to the current table predicts three downgrades and two fixes. That is the
expected, healthy outcome — the table has never been checked, so its first check should
move rows. R2.3's rule matters more than the specific rows: **a downgrade is not a
regression; a false claim is.**

---

## 4. Package contract (R11)

Target layout after R10. The only structural change is that CrewAI's implementation moves
next to the other two backends.

```
src/ai_team/
├── core/           protocols, results, run identity, spend guard, team profile
├── config/         settings, models, routes, cost estimation, token tracking
├── harness/        the product: acceptance, context, receipts, routing, journal, lessons
├── tools/          ToolBus + tool implementations (file, code, git, test, smoke)
├── guardrails/     behavioral, security, quality  (facade __init__ only — R11.3)
├── memory/         long-term store
├── monitor.py      thread-safe event collector
├── backends/
│   ├── registry.py
│   ├── crewai_backend/          ← + agents/ crews/ tasks/ flows/   (R10.1)
│   ├── langgraph_backend/
│   └── claude_agent_sdk_backend/
└── ui/             web server (routers — R13) + artifacts service + frontend
```

**Import rules** (enforced by R10.5):

| Package | May import | May never import |
| --- | --- | --- |
| `core/` | stdlib, pydantic | anything in `ai_team` except `config` |
| `config/` | `core` | `backends`, `harness`, `ui`, `tools` |
| `harness/` | `core`, `config`, `tools`, `guardrails` | `backends`, `ui` (already its docstring rule) |
| `tools/`, `guardrails/`, `memory/` | `core`, `config`, `harness` | `backends`, `ui` |
| `backends/*` | everything above, and only its own subtree | another backend's subtree |
| `ui/` | everything above | another backend's internals |
| `evals/` | `core`, `harness`, `config` (contracts only) | `backends` (R10.2) |

**After Track B (R11.4–11.5):** `utils/` is dissolved. Owners: `tools/coverage_paths.py`,
`config/demo_input.py`, `backends/comparison.py`, `backends/crewai_backend/callbacks.py`,
`backends/crewai_backend/llm_wrapper.py`. `reasoning.py` was unreachable and deleted.
`models/` remains — it owns shared domain types (`requirements`, `architecture`,
`development`, `qa_models`, `comparison_report`). `models/outputs.py` was a single-consumer
LLM schema dump used only by the artifacts service; that consumer now normalizes dicts
and the file is gone.

---

## 5. Documentation model (R3, R4)

### 5.1 Four kinds of document, one rule each

| Kind | Files | Rule |
| --- | --- | --- |
| **Entry** | `README.md` | Accurate index, verified by test (R5.2). One screen to the interesting part. |
| **Reference** | `ARCHITECTURE`, `HARNESS`, `GUARDRAILS`, `SECURITY`, `EVAL_METHODOLOGY`, `MODELS`, `TEAM_PROFILES`, `GETTING_STARTED`, `AGENTS` | Describes the system as it is **now**. Every path in it resolves (R4.2). One subject, one file. |
| **Record** | `docs/journal/**`, `docs/posts/**`, `docs/troubleshooting/**`, `docs/eval-runs/**` | Append-only, dated, never edited except for broken links. This is the repo's strongest asset and its voice. |
| **Plan** | `.kiro/specs/**` | The only place aspirations live. Roadmaps in `docs/` are plans in the wrong folder. |

`EVALS_ROADMAP.md` (68 KB, self-labelled aspirational) is a Plan sitting in Reference
space; `COMPARISON_RESULTS.md` (512 lines, "historical run diary") is a Record duplicating
the journal; `performance_report.md` is a Reference whose content is an apology for not
existing. Each resolves by moving to its correct kind or leaving.

### 5.2 Workspace-artifact notation (R4.2)

Docs legitimately name files that exist only inside a generated run workspace
(`run.json`, `ACCEPTANCE.json`, `logs/costs.jsonl`, `docs/qa_verdicts.jsonl`, `calc.py`).
The reference checker cannot distinguish those from stale source paths — in the audit they
were ~200 of ~300 raw hits, which is why the number looked alarming and mostly was not.

Convention: **workspace artifacts are written with a `<workspace>/` prefix**
(`` `<workspace>/logs/costs.jsonl` ``). The checker skips any path starting with
`<workspace>/`, and flags every other unresolvable path. One convention, applied once,
turns a noisy check into a precise one.

### 5.3 What "outdated" means here

Not age. `docs/journal/2026-06-24.md` is three months old and perfectly current as a
record of 24 June. A document is outdated when it (a) describes behaviour the code no
longer has, (b) points at files that no longer exist, or (c) states a plan that a spec has
since superseded. Age is only evidence.

### 5.4 Data artifacts (R21)

Three categories, one rule each. The rule is stated in the README of the directory that holds
the files, so the classification travels with the data.

| Category | Meaning | Examples | Rule |
| --- | --- | --- | --- |
| **Authored** | A human wrote it as an input | `evals/scenarios/*.json`, `config/agents.yaml`, `evals/corpora/guardrails/thresholds.yaml` | Reviewed like code |
| **Generated** | A named command produces it | reports, `docs/benchmark_results.json` (absent), coverage output | Committed only with its regeneration command stated; otherwise gitignored |
| **Accepted** | A human blessed a measurement | `evals/baselines/tier_a.json` | Carries date, git sha, and a `reason` that explains the numbers |

The audit's result by category:

- **Authored: clean.** 94 fixture traces, 20 distinct check ids, **zero orphans in either
  direction**, plus 12 consistently named backend coverage fixtures. `tests/fixtures/` is
  likewise fully referenced. This is the best-maintained data in the repo and §9's guard exists
  to keep it that way.
- **Accepted: stale.** `tier_a.json` is a month old, pinned to a pre-harness-alignment sha,
  covers 13 of 20 registered checks, and records all thirteen as `fail` with
  `suite_pass_pow_k: 0.0`. For a corpus deliberately built from fail/pass pairs that may be
  correct — but the file says nothing about it, and it is the file that defines what the
  flagship $0 gate accepts.
- **Unclassified: 7 MB of images.** 25 of 38 are referenced by nothing. Roughly half are
  external publication assets (`substack-*`, `hero-linkedin.*`) that have a purpose the
  repository never states; the rest are run screenshots from July whose documents have moved on.

`evals/golden/.validation_log.jsonl` fits none of the three: a hidden, tracked, zero-length
append log. It is also the shape of the recorded golden-file test-isolation defect — a tracked
file that tests append to.

---

## 6. Complexity ratchets (R12)

Three counters, stored in one file, enforced by one test:

```toml
# tests/unit/repo/ratchets.toml — see R20.3; values dated and sourced
functions_over_80_lines   = 63   # 2026-09-13 baseline
functions_over_150_lines  = 8
functions_over_8_params   = 17
mypy_ignore_errors_modules = 16
docker_image_mb            = 0   # set by task 8.4
```

**Exemption (R12.6):** a function is exempt when its branch count is ≤ 2 and it is a flat
declarative builder — `evals/cli.py:build_parser` (215 lines, 0 branches) is the canonical
case. Long ≠ complex; the ratchet targets `_cmd_run` (259 lines, **71 branches**, 16
params), not a parser definition.

`_cmd_run`'s 16 parameters are the deeper smell: the CLI signature and the run signature
are the same function. R12.4 splits them with a `RunOptions` dataclass built from
`argparse.Namespace`, which also makes the run path callable from a test without
constructing a CLI invocation.

---

## 7. Control-plane security (R15, R16)

### 7.1 Auth

```python
# ui/web/auth.py
def require_token(x_ai_team_token: str = Header(default="")) -> None:
    expected = get_settings().web.token          # AI_TEAM_WEB_TOKEN
    if not expected:                              # loopback-only mode (R15.4)
        return
    if not secrets.compare_digest(x_ai_team_token, expected):
        raise HTTPException(401, "Invalid or missing token")
```

One dependency, applied to every router in R13's split except `/api/health`. Three rules
make it safe by default rather than by configuration:

1. `--host` defaults to `127.0.0.1` (R15.5).
2. A non-loopback bind without `AI_TEAM_WEB_TOKEN` is **refused at startup**, not warned
   about (R15.4 sets the warning for loopback; the refusal is what makes 15.5 real).
3. WebSockets validate the token at handshake **and** check `Origin` — CORS middleware
   never sees a WebSocket upgrade, which is the mistake this rule exists to prevent
   (R15.7).

Local development keeps its single command: loopback, no token, warning in the log.

### 7.2 Path containment

```python
def _abs_path_for_rel(project_id, root, rel_path) -> Path:
    if ".." in rel_path or rel_path.startswith("/"):   # existing, keep
        raise ValueError("Invalid path")
    if _is_sensitive(rel_path):                        # existing, keep as defence-in-depth
        raise ValueError("Sensitive path not allowed")
    base = _tree_root(project_id, root).resolve()
    resolved = (base / rel_path).resolve()
    if not resolved.is_relative_to(base):              # NEW — the actual boundary
        raise ValueError("Path escapes project root")
    return resolved
```

The existing checks are string-shaped and run *before* the join, so they cannot see a
symlink. Agents write into this workspace; a symlink is a file an agent can create. The
post-resolve assertion is the boundary, and the string checks become what they always
were — defence in depth (R16.3).

`project_id` is already validated (`resolve_run_workspace_dir` rejects `..`, `/`, `\`),
which is why this is a containment gap rather than an open traversal. Worth stating
precisely in the commit message: over-claiming a finding is its own credibility problem.

---

## 8. Container and compose (R18, R19)

| Defect | Fix |
| --- | --- |
| No Node stage; image serves no UI despite its title | Add `FROM node:22-slim AS frontend` → `npm ci && npm run build` → copy `dist/` into runtime; or retitle to API-only |
| `register_frontend()` returns silently when `dist/` is absent | `logger.warning` naming the expected path |
| `build-essential` in the **runtime** stage | Builder only; `git` justified by agent tooling or removed |
| `.dockerignore` misses `node_modules`, `dist`, `workspace`, `logs`, `.coverage-data` | Add them — `COPY src ./src` currently carries ~230 MB of frontend deps |
| Healthcheck probes `/api/backends` | Probe `/api/health` |
| `build: .` with compose in `docker/` | `context: ..`, `dockerfile: docker/Dockerfile` |
| Ollama service + NVIDIA GPU reservation in the default file | Remove, or move behind `profiles: [local-llm]` |
| No resource limits, no restart policy | Add both |

The CI image job (R18.6) asserts four properties: non-root user, no `gcc` on `PATH`,
image size under the ratchet, and `/api/health` → 200 in a started container. Those four
are what a reviewer would check by hand, which is the point of automating them.

---

## 9. Enforcement suite (R9, R20)

New package `tests/unit/repo/` — eleven assertions across eight test modules:

| Test | Asserts | Fails with |
| --- | --- | --- |
| `test_reachability.py` | No orphan modules; dormant allowlist accurate | `harness/foo.py is imported only by tests. Wire it, add it to DORMANT_MODULES with its flag, or delete it.` |
| `test_references.py` | Relative links and source paths resolve (§5.2 convention) | `docs/X.md:42 → ../campaign/EVAL_GATE_STATUS.md does not exist` |
| `test_readme_structure.py` | README tree ≡ real packages | `README structure omits: harness, models, utils` |
| `test_collection.py` | No `test_*.py` outside `testpaths` | `evals/backends/test_crewai_eval.py is never collected` |
| `test_type_budget.py` | mypy `ignore_errors` module count ≤ ratchet | `ignore_errors covers 17 modules; budget is 16` |
| `test_complexity.py` | Three complexity ratchets | `main.py:_cmd_run is 259 lines (budget: functions >150 lines = 8, now 9)` |
| `test_import_direction.py` | §4 import rules | `evals/checks/trajectory.py imports ai_team.flows; evals may not import backends` |
| `test_data_artifacts.py` | Fixture↔check mapping both ways; baseline covers every registered check; no unreferenced image outside the publication allowlist | `CHK-foo has no fixture`; `baseline covers 13 of 20 checks`; `docs/images/dashboard.png is referenced by nothing` |

Plus, outside `tests/unit/repo/`, the behaviour tests for what this spec changes:
`tests/unit/ui/test_auth.py` (route coverage + bind rules, R15) and
`tests/unit/ui/test_artifacts_adversarial.py` (symlink containment, R16).

Total budget: < 30 s (R20.5), measured once at task 8.6. All the repo guards read files and
parse ASTs; none import the application.

**The bar for all of them is R24**, and two of its clauses carry most of the weight:

- *Fail on an empty match set (R24.4).* A glob that stops matching after a refactor reports
  success. This is the default failure mode of repo-hygiene tests and the reason most such
  suites quietly stop working.
- *Ship a recorded way to watch it fail (R24.3).* Either a negative fixture or a one-line
  mutation in the docstring. A guard nobody has seen fail is a guard nobody knows works.

---

## 10. Migration order and risk

Track A is phases 1–5, 9 and 8; Track B is 6 and 7 (see `tasks.md`, "Two tracks"). The risk
table below is ordered by phase number, which is the dependency order — not the order to do
them in.

| Phase | Content | Risk | Reversible |
| --- | --- | --- | --- |
| 1 Delete | orphans, uncollected tests, empty dirs, dead docs, ~7 MB of unreferenced images | **Low** | trivially |
| 2 Truth | harness table, README, links, docs consolidation, Tier A baseline refresh | **Low** | trivially |
| 3 Gates | frontend CI, type budget, collection check | **Low** — may go red immediately, which is the point | yes |
| 4 Security | token, bind default, path containment, SECURITY.md | **Medium** — changes the dev command's default host | yes |
| 5 Container | Node stage, dockerignore, compose context | **Medium** — image build changes | yes |
| 6 Boundaries | move 6,772 LOC under `crewai_backend/` | **High** — largest diff in the repo | via shims |
| 7 Complexity | three worst functions, web router split | **Medium-High** — touches the run path and every route | per-commit |
| 8 Guards | enforcement suite + ratchets | **Low** | yes |
| 9 Evidence | one real benchmark, operating envelope, retention policy | **Low** — additive; the only risk is publishing a number that invites scrutiny, which is the point | yes |

**Rationale.** Deletion first so nothing later is spent on code that leaves. Truth second
because it is nearly free and it is what a reviewer reads first. Gates third so every
later phase is protected by them. Security before the big moves because it is the highest
consequence and the smallest diff. The two large refactors (6, 7) come last, behind
compatibility shims and a green suite, and are independently revertable.

**On Track B.** Phases 6 and 7 are the two largest diffs in the repository — 6,772 LOC moved
and 24 routes re-homed — and a reviewer reading for thirty minutes will not notice either. They
are in the spec because the package tree currently tells a false story and a 259-line,
71-branch function is a real maintenance cost. They are *not* in the spec because they improve
the showcase. Schedule them on the maintainer's budget, not the portfolio's, and note that
R10.3 was deliberately relaxed: this repository has no external consumers, so deprecation shims
for the moved packages are optional and the default is a hard move.

**The single highest-value hour in this spec is Phase 2, task 2.1** — making the harness
status table true. It is the table a reviewer reads to decide whether the project is
serious, and it currently contains two claims the code does not support.

---

## 11. Testing strategy

| Layer | Covers | Command |
| --- | --- | --- |
| Lint / format | style | `uv run ruff check . && uv run ruff format --check .` |
| Types | `src/`, `evals/` minus the shrinking ignore list | `uv run mypy src/ && uv run mypy evals/` |
| Repo guards (new) | R9/R20 | `uv run pytest tests/unit/repo` |
| Unit (1,456 functions) | behaviour | `uv run pytest tests/unit` |
| Frontend (110 cases, **new to CI**) | components, utils | `npm run lint && npm test` |
| Web E2E (Playwright) | the app still works — the control for phases 6 and 7 | `uv run pytest tests/e2e/web -m web_e2e` |
| Image (new) | R18.6 | `docker build` + assertions |
| Tier A evals | $0 replay gate | `uv run python -m evals.cli run --tier A` |

The Playwright suite is what makes the two large refactors safe: it selects by
`data-testid` and asserts behaviour, so if it stays green while 6,772 LOC move and 24
routes are re-homed, the changes were structural only.

---

## 12. Open decisions

Recorded 2026-09-13. No unanswered row remains.

| # | Decision | Default if unanswered | Status |
| --- | --- | --- | --- |
| 12.1 | `lessons_loop` — wire it, or downgrade the `closed-loop` claim? | **Wire** (§2). The claim is worth more than the week. | **Done** — wired through `ResultsBundle` |
| 12.2 | `session_loop` — dormant behind a flag, or delete until its ablation runs? | **Dormant behind `AI_TEAM_SESSION_LOOP`** | **Done** — dormant |
| 12.3 | Container serves the UI, or is honestly API-only? | **Serves the UI** — add the Node stage; the dashboard is a large part of what the project demonstrates | **Done** — Node stage in `docker/Dockerfile` |
| 12.4 | `.archive/` — delete from the tree, or keep with a stated retention rule? | **Delete**; git history is the archive | **Keep** — owner override 2026-09-13; `.archive/README.md` states retention and why each tracked survivor stays |
| 12.5 | `COMPARISON_RESULTS.md` — merge into the journal, or keep as a distinct diary? | **Keep, with a purpose line** (R3.2); merging 512 lines of dated records loses their order | **Done** — kept |
| 12.6 | Build backend after dropping Poetry tables — `hatchling` or `uv_build`? | **hatchling** (boring, widely understood, reads PEP 621 directly) | **Done** — hatchling |
| 12.7 | Move `agents/crews/tasks/flows` with shims, or hard-move and update imports? | **Shims for one release** with a removal date in the docstring | **Done** — shims warn until 2026-12-31 (v0.3.0) |
| 12.8 | Web auth — shared token, or skip auth and document loopback-only? | **Shared token**; "it's local-only" is the sentence every incident report starts with | **Done** — `AI_TEAM_WEB_TOKEN` |
| 12.9 | R22 benchmark — spend real money on one live multi-backend run, or publish mock-labelled numbers only? | **One live run, budget-capped.** A labelled mock benchmark is honest but answers nothing; this is the only place in the spec where spending is worth arguing for | **Pending human spend** (task 9.1, $25). Envelope documented; mock numbers not published |
| 12.10 | Track B (phases 6–7) — do it, or record the layout problem in `ARCHITECTURE.md` and move on? | **Record and defer** unless the repo keeps being developed | **Done** — Phases 6 and 7 landed on `feature/phase-harness-alignment` |

Decisions already closed by the requirements, recorded so they are not reopened: no
behaviour change to the harness or taxonomy (constraints); deletion beats archiving for
unreachable code (constraints); route paths and `data-testid`s stay stable (R13.2); no
task in this spec spends money (constraints).
