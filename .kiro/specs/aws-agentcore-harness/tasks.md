# Tasks: AWS Managed-Loop Backend (AgentCore Harness)

**Spec ID:** `aws-agentcore-harness`
**Read first:** [`requirements.md`](./requirements.md), then [`design.md`](./design.md).
**Blocked on:** `cloud-backend-foundation` Phases 0–3; from `aws-strands-agentcore`: 0.1, 0.2,
2.0 and the shared Terraform modules (3.1–3.3). Not blocked on the Strands backend itself.
**When done:** [`docs/agentcore-harness/USER_GUIDE.md`](../../../docs/agentcore-harness/USER_GUIDE.md)
must match what was built. Fix the guide in the same PR as the behaviour it describes.

Living checklist. Check a box only when its Definition of done is literally true.
Tasks marked **💲** spend money and need Rick's go-ahead in the session.
Tasks marked **🔑** need AWS credentials on Rick's Mac.

---

## How to execute this plan (Cursor)

One task per session, on branch `feat/agentcore-harness-<task-id>`. Then:

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

- [ ] **0.1 Spike: pin the Harness APIs**
  - From current AWS docs, record in `docs/adr/` (appendix to ADR-001), each with a link and
    the date checked:
    - `CreateHarness` / `UpdateHarness` / `InvokeHarness` request fields, and the boto3 version
      that ships them;
    - the inline-function tool spec (field names, schema format) and the exact
      `toolUse` → `toolResult` round trip, including how several tool calls in one turn are
      returned;
    - whether `allowedTools` removes built-in tool definitions from the prompt, or only blocks
      their use (and the token overhead if it doesn't);
    - whether a Bedrock guardrail can be attached to a harness;
    - session rules: id length (≥ 33), idle timeout, maximum lifetime, how to end a session;
    - stop controls: `maxIterations`, `maxTokens`, `timeoutSeconds` meaning and maximums;
    - truncation options and defaults;
    - the first `hashicorp/aws` release with `aws_bedrockagentcore_harness` and its endpoint
      resource, or the `awscc` fallback;
    - regions and quotas (harnesses per account, sessions per harness).
  - **Definition of done:** every item recorded with a link and date; `pyproject.toml` pins the
    boto3/botocore floor that has `invoke_harness`; `design.md` §3–§4 field names updated to
    match.
  - _Requirements: R2, R4, R6_

## Phase 1: Backend against a fake client ($0)

- [ ] **1.1 Register `agentcore-harness`**
  - Add the name to `BackendName`, the registry, the CLI, `run_smoke_batch.py` and the web
    catalog. `target=local|container` fail before spend with a message pointing at `strands`.
  - **Definition of done:** a unit test shows both refusals; `ai-team run --backend
    agentcore-harness --target cloud` without config fails with "no harness config" before any
    AWS call.
  - _Requirements: R1.1–R1.3_

- [ ] **1.2 `client.py`: `HarnessClient`, `Boto3HarnessClient`, `FakeHarnessClient`**
  - The fake replays `tests/conformance/scripts/thin_slice.yaml` as stream events.
  - **Definition of done:** a unit test drives the fake through one role and gets the scripted
    `toolUse` blocks and `metadata` back; the boto3 client is covered with a stubbed botocore
    response.
  - _Requirements: R2.1, R2.4_

- [ ] **1.3 `tools.py`: inline functions from the tool bridge**
  - **Definition of done:** for each thin-slice role, the generated inline-function list equals
    `bridged_tools_for_role(role)` by name and schema; a `toolUse` for `write_file` produces the
    same audit row and draft as calling `ToolBus.invoke` directly; a tool error comes back as
    observation text.
  - _Requirements: R2.2, R2.3_

- [ ] **1.4 `driver.py`: role turn loop + agents-as-tools**
  - **Definition of done:** with the fake client, the manager calls `developer`, which opens a
    child session with its own id (≥ 33 characters), and the manager receives the summary, not
    the transcript. No request ever ends with a `toolUse` block (asserted in the test).
  - _Requirements: R2.5, R3.1, R3.2_

- [ ] **1.5 `gate.py` + `commit_phase` + acceptance**
  - **Definition of done:** a conformance test shows (a) a refused `commit_phase` blocks the
    phase, (b) a manager that stops early gets at most 2 follow-up turns and the run then ends
    `failed` with `phase_not_committed:<phase>`, (c) accepts come from harness evidence.
  - _Requirements: R3.3, R3.4_

- [ ] **1.6 `usage.py` + `spans.py`**
  - **Definition of done:** a fake turn reporting 1,000 in / 500 out tokens records the priced
    cost for that role; a turn with no `metadata` records `observed_usd: null` plus a warning;
    `TraceBuilder` builds a trace with `agent`, `llm_call`, `tool_use` and `tool_result` spans.
  - _Requirements: R5.1, R5.3_

- [ ] **1.7 Conformance green**
  - **Definition of done:** `uv run pytest tests/conformance -q -k agentcore-harness` passes,
    including the `budget_exceeded` and `timeout` cases, with no network access.
  - _Requirements: R1.4, R4.3_

- [ ] **1.8 `ai-team harness export-tools`**
  - Writes `infra/terraform/aws/envs/dev/harness_tools.json` and `prompts/*.md` from
    `common/roles.py` and the tool bridge.
  - **Definition of done:** running it twice produces identical files; a unit test checks the
    output matches what 1.3 generates.
  - _Requirements: R6.1_

## Phase 2: Terraform (plan free; apply 💲)

- [ ] **2.1 Module `agentcore_harness`**
  - One harness per role, a named endpoint per harness pinned to its version, `allowedTools`
    limited to the role's inline functions, memory off, limits and truncation set.
  - **Definition of done:** validates against the pinned provider; checkov clean or reasoned
    skips; `terraform-docs` README generated.
  - _Requirements: R6.1_

- [ ] **2.2 Module `iam_harness`**
  - Execution role: listed inference profiles and their foundation models, its log group,
    nothing else. Invoker policy: `InvokeHarness` on the four endpoints; explicit deny on
    `InvokeAgentRuntimeCommand`.
  - **Definition of done:** a `terraform test` asserts no `*` actions, profile/model pairing,
    and the explicit deny.
  - _Requirements: R3.5, R6.2, R6.3_

- [ ] **2.3 🔑 `envs/dev` wiring + plan**
  - Behind `enable_agentcore_harness` (default `false`); `harness_config` output.
  - **Definition of done:** `terraform plan -var enable_agentcore_harness=true` succeeds on
    Rick's Mac; the plan summary (resources and IAM statements) is pasted in the task notes and
    reviewed by Rick; with the flag off, the plan is unchanged from before this spec.
  - _Requirements: R6.4, R6.5_

- [ ] **2.4 💲🔑 First apply + teardown drill**
  - **Definition of done:** apply succeeds; `terraform output -json harness_config >
    config/harness.dev.json` works; destroy, then `teardown_check.sh aws` shows 0 billable
    resources. Time each step and record it.
  - _Requirements: R6.6_

## Phase 3: Live runs (💲 ≤ $10)

- [ ] **3.1 💲🔑 Live thin slice**
  - **Definition of done:** `ai-team run --backend agentcore-harness --target cloud
    "<thin slice>"` completes; cost recorded and within ±20% of CloudWatch `AWS/Bedrock` token
    metrics; median latency per inline-function round trip recorded; row added to
    `docs/CLOUD_NATIVE.md`.
  - _Requirements: R7.1, R5.2_

- [ ] **3.2 💲 Traces: two sources**
  - **Definition of done:** the run is visible in CloudWatch; an export of those spans,
    imported with `evals trace import-otel`, agrees with the harness spans within tolerance, or
    the difference is written up in the journal.
  - _Requirements: R5.4_

- [ ] **3.3 💲 Comparison write-up**
  - Same brief, same model: Step 0 rows, `strands` (local), `agentcore-harness`. One extra
    harness run with truncation `none`.
  - **Definition of done:** the comparison table and the "what the managed loop could not do"
    list (R7.3) are merged into `docs/CLOUD_NATIVE.md`.
  - _Requirements: R7.2, R7.3, R4.5_

- [ ] **3.4 Destroy**
  - **Definition of done:** the teardown check shows 0 billable resources.

- [ ] **3.5 User guide matches reality**
  - Walk `docs/agentcore-harness/USER_GUIDE.md` top to bottom on a clean checkout.
  - **Definition of done:** every command in the guide ran as written, or the guide was fixed;
    the "Status" banner at the top of the guide is removed.

## Phase 4: Stretch

- [ ] **4.1 Nine roles on harnesses**
  - **Definition of done:** conformance passes with the full phase plan; one live run finishes.
  - _Requirements: R8.1_
- [ ] **4.2 💲 Join the 30-run batch**
  - **Definition of done:** finish rate with a Wilson interval published next to the others.
  - _Requirements: R8.2_
- [ ] **4.3 Export-to-code diff**
  - **Definition of done:** `agentcore export harness` output for the manager is saved under
    `docs/agentcore-harness/export/`, with a one-page comparison to `strands_backend`.
  - _Requirements: R8.3_
