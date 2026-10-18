# Tasks: AWS-native Backend (Strands + AgentCore)

**Spec ID:** `aws-strands-agentcore`
**Read first:** [`requirements.md`](./requirements.md), then [`design.md`](./design.md).
**Blocked on:** `cloud-backend-foundation` Phases 0–3 (0.5, conformance in CI, is still open).
Also needed: foundation 4.2 before tasks 1.5–1.6, and foundation 6.2–6.3 before any 💲 task.
**Revised:** 2026-10-18. New tasks 2.0 (Step 0 baseline) and 4.0 (lessons in the cloud);
tightened 0.1, 0.2, 2.1, 2.2, 3.1, 3.2, 3.6, 4.1; optional 5.4 and 5.5.

Living checklist. Check a box only when its Definition of done is literally true.
Tasks marked **💲** spend money and need Rick's go-ahead in the session.
Tasks marked **🔑** need AWS credentials on Rick's Mac.

---

## How to execute this plan (Cursor)

One task per session, on branch `feat/aws-native-<task-id>`. Then:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ evals/
uv run pytest tests/unit tests/conformance -q
# infra tasks also:
(cd infra/terraform/aws/envs/dev && terraform fmt -check -recursive ../.. && terraform validate)
```

Never run `terraform apply` or `destroy` without Rick's explicit go-ahead in that session.
After any cloud session, run `infra/scripts/teardown_check.sh aws`.

---

## Phase 0: Spike and pin (free)

- [ ] **0.1 Spike: pin the APIs this spec depends on**
  - From current docs, record in `docs/adr/` (appendix to the cloud-native ADR):
    - the Strands version, its Ollama and Bedrock model providers, and how to register a
      tool from a runtime JSON schema;
    - the AgentCore Runtime service contract: port, endpoint paths, payload, architecture,
      and the supported pattern for work longer than one request;
    - the first `hashicorp/aws` 6.x release with `aws_bedrockagentcore_agent_runtime`,
      `_memory` and `_code_interpreter`, proven with `terraform providers schema -json`.
      The current 5.100.0 pin predates them;
    - the `us.` inference-profile ids for the chosen models, and the foundation-model ARNs
      each profile routes to (needed for IAM in 3.2);
    - the Strands `BedrockModel` options for prompt caching and for evaluating the guardrail
      on the latest message only;
    - the Runtime's async-task API (`add_async_task`, `HealthyBusy`), `StopRuntimeSession`,
      and whether the Runtime supports S3 Files or EFS mounts.
  - **Definition of done:** every item is recorded with a doc link and the date checked,
    `pyproject.toml` gains a `strands` extra with pinned versions, and every AWS module's
    `versions.tf` uses the new provider pin with `terraform validate` green.
  - _Requirements: R1, R2.2, R4.1, R5.1_

- [ ] **0.2 🔑 Rick: account prep** *(human task, about 30 min)*
  - Submit the Anthropic first-time-use form in the Bedrock console. Serverless models are
    otherwise enabled by default (confirm in 0.1).
  - Create the `ai-team` AWS profile (SSO or IAM user) with admin rights in a dev account,
    used only for Terraform.
  - **Definition of done:** `aws sts get-caller-identity --profile ai-team` works, and a
    `bedrock-runtime converse` call succeeds for both chosen `us.` profile ids.

## Phase 1: Local, in-process and container ($0)

- [ ] **1.1 `strands_backend` skeleton + fake model**
  - Add `backend.py`, `models.py` (with the `fake` provider only) and `agents.py` for the
    thin slice (design §2).
  - **Definition of done:** the conformance suite passes for `strands` with the fake model.
  - _Requirements: R1.1–R1.5_

- [ ] **1.2 Tool adapter**
  - `tools.py`: BridgedTool → Strands tools.
  - **Definition of done:** a unit test shows each of the developer role's tools callable
    through Strands, with results equal to calling `ToolBus.invoke` directly.
  - _Requirements: R1.3_

- [ ] **1.3 `commit_phase` harness tool and acceptance hook**
  - **Definition of done:** a conformance test shows the manager can't advance a phase
    when guardrails fail, and that accepts are recorded from harness evidence.
  - _Requirements: R1.3_

- [ ] **1.4 Usage → spend guard**
  - **Definition of done:** a fake model reporting 1,000 in / 500 out tokens records the
    priced cost, and a model reporting none records `observed_usd: null` plus a warning.
  - _Requirements: R1.4_

- [ ] **1.5 Ollama provider + local smoke**
  - **Definition of done:** `make local-smoke BACKEND=strands` passes the thin slice against
    host Ollama, recorded as `model_tier: local`. Spans show up in Aspire (compose
    `observability` profile running) and import with `evals trace import-otel`.
  - _Requirements: R2.1_

- [ ] **1.6 Container implementing the Runtime contract**
  - Add `docker/strands.Dockerfile` (arm64) and `runtime_app.py` per the contract pinned in 0.1.
  - **Definition of done:** `docker compose --profile strands --profile observability up`,
    then `ai-team run --backend strands --target container "<thin slice>"`, passes. The
    artifacts land in `output/runs/<id>/` in the same layout as a local run.
  - _Requirements: R2.2, R2.3, R5.1.4_

## Phase 2: Bedrock models from the laptop (💲 ≤ $5)

- [ ] **2.0 💲🔑 Step 0: existing backends on Bedrock** *(any time after 0.2; independent of Phase 1)*
  - `claude-agent-sdk`: skip the `ANTHROPIC_API_KEY` precondition in `orchestrator.py` when
    `CLAUDE_CODE_USE_BEDROCK=1`, and pass the AWS profile through.
  - `langgraph`: add the LiteLLM `bedrock/<us. profile id>` path in `llm_factory.py`, and let
    `model_validation.py` accept Bedrock ids.
  - Use the same model ids that 2.1 configures for Strands.
  - **Definition of done:** the thin slice is green on both backends via Bedrock, with cost
    recorded and a row each in `docs/CLOUD_NATIVE.md`. Unit tests cover both config paths
    with stubbed clients.
  - _Requirements: R0_

- [ ] **2.1 Bedrock provider + pricing**
  - **Definition of done:** config-only switch per design §3, with price entries added. A
    unit test with a stubbed Bedrock client shows usage is priced, including cache-read and
    cache-write tokens.
  - _Requirements: R3.1, R3.3_

- [ ] **2.2 💲🔑 Live smoke on Bedrock (in-process)**
  - **Definition of done:** thin slice green on Bedrock. Record the cost next to the
    CloudWatch `AWS/Bedrock` token metrics for the run window, priced by our table (within
    ±20%), and add a row to `docs/CLOUD_NATIVE.md` (strands / local / bedrock). The billing
    console figure is added the next day as a note; it does not gate the task.
  - _Requirements: R3_

- [ ] **2.3 💲🔑 Live smoke on Bedrock (container)**
  - Pass AWS credentials to the container via a mounted profile, read-only, never as env keys.
  - **Definition of done:** green, with a row added to the table.
  - _Requirements: R3.2_

## Phase 3: Terraform (plan free; apply 💲)

- [ ] **3.1 Modules: `ecr_repo`, `artifacts_bucket`, `observability`**
  - `observability` also turns on CloudWatch Transaction Search (AgentCore traces need it)
    and adds an alarm on `AWS/Bedrock` token metrics as the real-time spend backstop.
  - `artifacts_bucket` holds `runs/` (expires after 14 days) and `state/` (versioned, kept).
  - **Definition of done:** they validate, checkov is clean or has reasoned skips, and
    `terraform-docs` READMEs are generated.
  - _Requirements: R4.1_

- [ ] **3.2 Module: `iam_runtime_role`**
  - Least-privilege policy documents per design §5.
  - Each model gets one statement listing its `us.` inference-profile ARN and the
    foundation-model ARNs that profile routes to, conditioned on `bedrock:InferenceProfileArn`.
  - **Definition of done:** a `terraform test` asserts there are no `*` actions, that only
    the listed profile and model ARNs are allowed, and that every profile is paired with its
    model ARNs.
  - _Requirements: R4.1, R4.2_

- [ ] **3.3 Module: `bedrock_guardrail`**
  - **Definition of done:** it validates, and its outputs expose the guardrail id and
    version for the backend config.
  - _Requirements: R4.1_

- [ ] **3.4 Module: `agentcore_runtime`**
  - Takes the image by digest and the role ARN, with env vars for the bucket, region,
    model ids and guardrail.
  - **Definition of done:** it validates against the pinned provider version.
  - _Requirements: R4.1_

- [ ] **3.5 `push_image_aws.sh`**
  - **Definition of done:** the script builds arm64, pushes, and prints the digest. A dry
    run mode prints the commands without running them.
  - _Requirements: R4.3_

- [ ] **3.6 🔑 `envs/dev` wiring + plan**
  - `backend.hcl.example` uses the S3 backend with `use_lockfile = true` (no DynamoDB table).
  - **Definition of done:** `terraform plan` succeeds on Rick's Mac. The plan summary
    (resource counts and IAM statements) is pasted into the task notes and reviewed by Rick.
  - _Requirements: R4_

- [ ] **3.7 💲🔑 First apply + teardown drill**
  - Rick runs apply, pushes the image, runs apply again with the digest, then destroy.
  - **Definition of done:** `teardown_check.sh aws` prints 0 billable resources after
    destroy. Record the time taken for each step.
  - _Requirements: R4.4_

## Phase 4: Cloud run end to end (💲 ≤ $10)

- [ ] **4.0 Lessons persist across cloud runs**
  - In `runtime_app.py`: fetch `state/lessons.db` with its ETag at start, write it back with
    `If-Match` at the end, and on a conflict re-fetch, merge and retry once (design §4).
  - **Definition of done:** a conformance test runs the thin slice twice on
    `target=container`, each time in a fresh container against a local S3 stand-in (moto or
    MinIO), and shows a lesson written in run 1 is injected in run 2. A unit test covers the
    conflict path.
  - _Requirements: R5.4_

- [ ] **4.1 `remote.py`: RemoteRunClient for AgentCore**
  - Poll with the same `runtimeSessionId`, and end the session with `StopRuntimeSession` after
    download. The container syncs artifacts after every commit and `logs/` in a `finally`.
  - **Definition of done:** it passes the foundation's remote-client tests against the
    local container (target=container), before any cloud call. A test that kills the
    container mid-run still finds `logs/` and the last committed phase in the bucket.
  - _Requirements: R5.1_

- [ ] **4.2 💲🔑 Cloud smoke: thin slice**
  - **Definition of done:** `ai-team run --backend strands --target cloud` completes, with
    artifacts downloaded and cost recorded, and the trace visible in CloudWatch. A table
    row and a screenshot of the CloudWatch trace go in `docs/images/`.
  - _Requirements: R5.1, R5.3_

- [ ] **4.3 💲 Traces back into ai-team**
  - **Definition of done:** `evals trace import-otel` on the exported spans gives kind
    counts within the two-reader tolerance of the harness spans for the same run, or the
    difference is written up in the journal.
  - _Requirements: R5.2_

- [ ] **4.4 Destroy**
  - **Definition of done:** the teardown check shows 0 billable resources.

## Phase 5: Native mechanisms compared (💲 ≤ $5)

- [ ] **5.1 AgentCore Memory as the lessons store**
  - Add a `memory` module and an adapter behind the lessons interface.
  - **Definition of done:** in a cloud run, the lessons written in run 1 are retrieved in
    run 2, and a unit test with a stub covers the adapter.
  - _Requirements: R6.1_

- [ ] **5.2 Guardrail evidence**
  - **Definition of done:** a seeded prompt-injection input is blocked by the Bedrock
    guardrail, and the same input is also caught (or not) by ai-team's security guardrail.
    Both outcomes are recorded.
  - _Requirements: R6.2_

- [ ] **5.3 Write-up in `docs/CLOUD_NATIVE.md`**
  - For Memory, Guardrails and Observability: replaced, complemented or couldn't replace,
    with one reason each.
  - **Definition of done:** the section is merged and linked from the README.
  - _Requirements: R6.2_

- [ ] **5.4 💲 (Optional) Code Interpreter as the sandbox for agent-written code**
  - Run the quality gate's pytest and ruff in AgentCore Code Interpreter under its own role,
    with no Bedrock or S3 write access.
  - **Definition of done:** a cloud thin slice passes with the gate running in Code
    Interpreter, and the write-up compares its time and cost with in-session runs.
  - _Requirements: R6.3_

- [ ] **5.5 Moved:** the AgentCore Managed Harness now has its own spec,
  [`../aws-agentcore-harness/`](../aws-agentcore-harness/), as the `agentcore-harness` backend.
  Nothing to do here.

## Phase 6: Stretch, the full team

- [ ] **6.1 Nine roles on Strands**
  - **Definition of done:** the conformance suite passes with the full phase plan, and one
    live Bedrock run finishes.
  - _Requirements: R7.1_
- [ ] **6.2 💲 Join the 30-run batch**
  - **Definition of done:** finish rate with a Wilson interval is published next to the
    other backends.
  - _Requirements: R7.2_
