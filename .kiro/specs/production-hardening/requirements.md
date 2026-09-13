# Requirements — Production Hardening

**Spec ID:** `production-hardening`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target repo:** `ai-team` (whole repo: `src/`, `evals/`, `tests/`, `docs/`, `docker/`, CI)
**Created:** 2026-09-13
**Related:** [`../ui-refinement/`](../ui-refinement/) covers the web frontend's design system
and accessibility; this spec does not restate it. [`../eval-harness/`](../eval-harness/) and
[`../harness-alignment/`](../harness-alignment/) define the eval and arm machinery whose
*wiring* this spec audits.

---

## Introduction

This repository is the portfolio artifact. Its claim is not "a multi-agent demo" — it is
*"I build production-ready, enterprise-grade, performant, secure, scalable systems."* A
reviewer with thirty minutes will test that claim in a specific order: skim the README,
open the Dockerfile, look for auth on the API, check whether CI actually gates anything,
then grep for the module a doc just named. This spec fixes what that reviewer finds.

The codebase is genuinely strong in the places most projects are weak: a real failure
taxonomy bound to deterministic checks, a $0 replay gate, subprocess isolation with hard
kills, per-run spend guards, adversarial guardrail tests, an honest `SECURITY.md` threat
model, 1,456 test functions, and an engineering journal that records corrections rather
than hiding them. None of that is in question here.

What the audit found is a consistent, fixable pattern: **the repository's claims have
drifted ahead of its wiring.** Five specific gaps, each of which a reviewer can find in
minutes:

**1. Code that ships but is not reachable (~800 LOC).** `harness/lessons_loop.py` (161),
`harness/session_loop.py` (315), `harness/verifiers.py` (25), `harness/qa_verdicts.py`
(75), and `evals/ladder_report.py` (228) are imported by **nothing but their own unit
tests**. `docs/HARNESS.md`'s status table nevertheless marks Feedback **closed-loop**
citing `lessons_loop.py`, and Verification **enforced** citing `verifiers.py`;
`docs/SELF_IMPROVEMENT.md` states lessons "now write through
`src/ai_team/harness/lessons_loop.py`". The harness-alignment spec deliberately ships
Phases 8–10 off by default — that is sound — but "off by default" currently means
*unreferenced*, with no flag that could turn it on, while two documents say it is live.

**2. Gates that do not gate.** `testpaths = ["tests"]`, so `evals/backends/test_*_eval.py`
and `evals/test_backend_comparison.py` — **808 LOC of tests** — are never collected, and
are additionally `ignore_errors = true` under mypy. CI runs `npm ci && npm run build` for
the frontend but never `npm test` or `npm run lint`, so **110 frontend test cases and the
ESLint config never execute in CI**. `mypy` "passes" while `ignore_errors = true` covers
two of three backends, `agents.*`, `crews.*`, `flows.main_flow`, `tools.test_tools`,
`tools.smoke_tools`, `evals.run_evals`, and more — roughly half the Python by volume.

**3. A layout that tells the wrong story.** `agents/` (1,327), `crews/` (1,388),
`tasks/` (1,071), and `flows/` (2,986) — **6,772 LOC** — sit at the top level of
`src/ai_team/` as though they were the shared domain model. They are reachable only
through `backends/crewai_backend/backend.py`. The other two backends are self-contained
subtrees. Meanwhile the README's "Project structure" section omits `agents/`, `crews/`,
`tasks/`, `flows/`, `harness/`, `models/`, `reports/`, and `utils/` entirely — including
`harness/`, which the same README calls "the real deliverable".

**4. A control plane with no controls.** `src/ai_team/ui/web/server.py` (1,791 LOC, 24
routes) has **no authentication on any route** and defaults to `--host 0.0.0.0`. Those
routes start paid LLM runs (`/ws/run`, `POST /api/demo`), resume human-gated runs, delete
workspaces (`DELETE /api/runs/{run_id}`), and stream arbitrary workspace files
(`GET /api/projects/{id}/file`). `SECURITY.md` models agent-layer threats carefully and
does not mention the control plane at all. The container story has the same shape: the
Dockerfile is titled "web UI (FastAPI + React)" but has **no Node build stage**, so
`register_frontend()` silently returns and the container serves no UI; the runtime stage
installs `build-essential`; `.dockerignore` does not exclude `node_modules`, so
`COPY src ./src` drags ~230 MB of frontend dependencies into both images; the healthcheck
probes `/api/backends` rather than `/api/health`; and `docker-compose.yml` still builds
against an Ollama service with NVIDIA GPU reservations from an era the docs have moved on
from — with a `build: .` context that cannot see `pyproject.toml`.

**5. Committed data nobody can classify.** 195 tracked JSON/JSONL/YAML files, and the one
that matters most is stale: `evals/baselines/tier_a.json` — the accepted baseline that defines
what the $0 gate passes — was accepted `2026-08-16` against a pre-harness-alignment sha, covers
**13 of 20 registered checks**, and marks every one `"fail"` with `suite_pass_pow_k: 0.0`,
explaining none of it. Alongside it, **25 of 38 tracked images (~7 MB of the 9 MB in
`docs/images/`)** are referenced by nothing, and `evals/golden/.validation_log.jsonl` is a
tracked, hidden, zero-length append log. The counterweight is the fixture corpus: 94 traces, 20
check ids, **zero orphans in either direction** — the best-maintained data here, and the reason
R21 guards it rather than touching it.

### The principle this spec enforces

> **Nothing ships that is not reachable, and nothing is claimed that is not checked.**

Every requirement below either makes a claim true, makes a gate real, or deletes something
that is neither.

### What this spec adds

| Area | Gap today | Requirement |
| --- | --- | --- |
| Unreachable modules | ~800 LOC imported only by their own tests | R1 |
| Harness status claims | `HARNESS.md` marks unwired layers *enforced* / *closed-loop* | R2 |
| Doc sprawl | 42 markdown files, three overlapping narrative streams, 68 KB aspirational roadmap | R3 |
| Reference rot | ~65 dead links in `PROMPT_TRACKING.md`; ~20 doc→source paths that no longer exist | R4 |
| README accuracy | Structure omits 8 packages incl. `harness/`; taxonomy cited as FM-001…010 (now …017) | R5 |
| Uncollected tests | 808 LOC never run by pytest | R6 |
| Frontend gates | 110 vitest cases + ESLint never run in CI | R7 |
| Type coverage | `ignore_errors` over ~half the Python | R8 |
| Drift | Nothing prevents the next orphan module or dead doc link | R9 |
| Package boundaries | 6,772 LOC of CrewAI-private code at top level | R10 |
| Core contract | No stated rule for what `core/` and `harness/` may own | R11 |
| Complexity | 63 functions > 80 lines; worst is 259 lines / 71 branches / 16 params | R12 |
| Web module size | One 1,791-line module holds all 24 routes | R13 |
| Dependency source | PEP 621 **and** Poetry tables, hand-synced; author is "Your Name" | R14 |
| Control-plane auth | No authentication; binds `0.0.0.0` by default | R15 |
| Path containment | No post-resolve boundary assertion on artifact reads | R16 |
| Threat model | `SECURITY.md` omits the API surface entirely | R17 |
| Container image | No frontend build; `build-essential` in runtime; `node_modules` shipped | R18 |
| Compose topology | Ollama + GPU leftovers; broken build context | R19 |
| Enforcement | Conventions live in prose | R20 |
| Data artifacts | Stale/partial Tier A baseline; 25 unreferenced images (~7 MB); a tracked empty log | R21 |
| Performance & scale | Two of the four claimed properties have no evidence and no stated limits | R22 |
| Repo surface | Actions pinned by mutable tag; no PR/issue template, CODEOWNERS, or CHANGELOG | R23 |
| Test quality | ~12 new test modules, and no stated bar for the tests themselves | R24 |

### Design constraints (decided)

| Constraint | Decision |
| --- | --- |
| Behaviour | No change to run semantics, the failure taxonomy, check IDs, or trace schema. This spec moves, deletes, wires, and gates — it does not redesign the harness. |
| Backward compatibility | `ai-team` and `ai-team-web` console entry points, CLI flags, REST/WS paths, and `data-testid` values stay stable. Python import paths **may** change (R10) — that is the point — but only behind a deprecation shim for one release. |
| Deletion bias | When code is unreachable, the default is **delete**, not comment out or archive. Git history is the archive. |
| Wiring bias | When a module is deliberately dormant (R1's "off by default" set), it must be reachable behind an explicit, documented, tested flag — not left unreferenced. |
| Spend | Every task runs offline **except task 9.1**, the published benchmark, which needs one real multi-backend run. That run SHALL be human-triggered, budget-capped at **$25**, and recorded with its receipt. No other task may add a live model call. |
| Scope boundary | Frontend design-system and accessibility work belongs to [`../ui-refinement/`](../ui-refinement/) and is not duplicated here. R7 (running its tests in CI) is the only overlap. |
| Verification | `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy evals/ && uv run pytest tests/unit` green after every task; full CI green at each phase boundary. |

### Non-goals

- Rewriting any backend, changing orchestration behaviour, or altering agent prompts.
- New features, new pages, new metrics, new failure modes.
- Multi-tenancy, RBAC, SSO, or a hosted deployment. R15 adds a single-operator auth
  boundary, not an identity system.
- Kubernetes manifests, Helm charts, or a cloud deployment story.
- Raising the coverage floor as a goal in itself. R8 raises *type* coverage; the
  `fail_under = 60` line-coverage ratchet is left to its existing process.
- **Building scale.** R22 requires measuring and stating the envelope; it explicitly forbids
  implementing a persistent run store, a queue, or a worker pool for a single-operator tool.
- Rewriting the engineering journal. It is an append-only record and stays as written
  (R3.5).

### Glossary

| Term | Definition |
| --- | --- |
| **Reachable** | Imported, directly or transitively, from a console entry point, a CLI, the web app, or a check registry — not merely from a test. |
| **Dormant** | Deliberately not on the default path, but reachable behind a documented flag and exercised by at least one test that sets that flag. |
| **Orphan** | A module that is neither reachable nor dormant. R1 deletes orphans. |
| **Control plane** | The FastAPI app in `src/ai_team/ui/web/server.py` and everything it can start, stop, read, or delete. |
| **Claim** | A statement in a doc about what the system does. R2/R4/R5 require every claim to be checkable. |
| **Ratchet** | A numeric floor stored in config that a test enforces and that may only move in the improving direction. |

---

## Requirements

### R1 — Every shipped module is reachable or dormant-by-flag

**User story:** As a reviewer grepping for the module a doc just named, I want to find it
wired into something.

**Acceptance criteria**

1.1 NO MODULE under `src/ai_team/` or `evals/` (excluding `evals/arms/vendor/`, which is a
pinned third-party copy) SHALL be imported exclusively by its own tests.

1.2 FOR EACH of `harness/lessons_loop.py`, `harness/session_loop.py`,
`harness/verifiers.py`, `harness/qa_verdicts.py`, and `evals/ladder_report.py`, THE TEAM
SHALL make an explicit, recorded decision: **wire**, **dormant**, or **delete**.

1.3 WHERE the decision is **wire**, the module SHALL be reachable from a default run,
CLI command, or registry, and at least one test SHALL exercise it through that path rather
than by direct import.

1.4 WHERE the decision is **dormant**, THE SYSTEM SHALL expose a single documented
environment flag or CLI option that activates it, the flag SHALL appear in
`.env.example` and the configuration reference, and a test SHALL exercise the module
**through the flag**, asserting both the on and off paths.

1.5 WHERE the decision is **delete**, the module and its tests SHALL be removed in one
commit whose message names the superseding mechanism, if any.

1.6 THE `ablation component` STRING LIST in `evals/arms/base.py` SHALL name only
components that are reachable or dormant per 1.3/1.4; a component that names an orphan
SHALL be removed from the list.

1.7 `src/ai_team/rag/`, `src/ai_team/optimizers/`, `tests/unit/rag/`, and any other
directory containing no tracked files SHALL be removed.

---

### R2 — The harness status table is checked, not asserted

**User story:** As a reader of `HARNESS.md`, I want the word "enforced" to mean something
a test verified this morning.

**Acceptance criteria**

2.1 EACH ROW of the `docs/HARNESS.md` status table SHALL name a module path, and a test
SHALL assert that every named path exists and is reachable per R1.1.

2.2 THE STATUS VALUES `instrumented`, `enforced`, and `closed-loop` SHALL each have a
machine-checkable definition recorded in `design.md` §3, and a test SHALL assert the
claimed status against it:
- `instrumented` — the module is imported on a default run path;
- `enforced` — a test demonstrates the default path *fails or blocks* when the layer is
  bypassed;
- `closed-loop` — a test demonstrates output from one run changing input to the next.

2.3 WHERE a row cannot meet its claimed status, the row SHALL be downgraded in the same
commit that discovers it. Downgrading is not a regression; a false claim is.

2.4 `docs/SELF_IMPROVEMENT.md`'s statement that lessons write through
`harness/lessons_loop.py` SHALL be made true (R1.3) or corrected (R1.4/R1.5).

2.5 THE TABLE'S "Honest gaps" PARAGRAPH SHALL be retained. It is the most credible
paragraph in the document and its style SHALL be extended to the rest of the docs, not
removed.

---

### R3 — One home per subject

**User story:** As a reader, I want one document per topic and a clear reason for every
file that survives.

**Acceptance criteria**

3.1 THE DOCUMENTATION SET SHALL be reduced to documents that are current, distinct, and
linked from `README.md` or from another surviving document. Today there are 42 markdown
files under `docs/`, of which the README indexes 16.

3.2 THE FOLLOWING SHALL be resolved explicitly:

| Document | Issue | Required outcome |
| --- | --- | --- |
| `docs/EVALS_ROADMAP.md` (68 KB) | Self-declared "aspirational", scoped 2026-07, superseded by two Kiro specs | Reduce to a short backlog that links the specs, or move to `.archive/` |
| `docs/prompts/PROMPT_TRACKING.md` | ~65 links to `phase-*.md` files that do not exist | Rewrite as a short provenance note, or archive |
| `docs/performance_report.md` | 22 lines whose entire content explains that the document is not real | Delete; the explanation belongs in the journal |
| `docs/COMPARISON_RESULTS.md` (512 lines) | "Historical run diary" overlapping `docs/journal/` | Merge into the journal or state its distinct purpose in its first line |
| `docs/RESULTS.md` | Named "Results" but documents bundle layout | Rename to reflect content (e.g. `RUN_ARTIFACTS.md`) |
| `docs/EVALS.md` vs `docs/EVAL_METHODOLOGY.md` vs `evals/README.md` | Three entry points to one subject | Keep one entry point; the others link to it |
| `.archive/` (21 tracked files) | Removed demos and superseded plans kept in-tree | Delete from the working tree — git history is the archive — or state the retention rule in `.archive/README.md` |

3.3 EVERY SURVIVING DOCUMENT SHALL open with one sentence stating what it is for and, for
any document containing measurements, the date and conditions of those measurements.

3.4 NO DOCUMENT SHALL present numbers from a mock or demo run without labelling them as
such in the same visual block as the numbers. *(Review item — judged by a human at the phase
gate, not by a test. It is listed as a criterion because it is verifiable by reading, not
because it is automatable.)*

3.5 `docs/journal/` IS APPEND-ONLY and SHALL NOT be edited by this spec, except to fix
broken relative links (R4.2). Its value is that it was written at the time.

---

### R4 — Reference integrity

**User story:** As a reader following a path in a doc, I want the file to be there.

**Acceptance criteria**

4.1 EVERY RELATIVE MARKDOWN LINK in a tracked `.md` file SHALL resolve to a tracked file
or directory. The audit found ~70 that do not, concentrated in
`docs/prompts/PROMPT_TRACKING.md` (~65), plus
`docs/EVAL_METHODOLOGY.md` and `docs/posts/harness-map.md`
(→ `campaign/EVAL_GATE_STATUS.md`), `docs/prompts/PROMPTS.md`
(→ `.archive/phase-7-agentcore-deployment.md`), and three journal `handoff-*.md` links.

4.2 EVERY INLINE SOURCE PATH in a tracked `.md` file SHALL resolve to a tracked file,
**except** paths that name artifacts produced inside a run workspace
(`run.json`, `state.json`, `ACCEPTANCE.json`, `logs/*.jsonl`, `docs/qa_verdicts.jsonl`,
generated `calc.py`, and similar). Workspace artifacts SHALL be written in a visually
distinct form so a checker can tell them apart — `design.md` §5 specifies the convention.

4.3 THE FOLLOWING referenced-but-absent paths SHALL be fixed or removed:
`evals/evidence.py`, `evals/trajectory.py`, `evals/fixtures.py` (now a package),
`docs/security_report.md`, `docs/WEB_DASHBOARD.md`, `docs/SELF_IMPROVEMENT_AUDIT.md`,
`docs/SELF_IMPROVEMENT_DESIGN.md`, `memory/knowledge_base.py`,
`scripts/setup_openrouter.sh`, `scripts/setup_ollama.sh`, `scripts/test_models.py`,
`scripts/extract_lessons.py`, `scripts/show_metrics.py`.

4.4 A LINK CHECK SHALL run in CI over tracked markdown and SHALL fail the build on an
unresolvable relative link (R20).

4.5 EXTERNAL (http) LINKS ARE OUT OF SCOPE for the CI gate — they fail for reasons the
repo does not control.

---

### R5 — The README is an accurate index

**User story:** As a first-time reader, I want the first page to match the repository.

**Acceptance criteria**

5.1 THE "Project structure" TREE SHALL list every top-level package under
`src/ai_team/`. It currently omits `agents/`, `crews/`, `tasks/`, `flows/`, `harness/`,
`models/`, `reports/`, and `utils/` — including `harness/`, which the same README
identifies as the real deliverable.

5.2 THE TREE SHALL be generated or verified by a test, so it cannot drift again (R20).

5.3 THE README SHALL cite the taxonomy by its current range. It says "FM-001…010"; the
taxonomy is at 1.2.0 with FM-001…017.

5.4 THE README'S DESCRIPTION of `evals/backends/` as "Live backend eval clients (pytest)"
SHALL be corrected or removed in line with R6.

5.5 THE DOCUMENTATION TABLE SHALL list every surviving document (R3.1), or state that it
is a curated subset and where the full index lives.

5.6 THE README SHALL state, in one line near the top, what a reader should look at first
to judge the engineering — the harness, the taxonomy, and the $0 gate — because a
portfolio artifact that does not direct attention wastes the reviewer's first two minutes.

---

### R6 — Tests that exist, run

**User story:** As a maintainer, I want the test count on the badge to mean something.

**Acceptance criteria**

6.1 `evals/backends/test_claude_sdk_eval.py` (175), `evals/backends/test_crewai_eval.py`
(169), `evals/backends/test_langgraph_eval.py` (191), and
`evals/test_backend_comparison.py` (273) — **808 LOC never collected** because
`testpaths = ["tests"]` — SHALL be either moved under `tests/` and made to pass, or
deleted.

6.2 WHERE they are moved, they SHALL carry an existing marker (`integration`, `real_llm`,
or `slow`) so the default suite stays offline and free, and they SHALL be removed from the
mypy `ignore_errors` list.

6.3 NO TEST FILE SHALL live outside `testpaths` after this spec, and a check SHALL assert
it (R20).

6.4 THE TWO TEST-ISOLATION DEFECTS already recorded in project memory (golden-file writes;
the order-dependent workspace test) SHALL be confirmed fixed or ticketed here with a task.

6.5 THE 35 `pytest.skip` CALL SITES SHALL be reviewed; each SHALL skip on a *missing
precondition* (no API key, service unreachable), never to route around a failing
assertion.

---

### R7 — Frontend quality gates run in CI

**User story:** As a maintainer, I want the frontend's 110 tests to be able to fail the
build.

**Acceptance criteria**

7.1 THE CI WEB JOB SHALL run `npm run lint` and `npm test` in addition to
`npm run build`. It currently runs only `npm ci && npm run build`.

7.2 THE FRONTEND TEST STEP SHALL fail the job on a failing test; it SHALL NOT be
`continue-on-error`.

7.3 FRONTEND COVERAGE MAY be reported but SHALL NOT gate in this spec.

7.4 THE `ui-refinement` SPEC'S DRIFT TEST, once it exists, runs inside `npm test` and
needs no separate CI step.

---

### R8 — Type checking covers the code it claims to

**User story:** As a reviewer, I want "mypy passes" to be a statement about the codebase,
not about a shrinking subset of it.

**Acceptance criteria**

8.1 THE `ignore_errors = true` OVERRIDES in `pyproject.toml` — currently covering
`ai_team.backends.langgraph_backend.*`, `ai_team.backends.claude_agent_sdk_backend.*`,
`ai_team.agents.*`, `ai_team.crews.*`, `ai_team.flows.main_flow`,
`ai_team.memory.memory_config`, `ai_team.tools.git_tools`, `ai_team.tools.test_tools`,
`ai_team.tools.smoke_tools`, `ai_team.utils.callbacks`, `evals.fixtures*`,
`evals.metrics`, `evals.run_evals`, `evals.backends.*`, and
`evals.test_backend_comparison` — SHALL be recorded as a **countable debt** with a floor
that only moves down.

8.2 THE SYSTEM SHALL enforce the debt as a **line count, not a module count**: a test that
sums the LOC of every module matched by an `ignore_errors` override and fails when the sum
exceeds the recorded floor. Counting modules is gameable by splitting a file and treats a
30-line module as equal to a 1,440-line one — `flows/main_flow.py` alone is 1,440 of the
untyped lines.

8.3 THIS SPEC SHALL retire at least the overrides whose modules it already touches:
`evals.backends.*` and `evals.test_backend_comparison` (removed or moved by R6),
`ai_team.tools.smoke_tools` and `ai_team.tools.test_tools` (named *enforced* in the
harness table, R2).

8.4 EACH REMAINING OVERRIDE SHALL carry an inline comment naming the reason and the
condition under which it is removed. An override with no stated exit is not permitted.

8.5 NO NEW MODULE SHALL be added to the `ignore_errors` list without an accompanying
entry in the same commit's message explaining why the floor moved the wrong way.

---

### R9 — Drift guards for reachability and references

**User story:** As the maintainer, I want the next orphan module to fail CI, not to be
discovered in a review six months later.

**Acceptance criteria**

9.1 THE SYSTEM SHALL add a reachability test that builds the import graph over
`src/ai_team/` and `evals/` (vendored code excluded) and fails on any module that is
neither reachable from an entry point nor listed in an explicit, commented
`DORMANT_MODULES` allowlist.

9.2 THE ALLOWLIST IS THE DOCUMENTATION of every deliberately dormant module and SHALL
name the flag that activates each (R1.4).

9.3 THE SYSTEM SHALL add a link/reference checker per R4.4.

9.4 THE SYSTEM SHALL add a test asserting the README structure tree matches the real
package layout (R5.2).

9.5 EVERY GUARD SHALL fail with a message naming the file and the fix. A guard whose
output is `expected 3 to be 0` will be skipped by the next person in a hurry.

9.6 THE GUARDS SHALL run in the existing `lint` CI job, not a new one.

---

### R10 — CrewAI-private code lives under its backend

**User story:** As a reader of the package tree, I want the layout to tell me the truth
about what is shared and what belongs to one engine.

**Acceptance criteria**

10.1 `src/ai_team/agents/` (1,327 LOC), `crews/` (1,388), `tasks/` (1,071), and `flows/`
(2,986) — **6,772 LOC reachable only through `backends/crewai_backend/backend.py`** —
SHALL move under `src/ai_team/backends/crewai_backend/`, matching the self-contained shape
of the other two backends.

10.2 THE ONE EXTERNAL CONSUMER, `evals/checks/trajectory.py`, imports `ai_team.flows` for
phase names. That coupling SHALL be replaced by a backend-neutral source (a constant in
`core/`, or the taxonomy), so a check never imports a backend.

10.3 IMPORT-PATH COMPATIBILITY: this repository has **no external consumers** — nothing
outside it imports `ai_team.crews`. Shim modules are therefore **optional**, and the default
is a hard move with imports updated in the same commit. Add shims only if an external
consumer is known to exist; a deprecation cycle for an audience of zero is ceremony, and a
reviewer reads it as cargo-culting rather than as care.

10.4 AFTER THE MOVE, the three backend subtrees SHALL be symmetric: each owns its agents,
its orchestration, and its adapters, and imports shared contracts only from `core/`,
`harness/`, `config/`, `tools/`, and `guardrails/`.

10.5 A TEST SHALL assert that no module under `core/`, `harness/`, `config/`, or `evals/`
imports from `ai_team.backends.*` (the dependency direction rule).

10.6 THE MOVE SHALL be a pure relocation: no behaviour change, no signature change, no
opportunistic refactor in the same commit.

---

### R11 — Stated contract for the shared core

**User story:** As a contributor adding a feature, I want to know which package it goes in
without reading all fifteen.

**Acceptance criteria**

11.1 `design.md` §4 SHALL state, in one table, what each surviving top-level package owns
and what it may import. The table SHALL fit on one screen — if it does not, the package
structure is the problem, not the table. *(Review item.)*

11.2 `harness/__init__.py`'s EXISTING DOCSTRING RULE — "This module MUST NOT import
backends or crews" — SHALL be generalized into that table and enforced by the test in
R10.5.

11.3 `src/ai_team/guardrails/__init__.py` (572 LOC of logic in a package `__init__`) SHALL
move its implementation into named modules, leaving the `__init__` as a facade of imports
and `__all__`.

11.4 `src/ai_team/utils/` SHALL be dissolved or justified: a package named "utils" states
that its contents had no home. Each member (`reasoning.py` 348, `backend_comparison.py`,
`callbacks.py`, `llm_wrapper.py`, `demo_input.py`, `coverage_paths.py`) SHALL move to the
package that owns its subject or be deleted if unreachable (R1).

11.5 THE `models/` PACKAGE (939 LOC, of which `outputs.py` at 459 is imported only by
`ui/artifacts/service.py`) SHALL be reviewed against the same rule.

---

### R12 — Complexity budget

**User story:** As a reviewer opening a random file, I want to be able to read a function
without scrolling twice.

**Acceptance criteria**

12.1 THE AUDIT BASELINE IS: **63 functions over 80 lines**, 8 over 150, 17 with more than
8 parameters. The worst are `src/ai_team/main.py:_cmd_run` (259 lines, 71 branches, 16
parameters), `backends/claude_agent_sdk_backend/tools/mcp_server.py:build_ai_team_mcp_tools`
(264 lines), `evals/gate.py:evaluate_gate` (230 lines, 38 branches),
`ui/web/server.py:_execute_run` (183 lines), and `flows/main_flow.py:_kickoff_impl`
(154 lines).

12.2 THE SYSTEM SHALL record these counts as ratchets in a config file and SHALL add a
test that fails when any count rises. **Branch count is the primary axis**; line count is
secondary. A ratchet on length alone rewards splitting a function in half at an arbitrary
point, which moves the number without improving anything — `_cmd_run`'s 71 branches are the
defect, its 259 lines are the symptom.

12.3 THIS SPEC SHALL reduce the three worst offenders below 120 lines each by extraction,
not by reformatting: `_cmd_run`, `build_ai_team_mcp_tools`, `evaluate_gate`.

12.4 `_cmd_run`'s 16 PARAMETERS SHALL be replaced by a single typed options object built
from the parsed arguments, so the CLI surface and the run surface stop being the same
signature.

12.5 EXTRACTED FUNCTIONS SHALL be covered by the existing tests for their parent; where
the parent had no test, one SHALL be added before the extraction.

12.6 THE RATCHET SHALL NOT be applied to `evals/cli.py:build_parser` (215 lines, 0
branches) or other flat declarative builders; `design.md` §6 SHALL define the exemption
narrowly.

---

### R13 — The web API is decomposed

**User story:** As a contributor fixing one endpoint, I do not want to open a
1,791-line module.

**Acceptance criteria**

13.1 `src/ai_team/ui/web/server.py` (1,791 LOC, 24 routes) SHALL be split into FastAPI
routers by resource: health/catalog, runs, comparisons, projects/artifacts, websockets —
plus an app factory.

13.2 EVERY ROUTE PATH, METHOD, RESPONSE SHAPE, AND STATUS CODE SHALL be unchanged. The
Playwright suite (`tests/e2e/web`) and the frontend API client are the proof.

13.3 THE SPLIT SHALL NOT introduce a new abstraction layer — no service/repository
indirection, no DI container. Routers plus the existing modules are enough.

13.4 THE MODULE-LEVEL SIDE EFFECTS (the module-scope `app`, the CORS middleware, the
`_FRONTEND_REGISTERED` global) SHALL move into an app factory so tests can build an app
without import-time state.

13.5 THE COST-RESOLUTION FALLBACK CHAIN (`_resolve_token_estimate` tries the monitor, then
the receipt, then live spend) SHALL be consolidated into one documented resolver with a
stated precedence order, since it currently reads as three competing sources of truth for
the number the dashboard shows.

---

### R14 — One dependency source, real project metadata

**User story:** As someone installing this, I want one answer to "what does it depend on".

**Acceptance criteria**

14.1 `pyproject.toml` SHALL declare dependencies **once**. It currently carries a PEP 621
`[project.dependencies]` list **and** a parallel `[tool.poetry.dependencies]` list that
must be hand-synced, while the build backend is `poetry-core` and the documented workflow
is `uv sync`.

14.2 THE SURVIVING DECLARATION SHALL be PEP 621 `[project]`, with a build backend that
reads it. The Poetry tables SHALL be removed.

14.3 `[project]` SHALL carry real `authors` metadata. The Poetry table currently reads
`"Your Name <your.email@example.com>"` in a repository whose purpose is attribution.

14.4 THE PINNING COMMENTS that explain non-obvious constraints (`litellm == 1.74.9`,
the `aiohttp` CVE floor, the `pip >= 26.2` constraint) SHALL be preserved verbatim in the
surviving declaration. They are evidence of real dependency work and are worth more than
the lines they occupy.

14.5 `uv sync --frozen` AND `uv build` SHALL both succeed after the change, and CI SHALL
prove it.

---

### R15 — The control plane has a control

**User story:** As anyone who runs this on a laptop on a shared network, I want the API
that spends money to require a credential.

**Acceptance criteria**

15.1 EVERY MUTATING ROUTE SHALL require authentication: `POST /api/estimate`,
`POST /api/demo`, `POST /api/runs/{id}/resume`, `POST /api/runs/{id}/cancel`,
`DELETE /api/runs/{id}`, and the `/ws/run` WebSocket.

15.2 READ ROUTES that expose workspace contents — `/api/projects/{id}/tree`,
`/api/projects/{id}/file`, `/api/projects/{id}/download.zip`, `/api/runs*` — SHALL require
the same credential.

15.3 THE MECHANISM SHALL be a single shared token supplied by environment variable
(`AI_TEAM_WEB_TOKEN`), checked by one FastAPI dependency, compared with
`secrets.compare_digest`. This is a single-operator boundary, not an identity system
(non-goal).

15.3a THE SYSTEM SHALL add a **route-coverage test** that enumerates `app.routes` at import
time and asserts every route is either listed in an explicit public allowlist (`/api/health`,
the SPA catch-all, static assets) or carries the auth dependency. Asserting that today's 24
routes return 401 checks this spec's work; the route-coverage test is what catches the
twenty-fifth route somebody adds next year. The allowlist is the documentation of every
deliberately public endpoint.

15.4 WHERE `AI_TEAM_WEB_TOKEN` IS UNSET, THE SERVER SHALL bind loopback only and SHALL log
a prominent warning at startup stating that the control plane is unauthenticated. It SHALL
NOT bind a non-loopback interface without a token.

15.5 THE DEFAULT `--host` SHALL become `127.0.0.1`. Binding `0.0.0.0` SHALL require both
an explicit flag and a configured token.

15.6 THE FRONTEND SHALL send the token when present; the development flow SHALL remain
one command with no token required, because it binds loopback (15.4).

15.7 THE WEBSOCKET ENDPOINTS SHALL validate the token at handshake and SHALL validate
`Origin` against the configured CORS allowlist, since CORS does not apply to WebSockets.

15.8 RATE LIMITING IS OUT OF SCOPE, but `design.md` §7 SHALL record it as the next
control.

---

### R16 — Artifact reads cannot escape the workspace

**User story:** As an operator, I want a symlink written by an agent to be unable to read
my home directory through the dashboard.

**Acceptance criteria**

16.1 `_abs_path_for_rel` in `src/ai_team/ui/artifacts/service.py` SHALL assert containment
**after** resolution: `resolved.is_relative_to(base)` (or `os.path.commonpath`), raising
otherwise. Today it checks `".." in rel_path` and a leading `/` before joining, then
returns `(base / rel_path).resolve()` with no post-resolve assertion — so a symlink inside
the workspace, which agents can create, resolves outside the boundary.

16.2 DIRECTORY WALKS (`_list_relative_files`, `build_tree`, `workspace_zip_bytes`) SHALL
not follow symlinks out of the base, and SHALL skip symlinked entries whose target is
outside it.

16.3 THE SENSITIVE-PATH FILTER (`_is_sensitive`, a substring denylist) SHALL be documented
as defence-in-depth rather than as the boundary, and the boundary SHALL be 16.1.

16.4 ADVERSARIAL TESTS SHALL cover: a symlink to `/etc/passwd`, a symlink to a sibling
run's workspace, a nested symlinked directory, and an absolute-path `project_id`. This
matches the project's existing rule that every tool ships with adversarial tests.

16.5 THE ZIP DOWNLOAD SHALL apply the same containment rules as the file read, so the two
paths cannot diverge.

---

### R17 — The threat model covers the control plane

**User story:** As a security reviewer, I want the document to model the system I can
reach over the network.

**Acceptance criteria**

17.1 `SECURITY.md` SHALL add control-plane rows to its threat table: unauthenticated run
start (cost), unauthenticated deletion (destructive), workspace read exposure
(confidentiality), and WebSocket origin spoofing.

17.2 EACH NEW ROW SHALL name its control per R15/R16, in the same
threat/vector/control format already used.

17.3 `SECURITY.md` SHALL state the intended deployment posture in one line — a
single-operator tool bound to loopback unless a token is configured — so that a reader
knows what is and is not claimed.

17.4 THE EXISTING AGENT-LAYER CONTENT SHALL be preserved. It is the strongest document in
the repository.

17.5 THE DOCUMENT SHALL state the vulnerability-reporting channel and the supported
version window, since a repository that claims enterprise readiness is expected to have
one.

---

### R18 — The container is what it says it is

**User story:** As a reviewer running `docker build`, I want the image to contain the
application it advertises and nothing else.

**Acceptance criteria**

18.1 THE DOCKERFILE IS TITLED "web UI (FastAPI + React)" BUT HAS NO NODE BUILD STAGE, so
`frontend/dist/index.html` never exists in the image and `register_frontend()` silently
returns — the container serves the API with no UI. THE SYSTEM SHALL either add a Node
build stage that produces `dist/` and copies it into the runtime image, or retitle the
image and document it as API-only.

18.2 `register_frontend()` SHALL log a warning when `dist/index.html` is missing instead
of returning silently, so this failure is visible in container logs.

18.3 THE RUNTIME STAGE SHALL NOT install `build-essential`. A compiler toolchain in a
production image is attack surface and image weight; it belongs in the builder stage only.
`git` SHALL be justified (the agents use it) or removed.

18.4 `.dockerignore` SHALL exclude `node_modules`, `dist`, `workspace`, `logs`, and
`.coverage-data`. Today `COPY src ./src` carries the frontend's `node_modules`
(~230 MB locally) into both stages.

18.5 THE HEALTHCHECK SHALL probe `/api/health`, which exists for that purpose, rather than
`/api/backends`.

18.6 THE IMAGE SHALL declare a non-root `USER` (it does) and SHALL be verified by a CI
step that builds the image and asserts: non-root user, no `gcc` on `PATH`, image size
below a recorded ratchet, and `/api/health` returning 200 in a started container.

18.7 THE IMAGE SHALL NOT bake secrets; `.env` is already excluded and SHALL remain so.

---

### R19 — Compose describes the current system

**User story:** As someone running `docker compose up`, I want it to work and to reflect
how the project actually runs.

**Acceptance criteria**

19.1 `docker/docker-compose.yml` USES `build: .` WITH THE COMPOSE FILE IN `docker/`, so
the build context cannot see `pyproject.toml`, `uv.lock`, or `src/`. THE CONTEXT SHALL be
corrected (`context: ..`, `dockerfile: docker/Dockerfile`) and a CI step SHALL prove the
compose build succeeds.

19.2 THE `ollama` SERVICE with NVIDIA GPU reservations SHALL be removed or moved behind an
optional profile. The documented provider path is OpenRouter/Anthropic, the Ollama setup
scripts the docs reference no longer exist (R4.3), and a GPU reservation in the default
compose file will fail on most reviewers' machines.

19.3 THE APP SERVICE SHALL set `AI_TEAM_WEB_TOKEN` (R15) and SHALL NOT publish a port
without it.

19.4 THE APP SERVICE SHALL declare resource limits and `restart` policy, since the claim
under test is operational maturity.

19.5 VOLUME MOUNTS SHALL cover `workspace/` as well as `output/`, or the compose run SHALL
document that run workspaces are ephemeral.

---

### R20 — Everything here is enforced by a check

**User story:** As the maintainer, I want this spec to be the last time these things are
found by a human.

**Acceptance criteria**

20.1 EACH OF THE FOLLOWING SHALL have an automated check that fails the build:
reachability (R9.1), dormant-module allowlist (R9.2), reference integrity (R9.3), README
structure (R9.4), tests-outside-testpaths (R6.3), mypy-ignore budget (R8.2), complexity
ratchets (R12.2), dependency-direction rule (R10.5), data artifacts and image references
(R21.2, R21.4, R21.8), image properties (R18.6), compose build (R19.1).

20.2 THE CHECKS SHALL live beside the code they check (`tests/unit/repo/`) and SHALL run
in the existing `lint` and `test` CI jobs.

20.3 EVERY RATCHET VALUE SHALL be stored in one file with a comment recording the date and
the measurement that set it, in the style of the existing `fail_under` history block in
`pyproject.toml` — which is a model of how to record a ratchet and SHALL be cited as the
precedent.

20.4 A RATCHET MAY ONLY MOVE in the improving direction; a commit that loosens one SHALL
state why in its message.

20.5 THE FULL CHECK SUITE SHALL add no more than 30 seconds to CI, measured once at task
8.6 and recorded in `BASELINE.md`. A guard that makes the build slow is a guard that gets
disabled. *(Measured once, not asserted per-run — a wall-clock assertion in CI is itself a
flaky test.)*

---

### R21 — Data and generated artifacts

**User story:** As a reviewer, I want every committed data file to be either an input the
system reads, a baseline someone accepted, or evidence — and to be able to tell which.

**Context.** The audit's first pass covered markdown, Python, and the frontend; it did not
cover the 195 tracked JSON/JSONL/YAML files, 38 images, or the accepted baselines. A second
pass found the eval fixture corpus in excellent condition and three problems elsewhere.

**Acceptance criteria**

21.1 **The Tier A baseline is stale and partial.** `evals/baselines/tier_a.json` was accepted
`2026-08-16` against git sha `f534cee` — before the harness-alignment work landed — records
outcomes for **13 checks while 20 are registered**, marks every one of those 13 `"fail"`, and
carries `suite_pass_pow_k: 0.0`.

THE TEAM SHALL **first diagnose, then decide**: run `python -m evals.cli run --tier A` against
the current corpus and determine whether an aggregate per-check `"fail"` is the correct encoding
for a corpus deliberately built from fail/pass fixture pairs, or a defect. Only then SHALL the
baseline be regenerated (`baseline accept --reason …`) or left as-is with an explanatory
`reason`.

THIS ORDER IS MANDATORY. This audit did not run the suite; it read the file. Regenerating a
baseline whose semantics nobody has confirmed replaces one unexplained reference state with
another, in the single file that defines what the $0 gate accepts.

21.2 A TEST SHALL assert that the baseline covers every registered check id, so a new check
cannot be added without either a baseline entry or an explicit exemption.

21.3 **25 of 38 tracked images (~7 MB of the repo's 9 MB `docs/images/`) are referenced by no
tracked file**, including `dashboard.png` (808 KB), `ai-team-work-sample-{1,2}.png` (1.4 MB),
twelve `compare-2026-07-03-*` screenshots, `compare-verified-2026-07-06.gif` (676 KB), and the
`substack-*` / `hero-linkedin.*` publication assets. EACH SHALL be either referenced from a
document, moved under a clearly named directory with a `README.md` stating it is an external
publication asset, or deleted.

21.4 A DRIFT GUARD SHALL fail on an image under `docs/images/` that no tracked file references
and that is not listed in the publication-assets allowlist (R9, R20).

21.5 `evals/golden/.validation_log.jsonl` IS TRACKED, HIDDEN, AND EMPTY (0 lines) — an
append-only log committed at zero length. It SHALL be untracked and gitignored, or its purpose
and write path SHALL be documented in `evals/golden/README.md`. A tracked append log that tests
write to is also how the recorded golden-file test-isolation defect (R6.4) reproduces.

21.6 EVERY TRACKED DATA FILE SHALL be classifiable as **authored** (an input a human wrote:
scenarios, agent/task YAML, thresholds), **generated** (produced by a named command), or
**accepted** (a baseline a human blessed, with date and sha). THE CLASSIFICATION SHALL be
stated in the README of the directory that holds it. Directories needing one today:
`evals/fixtures/traces/`, `evals/baselines/`, `evals/golden/`, `tests/fixtures/`,
`evals/corpora/`, `docs/images/`.

21.7 NO GENERATED FILE SHALL be committed without a stated regeneration command.
`docs/benchmark_results.json` — referenced by `docs/performance_report.md` and absent from the
tree — is the existing example of the confusion this rule prevents (R3.2 deletes that document;
this rule stops the next one).

21.8 **The eval fixture corpus SHALL be protected as-is.** The audit found 94 fixture traces
covering 20 distinct check ids with **zero orphan fixtures and zero checks lacking a fixture**,
plus 12 consistently named backend coverage fixtures. This is the best-maintained data in the
repository. A guard SHALL assert both directions of that mapping so it stays true.

21.9 THE VERSION FILES SHALL state what they version. `evals/VERSION` reads `0.1.0` while
`evals/taxonomy/failure_modes.yaml` is at `1.2.0` with 17 failure modes; a reader cannot tell
whether these track the same thing.

21.10 `.cursor/rules/crewai-agents-crews-flows.mdc` AND `.cursor/rules/crewai-tools.mdc`
describe paths that R10 moves. THEY SHALL be updated in the same phase as the move, since a
stale agent rule silently teaches the wrong layout to every future contributor — human or not.

---

### R22 — Performance and scale envelope

**User story:** As a reviewer testing the claim "performant and scalable", I want a number and
a stated limit, not an adjective.

**Context.** The repository's purpose sentence claims four properties. Production-readiness and
security have requirements above. **Performance and scale had none** — this spec's own gap, and
the one a technically strong reviewer probes hardest, because it is where most portfolio
projects are silent. Today: `tests/performance/test_benchmarks.py` holds eight benchmark tests
that publish nothing; the only performance document is being deleted (R3.2) because its numbers
came from a mock-LLM run; and `ui/web/server.py` holds run state in a **process-local dict wiped
on every restart** (`RunState.runs`, whose own docstring says so — the Compare tab's
reattachment machinery exists to work around it).

The fix is not to build scale. It is to **measure once and state the envelope honestly** — which
is the same move that makes `SECURITY.md` and the "Honest gaps" paragraph credible.

**Acceptance criteria**

22.1 THE SYSTEM SHALL publish one real benchmark with real numbers, generated by a recorded
command, stating hardware, model, date, and sample size. THE RUN SHALL be human-triggered and
capped at **$25** (design §12.9), and SHALL reuse the existing spend guard rather than a new
one. A benchmark that cannot be reproduced
from the repository SHALL NOT be published.

22.2 THE BENCHMARK SHALL measure what the harness controls and what a reader would actually ask:
wall-clock and cost per phase, tokens per run, and the overhead the harness adds over a bare
backend call — not a synthetic microbenchmark.

22.3 WHERE the benchmark is produced by a mock or demo run, it SHALL say so in the same block as
the numbers, and SHALL state what it does and does not measure (R3.4). The deleted
`performance_report.md` is the precedent: its admission that mock timings "read like performance
data but measured nothing" is the standard to meet.

22.4 THE SYSTEM SHALL document the **operating envelope** in one place: single process; run
registry in memory and lost on restart; concurrent-run ceiling and where it comes from;
per-run workspace disk growth; the spend ceiling; and the wall-clock kill.

22.5 THE ENVELOPE DOCUMENT SHALL state what would have to change to lift each limit — a
persistent run store, a queue, a worker pool — **without implementing any of it**. Naming the
next architectural step is evidence of judgement; building it for a single-operator tool is
evidence of the opposite.

22.6 THE SYSTEM SHALL define a **retention policy** for `workspace/` and `output/`, which grow
without bound (437 run directories, 28 MB, on the audit machine), and SHALL provide the command
that enforces it.

22.7 `tests/performance/` SHALL either produce the published artifact of 22.1 or be removed.
Eight benchmark tests that publish nothing are the same defect as a module nothing imports
(R1).

22.8 NO SCALABILITY CLAIM SHALL appear in the README that 22.4 does not support. If the envelope
is "one operator, one machine, runs are ephemeral", the README says that — a precise small claim
reads as senior; a vague large one reads as marketing.

---

### R23 — Repository surface and supply chain

**User story:** As a reviewer, I want the repository's own metadata to show the same care as its
code.

**Context.** These are 30-minute items with disproportionate payoff, because they are the
conventions a reviewer checks reflexively before reading any code.

**Acceptance criteria**

23.1 EVERY GITHUB ACTION SHALL be pinned to a commit SHA, not a floating tag. All 27 `uses:`
lines across both workflows currently pin `@v4` / `@v5`, which is a mutable reference — the
standard supply-chain finding for a repository that ships a `security` CI job and a threat
model.

23.2 THE REPOSITORY SHALL provide a pull-request template and at least one issue template.
Neither exists.

23.3 THE REPOSITORY SHALL provide `CODEOWNERS`, even with a single owner. It states who is
accountable, which is the point.

23.4 THE PROJECT SHALL carry a `CHANGELOG.md` and at least one tagged release. `version` has
been `0.1.0` since the first commit while the project has passed through three orchestration
backends and two spec cycles.

23.5 EVERY BADGE in the README SHALL reflect a check that runs. The CI badge is accurate; any
badge added later SHALL meet the same bar.

23.6 THE SECURITY CI JOB SHALL publish its `pip-audit` output as an artifact, so "the security
job passed" is inspectable rather than asserted.

23.7 AN SBOM IS OPTIONAL. WHERE one is produced, it SHALL be generated in CI from the lockfile,
never committed by hand.

---

### R24 — Test design bar for everything this spec adds

**User story:** As the maintainer, I do not want ten new guard modules to become the next
source of flaky, order-dependent tests.

**Context.** This spec adds roughly a dozen test modules — eight repo guards, adversarial
artifact tests, auth tests, container assertions. They parse files, walk the tree, and read
config, which is precisely the shape that produced this repository's two existing
test-isolation defects (golden-file writes; an order-dependent workspace test). A guard suite
that is itself unreliable is worse than no guard suite, because it trains the team to re-run
CI until it goes green.

**Acceptance criteria**

24.1 EVERY TEST this spec adds SHALL be **offline, deterministic, and order-independent**: no
network, no model call, no dependence on the working directory, no dependence on another
test having run. The suite SHALL pass under a shuffled run.

24.2 NO TEST this spec adds SHALL write to a tracked file. The existing `tests/conftest.py`
hash guard over `evals/golden/`, `evals/fixtures/traces/`, and `evals/taxonomy/` already
asserts this for those paths; the new tests SHALL respect it rather than extend the ignore
list.

24.3 EVERY GUARD SHALL ship with a demonstration that it can fail. Either a negative fixture
committed alongside it, or a one-line mutation recorded in the test's docstring
(`to see this fail: add padding: 0.35rem to App.css`). A guard nobody has watched fail is a
guard nobody knows works.

24.4 EVERY GUARD THAT SCANS A SET SHALL fail when the set is empty. A glob that matches
nothing, a registry that imports nothing, or an AST walk over zero files SHALL raise rather
than report success — the most common silent failure in repo-hygiene tests is a path that
stopped matching after a refactor.

24.5 NO NEW PYTEST MARKER SHALL be introduced without an entry in `pyproject.toml`'s `markers`
list. The repo registers twelve markers today and that discipline SHALL hold.

24.6 EVERY GUARD'S FAILURE MESSAGE SHALL name the offending file, the line where possible, and
the action that fixes it (R9.5). This is restated here because it is the single property that
decides whether a guard survives its first angry morning.

24.7 THE NEW TESTS SHALL live in `tests/unit/repo/` (repository invariants) or beside the code
they cover (`tests/unit/ui/`, `tests/unit/harness/`), never in a new top-level directory.

24.8 THE ADDED RUNTIME SHALL be measured once at task 8.6 and recorded, not asserted per-run
(R20.5).

---

## Traceability summary

| Requirement | Primary files |
| --- | --- |
| R1, R2 | `src/ai_team/harness/*`, `evals/ladder_report.py`, `evals/arms/base.py`, `docs/HARNESS.md`, `docs/SELF_IMPROVEMENT.md` |
| R3, R4, R5 | `docs/**`, `README.md`, `.archive/` |
| R6 | `evals/backends/test_*.py`, `evals/test_backend_comparison.py`, `pyproject.toml` |
| R7 | `.github/workflows/ci.yml` |
| R8 | `pyproject.toml`, `tests/unit/repo/test_type_budget.py` (new) |
| R9, R20 | `tests/unit/repo/*` (new), `.github/workflows/ci.yml` |
| R10, R11 | `src/ai_team/{agents,crews,tasks,flows,utils,models,guardrails}/`, `evals/checks/trajectory.py` |
| R12 | `src/ai_team/main.py`, `backends/claude_agent_sdk_backend/tools/mcp_server.py`, `evals/gate.py` |
| R13 | `src/ai_team/ui/web/server.py` → `ui/web/routers/*` |
| R14 | `pyproject.toml` |
| R15, R17 | `src/ai_team/ui/web/server.py`, `config/settings.py`, `SECURITY.md`, `.env.example` |
| R16 | `src/ai_team/ui/artifacts/service.py`, `tests/unit/ui/test_artifacts_adversarial.py` (new) |
| R18, R19 | `docker/Dockerfile`, `docker/docker-compose.yml`, `.dockerignore` |
| R21 | `evals/baselines/tier_a.json`, `evals/golden/`, `docs/images/`, `evals/VERSION`, `.cursor/rules/*.mdc` |
| R22 | `tests/performance/`, `docs/PERFORMANCE.md` (new), `ui/web/server.py` (`RunState`), `scripts/` (retention) |
| R23 | `.github/workflows/*.yml`, `.github/` templates, `CODEOWNERS`, `CHANGELOG.md` |
| R24 | every test module this spec adds; `tests/conftest.py`; `pyproject.toml` markers |
