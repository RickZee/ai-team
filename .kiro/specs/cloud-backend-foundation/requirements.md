# Requirements: Cloud Backend Foundation

**Spec ID:** `cloud-backend-foundation`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Created:** 2026-09-28
**Budget:** **$0.00.** Every task runs offline with fake models or a local Ollama model.
**Executed by:** Cursor, one task per session (see [`tasks.md`](./tasks.md)).
**Consumed by:** [`../aws-strands-agentcore/`](../aws-strands-agentcore/) and
[`../azure-agent-framework/`](../azure-agent-framework/). Both are blocked on Phases 0–3 here.

---

## Introduction

ai-team runs one nine-agent team on three frameworks (LangGraph, CrewAI, Claude Agent SDK)
behind one `Backend` protocol (`src/ai_team/core/backend.py`). The next step is two
**cloud-native** backends: **Strands Agents on Amazon Bedrock AgentCore** and
**Microsoft Agent Framework on Azure AI Foundry**. They use each cloud's own orchestration,
hosting, identity, guardrail and observability services, not just its hosted models.

Adding backends four and five exposes a problem the first three hid. What a backend must
do to count as "an ai-team backend" is not written down or tested anywhere. Each existing
backend reached the harness (ToolBus, draft-then-commit, spend guard, results bundle,
traces) by its own route, and September's audit found backends that silently missed parts
of it. One example: QA could only record an acceptance on the Claude SDK path, which
produced 135 rejects and 0 accepts on the other two.

This spec builds the shared foundation once, so both cloud backends plug into it and are
held to the same bar:

1. A **backend conformance suite**: an executable definition of an ai-team backend.
2. A **tool bridge** that exposes the ToolBus to any framework's tool API.
3. **Harness-owned acceptance**, so acceptance never depends on a framework exposing one tool.
4. A **local-first runtime**: Docker Compose with a local model and a local
   OpenTelemetry stack, so a clone runs both new backends at $0 with no cloud account.
5. **OpenTelemetry ingest**, so traces emitted natively by Strands or Agent Framework land
   in the ai-team eval pipeline.
6. **Terraform conventions and CI checks** shared by the AWS and Azure stacks.

## Glossary

| Term | Meaning |
| --- | --- |
| **Backend** | An implementation of `ai_team.core.backend.Backend` |
| **Execution target** | Where a backend's agents run: `local` (in-process), `container` (local Docker), `cloud` (AgentCore Runtime / Azure) |
| **Conformance suite** | `tests/conformance/`, parametrized over every registered backend |
| **Thin slice** | The four-role pipeline a new backend must run first: manager → architect → developer → QA |
| **Harness evidence** | Results the harness collects itself: pytest, ruff, the runtime smoke gate |

---

## R1: Backend conformance suite

**User story:** As the maintainer, I want one executable definition of an ai-team backend,
so a new backend is done when it passes, not when it looks done.

1. THE SYSTEM SHALL provide `tests/conformance/`, parametrized over every backend returned
   by the registry, runnable offline with a deterministic fake model.
2. FOR each backend, the suite SHALL assert that on the thin-slice smoke task:
   1. every tool call went through `ToolBus.invoke` (one `logs/audit.jsonl` row per call);
   2. every write was staged as a draft and committed only by `commit_pending_drafts`;
   3. spend was recorded through `spend_guard.record_usage` or `reconcile_spend`, and
      `current_spend()` reports a non-null `source`;
   4. a results bundle was written with the backend's own name, `started_at` and `completed_at`;
   5. `TraceBuilder` builds a trace with at least one `llm`, one `tool_use` and one
      `tool_result` span;
   6. a run exceeding its budget ends as `budget_exceeded`, and a run exceeding its
      wall-clock limit ends as `timeout`, both with a closed run record.
3. THE existing three backends SHALL pass the suite before either cloud backend starts.
   Failures found here are fixed in this spec, not waived.
4. THE suite SHALL run in CI on every PR at $0.

## R2: Tool bridge

**User story:** As a backend author, I want ToolBus tools exposed in my framework's native
tool format, so I never re-implement a tool or bypass the harness.

1. THE SYSTEM SHALL provide `ai_team.backends.common.tool_bridge` that turns each
   registered `ToolSpec` into a framework-neutral descriptor: name, description, JSON
   Schema derived from the pydantic args model, and a callable that invokes `ToolBus.invoke`.
2. Adapters SHALL exist for Strands (`@tool` / tool spec) and Microsoft Agent Framework
   (function tools). Each adapter is under 150 lines and has unit tests.
3. Tool observations SHALL be rendered to the model with `observation_to_agent_text`,
   so every backend shows models the same text.
4. Role-scoped tool sets SHALL come from the existing role → tools mapping, never from a
   per-backend list.

## R3: Harness-owned acceptance

**User story:** As someone reading a run, I want "accepted" to mean the same thing on every
backend.

1. AFTER the quality gate runs, THE HARNESS SHALL mark each acceptance criterion as
   `passing`, `failing` or `unverified` from harness evidence: tests, lint, and smoke probes.
2. THE QA agent's own verdicts SHALL be kept as a second signal. Every disagreement between
   the QA verdict and harness evidence SHALL be logged as a `qa_disagreement` span.
3. `acceptance_mark_passing` SHALL stay available where a framework exposes it, but a run's
   acceptance result SHALL NOT depend on it.
4. A regression test SHALL show that LangGraph and CrewAI runs with passing tests now
   record accepts (they recorded 0 in the September corpus).

## R4: Local-first runtime

**User story:** As a stranger who cloned the repo, I want to run the cloud-native backends
without an AWS or Azure account.

1. `docker/docker-compose.yml` SHALL gain profiles:
   - `observability`: OpenTelemetry Collector plus the Aspire dashboard, with the Collector
     also writing OTLP JSON to `output/otel/`;
   - `strands` and `agent-framework`: each backend as a container, wired to the collector.
2. The local model SHALL be **Ollama on the host** (reached via `host.docker.internal`),
   because Docker on macOS has no GPU access. The model id SHALL be pinned in config and
   chosen for tool-calling support.
3. `make local-smoke BACKEND=<name>` (or the equivalent script) SHALL run the thin-slice
   smoke task against the local model, in-process and in the container, and print one
   pass/fail line per step.
4. Local runs SHALL cost $0 and SHALL be labelled `model_tier: local` in the results bundle,
   so no local run is ever read as a quality result.

## R5: OpenTelemetry ingest

**User story:** As the eval maintainer, I want traces that Strands and Agent Framework emit
natively to be scored by the same checks as every other backend.

1. THE SYSTEM SHALL provide `evals trace import-otel <path>`, which maps OTLP JSON spans
   following the OpenTelemetry GenAI semantic conventions to ai-team span kinds (`llm`,
   `tool_use`, `tool_result`, `agent`).
2. The mapping SHALL be a single table in code, with a fixture per framework and a test
   asserting span counts on each fixture.
3. Where a backend also writes ai-team's own telemetry, THE builder SHALL prefer
   harness-written spans and record the OTel import as a second reader (the
   two-readers rule from the course, week 3).

## R6: Registry, CLI and batch support

1. `BackendName` (`evals/trace/models.py`) SHALL gain `strands` and `agent-framework`.
2. `backends/registry.py`, the CLI `--backend` flag, `scripts/run_smoke_batch.py` and the
   web catalog SHALL accept both names, plus `--target local|container|cloud`.
3. An unknown target, or a target the backend doesn't support, SHALL fail before any spend
   with a message naming the supported targets.

## R7: Terraform conventions

**User story:** As a reviewer of this repo, I want the infrastructure to read like it was
written by someone who runs production cloud.

1. Layout: `infra/terraform/{aws,azure}/` with `modules/` and `envs/dev/`. Every module
   has `variables.tf`, `outputs.tf`, `versions.tf` (pinned providers) and a `README.md`
   generated by `terraform-docs`.
2. Every resource SHALL carry `project = "ai-team"`, `env`, `owner` and `cost_center` tags,
   set once through provider default tags (AWS) or a shared `locals` map (Azure).
3. **Budgets are code:** each stack SHALL create a monthly budget with an alert at 50% and
   100% of a variable defaulting to $25.
4. **No long-lived secrets:** workload identity and managed identity (IAM roles, Azure
   managed identity) are used wherever the service supports it. Where a key is unavoidable,
   it lives in Secrets Manager or Key Vault, never in state outputs or `.tfvars` in git.
5. State SHALL default to local and be configurable to S3 with DynamoDB locking, or to an
   Azure Storage backend, via a `backend.hcl` that is not committed.
6. CI SHALL run, with no cloud credentials: `terraform fmt -check`, `terraform validate`,
   `tflint`, and `checkov`. Any checkov finding that is accepted gets an inline skip with a
   reason.
7. Every stack SHALL document a one-command teardown, and a teardown check SHALL confirm
   no billable resources remain.

## R8: Honesty on surfaces

1. `docs/CLOUD_NATIVE.md` SHALL hold one status table: backend × target (`local`,
   `container`, `cloud`), each cell marked `green`, `red`, `not yet` or `not available`,
   with date, run id, model and cost. No cell is ever left blank.
2. The README SHALL link that table and SHALL NOT claim a cloud cell that isn't `green`.
