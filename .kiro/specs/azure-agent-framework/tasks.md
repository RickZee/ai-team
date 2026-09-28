# Tasks: Azure-native Backend (Agent Framework + Foundry)

**Spec ID:** `azure-agent-framework`
**Read first:** [`requirements.md`](./requirements.md), then [`design.md`](./design.md).
**Blocked on:** `cloud-backend-foundation` Phases 0–3.

Living checklist. Check a box only when its Definition of done is literally true.
Tasks marked **💲** spend money and need Rick's go-ahead in the session.
Tasks marked **🔑** need `az login` on Rick's Mac.

---

## How to execute this plan (Cursor)

One task per session, on branch `feat/azure-native-<task-id>`. Then:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ evals/
uv run pytest tests/unit tests/conformance -q
# infra tasks also:
(cd infra/terraform/azure/envs/dev && terraform fmt -check -recursive ../.. && terraform validate)
```

Never run `terraform apply` or `destroy` without Rick's explicit go-ahead in that session.
After any cloud session, run `infra/scripts/teardown_check.sh azure`.

---

## Phase 0: Spike and pin (free)

- [ ] **0.1 Spike: pin the APIs this spec depends on**
  - Record in the cloud-native ADR appendix, each with a doc link and the date checked:
    - the Agent Framework Python package version;
    - which workflow builder to use for a fixed phase order with a human-in-the-loop pause;
    - the function-tool API that accepts an explicit JSON schema;
    - the OpenAI-compatible client and the Foundry/Azure client names;
    - how Foundry projects are created in Terraform today (azurerm, azapi or AVM), and
      whether Agent Framework can use a project created that way;
    - the Prompt Shields API (direct and indirect);
    - the OTel → Application Insights setup for Agent Framework;
    - the Container Apps Job maximum execution timeout.
  - **Definition of done:** everything above is recorded, and `pyproject.toml` gains an
    `agent-framework` extra with pinned versions.
  - _Requirements: R1, R2, R3, R4, R6_

- [ ] **0.2 🔑 Rick: subscription prep** *(human task, about 45 min)*
  - A pay-as-you-go subscription. Check model quota for the chosen GPT models in the
    target region, and whether Claude in Foundry is offered.
  - Run `az login`. Create a service principal only if CI plan ever needs one; it doesn't yet.
  - **Definition of done:** `az account show` works, and the quota check result is
    recorded in the task notes.

## Phase 1: Local, in-process and container ($0)

- [ ] **1.1 `agent_framework_backend` skeleton + fake client**
  - Add `backend.py`, `clients.py` (with `fake`), `executors.py` and `workflow.py` for the
    thin slice (design §2).
  - **Definition of done:** the conformance suite passes for `agent-framework`.
  - _Requirements: R1.1–R1.5_

- [ ] **1.2 Tool adapter**
  - **Definition of done:** every developer-role tool is callable through Agent Framework,
    with results identical to `ToolBus.invoke`.
  - _Requirements: R1.3_

- [ ] **1.3 Harness commit steps + acceptance**
  - **Definition of done:** a conformance test shows a failed guardrail routes back and
    blocks the next phase, and accepts are recorded from harness evidence.
  - _Requirements: R1.3_

- [ ] **1.4 Human-in-the-loop → `human_review`**
  - **Definition of done:** a seeded guardrail escalation pauses the workflow, and the
    results bundle says `human_review`, not `failed`.
  - _Requirements: R1.6_

- [ ] **1.5 Usage → spend guard**
  - **Definition of done:** same checks as the AWS spec, task 1.4.
  - _Requirements: R1.4_

- [ ] **1.6 Ollama via the OpenAI-compatible client + local smoke**
  - **Definition of done:** `make local-smoke BACKEND=agent-framework` is green
    (`model_tier: local`), spans show in Aspire, and `import-otel` works on them.
  - _Requirements: R2.1_

- [ ] **1.7 Container (`job_main`) + compose**
  - **Definition of done:** `ai-team run --backend agent-framework --target container`
    passes the thin slice, with artifacts in the same layout as a local run and the exit
    codes behaving per design §4.
  - _Requirements: R2.2, R2.3_

- [ ] **1.8 DevUI entry point**
  - **Definition of done:** `make af-devui` opens the thin-slice workflow in DevUI, and a
    short section in `docs/CLOUD_NATIVE.md` shows how to debug a run with it.
  - _Requirements: R2.4_

## Phase 2: Foundry models from the laptop (💲 ≤ $5)

Needs model deployments to exist. Either create them by hand in the portal once (and
record that), or run Phase 3.1–3.3 first. Terraform is preferred.

- [ ] **2.1 Foundry client + Entra auth + pricing**
  - **Definition of done:** a config-only switch. A unit test with a stubbed credential and
    client shows usage is priced, and no key is read from env.
  - _Requirements: R3.1, R3.2_

- [ ] **2.2 💲🔑 Live smoke on Foundry (in-process)**
  - **Definition of done:** thin slice green, cost recorded, and a table row added
    (agent-framework / local / foundry).
  - _Requirements: R3_

- [ ] **2.3 💲🔑 Live smoke on Foundry (container)**
  - Mount the az CLI token cache read-only, or use a short-lived token. Never a key.
  - **Definition of done:** green, with a table row added.
  - _Requirements: R3.2_

## Phase 3: Terraform (plan free; apply 💲)

- [ ] **3.1 Modules: `observability`, `artifacts_storage`, `key_vault`, `acr`**
  - **Definition of done:** they validate, checkov is clean or has reasoned skips, and
    `terraform-docs` READMEs are generated.
  - _Requirements: R4.1_

- [ ] **3.2 Module: `foundry` (AI Services + project + deployments)**
  - Use the path chosen in 0.1 (azapi, AVM or one documented CLI step).
  - **Definition of done:** it validates, and the outputs give the endpoint and deployment
    names that the backend config consumes.
  - _Requirements: R4.1_

- [ ] **3.3 Module: `identity_rbac`**
  - **Definition of done:** a `terraform test` asserts there are no subscription-scope
    role assignments, and every assignment has a comment.
  - _Requirements: R4.1, R4.2_

- [ ] **3.4 Module: `container_apps_job`**
  - Manual trigger, image by digest, user-assigned identity, the timeout from 0.1, and
    secrets referenced from Key Vault.
  - **Definition of done:** validates.
  - _Requirements: R4.1_

- [ ] **3.5 `push_image_azure.sh`**
  - **Definition of done:** it builds and pushes to ACR and prints the digest, with a dry
    run mode.
  - _Requirements: R4.3_

- [ ] **3.6 🔑 `envs/dev` wiring + plan**
  - **Definition of done:** `plan` succeeds on Rick's Mac. The summary (resource counts and
    role assignments) is pasted into the notes and reviewed by Rick.
  - _Requirements: R4_

- [ ] **3.7 💲🔑 First apply + teardown drill**
  - **Definition of done:** apply, push, apply again with the digest, then destroy.
    `teardown_check.sh azure` reports 0 billable resources, with the time for each step
    recorded.
  - _Requirements: R4.4_

## Phase 4: Cloud run end to end (💲 ≤ $10)

- [ ] **4.1 `remote.py`: RemoteRunClient for Container Apps Jobs**
  - **Definition of done:** it passes the foundation's remote-client tests with a fake job
    API, and against the local container target.
  - _Requirements: R5.1_

- [ ] **4.2 💲🔑 Cloud smoke: thin slice**
  - **Definition of done:** `ai-team run --backend agent-framework --target cloud`
    completes, with artifacts downloaded, cost recorded, and the trace visible in
    Application Insights. A table row and a screenshot go in `docs/images/`.
  - _Requirements: R5.1, R5.3_

- [ ] **4.3 💲 Traces back into ai-team**
  - **Definition of done:** the two-reader comparison for the same run is recorded.
  - _Requirements: R5.2_

- [ ] **4.4 Destroy**
  - **Definition of done:** the teardown check shows 0 billable resources.

## Phase 5: Native mechanisms compared (💲 ≤ $5)

- [ ] **5.1 Prompt Shields adapter**
  - Direct check on the brief, indirect check on tool outputs.
  - **Definition of done:** unit tests with a stubbed API, plus one live check each for a
    seeded direct and a seeded indirect injection.
  - _Requirements: R6.1, R6.2_

- [ ] **5.2 Write-up in `docs/CLOUD_NATIVE.md`**
  - For Prompt Shields, Application Insights / Foundry tracing and Entra identity: replaced,
    complemented or couldn't replace, with one reason each.
  - **Definition of done:** merged and linked from the README.
  - _Requirements: R6.3_

## Phase 6: Stretch

- [ ] **6.1 💲 Foundry Agent Service hosted agent**
  - **Definition of done:** either green with a table row, or `not available` with the
    reason and date.
  - _Requirements: R7.1_
- [ ] **6.2 Nine roles + 30-run batch**
  - **Definition of done:** finish rate with a Wilson interval, next to the other backends.
  - _Requirements: R7.2_
