# Glossary

The words this repo uses, in plain language, each with the file where it lives. Read it top to
bottom for a tour of the system, or search for the word you just met.

- [The system](#the-system)
- [Tools and safety](#tools-and-safety)
- [Runs and records](#runs-and-records)
- [Evaluation](#evaluation)
- [Measurement](#measurement)
- [Working on the repo](#working-on-the-repo)

## The system

| Term | What it means | Where it lives |
| --- | --- | --- |
| **Harness** | Everything around the model that runs the same on every framework: tools, guardrails, routing, the spend guard, logs and gates. The repo's position: the product is the harness; the frameworks are engines. | [HARNESS.md](HARNESS.md) |
| **Seven harness layers** | Tools, verification, context, guardrails, observability, routing, feedback. Each lists the module that owns it, the failure modes it covers and the checks that watch it. | [HARNESS.md](HARNESS.md) |
| **Instrumented / enforced / closed-loop** | How far a layer has got. *Instrumented*: its module is on the default run path. *Enforced*: bypassing it makes the default path fail, and a named test shows it. *Closed-loop*: the output of run *n* changes the input of run *n+1*. | [HARNESS.md](HARNESS.md#status-table-r193) |
| **Backend** | The orchestration engine a run uses: LangGraph, CrewAI or the Claude Agent SDK. Strands and Microsoft Agent Framework are stubs. | [`src/ai_team/backends/`](../src/ai_team/backends/), [FRAMEWORKS.md](FRAMEWORKS.md) |
| **Backend protocol** | The one interface every backend implements: `run()` and `stream()`, both returning a `ProjectResult`. | [`core/backend.py`](../src/ai_team/core/backend.py), [`core/result.py`](../src/ai_team/core/result.py) |
| **Conformance suite** | Offline tests every backend must pass. It is the executable definition of a backend. | [`tests/conformance/`](../tests/conformance/) |
| **Roles** | The nine agents: manager, product owner, architect, cloud engineer, DevOps engineer, backend developer, frontend developer, full-stack developer and QA engineer. | [`config/agents.yaml`](../src/ai_team/config/agents.yaml), [AGENTS.md](AGENTS.md) |
| **Team profile** | A named roster of agents and phases (`full`, `prototype`, `smoke`, `backend-api`, …), chosen with `--team`. | [`config/team_profiles.yaml`](../src/ai_team/config/team_profiles.yaml), [TEAM_PROFILES.md](TEAM_PROFILES.md) |
| **Smoke profile** | Architect, backend developer and QA engineer through planning, development and testing. The small team used for batches. | [`config/team_profiles.yaml`](../src/ai_team/config/team_profiles.yaml) |

## Tools and safety

| Term | What it means | Where it lives |
| --- | --- | --- |
| **ToolBus** | The one path every tool call takes: look up the tool, validate its arguments, check permission, branch on the tool's kind, write an audit row. A schema or permission failure never runs the tool. | [`tools/bus.py`](../src/ai_team/tools/bus.py) |
| **Tool kinds** | `read` runs now. `write` lands as a draft. `irreversible` is gated. | [`tools/kinds.py`](../src/ai_team/tools/kinds.py), [`tools/catalog.py`](../src/ai_team/tools/catalog.py) |
| **Draft-then-commit** | Agent writes are staged under `workspace/.harness/drafts/` and reach the real workspace only when the harness commits them: a pull request for side effects. On by default (`AI_TEAM_DRAFT_WRITES`). | [`tools/draft.py`](../src/ai_team/tools/draft.py) |
| **Irreversible tools** | `delete_file`, `execute_shell`, and overwriting a lockfile or `.env`. Blocked unless the operator allows them (`AI_TEAM_ALLOW_IRREVERSIBLE`); a model passing `confirm=true` is not enough. | [`tools/catalog.py`](../src/ai_team/tools/catalog.py), [`tools/kinds.py`](../src/ai_team/tools/kinds.py) |
| **Spend guard** | A per-run cost ceiling, $5 by default (`AI_TEAM_RUN_BUDGET_USD`). Its `BudgetExceededError` subclasses `BaseException`, so a catch-all retry handler can't swallow it. | [`core/spend_guard.py`](../src/ai_team/core/spend_guard.py) |
| **Guardrails** | Checks on agent output. *Behavioral*: did the agent stay in its role and scope. *Security*: unsafe execution, PII and secrets, prompt injection, path traversal. *Quality*: syntax, size, complexity, docstrings. | [GUARDRAILS.md](GUARDRAILS.md), [`guardrails/`](../src/ai_team/guardrails/) |
| **Relevance floor** | The scope check's lexical threshold, 0.15. It was 0.25 until correct QA output kept scoring below it. | [`guardrails/behavioral.py`](../src/ai_team/guardrails/behavioral.py) |
| **Router** (`route_after_testing`) | LangGraph's decision after testing: go on to the smoke test, retry development, or hand the run to a human. A guardrail failure in testing goes straight to a human. | [`langgraph_backend/graphs/routing.py`](../src/ai_team/backends/langgraph_backend/graphs/routing.py) |
| **Task routing** | A config table that maps a task type to a model: `classify` and `format` to a small model, `plan`, `judge` and `generate` to a stronger one, `mechanical_check` to no model at all. | [`config/task_routes.yaml`](../src/ai_team/config/task_routes.yaml), [`harness/router.py`](../src/ai_team/harness/router.py) |
| **Checkpointer** | LangGraph's saved state (SQLite by default, Postgres optional), so a run can pause and resume on the same thread. | [`langgraph_backend/checkpointer.py`](../src/ai_team/backends/langgraph_backend/checkpointer.py) |
| **Interrupt / HITL** | Human in the loop: a run stops and waits for a person. LangGraph uses `interrupt()`; the Claude Agent SDK uses `AskUserQuestion`. | [`langgraph_backend/graphs/main_graph.py`](../src/ai_team/backends/langgraph_backend/graphs/main_graph.py) |
| **`complete_approved`** | A run a human approved past a failing gate. It is reported as its own status, never as plain success. | [`ui/web/server.py`](../src/ai_team/ui/web/server.py) |
| **Watchdog** | The run's wall-clock limit. Stage one raises `DemoTimeoutError` so the run can unwind. If the run is still alive after a grace period, stage two closes the run record as `timeout` and exits with code 124. | [`scripts/run_demo.py`](../scripts/run_demo.py) |
| **Stopped run** | A run cut off by the watchdog or the spend guard. On LangGraph it keeps the checkpointer's last state and the node it stopped in (`stopped_in`), so the cause can be read. | [`harness/stopped_run.py`](../src/ai_team/harness/stopped_run.py) |
| **Runtime smoke gate** | Starts the generated app and makes real HTTP calls, because unit tests passing doesn't prove the app runs. | [`tools/smoke_tools.py`](../src/ai_team/tools/smoke_tools.py) |
| **Three-file contract** | `CONSTRAINTS.md` (pinned, never summarized), `STATE.md` (the last few phase facts) and `LESSONS.md` (generated from the lessons store). Owned by the harness, not the model. | [`harness/context.py`](../src/ai_team/harness/context.py) |
| **ACCEPTANCE.json** | The run's acceptance list. The harness is the only writer; an agent can only move an item from failing to passing, with evidence, through `mark_passing`. | [`harness/acceptance.py`](../src/ai_team/harness/acceptance.py) |
| **Harness-owned acceptance** | Whether a run is accepted comes from quality-gate evidence (tests, lint, smoke), not from a QA agent's opinion. A criterion with no evidence stays `unverified`. | [`backends/common/acceptance.py`](../src/ai_team/backends/common/acceptance.py) |

## Runs and records

| Term | What it means | Where it lives |
| --- | --- | --- |
| **Run record** | `output/runs/<id>/`: `run.json`, `state.json`, `events.jsonl`, artifacts, reports and logs. Generated code goes to `workspace/<id>/` instead. | [RUN_ARTIFACTS.md](RUN_ARTIFACTS.md) |
| **Phase, cost and audit logs** | `phases.jsonl` (phase start and end) and `costs.jsonl` (the run's spend) in the run's `logs/`; `audit.jsonl` (one row per tool call) in the workspace `logs/`. | [`harness/telemetry.py`](../src/ai_team/harness/telemetry.py), [`tools/bus.py`](../src/ai_team/tools/bus.py) |
| **`writer: harness`** | A stamp on every harness log row, added inside the writer rather than by the caller, so a call site can't forge where a row came from. | [`harness/telemetry.py`](../src/ai_team/harness/telemetry.py) |
| **Self-reported telemetry** | A signal the model was asked to write, instead of code writing it. It fails silently. Proposed as FM-018; not in the taxonomy yet. | [journal, 2026-09-13](journal/2026-09-13-eval-methodology-audit.md) |
| **Change receipt** | `receipt.json`, written when a run finalizes: the on-disk truth for its cost, files and smoke result. The dashboard reads it. | [`harness/receipt.py`](../src/ai_team/harness/receipt.py) |
| **Trace / span** | A trace is the immutable record of one run. A span is one typed step in it, with start and end times. | [`evals/trace/`](../evals/trace/) |
| **Trace boundary** | The line between running and scoring. Left of it, execution: billed and flaky. Right of it, scoring: free and deterministic. Checks only read traces. | [`evals/README.md`](../evals/README.md) |
| **OpenInference / OTel shape** | Trace telemetry targets OpenInference and OpenTelemetry conventions, so external viewers can read it. | [`evals/trace/otel_import.py`](../evals/trace/otel_import.py) |

## Evaluation

| Term | What it means | Where it lives |
| --- | --- | --- |
| **Failure mode (`FM-xxx`)** | A named, versioned way the system fails, with its layer, a definition and the checks that detect it. | [`evals/taxonomy/failure_modes.yaml`](../evals/taxonomy/failure_modes.yaml), [failure taxonomy write-up](posts/failure-taxonomy.md) |
| **Layer** | Whose failure it is: model, framework, harness or provider. Most failures in the taxonomy are harness failures. | [`evals/taxonomy/failure_modes.yaml`](../evals/taxonomy/failure_modes.yaml) |
| **Deterministic check (`CHK-…`)** | A code-only test over a trace. No LLM, no cost. | [`evals/checks/`](../evals/checks/) |
| **Check outcomes** | `pass`, `fail`, `not_applicable` and `error`. *Not applicable* is an abstain: nothing here to judge, so it stays out of the denominator. An error is never counted as a decision. | [`evals/checks/base.py`](../evals/checks/base.py) |
| **Fixture** | A hand-built trace that a check must pass, fail or abstain on (`CHK-…__pass.json`, `__fail.json`, `__na.json`). A specification, not an observation. | [`evals/fixtures/traces/`](../evals/fixtures/traces/) |
| **Baseline** | What the suite did last time. It answers "did this change?" | [`evals/baselines/`](../evals/baselines/) |
| **Fixture contract** | Three rules that need no baseline. Completeness: every check has all three fixtures. Expectation: each fixture gives the outcome its name declares. Uniqueness: no trace is loaded twice. | [`evals/fixture_contract.py`](../evals/fixture_contract.py) |
| **Eval gate** | Compares a suite run with the baseline and the fixture contract. Exit 0 pass, 1 regression, 2 harness error. Runs offline for $0; CI runs it warn-only for now. | [`evals/gate.py`](../evals/gate.py), [EVAL_GATE_STATUS.md](EVAL_GATE_STATUS.md) |
| **Tiers A / B / C** | A: offline replay of stored traces, $0. B and C: live runs with a budget, started by a person. | [`evals/README.md`](../evals/README.md), [EVAL_METHODOLOGY.md](EVAL_METHODOLOGY.md) |
| **Corpus kinds** | `FIXTURE-ONLY` (proves the checks behave), `CORPUS` (real runs, with n), `LIVE` (a run just executed). Every rate says which one it came from. | [`evals/coverage.py`](../evals/coverage.py) |
| **Liveness** | Per check: `live`; `thin` (under 10 decided, or over 90% abstain); `blind` (never decided anything); `unreachable` (its evidence has no producer). | [`evals/coverage.py`](../evals/coverage.py) |
| **EVIDENCE-STARVED / NON-REPRESENTATIVE** | Stamps on a report. Evidence-starved: more than half the outcomes are abstains. Non-representative: the corpus misses its diversity floors. | [`evals/coverage.py`](../evals/coverage.py), [EVAL_METHODOLOGY.md](EVAL_METHODOLOGY.md) |
| **Open coding** | Reading traces and naming the failures yourself, before any taxonomy or model suggests them. | [course, week 4](../course/week-4-read.md) |
| **Golden set** | Human-labeled examples. About 40% go to a test split, which a judge prompt is checked against once per version. | [EVAL_METHODOLOGY.md](EVAL_METHODOLOGY.md#golden-set-and-splits), [`evals/golden.py`](../evals/golden.py) |
| **LLM-as-judge** | A model giving a yes/no verdict. Advisory until TPR and TNR ≥ 0.90, κ ≥ 0.70 and n ≥ 100 on the test split. | [`evals/judges/`](../evals/judges/), [EVAL_METHODOLOGY.md](EVAL_METHODOLOGY.md) |
| **minieval** | A one-file, standard-library version of the eval kit, for *Evals Without the Jargon*. | [`docs/course/minieval.py`](course/minieval.py) |

## Measurement

| Term | What it means | Where it lives |
| --- | --- | --- |
| **n** | How many runs a rate comes from. Every published rate carries it. | [course, session 5](course/session-5-every-number-needs-n.md) |
| **Wilson interval** | The 95% range a pass rate could plausibly be in, given n. It stays inside 0–100% and behaves at 0/5 and 5/5. | [`scripts/batch_stats.py`](../scripts/batch_stats.py) |
| **Batch** | N identical runs through the same command, summarized with rates, intervals and medians. A verdict prints only when the intervals don't overlap. | [`scripts/run_smoke_batch.py`](../scripts/run_smoke_batch.py) |
| **Green run** | Tests ran, none failed, and the run wasn't stopped. | [`scripts/run_smoke_batch.py`](../scripts/run_smoke_batch.py), [course, session 1](course/session-1-what-green-means.md) |
| **Cost per role** | Each agent's share of a run's tokens, counted only when the run's messages cover at least 90% of the cost log. | [`scripts/role_cost.py`](../scripts/role_cost.py), [`harness/role_cost.py`](../src/ai_team/harness/role_cost.py) |
| **Arm / ladder** | An arm changes the harness while the framework and model stay fixed. The ladder runs arms in order: solo, harnessed solo, reference, ai-team with components ablated, full ai-team. | [`evals/arms/`](../evals/arms/) |
| **Harnessed solo** | The full harness driving one generalist agent (role decomposition switched off). It separates what the harness buys from what the nine roles buy. | [`evals/arms/ai_team.py`](../evals/arms/ai_team.py) |

## Working on the repo

| Term | What it means | Where it lives |
| --- | --- | --- |
| **Ratchet** | A repo number that may only improve: type-check exemptions, long functions, functions with many parameters, Docker image size. The test-coverage floor works the same way. | [`tests/unit/repo/ratchets.toml`](../tests/unit/repo/ratchets.toml), [`pyproject.toml`](../pyproject.toml) |
| **ADR** | Architecture Decision Record: one decision, its context and its consequences. | [`adr/`](adr/) |
| **Journal** | Dated entries: what broke, when, and the commit that fixed it, corrections included. | [`journal/`](journal/README.md) |
| **Spec** | Planned work, written as requirements, then design, then tasks. | [`.kiro/specs/`](../.kiro/specs/README.md) |

Missing a word? Add it here in the same pull request that introduces it.
