# ADR-001: Cloud-native backends

**Status:** Accepted
**Date:** 2026-09-28

## Context

ai-team already runs one nine-agent team on LangGraph, CrewAI, and the Claude
Agent SDK behind `ai_team.core.backend.Backend`. The next two backends are
**Strands Agents on Amazon Bedrock AgentCore** and **Microsoft Agent Framework
on Microsoft Foundry (formerly Azure AI Foundry)**.

Hosting only the model (Bedrock or Azure OpenAI behind the existing backends)
would not exercise the thing this repo is for: which failures belong to the
framework. AgentCore and Foundry each bring their own orchestration, identity,
guardrails, and traces. Using those services is the experiment. Pointing the
current backends at a cloud model would measure the model again.

## Decision

1. Add two backends, `strands` and `agent-framework`. They adapt to the existing
   harness (ToolBus, draft-then-commit, spend guard, results bundle, traces).
   The harness is not rewritten to suit them. `tests/conformance/` is the
   definition of "an ai-team backend."
2. Every backend declares an **execution target**:
   - `local` — in-process Python
   - `container` — the same image the cloud will run, on the operator's machine
   - `cloud` — AgentCore Runtime or an Azure Container Apps job
   For `container` and `cloud`, `run()` is a thin client. Inside the container
   the backend runs with `target=local`.
3. Infrastructure is **Terraform**, one tree per cloud under `infra/terraform/`.
   This supersedes the archived CDK plan for AgentCore. One tool across both
   clouds is what a multi-cloud platform team already runs, and the conventions
   (tags, budgets, identity, `fmt` / `validate` / `tflint` / `checkov` with no
   cloud credentials) are checkable in CI.
4. A clone can run both new backends at $0: Ollama on the host, and a local
   OpenTelemetry collector plus the Aspire dashboard. Those runs are labeled
   `model_tier: local` and are not quality results.

## What each cloud could replace, and what this project does

| Harness piece | AWS native | Azure native | Decision |
| --- | --- | --- | --- |
| Memory | AgentCore Memory | Foundry threads / Cosmos | Keep ai-team's file workspace and lessons store. Cloud memory is optional later, not a second source of truth. |
| Guardrails | Bedrock Guardrails | Foundry content filters | Keep ai-team guardrails on the tool path. Cloud guardrails may sit in front of the model; they do not replace the harness checks. |
| Tracing | CloudWatch / AgentCore traces | App Insights / Foundry traces | Ingest OTel into the existing trace builder. Harness spans win when both exist (two readers). |
| Identity | IAM roles | Managed identity | Workload identity only. No long-lived keys in git, state outputs, or `.tfvars`. |

## Consequences

- `BackendName`, the CLI, the smoke batch, and the web catalog learn the two
  names before the pipelines exist. Calling them fails with a pointer at the
  cloud spec, before any spend.
- AWS and Azure stay separate. There is no shared cloud abstraction.
- `terraform apply` and `terraform destroy` are not agent actions. `fmt`,
  `validate`, and `plan` are.
