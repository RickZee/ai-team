# Design: Azure-native Backend

**Spec ID:** `azure-agent-framework` · **Read first:** [`requirements.md`](./requirements.md)

---

## 1. Components

```
src/ai_team/backends/agent_framework_backend/
  backend.py        # AgentFrameworkBackend(ThreadedBackend): dispatch on ExecutionTarget
  workflow.py       # build_thin_slice_workflow(), build_full_workflow()
  executors.py      # one executor per role; wraps an Agent Framework agent
  tools.py          # BridgedTool → Agent Framework function tools (explicit JSON schema)
  clients.py        # chat client factory: ollama(OpenAI-compatible) | foundry | fake
  auth.py           # DefaultAzureCredential / managed identity; Key Vault fallback
  shields.py        # Prompt Shields adapter → guardrail result
  usage.py          # usage → spend_guard
  job_main.py       # container entrypoint for the Container Apps Job
  remote.py         # RemoteRunClient: start job execution, poll, fetch from Blob
docker/agent-framework.Dockerfile
infra/terraform/azure/...
```

## 2. Orchestration: a workflow, not a mega-agent

```
 brief ─► [Shields] ─► Manager ─► Architect ─► commit(arch) ─► Developer ─► commit(dev)
                                                                  │
                     human_review ◄── guardrail escalation ◄──────┤
                                                                  ▼
                                               QA ─► commit(test) ─► acceptance.evaluate
```

- Each role is an executor wrapping one agent with its role-scoped tools.
- `commit(phase)` is a harness step: guardrails, then `commit_pending_drafts(phase=...)`.
  A failure routes back to the previous executor, capped by the same retry budget as the
  LangGraph backend.
- The escalation edge uses the framework's request/response (human-in-the-loop)
  mechanism, and maps to `human_review` in the results bundle.
- The thin slice and the full team are two builders over the same executors. The spike
  (0.1) pins which workflow builder API to use (explicit graph vs a sequential or handoff
  builder) and records the choice in the ADR.

## 3. Clients and identity

```yaml
# config: agent_framework section
provider: ollama | foundry | fake
ollama:  {base_url: http://localhost:11434/v1, model: <pinned>}
foundry: {endpoint: <from terraform output>, api_version: <pinned>,
          deployments: {manager: <deployment name>, specialist: <deployment name>},
          auth: entra | key_vault_key}
```

`auth.py` returns a token credential. It uses `DefaultAzureCredential` locally (az login)
and `ManagedIdentityCredential(client_id=...)` in the job. Keys are only fetched from Key
Vault, and only when `auth: key_vault_key` is set explicitly.

## 4. The container

```
docker/agent-framework.Dockerfile
  FROM python:3.11-slim
  + uv sync --frozen --extra agent-framework
  + pytest, ruff
  ENTRYPOINT ["python", "-m", "ai_team.backends.agent_framework_backend.job_main"]
  # args/env: RUN_ID, DESCRIPTION (or blob path to it), PROFILE, ARTIFACTS_URL
```

`job_main` runs the backend with `target=local`, uploads `workspace/` and
`output/runs/<id>/` to Blob Storage under `runs/<id>/`, and exits with 0 (completed),
2 (human_review), 3 (budget or timeout) or 1 (error). The exit code is also written into
the results bundle, because Container Apps Job status alone can't tell them apart.

## 5. Terraform (envs/dev)

```hcl
module "rg_obs"    { source = "../../modules/observability"       # RG, Log Analytics, App Insights
                     name   = "ai-team-dev" }
module "foundry"   { source = "../../modules/foundry"             # AI Services + project (azapi/AVM)
                     deployments = var.model_deployments }        # manager + specialist
module "identity"  { source = "../../modules/identity_rbac"       # UAMI + scoped role assignments
                     ai_services_id = module.foundry.id  acr_id = module.acr.id
                     storage_container_id = module.storage.container_id  key_vault_id = module.kv.id }
module "acr"       { source = "../../modules/acr" }
module "storage"   { source = "../../modules/artifacts_storage"  expire_days = 14 }
module "kv"        { source = "../../modules/key_vault" }
module "job"       { source = "../../modules/container_apps_job"
                     image  = "${module.acr.login_server}/ai-team-af@${var.image_digest}"
                     identity_id = module.identity.id
                     env = { FOUNDRY_ENDPOINT = module.foundry.endpoint, APPLICATIONINSIGHTS_CONNECTION_STRING = ..., ... } }
module "budget"    { source = "../../modules/budget"  monthly_budget_usd = 25 }
```

- **Known risk:** Foundry projects created by Terraform have had issues being used from
  Agent Framework (see the Microsoft Q&A thread linked in the ADR). Spike 0.1 checks which
  path works today (azurerm, azapi, or the Azure Verified Module) and records it. If none
  works, the project is created by one documented CLI step and everything else stays in
  Terraform.
- **Deploy by digest**, as on AWS.
- The **App Insights connection string** isn't a secret credential but is still passed
  as a job secret, never logged.
- **Tests:** validate, tflint (azurerm ruleset), checkov. Optionally a `terraform test`
  asserting no subscription-scope role assignments besides the budget.

## 6. Observability, two readers

```
Agent Framework (OTel) ─► azure-monitor-opentelemetry ─► Application Insights (reader 1: Azure)
          │
          └─► OTLP file/collector export ─► evals trace import-otel ─► ai-team (reader 2)
ai-team harness spans ────────────────────────────────► TraceBuilder (primary)
```

Locally the same OTel goes to the Aspire dashboard. That's a nice symmetry, since Aspire
is Microsoft's own local telemetry viewer.

## 7. Prompt Shields placement

- **Direct:** the user brief, before the manager sees it.
- **Indirect:** any tool output that will be put back into a prompt (file reads, test
  output), checked before it reaches the next model call.
- A shield hit becomes a guardrail result with `source: "azure_prompt_shields"`. ai-team's
  own security guardrail still runs, and both results are logged. The comparison in R6 is
  built from those logs.

## 8. Cost controls

- Specialist tier on the cheaper deployment, with the per-run budget at $1.50.
- Container Apps Job, not an always-on app, so there's no idle compute cost.
- Destroy after every cloud session until Phase 5 is done.

## 9. Risks

| Risk | Mitigation |
| --- | --- |
| Subscription has no model quota (free trial) | Pay-as-you-go subscription; quota checked in 0.2 |
| Claude in Foundry unavailable on the subscription | GPT deployments only; the table notes it |
| Agent Framework API churn (1.x is recent) | Pin versions in 0.1; adapters kept thin |
| Terraform-created Foundry project unusable | Spike 0.1 chooses azapi, AVM or one CLI step |
| Long runs vs job timeout | Set the job replica timeout above the per-run wall-clock limit; test with the budget-exceeded path |
