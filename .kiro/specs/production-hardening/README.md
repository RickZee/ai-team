# Spec: `production-hardening`

Kiro-style three-document spec closing the gap between what this repository **claims** and
what it **wires** — so the codebase reads the way a reviewer expects a production-grade
enterprise system to read. Read in order:

1. **[`requirements.md`](./requirements.md)** — 24 requirements with EARS acceptance
   criteria, constraints, non-goals, and a file-level traceability table.
2. **[`design.md`](./design.md)** — the wire-or-delete decision table, machine-checkable
   status definitions, the package contract, the documentation model, security design,
   container fixes, the enforcement suite, migration risk, and eight open decisions.
3. **[`tasks.md`](./tasks.md)** — 10 phases, 62 tasks, each with a definition of done and
   requirement traceability.

Companion to [`../ui-refinement/`](../ui-refinement/) (frontend design system and
accessibility). Builds on, and does not restate, [`../eval-harness/`](../eval-harness/)
and [`../harness-alignment/`](../harness-alignment/).

## The one-line version

The engineering here is strong — a real failure taxonomy bound to deterministic checks, a
$0 replay gate, subprocess isolation, spend guards, adversarial tests, an honest threat
model, 1,456 tests, and a journal that records corrections. What has drifted is the wiring
*behind the claims*: ~800 LOC that nothing imports, 808 LOC of tests that never run, a
type gate that opts out of half the code, a control plane with no control, and a container
that does not contain the app it advertises.

## What the audit found

| | Evidence |
| --- | --- |
| **Unreachable code** | `harness/lessons_loop.py` (161), `session_loop.py` (315), `verifiers.py` (25), `qa_verdicts.py` (75), `evals/ladder_report.py` (228) — imported by **nothing but their own tests**, while `HARNESS.md` marks Feedback *closed-loop* and Verification *enforced* citing two of them |
| **Tests that never run** | `testpaths = ["tests"]`, so `evals/backends/test_*_eval.py` + `evals/test_backend_comparison.py` — **808 LOC** — are never collected (and are `ignore_errors` under mypy) |
| **Frontend gates idle** | CI runs `npm ci && npm run build` — never `npm test` or `npm run lint`, so **110 test cases and ESLint never execute in CI** |
| **Type gate opt-out** | `ignore_errors = true` covers two of three backends, `agents.*`, `crews.*`, `flows.main_flow`, `tools.test_tools`, `tools.smoke_tools`, `evals.run_evals`, and more — roughly half the Python |
| **Misleading layout** | `agents/` + `crews/` + `tasks/` + `flows/` = **6,772 LOC** at top level, reachable only through `crewai_backend/backend.py`; the README's structure tree omits those four **and** `harness/`, `models/`, `reports/`, `utils/` |
| **Control plane** | `server.py` (1,791 LOC, 24 routes): **no authentication on any route**, `--host` defaults to `0.0.0.0`. Those routes start paid runs, resume HITL, delete workspaces, and stream workspace files |
| **Path containment** | Artifact reads validate strings *before* the join but never assert containment after `resolve()` — a symlink written by an agent escapes the workspace |
| **Container** | Titled "FastAPI + React" with **no Node stage** (serves no UI); `build-essential` in the runtime stage; `.dockerignore` misses `node_modules` so `COPY src ./src` ships ~230 MB; healthcheck probes `/api/backends`; compose builds against Ollama + NVIDIA GPU with a context that cannot see `pyproject.toml` |
| **Complexity** | 63 functions > 80 lines, 8 > 150, 17 with > 8 params. Worst: `main.py:_cmd_run` — 259 lines, 71 branches, **16 parameters** |
| **Performance & scale** | Two of the four properties the repo claims have **no evidence and no stated limits**: eight benchmark tests publish nothing, the only perf doc is being deleted as meaningless, and run state lives in a process-local dict wiped on restart |
| **Repo surface** | All 27 GitHub Action `uses:` lines pin mutable tags (`@v4`), not SHAs; no PR/issue template, no `CODEOWNERS`, no `CHANGELOG`, `version` still `0.1.0` |
| **Data artifacts** | The accepted Tier A baseline (`evals/baselines/tier_a.json`) is a month stale, pinned to a pre-harness-alignment sha, covers **13 of 20 registered checks** and marks every one `fail` with `suite_pass_pow_k: 0.0` — with no sentence explaining why. **25 of 38 tracked images (~7 MB)** are referenced by nothing. `evals/golden/.validation_log.jsonl` is a tracked, hidden, zero-length append log |
| **Doc rot** | 42 markdown files; ~70 dead relative links (≈65 in `PROMPT_TRACKING.md`); a 68 KB self-declared "aspirational" roadmap; a 22-line performance report whose content explains that it isn't real; `pyproject.toml` author reads `"Your Name <your.email@example.com>"` |

**Clean, and worth protecting:** the eval fixture corpus — 94 traces, 20 check ids, **zero orphan fixtures and zero checks without one** — is the best-maintained data in the repository. R21.8 adds a guard to keep it that way.

## The principle

> **Nothing ships that is not reachable, and nothing is claimed that is not checked.**

Every requirement makes a claim true, makes a gate real, or deletes something that is
neither.

## What is explicitly *not* wrong

The harness architecture, the Trace boundary, the check registry, the taxonomy, the tier
model, subprocess isolation, the spend guard, and the guardrail layering are sound and are
not touched. `SECURITY.md`, the "Honest gaps" paragraph in `HARNESS.md`, and the dated
`fail_under` history comment in `pyproject.toml` are the most senior-looking artifacts in
the repository — this spec extends that voice rather than trimming it.

## Two tracks

Phase numbers are a dependency order, **not a priority order**. Payoff per hour differs by an
order of magnitude:

| Track | Phases | Effort | Payoff |
| --- | --- | --- | --- |
| **A — what a reviewer sees** | 1 delete · 2 truth · 3 gates · 4 security · 5 container · 9 evidence · 8 guards | ~1 week | Everything findable in a 30-minute read, plus real numbers for "performant / scalable" |
| **B — what the maintainer feels** | 6 boundaries · 7 complexity | ~1 week | The two largest diffs in the repo (6,772 LOC moved, 24 routes re-homed) for changes near-invisible to a reader |

Recommended order: **1 → 2 → 3 → 4 → 5 → 9 → 8**, then Track B only if the repository keeps
being developed.

Deletion first, so nothing later is spent on code that leaves. Truth second — nearly free, and
it is what a reviewer reads first. Gates third, so every later phase is protected. Security
before the big moves: highest consequence, smallest diff.

**Sequencing with [`ui-refinement`](../ui-refinement/):** task 3.1 turns on `npm test` in CI,
and that spec's drift test is red until its Phases 1–6 land. Land 3.1 first *or* finish
`ui-refinement` first — not both at once, or `main` stays broken for days.

**The highest-value hour is task 2.1** — making the harness status table true. It is the
table a reviewer reads to decide whether the project is serious, and it currently contains
two claims the code does not support.

## Tests this spec adds

Twelve new test modules. Eight are repository invariants that make the spec self-enforcing;
four cover behaviour it changes.

| Test | Locks | Requirement |
| --- | --- | --- |
| `tests/unit/ui/test_auth.py` | 401 without a token, 200 with it; **route-coverage**: every route is authed or explicitly public; bind-default rules | R15 |
| `tests/unit/ui/test_artifacts_adversarial.py` | Symlink to `/etc/passwd`, symlink to a sibling run, nested symlink dir, absolute `project_id`, sensitive-name bypass | R16 |
| `tests/unit/repo/test_reachability.py` | No orphan modules; the dormant allowlist names each module's activation flag | R1, R9 |
| `tests/unit/repo/test_references.py` | Relative links and source paths resolve (`<workspace>/` convention excepted) | R4 |
| `tests/unit/repo/test_readme_structure.py` | README's structure tree ≡ real packages | R5 |
| `tests/unit/repo/test_collection.py` | No `test_*.py` outside `testpaths` | R6 |
| `tests/unit/repo/test_type_budget.py` | `ignore_errors` **LOC** budget, ratcheting down only | R8 |
| `tests/unit/repo/test_complexity.py` | Branch/length/param ratchets | R12 |
| `tests/unit/repo/test_import_direction.py` | `core`/`harness`/`evals` never import a backend | R10, R11 |
| `tests/unit/repo/test_data_artifacts.py` | Fixture↔check mapping both ways; baseline covers every check; no unreferenced image | R21 |
| Frontend vitest case | Token header attached when configured, absent when not | R15.6 |
| Retention unit test | Prune command removes/keeps correctly and is idempotent | R22.6 |

Plus a CI image job (non-root, no `gcc`, size ratchet, `/api/health` → 200) and a compose
build check, and **R24**, which sets the bar for all of them: offline, deterministic,
order-independent, no writes to tracked files, a recorded way to watch each guard fail, and a
guard that raises rather than passes when its match set is empty.

The 808 LOC of currently-uncollected eval tests are either moved under `tests/` and made to
pass, or deleted (task 1.2) — not left where pytest cannot see them.

## Constraints baked in

| | |
| --- | --- |
| Behaviour | No change to run semantics, the taxonomy, check IDs, or the trace schema |
| Compatibility | CLI flags, console scripts, REST/WS paths and `data-testid` values stay stable; Python import paths change only behind one-release shims |
| Spend | **Every task runs offline.** No task may add a live model call |
| Deletion bias | Unreachable code is deleted, not archived — git history is the archive |
| Wiring bias | Deliberately dormant code must be activatable in one documented step, with a test for both paths |
| Enforcement | Eleven guards in `tests/unit/repo/`, running in the existing `lint` job, adding < 30 s |
| Scale | R22 requires **measuring and stating** the envelope — implementing a persistent run store, queue, or worker pool is explicitly out of scope |
| Out of scope | Multi-tenancy, RBAC/SSO, Kubernetes, coverage-floor raises, rewriting the journal |

## Executing this with Cursor

```
Read .kiro/specs/production-hardening/requirements.md and design.md for context.
Implement task 1.3 from .kiro/specs/production-hardening/tasks.md.
Do not start any other task. Do not change run semantics, check IDs, route paths,
or data-testid values. Stop when its Definition of done is satisfied and
`uv run ruff check . && uv run mypy src/ evals/ && uv run pytest tests/unit` passes.
```

Two tasks need a **human decision before an agent starts**: task 0.2 (wire / dormant /
delete for the five orphan modules) and the eight open decisions in `design.md` §12.

## Minimum defensible slice

**Track A** (Phases 1, 2, 3, 4, 5, 9, 8). Delete what is unreachable, make the documents true,
make the gates real, put a control on the control plane, ship a container that contains the
app, and publish one honest benchmark with a stated envelope. Roughly a week, no architectural
change, and it fixes everything a reviewer finds in their first thirty minutes.

If even that is too long: **task 2.1 and Phase 4** — a status table that is true and an API
that cannot be driven by anyone on the network.
