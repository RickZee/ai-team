# Requirements: AWS-native Backend (Strands Agents on Amazon Bedrock AgentCore)

**Spec ID:** `aws-strands-agentcore`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Created:** 2026-09-28
**Budget:** Phases 0–1 **$0.00** (local). Phase 2 **≤ $5** (Bedrock models from the
laptop). Phases 3–5 **≤ $15** including hosting, tracing and teardown. Every spending
task is human-triggered.
**Depends on:** [`../cloud-backend-foundation/`](../cloud-backend-foundation/), Phases 0–3.
**Executed by:** Cursor, one task per session. `terraform apply/destroy` only with Rick's go-ahead.

---

## Introduction

This spec adds `strands`, a fourth orchestration backend built on AWS's own agent stack:

| Layer | AWS-native mechanism | What it replaces or complements in ai-team |
| --- | --- | --- |
| Orchestration | **Strands Agents SDK**: agents, agents-as-tools, multi-agent patterns | A peer of LangGraph, CrewAI and the Claude SDK |
| Models | **Amazon Bedrock**: Claude plus one cheaper model | OpenRouter |
| Hosting | **AgentCore Runtime**: containerized, session-isolated agent runtime | Local subprocess |
| Memory | **AgentCore Memory** (Phase 5) | Complements ai-team's long-term lessons store |
| Guardrails | **Bedrock Guardrails**: content and PII filters | Complements ai-team's security guardrails |
| Observability | **AgentCore Observability**: OpenTelemetry into CloudWatch | A second reader for ai-team traces |
| Identity | **IAM execution role** with least privilege | API keys |
| Infrastructure | **Terraform** (`hashicorp/aws` AgentCore, Bedrock, ECR, IAM, CloudWatch and Budgets resources) | None today |

**Principle:** local first. Every phase must pass the same thin-slice smoke test before
the next phase adds a cloud dependency:

```
Phase 1  in-process + Ollama         ($0)   ──►  Phase 1b  container + Ollama     ($0)
Phase 2  in-process + Bedrock models (≤$5)  ──►  Phase 3   Terraform + AgentCore  (≤$15)
Phase 4  cloud run end to end, traces back into ai-team evals
Phase 5  native mechanisms compared: Memory, Guardrails
```

---

## R1: Strands backend, in-process

1. THE SYSTEM SHALL provide `src/ai_team/backends/strands_backend/`, implementing `Backend`
   with `name = "strands"`.
2. The thin slice (manager → architect → developer → QA) SHALL be built from Strands
   agents. The manager orchestrates the others as agents-as-tools, and each specialist
   gets its role-scoped tools from the foundation's tool bridge.
3. Every tool call SHALL go through `ToolBus.invoke`, and all writes SHALL be drafts
   committed by the harness after the phase's guardrails pass.
4. Token usage reported by Strands SHALL be priced and recorded through the spend guard.
   Missing usage is recorded as `observed_usd: null` with a warning, never as $0.
5. The backend SHALL pass the foundation conformance suite with a fake Strands model.

## R2: Local model and container

1. The backend SHALL run against **Ollama** through Strands' Ollama model provider, with the
   model id pinned in config.
2. THE SYSTEM SHALL provide `docker/strands.Dockerfile` that builds a **linux/arm64** image
   implementing the **AgentCore Runtime service contract**: an HTTP server on port 8080
   with the invocation and health endpoints the Runtime expects. The exact contract is
   pinned in the spike task.
3. The same image SHALL run under Docker Compose (`--profile strands`) and pass the thin
   slice against host Ollama, exporting OTel spans to the local collector.

## R3: Bedrock models

1. The backend SHALL switch to **Bedrock models** by configuration only: provider, region,
   model or inference-profile ids, and an AWS profile name. No code changes.
2. Credentials SHALL come from the standard AWS credential chain (named profile or SSO).
   No access keys in `.env`.
3. Pricing for the chosen Bedrock models SHALL be added to the model price table, and a
   live smoke run SHALL record a cost that roughly matches the Bedrock console
   (within ±20%, to allow for rounding).

## R4: Infrastructure as code (Terraform)

1. `infra/terraform/aws/` SHALL create, in `envs/dev`:
   - an **ECR repository** with scan-on-push and a lifecycle policy that keeps 5 images;
   - an **IAM execution role** for the Runtime, allowing only: invoking the specific Bedrock
     model ARNs used, pulling from that ECR repo, writing its log group and traces, and
     read/write on the artifacts bucket prefix;
   - an **AgentCore agent runtime** (`aws_bedrockagentcore_agent_runtime`) pointing at the
     image digest, not a mutable tag;
   - a **Bedrock guardrail** (`aws_bedrock_guardrail`) with PII and prompt-attack filters,
     applied to model calls from the runtime;
   - an **S3 artifacts bucket**: encrypted, public access blocked, lifecycle-expired after
     14 days;
   - **CloudWatch**: a log group with 14-day retention, a dashboard (runs, errors, latency,
     tokens), and an alarm on runtime errors;
   - a **budget** through the foundation's budget module, $25 per month by default.
2. `plan` SHALL show no wildcard `Resource: "*"` in IAM policies except where an AWS
   service requires it, and each such exception SHALL be commented.
3. The image SHALL be built and pushed by `infra/scripts/push_image_aws.sh`
   (`docker buildx --platform linux/arm64`), which outputs the digest that Terraform consumes.
4. `terraform destroy` followed by `teardown_check.sh` SHALL report 0 billable resources.

## R5: Cloud execution target

1. `--backend strands --target cloud` SHALL:
   1. start a run on the AgentCore Runtime;
   2. survive runs longer than a single request, using the Runtime's supported mechanism
      for long-running work (pinned in the spike);
   3. have the container write the workspace and results bundle to the artifacts bucket;
   4. download both into `output/runs/<id>/` locally, in the same layout as a local run.
2. AgentCore Observability traces SHALL be viewable in CloudWatch, and the same spans
   SHALL be imported into ai-team with `evals trace import-otel`, via an export step or the
   container's dual OTLP export.
3. A cloud smoke run SHALL pass the thin slice, with its cost recorded, before the full
   nine-role pipeline is attempted.

## R6: Native mechanisms, compared honestly

1. **AgentCore Memory** (Terraform `aws_bedrockagentcore_memory`) SHALL be tried as the
   store for ai-team's role-scoped lessons, behind the existing lessons interface.
2. `docs/CLOUD_NATIVE.md` SHALL record, for Memory, Guardrails and Observability, whether
   the native mechanism replaced, complemented or could not replace the ai-team harness
   piece, with one reason each.

## R7: The full team (stretch, after R1–R6)

1. All nine roles SHALL run on Strands, using the same phase plan as the LangGraph backend.
2. The backend SHALL join the 30-run batch, so finish rate can be compared across backends
   with intervals.

## Non-goals

- AgentCore Gateway and Identity for third-party tools. The ai-team tools are in-process
  and stay behind ToolBus.
- A web front door for the cloud runtime.
- Production multi-account setup. This is one dev account with budgets and teardown.
