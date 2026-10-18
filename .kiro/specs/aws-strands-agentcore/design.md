# Design: AWS-native Backend

**Spec ID:** `aws-strands-agentcore` · **Read first:** [`requirements.md`](./requirements.md)

---

## 0. Order of work

Change one thing at a time, so every result has something to compare against.

| Step | What changes | Tasks |
| --- | --- | --- |
| 0 | Model provider only: existing backends on Bedrock | 2.0 |
| 1 | Framework: Strands, on the laptop | Phases 1–2 |
| 2 | Where it runs: AgentCore Runtime | Phases 3–4 |
| 3 | One AWS service at a time | Phase 5 |

## 1. Components

```
src/ai_team/backends/strands_backend/
  backend.py        # StrandsBackend(ThreadedBackend): run() dispatches on ExecutionTarget
  agents.py         # build_manager(), build_specialist(role) from common/roles.py
  tools.py          # BridgedTool → Strands tool spec (foundation tool bridge)
  models.py         # model factory: ollama | bedrock | fake  (config-driven)
  usage.py          # Strands usage → spend_guard.record_usage (priced)
  runtime_app.py    # AgentCore Runtime entrypoint (HTTP contract), used only in the image
  remote.py         # RemoteRunClient for target=cloud (start/status/fetch via boto3 + S3)
docker/strands.Dockerfile
infra/terraform/aws/...
```

## 2. Orchestration: agents-as-tools

```
                 Manager (Strands Agent)
          tools: architect(), developer(), qa(), commit_phase()
              │            │             │
        Architect      Developer        QA         ← each a Strands Agent with
        (read tools)   (write tools)    (test tools)  role-scoped BridgedTools
```

- The manager calls a specialist as a tool with the phase brief. It gets back a summary,
  never raw transcripts, which keeps its context small.
- `commit_phase()` is a harness tool. It runs the phase guardrails, then
  `commit_pending_drafts(phase=...)`. The manager must call it to advance, and the harness
  refuses if the guardrails fail. This is the same draft-then-commit rule as every other
  backend.
- After QA, the foundation's `acceptance.evaluate` runs on the harness evidence.

**Why agents-as-tools, not a swarm:** it gives a deterministic phase order, it's easy to
conformance-test, and it maps directly onto the existing phase plan. A Strands swarm or
graph variant is a later ablation, not the baseline.

## 3. Models

```yaml
# config: strands section
provider: ollama | bedrock | fake
ollama:  {host: http://localhost:11434, model: <pinned in foundation 4.1>}
bedrock: {region: us-east-1, profile: ai-team,
          models: {manager: <us. claude inference profile id>, specialist: <us. cheaper profile id>},
          prompt_caching: true,
          guardrail: {id: <from terraform output>, version: <n>}}
```

The Bedrock guardrail is attached per model call through the model configuration, so it
applies in Phase 2 (laptop) and Phase 4 (cloud) alike. Phase 3's Terraform creates it, and
Phase 2 runs without it until then.

The guardrail evaluates the latest message or tool result only, not the full context on
every turn. Guardrails are billed per 1,000 characters evaluated, so full-context checks on
every turn can approach the token bill. Indirect prompt injection arrives in tool results,
so those must be evaluated (task 5.2 confirms which message roles are).

The Step 0 baseline (requirements R0) uses the same model ids.

## 4. The container and the Runtime contract

```
docker/strands.Dockerfile
  FROM python:3.11-slim (linux/arm64)
  + uv sync --frozen --extra strands
  + pytest, ruff (the quality gate runs generated code inside the container)
  CMD serve runtime_app on :8080
```

`runtime_app.py` exposes the Runtime's invocation and health endpoints. Pin the exact
paths and the payload shape from the AgentCore docs in task 0.1 rather than assuming them.
An invocation:

1. creates the run id and workspace under `/tmp/ai-team/<id>`, and fetches
   `s3://<bucket>/state/lessons.db` (with its ETag) into the local lessons path;
2. runs `StrandsBackend(target=local).run(...)` in a worker thread, registered as an async
   task (`app.add_async_task` / `complete_async_task`) so `/ping` reports `HealthyBusy`.
   Nothing blocking runs on the request thread: a starved `/ping` gets the session reaped
   after 15 minutes;
3. syncs `workspace/` and `output/runs/<id>/` to `s3://<bucket>/runs/<id>/` after every
   `commit_pending_drafts`, and syncs `logs/` in a `finally`;
4. writes the lessons store back with `If-Match: <ETag>`. On a conflict (another run wrote
   lessons first) it re-fetches, merges (lessons are append-only rows) and retries once;
5. answers a `status` invocation on the same `runtimeSessionId`. The client ends the
   session with `StopRuntimeSession` after downloading.

The local `container` target talks to the same endpoints on `localhost:8080`, so the
remote client is tested before any AWS resource exists.

## 5. Terraform (envs/dev)

```hcl
module "ecr"        { source = "../../modules/ecr_repo"          name = "ai-team-strands" }
module "artifacts"  { source = "../../modules/artifacts_bucket"  expire_days = 14 }
module "guardrail"  { source = "../../modules/bedrock_guardrail" pii = true, prompt_attack = "HIGH" }
module "role"       { source = "../../modules/iam_runtime_role"
                      model_arns = var.bedrock_model_arns  ecr_repo_arn = module.ecr.arn
                      bucket_arn = module.artifacts.arn     log_group_arn = module.obs.log_group_arn }
module "runtime"    { source = "../../modules/agentcore_runtime"
                      image_uri = "${module.ecr.url}@${var.image_digest}"
                      role_arn  = module.role.arn           env = { ARTIFACTS_BUCKET = module.artifacts.name, ... } }
module "obs"        { source = "../../modules/observability"  retention_days = 14 }
module "budget"     { source = "../../modules/budget"          monthly_budget_usd = 25 }
```

- **Deploy by digest.** `push_image_aws.sh` prints the digest, and `var.image_digest`
  takes it. A new image means a new plan, with no hidden drift.
- **IAM least privilege** is written as data-source policy documents, one statement per
  capability, each commented with why it exists.
- **Tests:** `terraform validate` plus `tflint` and `checkov` in CI. Optionally, a
  `terraform test` file (`*.tftest.hcl`) asserting that the IAM policy has no `*` actions.
- Provider resources for AgentCore are recent. Pin the `hashicorp/aws` version that
  introduced them in `versions.tf`, and record the version in the ADR. The current pin
  (5.100.0) predates them; move every module together to the 6.x release task 0.1 finds.
- **Inference profiles in IAM.** A call through a `us.` profile is authorised against both
  the profile ARN and the foundation-model ARN in each region the profile routes to. Write
  one statement per model listing both, conditioned on `bedrock:InferenceProfileArn`. The
  `terraform test` asserts the pairing.
- **Transaction Search** is a one-time account setting that AgentCore traces need. The
  `observability` module turns it on, together with the token-metric spend alarm.
- **State:** the S3 backend with `use_lockfile = true` (Terraform 1.10 or later). No
  DynamoDB lock table.

## 6. Observability, two readers

```
Strands (OTel GenAI spans) ──► AgentCore Observability ──► CloudWatch  (reader 1: AWS)
            │
            └── dual export (OTLP → S3 file, or pull from CloudWatch) ──► evals trace import-otel
                                                                         (reader 2: ai-team)
ai-team harness spans (ToolBus audit, qa verdicts) ─────────────────────► TraceBuilder (primary)
```

The foundation's two-reader rule applies: harness spans are primary, and the OTel import
is compared against them. A disagreement is a finding, not a bug to hide.

The Runtime runs one container, so there is no collector sidecar. The second reader is an
in-process OTLP JSON exporter writing into the run's S3 prefix next to the artifacts.
Pulling from the CloudWatch `aws/spans` log group is the fallback.

## 7. Cost controls

- Phase 2 and 4 runs use `AI_TEAM_RUN_BUDGET_USD=1.50` and the cheaper model for specialists.
- The budget module alerts at $12.50 and $25.
- Budgets lag by hours. The real-time guard is the in-process spend guard, backed by a
  CloudWatch alarm on `AWS/Bedrock` token metrics (task 3.1).
- Compute is not the cost. A 30-minute run uses about $0.01 of Runtime, because CPU is
  billed only while busy, not while waiting on the model. Tokens are about $1–2 a run.
- Public network mode only. VPC mode needs about seven interface endpoints, roughly
  $70–100 a month, more than the whole dev budget, so it stays a written design.
- `destroy` runs at the end of every cloud session until Phase 5 is done. Nothing is
  left running overnight.

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| The Runtime's long-running contract differs from the design | Spike 0.1 pins it; the design adapts before any code |
| Terraform provider gaps for a new AgentCore feature | Use `awscc` or a documented one-off CLI step, recorded in the ADR |
| Local model too weak for tool use | Local runs prove plumbing only (`model_tier: local`); quality comes from Bedrock runs |
| Anthropic model use-case form not yet submitted | Submit it on day 1 (task 0.2); Phases 0–1 don't need it |
| Cloud runs lose lessons (session disk is discarded) | Lessons store round-trips through S3 with a conditional write (R5.4, task 4.0) |
| IAM refuses calls made through inference profiles | Pair profile and foundation-model ARNs (task 3.2) |
| Agent-written code can use the execution role's credentials | Tight role and budget in dev; optional Code Interpreter sandbox (task 5.4) |
