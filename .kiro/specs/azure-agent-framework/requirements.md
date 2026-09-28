# Requirements: Azure-native Backend (Microsoft Agent Framework on Azure AI Foundry)

**Spec ID:** `azure-agent-framework`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Created:** 2026-09-28
**Budget:** Phases 0–1 **$0.00** (local). Phase 2 **≤ $5** (Foundry models from the laptop).
Phases 3–5 **≤ $15** including hosting, tracing and teardown. Every spending task is
human-triggered.
**Depends on:** [`../cloud-backend-foundation/`](../cloud-backend-foundation/), Phases 0–3.
**Executed by:** Cursor, one task per session. `terraform apply/destroy` only with Rick's go-ahead.
**Priority:** execute **before** `aws-strands-agentcore` if only one can run. The Azure
stack is the gap in current target roles.

---

## Introduction

This spec adds `agent-framework`, a fifth orchestration backend built on Microsoft's own
agent stack:

| Layer | Azure-native mechanism | What it replaces or complements in ai-team |
| --- | --- | --- |
| Orchestration | **Microsoft Agent Framework** (Python, 1.x): agents and multi-agent **workflows** | A peer of LangGraph, CrewAI, the Claude SDK and Strands |
| Models | **Azure AI Foundry** model deployments (Azure OpenAI GPT; Claude in Foundry if the subscription allows) | OpenRouter |
| Identity | **Microsoft Entra ID**: `DefaultAzureCredential` locally, **user-assigned managed identity** in the cloud, RBAC-scoped | API keys |
| Guardrails | **Azure AI Content Safety, Prompt Shields**, on user and tool input | Complements ai-team's security guardrails |
| Hosting | **Azure Container Apps Job** (cloud target). **Foundry Agent Service** hosted agent as a stretch goal | Local subprocess |
| Observability | **OpenTelemetry → Application Insights** (Azure Monitor), plus Foundry tracing | A second reader for ai-team traces |
| Secrets | **Key Vault** for anything that can't use identity | `.env` |
| Infrastructure | **Terraform**: `azurerm`, plus `azapi` where Foundry resources are newer than `azurerm` | None today |

**Principle:** local first. Every phase must pass the same thin-slice smoke test before
the next phase adds a cloud dependency:

```
Phase 1  in-process + Ollama (OpenAI-compatible)  ($0)  ──►  Phase 1b container + Ollama ($0)
Phase 2  in-process + Foundry models, Entra auth  (≤$5) ──►  Phase 3  Terraform (≤$15)
Phase 4  cloud run on Container Apps Job, traces into App Insights and back into ai-team evals
Phase 5  native mechanisms compared: Prompt Shields, Foundry tracing; hosted agent (stretch)
```

---

## R1: Agent Framework backend, in-process

1. THE SYSTEM SHALL provide `src/ai_team/backends/agent_framework_backend/`, implementing
   `Backend` with `name = "agent-framework"`.
2. The thin slice (manager → architect → developer → QA) SHALL be an **Agent Framework
   workflow**, with one executor per role and edges following the phase plan. It SHALL NOT
   be a single agent with every tool.
3. Every tool call SHALL go through `ToolBus.invoke` via the foundation tool bridge, and
   writes SHALL be drafts committed by the harness between workflow steps, after guardrails.
4. Usage reported by the chat client SHALL be priced and recorded through the spend guard.
   Missing usage is `observed_usd: null` plus a warning, never $0.
5. The backend SHALL pass the foundation conformance suite with a fake chat client.
6. Human-in-the-loop: the workflow's request/response mechanism for pausing on a human
   decision SHALL be wired to ai-team's existing `human_review` outcome, so a guardrail
   escalation pauses the workflow rather than failing it.

## R2: Local model and container

1. The backend SHALL run against **Ollama** through Agent Framework's OpenAI-compatible
   chat client (`base_url` pointed at Ollama), with the model id pinned in config.
2. THE SYSTEM SHALL provide `docker/agent-framework.Dockerfile`, whose image runs a run
   given as CLI arguments or environment variables and exits. That's the shape an Azure
   Container Apps Job executes.
3. The image SHALL pass the thin slice under Docker Compose (`--profile agent-framework`)
   against host Ollama, exporting OTel to the local collector and Aspire dashboard.
4. Agent Framework's **DevUI** SHALL be documented as the local debugging entry point
   (`make af-devui`). It isn't used in tests.

## R3: Foundry models with Entra ID

1. The backend SHALL switch to **Azure AI Foundry model deployments** by configuration
   only: endpoint, deployment names per role tier, and API version.
2. Authentication SHALL be **keyless**: `DefaultAzureCredential`, so `az login` works
   locally and managed identity works in the cloud. API-key auth SHALL be supported only
   as an explicit fallback, read from Key Vault, never from `.env` in the cloud.
3. Pricing for the deployed models SHALL be added, and a live smoke run's recorded cost
   SHALL be within ±20% of Azure Cost Management once it updates, or the gap explained.

## R4: Infrastructure as code (Terraform)

1. `infra/terraform/azure/` SHALL create, in `envs/dev`:
   - a **resource group** with the shared tags;
   - a **Log Analytics workspace** and a workspace-based **Application Insights**;
   - an **AI Services / Foundry resource** with a **Foundry project** (using `azapi` or the
     Azure Verified Module where `azurerm` lags) and **model deployments** for the
     manager and specialist tiers;
   - **Content Safety** reachable from the same resource for Prompt Shields;
   - a **user-assigned managed identity** with **least-privilege role assignments**:
     model inference on the AI Services resource, `AcrPull` on the registry, blob data
     contributor on the artifacts container only, Key Vault secrets user, and monitoring
     publisher;
   - an **Azure Container Registry** (Basic, admin user disabled);
   - a **Storage account** for artifacts: TLS 1.2+, public blob access disabled, a
     lifecycle rule deleting after 14 days;
   - a **Key Vault** with RBAC authorization and purge protection off, since this is a dev
     environment (commented);
   - a **Container Apps environment** plus a **Container Apps Job** (manual trigger),
     running the image by digest with the managed identity;
   - a **budget** through the foundation module, $25 per month by default.
2. No role assignment SHALL be broader than its resource. No subscription-scope
   assignments except the budget. Each assignment gets a comment explaining why.
3. `push_image_azure.sh` SHALL build and push to ACR and print the digest for Terraform.
4. `terraform destroy` followed by `teardown_check.sh azure` SHALL report 0 billable resources.

## R5: Cloud execution target

1. `--backend agent-framework --target cloud` SHALL start a **Container Apps Job
   execution** with the run's description and profile, poll it to completion, and
   download the workspace and results bundle from Blob Storage into `output/runs/<id>/`,
   in the same layout as a local run.
2. Traces SHALL be viewable in Application Insights (transaction search or end-to-end
   view), and the same spans SHALL be imported into ai-team through
   `evals trace import-otel`, via dual export or a documented query export.
3. A cloud smoke run SHALL pass the thin slice with cost recorded before the full team is
   attempted.

## R6: Native mechanisms, compared honestly

1. **Prompt Shields** SHALL run on the user brief and on tool outputs that re-enter a
   prompt (indirect injection), as an input guardrail adapter next to ai-team's own
   security guardrail.
2. A seeded direct injection and a seeded indirect injection SHALL each be tested against
   both guardrails. Both results are recorded.
3. `docs/CLOUD_NATIVE.md` SHALL record, for Prompt Shields, Application Insights / Foundry
   tracing and Entra identity, whether the native mechanism replaced, complemented or
   could not replace the ai-team harness piece, with one reason each.

## R7: Stretch

1. **Foundry Agent Service hosted agent:** the same backend deployed as a hosted agent,
   if Terraform or the CLI supports it cleanly at execution time. Otherwise it's recorded
   as `not available` with the reason.
2. All nine roles on Agent Framework, joining the 30-run batch with a Wilson interval.

## Non-goals

- Copilot Studio and low-code agents.
- Private networking (VNet integration, private endpoints). Listed in the ADR as the
  production next step, not built here.
- Salesforce or any enterprise connectors.
