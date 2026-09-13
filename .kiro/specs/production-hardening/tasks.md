# Implementation Plan — Production Hardening

**Spec ID:** `production-hardening`
**Requirements:** [`requirements.md`](./requirements.md) · **Design:** [`design.md`](./design.md)

---

## How to execute this plan

### Two tracks, and they are not the same priority

The phase numbers are a dependency order, **not a priority order**. For a repository whose
purpose is to be read, the payoff per hour differs by an order of magnitude between phases:

| Phase | Track | Est. effort | What a reviewer sees |
| --- | --- | --- | --- |
| 1 Delete | **A** | 0.5 day | Nothing dead; ~1,600 LOC and ~7 MB lighter |
| 2 Truth | **A** | 1 day | Docs that match code — the highest-value hour in the spec is 2.1 |
| 3 Gates | **A** | 0.5 day | CI that can actually fail; pinned actions; a release |
| 4 Security | **A** | 1–1.5 days | An API that requires a credential; a threat model that covers it |
| 5 Container | **A** | 0.5 day | `docker build` produces the app it advertises |
| 9 Evidence | **A** | 1 day | Real numbers and a stated envelope for "performant / scalable" |
| 8 Guards | **A−** | 0.5 day | Nothing regresses — invisible to a reviewer, decisive for the maintainer |
| 6 Boundaries | **B** | 2–3 days | A tidier package tree. Near-invisible in a 30-minute read |
| 7 Complexity | **B** | 2–3 days | Shorter functions. Near-invisible in a 30-minute read |

**Track A is roughly a week and addresses everything a reviewer finds.** Track B is another
week of the largest, riskiest diffs in the repository (6,772 LOC moved; 24 routes re-homed)
for changes that mostly serve the maintainer. Do Track A first, in phase order; treat Track B
as optional and schedule it only if the repository is going to keep being developed.

Recommended order: **1 → 2 → 3 → 4 → 5 → 9 → 8**, then 6 and 7 if warranted.

### Coordination with `ui-refinement`

Task 3.1 turns on `npm test` in CI. The [`ui-refinement`](../ui-refinement/) spec adds a
stylesheet drift test that **fails until its Phases 1–6 land**. Sequence one of:

- land this spec's 3.1 first, then run `ui-refinement` Phases 1–6 before its Phase 9; or
- land `ui-refinement` Phases 1–9 entirely, then 3.1.

Turning on the CI step while a red-by-design test exists leaves `main` broken for days, which
is worse than either spec's problem.

### Rules

- Work **one task at a time, in order within a phase**. Do not batch phases.
- Every task lists a **Definition of done**. Do not mark it complete until each bullet is
  literally true.
- **Gate after every task:**
  `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy evals/ && uv run pytest tests/unit`
- **Gate after every phase** that touches the web layer or the run path:
  `uv run pytest tests/e2e/web -m web_e2e`
- **No task spends money except 9.1.** Nothing else here makes a live model call; if a task
  seems to need one, it is the wrong task. Task 9.1 (the published benchmark) is the single
  exception: human-triggered, capped at $25, receipt recorded.
- One commit per task, one PR per phase, each green on its own so any phase can be
  reverted independently.
- Phase 8's guards will fail until Phases 1–7 land. That is expected — do not write them
  early and do not weaken them to make them pass.

Cursor prompt shape:

```
Read .kiro/specs/production-hardening/requirements.md and design.md for context.
Implement task 1.3 from .kiro/specs/production-hardening/tasks.md.
Do not start any other task. Do not change run semantics, check IDs, route paths,
or data-testid values. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

---

## Phase 0 — Baseline

- [x] **0.1 Record the before state**
  - Write `.kiro/specs/production-hardening/BASELINE.md` with: LOC per top-level package;
    the five orphan modules and their LOC; the 808 LOC of uncollected tests; the
    `ignore_errors` module count (16); complexity counts (63 / 8 / 17); `docs/**.md` file
    count (42); count of unresolvable doc references; `docker build` image size; and the
    current `pytest tests/unit` pass count.
  - **Definition of done:** every number in `requirements.md`'s introduction is reproduced
    by a command recorded in `BASELINE.md`, so the spec's own claims are checkable.
  - _Requirements: R20.3_

- [x] **0.2 Record the wire-or-delete decisions**
  - Fill the decision column of `design.md` §2 for all five modules. This is a **human
    decision**, not an agent one — the agent records it.
  - **Definition of done:** each of the five has `wire`, `dormant`, or `delete` written in
    the table with one sentence of rationale.
  - _Requirements: R1.2_

---

## Phase 1 — Deletion

Nothing in this phase changes behaviour. Every deletion is preceded by a repo-wide search.

- [x] **1.1 Remove orphan modules marked `delete`**
  - For each module marked `delete` in 0.2, remove it and its tests in one commit naming
    the superseding mechanism.
  - **Definition of done:** `uv run pytest tests/unit` green; no reference to the module
    remains in `src/`, `evals/`, `tests/`, or `docs/`.
  - _Requirements: R1.5_

- [x] **1.2 Resolve the uncollected test files**
  - `evals/backends/test_claude_sdk_eval.py` (175), `test_crewai_eval.py` (169),
    `test_langgraph_eval.py` (191), `evals/test_backend_comparison.py` (273): move under
    `tests/integration/` with an appropriate marker and make them pass, or delete.
  - Remove the corresponding `ignore_errors` overrides from `pyproject.toml`.
  - **Definition of done:** no `test_*.py` outside `testpaths`; `uv run pytest tests/unit`
    and `uv run pytest tests/integration -m "not real_llm"` green; two `ignore_errors`
    entries gone.
  - _Requirements: R6.1, R6.2, R8.3_

- [x] **1.3 Remove empty and orphan directories**
  - `src/ai_team/rag/`, `src/ai_team/optimizers/`, `tests/unit/rag/`, `evals/annotations/`
    (if it has no `.gitkeep` purpose), and the untracked
    `src/ai_team/ui/web/frontend/workspace/` debris.
  - **Definition of done:** `find src evals tests -type d -empty` returns only directories
    with a documented `.gitkeep` purpose.
  - _Requirements: R1.7_

- [x] **1.4 Resolve `.archive/`**
  - Per decision 12.4: **keep** the 21 tracked files and add
    `.archive/README.md` stating the retention rule and why each survivor is kept.
  - Fix the two docs linking into it (`docs/prompts/PROMPTS.md`,
    `docs/prompts/PROMPT_TRACKING.md`).
  - **Definition of done:** no doc links into a non-existent archive path.
  - _Requirements: R3.2, R4.1_

- [x] **1.5 Resolve unreferenced images and the tracked empty log**
  - Triage the 25 unreferenced images (~7 MB): reference, move to a publication-assets
    directory with a `README.md` stating their purpose, or delete.
  - Untrack and gitignore `evals/golden/.validation_log.jsonl`, or document its purpose and
    write path in `evals/golden/README.md`.
  - **Definition of done:** every file under `docs/images/` is referenced or listed in the
    publication-assets allowlist; no tracked zero-length append log remains.
  - _Requirements: R21.3, R21.5_

- [x] **1.6 Consolidate the dependency declaration and fix project metadata**
  - Remove the `[tool.poetry]` / `[tool.poetry.dependencies]` / `[tool.poetry.group.dev]`
    tables; keep PEP 621 `[project]` as the single source; switch the build backend to one
    that reads it (design §12.6 defaults to `hatchling`).
  - Preserve the pinning comments verbatim — `litellm == 1.74.9`, the `aiohttp` CVE floor,
    the `pip >= 26.2` constraint. They are evidence of real dependency work.
  - Set real `authors` metadata in `[project]`; the Poetry table currently reads
    `"Your Name <your.email@example.com>"` in a repository whose purpose is attribution.
  - **Definition of done:** dependencies declared once; `uv sync --frozen` and `uv build`
    both succeed; CI proves both; no placeholder metadata remains anywhere in the file.
  - _Requirements: R14.1, R14.2, R14.3, R14.4, R14.5_

- [ ] **1.7 Phase gate**
  - **Definition of done:** full CI green; `BASELINE.md` updated with the LOC delta
    (expect roughly −1,500 to −2,000) and the repository size delta (expect roughly −7 MB
    from images).
  - _Requirements: R20.3_

---

## Phase 2 — Truth

The cheapest phase and the one a reviewer reads first.

- [x] **2.1 Make the harness status table true** *(highest-value task in this spec)*
  - Apply the §3 predicates to all seven rows of `docs/HARNESS.md`. For each row: verify
    the module path exists and is reachable; verify the claimed status against its
    predicate; downgrade the row if it cannot be demonstrated.
  - Expect downgrades on Feedback (`closed-loop` → until 2.2 wires it) and Verification.
  - **Definition of done:** every row's module path resolves; every status word is backed
    by a named test; the "Honest gaps" paragraph is retained and extended if the audit
    found new ones.
  - _Requirements: R2.1, R2.2, R2.3, R2.5_

- [x] **2.2 Wire the modules marked `wire`**
  - For each: put it on a default path, and add a test that exercises it *through* that
    path rather than by direct import.
  - `qa_verdicts`: wire the writer so `docs/qa_verdicts.jsonl` is produced — without it
    `CHK-evaluator-capitulation` can only return `inconclusive`, which is what the
    2026-09-12 journal records.
  - **Definition of done:** each wired module appears in the reachability graph from an
    entry point; `HARNESS.md` rows restored to their claimed status with the test named.
  - _Requirements: R1.3, R2.4_

- [x] **2.3 Make the modules marked `dormant` activatable**
  - Add one documented flag per module (`AI_TEAM_SESSION_LOOP`, a `ladder` CLI
    subcommand); add each to `.env.example` and the configuration reference; add a test
    asserting both the on and off paths.
  - **Definition of done:** each dormant module can be activated in one documented step;
    `evals/arms/base.py`'s component list names no orphan.
  - _Requirements: R1.4, R1.6_

- [x] **2.4 Fix the README**
  - Add the eight missing packages to the structure tree (`agents`, `crews`, `tasks`,
    `flows`, `harness`, `models`, `reports`, `utils` — noting that Phase 6 will move four
    of them). Correct `FM-001…010` to the current taxonomy range. Correct or remove the
    `evals/backends/` description per 1.2. Add the one-line "read this first" pointer.
  - **Definition of done:** the tree matches `ls src/ai_team/`; no claim in the README
    contradicts the code.
  - _Requirements: R5.1, R5.3, R5.4, R5.6_

- [x] **2.5 Adopt the workspace-artifact notation and fix references**
  - Apply the `<workspace>/` prefix convention (design §5.2) across docs; fix the ~70
    unresolvable relative links and the ~20 stale source paths listed in R4.3.
  - **Definition of done:** a manual run of the (not yet CI-wired) reference checker
    reports zero unresolvable references.
  - _Requirements: R4.1, R4.2, R4.3_

- [x] **2.6 Consolidate the document set**
  - Apply the R3.2 table: `EVALS_ROADMAP.md`, `PROMPT_TRACKING.md`,
    `performance_report.md`, `COMPARISON_RESULTS.md`, `RESULTS.md`, and the
    EVALS/EVAL_METHODOLOGY/evals-README overlap.
  - Add the one-line purpose statement to every surviving document (R3.3); label every
    mock/demo number (R3.4).
  - Do not edit `docs/journal/` except for broken links.
  - **Definition of done:** every surviving doc is linked from the README or another
    surviving doc; each opens with its purpose; no doc presents unlabelled mock numbers.
  - _Requirements: R3.1, R3.2, R3.3, R3.4, R3.5, R5.5_

- [x] **2.7 Refresh and explain the Tier A baseline**
  - Regenerate `evals/baselines/tier_a.json` against the current corpus
    (`python -m evals.cli baseline accept --reason …`) so it covers all 20 registered checks
    rather than 13, and pins a current sha.
  - Write a `reason` that explains what a per-check outcome means for a corpus built from
    deliberate fail/pass fixture pairs — the current file reads as "every check fails" with no
    explanation, and it is the file that defines what the $0 gate accepts.
  - Add `README.md` files classifying the contents of `evals/fixtures/traces/`,
    `evals/baselines/`, `evals/golden/`, `evals/corpora/`, `tests/fixtures/`, and
    `docs/images/` as authored / generated / accepted (design §5.4).
  - Reconcile `evals/VERSION` (`0.1.0`) with the taxonomy version (`1.2.0`) or state what each
    one versions.
  - **Definition of done:** the baseline covers every registered check id; its `reason` explains
    the outcome semantics; each named directory has a README stating its category; no reader has
    to guess whether a committed file is an input or an output.
  - _Requirements: R21.1, R21.6, R21.7, R21.9_

- [ ] **2.8 Phase gate**
  - _Requirements: R20.3_

---

## Phase 3 — Gates

- [x] **3.1 Frontend quality gates in CI**
  - Add `npm run lint` and `npm test` to the web CI job, before `npm run build`. Not
    `continue-on-error`.
  - **Definition of done:** CI runs 110 frontend cases; a deliberately broken test fails
    the job.
  - _Requirements: R7.1, R7.2_

- [x] **3.2 Type budget**
  - Add `tests/unit/repo/test_type_budget.py` counting modules matched by `ignore_errors`;
    record the floor (16 minus whatever 1.2 removed) in `ratchets.toml`; give every
    surviving override an inline comment naming its exit condition.
  - **Definition of done:** the test passes at the current count and fails when a module is
    added; no override lacks a stated exit.
  - _Requirements: R8.1, R8.2, R8.4, R8.5_

- [x] **3.3 Retire the overrides this spec has earned**
  - Remove `ignore_errors` for `ai_team.tools.smoke_tools` and `ai_team.tools.test_tools`
    (both cited as *enforced* in the harness table) and fix the resulting type errors.
  - **Definition of done:** `uv run mypy src/` green with two fewer overrides; ratchet
    lowered in the same commit.
  - _Requirements: R8.3_

- [x] **3.4 Collection guard**
  - `tests/unit/repo/test_collection.py`: no `test_*.py` outside `testpaths`.
  - **Definition of done:** passes now; fails if a test file is added under `evals/`.
  - _Requirements: R6.3_

- [ ] **3.5 Test hygiene sweep**
  - Confirm the two recorded isolation defects (golden-file writes; order-dependent
    workspace test) are fixed; review all 35 `pytest.skip` sites for the
    missing-precondition rule.
  - **Definition of done:** `uv run pytest tests/unit -p no:randomly` and a shuffled run
    both green; every skip names a precondition, not a failure.
  - _Requirements: R6.4, R6.5_

- [ ] **3.6 Repository surface and supply chain**
  - Pin all 27 `uses:` lines in both workflows to commit SHAs (keep the version as a trailing
    comment); add a PR template and one issue template; add `CODEOWNERS`; add `CHANGELOG.md`
    and cut a tagged release; publish the `pip-audit` output as a CI artifact.
  - **Definition of done:** no floating action tag remains; `gh release list` shows a tag;
    the security job's audit output is downloadable from the run.
  - _Requirements: R23.1, R23.2, R23.3, R23.4, R23.5, R23.6_

- [ ] **3.7 Phase gate**

---

## Phase 4 — Control plane

- [x] **4.1 Token authentication**
  - Add `AI_TEAM_WEB_TOKEN` to settings and `.env.example`; implement
    `ui/web/auth.py::require_token` per design §7.1 using `secrets.compare_digest`; apply
    to every mutating route and every workspace-reading route. `/api/health` stays open.
  - Add `tests/unit/ui/test_auth.py` covering, per route: 401 without the header, 200 with it,
    and 200 without it when no token is configured.
  - Add the **route-coverage test** in the same module: enumerate `app.routes` and assert each
    is either in the public allowlist (`/api/health`, SPA catch-all, static assets) or carries
    the auth dependency. This is the test that catches the twenty-fifth route, not the
    twenty-four this task secures.
  - **Definition of done:** both tests green; deleting the dependency from any one router makes
    the route-coverage test fail by name; `tests/e2e/web` green (it runs loopback with no
    token).
  - _Requirements: R15.1, R15.2, R15.3, R15.3a_

- [x] **4.2 Safe bind defaults**
  - Default `--host` to `127.0.0.1`; refuse a non-loopback bind unless a token is
    configured; log a startup warning when running unauthenticated on loopback.
  - **Definition of done:** `ai-team-web` binds loopback by default; `--host 0.0.0.0` without a
    token exits non-zero with a message naming the variable; `tests/unit/ui/test_auth.py`
    covers all three cases (default bind, non-loopback without token, non-loopback with token)
    by calling the argument parser and the bind guard directly — no socket is opened in a test.
  - _Requirements: R15.4, R15.5_

- [x] **4.3 WebSocket handshake checks**
  - Validate the token and the `Origin` header at `/ws/run` and `/ws/monitor/{run_id}`.
  - **Definition of done:** a WS connection from a disallowed origin is rejected at
    handshake; a test covers it. (CORS middleware never sees an upgrade — this is the gap
    the task exists to close.)
  - _Requirements: R15.7_

- [x] **4.4 Frontend token support**
  - Send the token when configured; no change to the zero-config local flow.
  - **Definition of done:** dev server works with no token; a configured token is sent on
    every API and WS call; a vitest case asserts the header is attached when configured and
    absent when not; frontend tests green.
  - _Requirements: R15.6_

- [x] **4.5 Artifact path containment**
  - Add the post-resolve `is_relative_to(base)` assertion; stop directory walks following
    symlinks out of the base; apply the same rules to the ZIP download.
  - **Definition of done:** the new adversarial tests (4.6) pass; no existing artifact test
    regresses.
  - _Requirements: R16.1, R16.2, R16.5_

- [x] **4.6 Adversarial artifact tests**
  - `tests/unit/ui/test_artifacts_adversarial.py`: symlink to `/etc/passwd`; symlink to a
    sibling run's workspace; nested symlinked directory; absolute-path `project_id`;
    sensitive-name bypass attempt.
  - **Definition of done:** all five fail closed; reverting 4.5 makes at least three fail.
  - _Requirements: R16.4_

- [x] **4.7 Update the threat model**
  - Add the four control-plane rows to `SECURITY.md` in its existing format; state the
    deployment posture in one line; add the reporting channel and supported-version window.
  - **Definition of done:** every new row names a control that exists in code after 4.1–4.5.
  - _Requirements: R17.1, R17.2, R17.3, R17.4, R17.5_

- [x] **4.8 Phase gate**
  - **Definition of done:** full CI green including `tests/e2e/web`; a manual check that
    the documented local quickstart still works end to end with no token.

---

## Phase 5 — Container

- [x] **5.1 `.dockerignore` and build context**
  - Add `node_modules`, `dist`, `workspace`, `logs`, `.coverage-data`.
  - **Definition of done:** build context size drops by roughly the frontend's
    `node_modules` (~230 MB locally); `docker build` succeeds.
  - _Requirements: R18.4_

- [x] **5.2 Frontend build stage (decision 12.3)**
  - Add a Node stage producing `dist/`; copy it into the runtime image; make
    `register_frontend()` log a warning when `dist/index.html` is absent.
  - **Definition of done:** a started container serves the dashboard at `/`; the warning
    appears when the stage is skipped.
  - _Requirements: R18.1, R18.2_

- [x] **5.3 Runtime image minimality**
  - Remove `build-essential` from the runtime stage; justify or remove `git`; switch the
    healthcheck to `/api/health`.
  - **Definition of done:** `gcc` absent from the runtime image; healthcheck passes;
    image size recorded as the ratchet.
  - _Requirements: R18.3, R18.5_

- [x] **5.4 Compose correctness**
  - Fix the build context (`context: ..`, `dockerfile: docker/Dockerfile`); remove or
    profile-gate the Ollama + GPU service; set `AI_TEAM_WEB_TOKEN`; add resource limits and
    a restart policy; decide the `workspace/` mount.
  - **Definition of done:** `docker compose -f docker/docker-compose.yml build` succeeds
    from a clean checkout on a machine with no GPU.
  - _Requirements: R19.1, R19.2, R19.3, R19.4, R19.5_

- [x] **5.5 Image CI job**
  - Build the image in CI and assert: non-root user, no `gcc` on `PATH`, size under the
    ratchet, `/api/health` → 200 in a started container.
  - **Definition of done:** the job fails if any assertion is violated; runtime under two
    minutes.
  - _Requirements: R18.6, R18.7_

- [x] **5.6 Phase gate**

---

## Phase 6 — Package boundaries *(largest diff)*

- [ ] **6.1 Break the eval→backend coupling**
  - Replace `evals/checks/trajectory.py`'s import of `ai_team.flows` with a
    backend-neutral phase-name source in `core/` or the taxonomy.
  - **Definition of done:** no module under `evals/` imports `ai_team.backends` or
    `ai_team.flows`; check behaviour unchanged (Tier A replay identical).
  - _Requirements: R10.2_

- [ ] **6.2 Move the CrewAI-private packages**
  - `git mv` `agents/`, `crews/`, `tasks/`, `flows/` under
    `src/ai_team/backends/crewai_backend/`. Update imports. **No other change in this
    commit.**
  - Update `.cursor/rules/crewai-agents-crews-flows.mdc` and `.cursor/rules/crewai-tools.mdc`
    to the new paths in the same commit — a stale agent rule silently teaches the wrong
    layout to every future contributor, human or not.
  - **Definition of done:** `uv run pytest tests/unit` green; the diff contains only path,
    import, and agent-rule changes; `tests/e2e/web` green.
  - _Requirements: R10.1, R10.6, R21.10_

- [ ] **6.3 Deprecation shims**
  - Add `ai_team.agents`, `ai_team.crews`, `ai_team.tasks`, `ai_team.flows` shim modules
    that re-export and emit `DeprecationWarning` with a removal date.
  - **Definition of done:** old import paths work and warn; a test asserts the warning.
  - _Requirements: R10.3_

- [ ] **6.4 Import-direction guard**
  - `tests/unit/repo/test_import_direction.py` enforcing the design §4 table.
  - **Definition of done:** passes; adding `from ai_team.backends...` to a `core/` module
    fails it with a message naming the rule.
  - _Requirements: R10.4, R10.5, R11.2_

- [ ] **6.5 Guardrails facade**
  - Move the 572 lines of logic out of `guardrails/__init__.py` into named modules,
    leaving imports and `__all__`.
  - **Definition of done:** no behaviour change; every existing guardrail test green
    without import changes.
  - _Requirements: R11.3_

- [ ] **6.6 Dissolve `utils/` and review `models/`**
  - Move each member of `utils/` to the package that owns its subject, or delete it if
    unreachable. Move `models/outputs.py` to `ui/artifacts/` if it remains single-consumer.
  - **Definition of done:** no package named `utils` remains, or `design.md` §4 records why
    it does; every moved module has a stated owner.
  - _Requirements: R11.4, R11.5_

- [ ] **6.7 Phase gate**
  - **Definition of done:** full CI green; README structure tree updated to the post-move
    layout; `tests/e2e/web` green — the proof the move was structural only.

---

## Phase 7 — Complexity

- [ ] **7.1 `main.py:_cmd_run` (259 lines, 71 branches, 16 params)**
  - Introduce a `RunOptions` dataclass built from the parsed namespace; extract the
    argument-resolution, backend-selection, and result-reporting blocks.
  - **Definition of done:** `_cmd_run` under 120 lines and 8 parameters; the run path is
    callable from a test without constructing a CLI invocation; CLI behaviour identical
    (every flag still works).
  - _Requirements: R12.3, R12.4, R12.5_

- [ ] **7.2 `mcp_server.py:build_ai_team_mcp_tools` (264 lines)**
  - Extract one builder per tool group.
  - **Definition of done:** under 120 lines; the MCP tool list is byte-identical before and
    after (assert it in a test).
  - _Requirements: R12.3, R12.5_

- [ ] **7.3 `evals/gate.py:evaluate_gate` (230 lines, 38 branches)**
  - Extract per-criterion evaluation; keep the decision table in one readable place.
  - **Definition of done:** under 120 lines; Tier A gate output identical on the committed
    corpus.
  - _Requirements: R12.3, R12.5_

- [ ] **7.4 Web router split**
  - Split `server.py` (1,791 LOC, 24 routes) into routers by resource plus an app factory;
    move module-level side effects into the factory.
  - **Definition of done:** every route path, method, response shape and status code
    unchanged; `tests/e2e/web` green; no new abstraction layer introduced.
  - _Requirements: R13.1, R13.2, R13.3, R13.4_

- [ ] **7.5 One cost resolver**
  - Consolidate `_resolve_token_estimate`'s three-source fallback into one resolver with a
    documented precedence order.
  - **Definition of done:** one function owns the number the dashboard shows; its
    precedence is stated in a docstring and covered by a test per source.
  - _Requirements: R13.5_

- [ ] **7.6 Phase gate**

---

## Phase 8 — Guards

Every task in this phase is subject to **R24**: offline, deterministic, order-independent, no
writes to tracked files, a recorded way to watch it fail, and a failure on an empty match set.
A guard that silently matches nothing is the default failure mode of repo-hygiene tests, and
it is worse than no guard because it reports success.

- [x] **8.1 Reachability guard**
  - `tests/unit/repo/test_reachability.py` with the commented `DORMANT_MODULES` allowlist
    naming each module's activation flag.
  - **Definition of done:** passes; adding an unreferenced module fails it with the
    three-option message from design §9.
  - _Requirements: R9.1, R9.2, R9.5_

- [x] **8.2 Reference guard**
  - `tests/unit/repo/test_references.py` implementing the `<workspace>/` convention;
    relative links and source paths only, no external HTTP.
  - **Definition of done:** passes; a deliberately broken link fails it with file and line.
  - _Requirements: R4.4, R9.3_

- [x] **8.3 README structure guard**
  - `tests/unit/repo/test_readme_structure.py`.
  - **Definition of done:** passes; adding a package without updating the README fails it.
  - _Requirements: R5.2, R9.4_

- [x] **8.4 Data-artifact guard**
  - `tests/unit/repo/test_data_artifacts.py`: fixture↔check mapping in both directions (94
    fixtures / 20 check ids / zero orphans today — keep it that way); baseline covers every
    registered check; no image outside the publication allowlist is unreferenced.
  - **Definition of done:** passes; adding a check without a fixture, or an image nothing
    references, fails it by name; the test raises rather than passes if the fixture glob or the
    check registry comes back empty (R24.4); the docstring records the one-line mutation that
    makes it fail.
  - _Requirements: R21.2, R21.4, R21.8_

- [x] **8.5 Complexity ratchets**
  - `tests/unit/repo/test_complexity.py` + `ratchets.toml` with dated comments in the style
    of the existing `fail_under` history block.
  - **Definition of done:** passes at the post-Phase-7 counts; a new 150-line function fails
    it; the AST walk raises if it visits zero files (R24.4); the docstring records the mutation
    that makes it fail.
  - _Requirements: R12.1, R12.2, R12.6, R20.3, R20.4_

- [x] **8.6 Wire the guards into CI and close out**
  - Add `tests/unit/repo` to the `lint` job; measure and record the total added CI time.
  - Run the full suite shuffled and confirm order-independence for every test this spec added
    (R24.1); confirm the `tests/conftest.py` hash guard still passes, i.e. no new test writes to
    a tracked golden/fixture/taxonomy file (R24.2).
  - Update `BASELINE.md` with the after-state; answer every open decision in `design.md`
    §12.
  - **Definition of done:** all guards green in CI; §12 has no unanswered row; the numbers
    in `requirements.md`'s introduction are either fixed or restated as history.
  - _Requirements: R9.6, R20.1, R20.2, R20.5_

---

## Phase 9 — Evidence (performance and envelope)

Numerically last, **high priority** — see Track A in the execution order above. This phase is
what turns two of the four claimed properties from adjectives into artifacts.

- [ ] **9.1 Publish one real benchmark**
  - **Spends money — human-triggered only, $25 cap, reuse the existing spend guard.**
  - Run the existing `tests/performance/` benchmarks (or a replacement) against a real backend
    on a recorded machine, and publish `docs/PERFORMANCE.md` with: hardware, model ids, date,
    sample size, wall-clock and cost per phase, tokens per run, and the harness overhead over a
    bare backend call.
  - State the regeneration command in the document (R21.7).
  - **Definition of done:** every number traces to a command in the document; nothing is from a
    mock run unless labelled in the same block; a reader can reproduce it.
  - _Requirements: R22.1, R22.2, R22.3_

- [x] **9.2 Document the operating envelope**
  - One section of `docs/PERFORMANCE.md` (or `docs/OPERATIONS.md`): single process; run registry
    in memory and lost on restart (`RunState.runs` — its docstring already admits this);
    concurrent-run ceiling and its source; per-run disk growth; spend ceiling; wall-clock kill.
  - For each limit, name what would lift it — persistent run store, queue, worker pool — and
    state explicitly that none is implemented, and why that is correct for a single-operator
    tool.
  - **Definition of done:** every limit has a number or a mechanism; no limit is described
    without its next step; the README's scalability language matches this section exactly.
  - _Requirements: R22.4, R22.5, R22.8_

- [x] **9.3 Retention policy**
  - Define and implement retention for `workspace/` and `output/` (437 run directories on the
    audit machine, unbounded), with a command that enforces it and a note in the envelope doc.
  - **Definition of done:** a documented command prunes runs older than the stated window;
    a unit test over a temporary tree asserts it removes what it should, keeps what it should,
    and is idempotent on a second run; the demo/quickstart path is unaffected.
  - _Requirements: R22.6_

- [x] **9.4 Resolve `tests/performance/`**
  - The eight benchmark tests either produce 9.1's artifact or are removed — publishing nothing
    is the same defect as a module nothing imports.
  - **Definition of done:** the directory is wired to the published benchmark, or gone, with the
    reason in the commit message.
  - _Requirements: R22.7_

- [x] **9.5 Phase gate**
  - **Definition of done:** full CI green; a reader can answer "how fast, how much, and what
    breaks first?" from one document.

---

## Minimum defensible slice

If the whole plan is too long: **Track A** — Phases 1, 2, 3, 4, 5, 9, 8. Roughly a week, no
architectural change, and it fixes everything a reviewer would find in their first thirty
minutes while turning "performant and scalable" from adjectives into a document.

Track B (Phases 6 and 7) is a second week of the two largest diffs in the repository for
changes a reviewer will not notice. Schedule it for the maintainer's benefit, not the
portfolio's.

If even that is too long: **task 2.1 and Phase 4.** A harness status table that is true,
and an API that cannot be driven by anyone on the network. Those two are the difference
between a very good field-study repository and one that also demonstrates production
judgement.
