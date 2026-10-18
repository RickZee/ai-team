# Requirements: AWS Managed-Loop Backend (Amazon Bedrock AgentCore Harness)

**Spec ID:** `aws-agentcore-harness`
**Status:** Draft
**Owner:** Rick Zakharov
**Created:** 2026-10-18
**Budget:** Phases 0–1 **$0.00** (fake client, offline). Phase 2 plan free, apply **≤ $2**.
Phase 3 **≤ $10** (live runs, tracing, teardown). Every spending task is human-triggered.
**Depends on:** [`../cloud-backend-foundation/`](../cloud-backend-foundation/) Phases 0–3, and
from [`../aws-strands-agentcore/`](../aws-strands-agentcore/): tasks 0.1 (provider pin, model
ids), 0.2 (AWS account prep), 2.0 (Step 0 Bedrock baseline) and the Terraform modules from
3.1–3.3 (`artifacts_bucket`, `observability`, `budget`, IAM patterns). It does **not** depend on
the Strands backend itself (Phases 1–4 of that spec).
**Executed by:** Cursor, one task per session. `terraform apply/destroy` only with Rick's go-ahead.
**User guide (written ahead, true once this spec is done):** [`docs/agentcore-harness/USER_GUIDE.md`](../../../docs/agentcore-harness/USER_GUIDE.md)

---

## Introduction

This spec adds `agentcore-harness`, a sixth backend in which **AWS runs the agent loop and
ai-team runs the tools**.

The AgentCore Harness (GA June 2026) is a managed agent loop. An agent is declared as
configuration: model, system prompt, tools, limits. AWS runs the loop (Strands under the hood)
in a per-session microVM. There is no orchestration code to write or host.

The question this backend answers: **how close does a configuration-only AWS agent get to a
hand-built one, on the same tasks, with the same tools, the same model and the same harness?**
It sits next to the `strands` backend (same framework, our code) and the Step 0 Bedrock rows
(same model, other frameworks), so the comparison changes one thing at a time.

| Layer | Mechanism | Who owns it |
| --- | --- | --- |
| Agent loop (plan, pick tool, read result, repeat) | **AgentCore Harness** | AWS |
| Model | **Amazon Bedrock**, the same `us.` inference profiles as Step 0 and `strands` | AWS |
| Tools | **Inline functions**: the loop pauses, returns the tool call to our client, our client runs it through `ToolBus.invoke` and sends the result back | ai-team |
| Workspace, drafts, commits, guardrails, spend guard, acceptance | Unchanged harness, running where the client runs | ai-team |
| Phase gate | Client-side: a run cannot advance or finish until `commit_phase` succeeds | ai-team |
| Observability | Harness stream events → ai-team spans (primary); AgentCore → CloudWatch (AWS view) | both |
| Infrastructure | **Terraform** `aws_bedrockagentcore_harness` (or `AWS::BedrockAgentCore::Harness` via `awscc` if needed) | ai-team |

**Why inline functions, not a hosted MCP server:** inline functions are the Harness's
client-side tool type. The loop stops at each tool call and hands control back, so ToolBus,
draft-then-commit and the audit log stay in our process, exactly as for every other backend.
A remote MCP server would mean hosting ToolBus as a network service and moving the workspace
off the caller. That is kept as a documented alternative (design §9), not built.

**Principle:** the same thin slice, the same model ids, the same harness. Only the owner of the
agent loop changes.

```
Phase 0  spike and pin APIs                                   ($0)
Phase 1  backend against a fake Harness client, conformance   ($0)
Phase 2  Terraform: four harnesses, IAM, endpoints            (plan $0, apply ≤ $2)
Phase 3  live thin slice, traces, comparison write-up         (≤ $10)
Phase 4  stretch: nine roles, 30-run batch, export-to-code diff
```

---

## R1: Backend and registration

1. THE SYSTEM SHALL provide `src/ai_team/backends/agentcore_harness_backend/`, implementing
   `Backend` with `name = "agentcore-harness"`.
2. `BackendName` (`evals/trace/models.py`), `backends/registry.py`, the CLI `--backend` flag,
   `scripts/run_smoke_batch.py` and the web catalog SHALL accept `agentcore-harness`.
3. The backend SHALL support `--target cloud` only. `local` and `container` SHALL fail before
   any spend, with a message naming the supported target and pointing at the `strands`
   backend for local runs.
4. The backend SHALL pass the foundation conformance suite using a fake Harness client
   (R2.4), offline, at $0.

## R2: Harness client and inline-function tools

1. All calls to AWS SHALL go through one `HarnessClient` protocol (`invoke(harness, session_id,
   messages) → event stream`), so the real boto3 client and the fake are interchangeable.
2. Each role's tools SHALL come from the foundation tool bridge (`bridged_tools_for_role`) and be
   declared to the Harness as **inline functions**, using each `BridgedTool.json_schema` as is.
3. WHEN the stream returns a `toolUse` block for an inline function, THE CLIENT SHALL run it
   through `BridgedTool.call` (that is, `ToolBus.invoke`) and send the observation text back as
   the matching `toolResult` on the same `runtimeSessionId`. Tool errors are returned as
   observation text, never raised.
4. THE SYSTEM SHALL provide `FakeHarnessClient`, which replays the conformance script
   (`tests/conformance/scripts/thin_slice.yaml`) as Harness stream events (`toolUse`,
   `metadata`, `messageStop`), so the backend is tested without AWS.
5. Session ids SHALL be at least 33 characters (a Harness rule), derived from the run id and the
   role, and stable for the life of that role's session.

## R3: Orchestration: agents as tools, across harnesses

1. The thin slice SHALL use **four harnesses**: `manager`, `architect`, `developer`, `qa`. Each
   has its own system prompt (from `common/roles.py`) and its own role-scoped inline functions.
2. The manager's tools SHALL be `architect(brief)`, `developer(brief)`, `qa(brief)` and
   `commit_phase(phase)`. Calling a specialist opens (or continues) that specialist's own
   Harness session, runs it to completion through the client, and returns a summary, never the
   raw transcript.
3. `commit_phase` SHALL run the phase guardrails and `commit_pending_drafts`, exactly as in the
   other backends. The client SHALL refuse to let a run finish with uncommitted phases: if the
   manager stops early, the client sends one follow-up turn naming the missing phase, at most
   `max_gate_retries` times (default 2), then ends the run as `failed` with the reason recorded.
4. Acceptance SHALL come from `acceptance.evaluate` on harness evidence, as for every backend.
   The QA harness's verdicts are the second signal.
5. Every built-in Harness tool (`shell`, `file_operations`, code interpreter, browser) SHALL be
   excluded through `allowedTools`, so no file is written except through ToolBus. The invoker's
   IAM SHALL deny `bedrock-agentcore:InvokeAgentRuntimeCommand`.

## R4: Models, guardrails, limits

1. The harnesses SHALL use the same `us.` inference-profile ids as `strands` and Step 0
   (manager on the Sonnet-class model, specialists on the cheaper one), set in Terraform and
   overridable per run only for experiments, with the override recorded in the results bundle.
2. IF the Harness accepts a Bedrock guardrail, THEN the guardrail from the shared
   `bedrock_guardrail` module SHALL be attached. If it does not, the gap SHALL be recorded in
   `docs/CLOUD_NATIVE.md` and ai-team's own guardrails remain the only check.
3. Each harness SHALL set `maxIterations`, `maxTokens` and `timeoutSeconds`. The client's spend
   guard and wall-clock limit remain the authority: `budget_exceeded` and `timeout` end the run
   with a closed run record, as the conformance suite requires.
4. Harness memory SHALL be disabled. Runs stay independent; ai-team's lessons store is injected
   at run start through the system prompt, as for the other backends.
5. Truncation SHALL be set explicitly (`sliding_window` unless the spike shows a reason not to)
   and recorded in the results bundle, because it changes what the model sees.

## R5: Spend and telemetry

1. Token usage from each `metadata` event SHALL be priced and recorded through the spend guard,
   per role. Missing usage is recorded as `observed_usd: null` with a warning, never as $0.
2. Any fixed per-request token overhead from built-in tool definitions that cannot be removed
   SHALL be measured in the spike and stated in `docs/CLOUD_NATIVE.md`.
3. THE CLIENT SHALL turn stream events into harness spans: `llm_call` per model turn (with
   tokens), `tool_use` / `tool_result` per inline function, `agent` per role session. These are
   the primary record.
4. AgentCore's own traces in CloudWatch are the second view. `evals trace import-otel` on an
   export of them SHALL agree with the harness spans within the two-source tolerance, or the
   difference is written up.

## R6: Infrastructure as code

1. `infra/terraform/aws/modules/agentcore_harness/` SHALL create one harness per role with:
   model id, system prompt, inline-function tool list, `allowedTools` limited to those inline
   functions, memory off, limits, truncation, and a **named endpoint** pinned to the version
   (never the auto-advancing `DEFAULT` endpoint).
2. A harness execution role SHALL allow only: invoking the listed inference profiles and their
   foundation models, and writing its log group. No S3, no Memory, no Gateway.
3. An invoker policy for the operator SHALL allow `InvokeHarness` on the four endpoints only, and
   explicitly deny `InvokeAgentRuntimeCommand`.
4. `envs/dev` SHALL wire the module behind `enable_agentcore_harness` (default `false`), reusing
   the shared `observability` and `budget` modules.
5. Terraform outputs SHALL include a `harness_config` JSON (region, endpoint ARNs per role, model
   ids, version) that the backend reads, so no ARN is typed by hand.
6. `terraform destroy` followed by `teardown_check.sh aws` SHALL report 0 billable resources.

## R7: Live runs and comparison

1. A live thin slice SHALL pass on `agentcore-harness`, with cost recorded against the CloudWatch
   `AWS/Bedrock` token metrics (±20%), and a row added to `docs/CLOUD_NATIVE.md`.
2. `docs/CLOUD_NATIVE.md` SHALL compare, on the same brief and model: Step 0 (`claude-agent-sdk`,
   `langgraph` on Bedrock), `strands` (local), and `agentcore-harness`. For each: finish,
   accepted criteria, tool calls, tokens, cost and wall-clock time.
3. The write-up SHALL say what the managed loop could not do that the hand-built backends do,
   with one concrete example each (for instance: phase order, retries, context control).

## R8: Stretch

1. The full nine-role pipeline on harnesses (one per role).
2. Joining the 30-run batch, with finish rate and a Wilson interval.
3. `agentcore export harness` on the manager, and a short diff against the hand-written
   `strands_backend`: what AWS generates versus what we wrote.

## Non-goals

- Hosting ToolBus as a network service (remote MCP server or Gateway target). Documented in
  design §9 as the alternative if tools ever need to run without the caller.
- A web front door or end-user auth (JWT inbound). The CLI with SigV4 is the only client.
- VPC network mode. Same reason as the Strands spec: the endpoints cost more than the budget.
- Replacing the `strands` backend. This is a comparison arm; both stay.
