# Requirements: AWS-native Backend (Strands Agents on Amazon Bedrock AgentCore)

**Spec ID:** `aws-strands-agentcore`
**Status:** Draft
**Owner:** Rick Zakharov
**Created:** 2026-09-28
**Budget:** Phases 0–1 **$0.00** (local). Step 0 baseline (task 2.0) and Phase 2 **≤ $5**
each (Bedrock models from the laptop). Phases 3–5 **≤ $15** including hosting, tracing and teardown. Every spending
task is human-triggered.
**Depends on:** [`../cloud-backend-foundation/`](../cloud-backend-foundation/), Phases 0–3.
As of 2026-10-18 foundation 0.5 (conformance in CI) is still open. Foundation 4.2 (compose
profiles) is needed before tasks 1.5–1.6, and 6.2–6.3 (budget modules, infra CI) before any
cloud spend.
**Revised:** 2026-10-18. Added the Step 0 Bedrock baseline (R0), lessons persistence in the
cloud (R5.4), inference-profile IAM and a same-day cost check (R3, R4), artifact sync after
every phase (R5.1), and an optional Code Interpreter test (R6.3).
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
Step 0   existing backends + Bedrock models (≤$5): only the model provider changes
Phase 1  in-process + Ollama         ($0)   ──►  Phase 1b  container + Ollama     ($0)
Phase 2  in-process + Bedrock models (≤$5)  ──►  Phase 3   Terraform + AgentCore  (≤$15)
Phase 4  cloud run end to end, traces back into ai-team evals
Phase 5  native mechanisms compared: Memory, Guardrails
```

**Second principle:** change one thing at a time. Step 0 changes only the model provider,
Phases 1–2 only the framework, Phases 3–4 only where the code runs. Each result is read
against the step before it. (The July comparisons ran LangGraph and CrewAI on DeepSeek and
the Claude SDK on Claude, so model and framework were already mixed together.)

---

## R0: Bedrock baseline for the existing backends (Step 0)

1. THE `claude-agent-sdk` backend SHALL run against Claude on Bedrock by configuration only
   (`CLAUDE_CODE_USE_BEDROCK=1` plus an AWS profile). The `ANTHROPIC_API_KEY` precondition
   SHALL be skipped in that mode.
2. THE `langgraph` backend SHALL reach the same Bedrock models through LiteLLM `bedrock/…`
   model ids, and model validation SHALL accept Bedrock ids as well as OpenRouter ids.
3. Both SHALL use the same model ids the `strands` backend uses (R3), so the only difference
   between a Step 0 run and a Strands run is the framework.
4. A thin-slice run on each SHALL be recorded in `docs/CLOUD_NATIVE.md` before any Strands
   result is compared with another backend.

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
   Prompt-cache read and write tokens SHALL be priced separately.
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
   live smoke run SHALL record a cost within ±20% of the CloudWatch `AWS/Bedrock`
   `InputTokenCount` / `OutputTokenCount` metrics for the run window, priced by the same
   table. The billing console lags about a day, so it is a next-day note, not the check.
4. Model ids SHALL be `us.` geographic inference profiles, so processing stays in US
   regions. `global.` profiles MAY be used in dev only and SHALL be labelled in the results
   bundle.

## R4: Infrastructure as code (Terraform)

1. `infra/terraform/aws/` SHALL create, in `envs/dev`:
   - an **ECR repository** with scan-on-push and a lifecycle policy that keeps 5 images;
   - an **IAM execution role** for the Runtime, allowing only: invoking the specific Bedrock
     inference-profile ARNs used **and** the foundation-model ARNs each profile routes to,
     pulling from that ECR repo, writing its log group and traces, and read/write on the
     artifacts bucket prefixes (`runs/` and `state/`);
   - an **AgentCore agent runtime** (`aws_bedrockagentcore_agent_runtime`) pointing at the
     image digest, not a mutable tag;
   - a **Bedrock guardrail** (`aws_bedrock_guardrail`) with PII and prompt-attack filters,
     applied to model calls from the runtime;
   - an **S3 artifacts bucket**: encrypted, public access blocked, `runs/` lifecycle-expired
     after 14 days, `state/` (the lessons store) versioned and kept;
   - **CloudWatch**: a log group with 14-day retention, a dashboard (runs, errors, latency,
     tokens), an alarm on runtime errors, an alarm on Bedrock token metrics as a real-time
     spend backstop, and Transaction Search enabled so AgentCore traces appear;
   - a **budget** through the foundation's budget module, $25 per month by default.
2. `plan` SHALL show no wildcard `Resource: "*"` in IAM policies except where an AWS
   service requires it, and each such exception SHALL be commented.
3. The image SHALL be built and pushed by `infra/scripts/push_image_aws.sh`
   (`docker buildx --platform linux/arm64`), which outputs the digest that Terraform consumes.
4. `terraform destroy` followed by `teardown_check.sh` SHALL report 0 billable resources.
5. All AWS modules SHALL pin the same `hashicorp/aws` 6.x release: the first that includes
   `aws_bedrockagentcore_agent_runtime`, `_memory` and `_code_interpreter` (pinned in task
   0.1). The current 5.100.0 pin predates them.

## R5: Cloud execution target

1. `--backend strands --target cloud` SHALL:
   1. start a run on the AgentCore Runtime;
   2. survive runs longer than a single request, using the Runtime's supported mechanism
      for long-running work (pinned in the spike);
   3. have the container write the workspace and results bundle to the artifacts bucket
      after every committed phase, and write `logs/` on every exit path, so a run that ends
      in `budget_exceeded`, `timeout` or a lost session still leaves something to grade;
   4. download both into `output/runs/<id>/` locally, in the same layout as a local run;
   5. end the Runtime session explicitly when the run finishes, rather than waiting out the
      15-minute idle timeout (memory is billed while a session sits idle).
2. AgentCore Observability traces SHALL be viewable in CloudWatch, and the same spans
   SHALL be imported into ai-team with `evals trace import-otel`, via an export step or the
   container's dual OTLP export.
3. A cloud smoke run SHALL pass the thin slice, with its cost recorded, before the full
   nine-role pipeline is attempted.
4. **Lessons SHALL persist across cloud runs.** The lessons store is a local SQLite file, and
   an AgentCore session's disk is discarded when the session ends. The container SHALL fetch
   the store from `state/` in the artifacts bucket at start and write it back at the end with
   a conditional write, so two runs cannot overwrite each other's lessons. Without this, the
   closed lessons loop (`docs/HARNESS.md`) is silently open on `target=cloud`.

## R6: Native mechanisms, compared honestly

1. **AgentCore Memory** (Terraform `aws_bedrockagentcore_memory`) SHALL be tried as the
   store for ai-team's role-scoped lessons, behind the existing lessons interface.
   ai-team's lessons store stays the source of truth (ADR-001): the test writes the same
   structured lessons to both and compares what each returns.
2. `docs/CLOUD_NATIVE.md` SHALL record, for Memory, Guardrails and Observability, whether
   the native mechanism replaced, complemented or could not replace the ai-team harness
   piece, with one reason each.
3. *(Optional)* **AgentCore Code Interpreter** MAY be tried as a separate sandbox for
   agent-written code (pytest, ruff) under its own identity, so generated code can no longer
   reach the execution role's credentials.

## R7: The full team (stretch, after R1–R6)

1. All nine roles SHALL run on Strands, using the same phase plan as the LangGraph backend.
2. The backend SHALL join the 30-run batch, so finish rate can be compared across backends
   with intervals.

## Non-goals

- AgentCore Gateway and Identity for third-party tools. The ai-team tools are in-process
  and stay behind ToolBus.
- A web front door for the cloud runtime.
- Production multi-account setup. This is one dev account with budgets and teardown.
- The AgentCore Managed Harness (config-only agent loop). It has its own spec,
  [`../aws-agentcore-harness/`](../aws-agentcore-harness/), which keeps tools in ToolBus by
  using the Harness's client-side inline functions.
- VPC network mode. About seven interface endpoints cost roughly $70–100 a month, more than
  the dev budget. It is documented as a design, not deployed.
