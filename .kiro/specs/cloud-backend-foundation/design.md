# Design: Cloud Backend Foundation

**Spec ID:** `cloud-backend-foundation` · **Read first:** [`requirements.md`](./requirements.md)

---

## 1. Shape of the change

```
                         ai_team.core.backend.Backend  (unchanged protocol)
                                        │
     ┌──────────────┬──────────────┬────┴─────────┬──────────────────┬───────────────────┐
     │ crewai       │ langgraph    │ claude-sdk   │ strands   (new)  │ agent-framework   │
     │              │              │              │ AWS              │ (new) Azure       │
     └──────┬───────┴──────┬───────┴──────┬───────┴────────┬─────────┴─────────┬─────────┘
            └──────────────┴──────────────┴────────────────┴───────────────────┘
                                        │
             backends/common/  ── tool_bridge · roles · acceptance · targets
                                        │
     harness (unchanged): ToolBus · drafts · spend_guard · guardrails · quality gate
                          · smoke gate · results bundle · telemetry
                                        │
                   evals/: TraceBuilder ← harness spans  +  import-otel ← OTLP JSON
```

The harness is not modified to suit the new backends. They adapt to it, which is exactly
what the conformance suite checks.

## 2. Conformance suite (R1)

```
tests/conformance/
  conftest.py              # backend_name parametrization from registry; fake-model fixtures
  fake_models.py           # scripted model: plan → write file → run tests → QA verdict
  test_tool_routing.py     # R1.2.1
  test_draft_commit.py     # R1.2.2
  test_spend.py            # R1.2.3
  test_results_bundle.py   # R1.2.4
  test_trace.py            # R1.2.5
  test_limits.py           # R1.2.6 budget + timeout
```

**Fake model per framework.** Each backend accepts an injected model client. That's a
`FakeChatModel` for LangGraph, a LiteLLM mock for CrewAI, a scripted transport for the
Claude SDK, and a custom `Model` for Strands and a custom chat client for Agent Framework.
All of them replay the same script, `tests/conformance/scripts/thin_slice.yaml`, so every
backend is asked to do the same four things. The script is data, so adding a backend never
edits the script.

**Thin-slice task.** "Create `calc.py` with `add(a, b)` and a pytest test." It's small
enough to be deterministic under a fake model, but it exercises write → draft → commit →
pytest → QA → acceptance.

## 3. Tool bridge (R2)

```python
# backends/common/tool_bridge.py
@dataclass(frozen=True)
class BridgedTool:
    name: str
    description: str
    json_schema: dict[str, Any]      # from ToolSpec.args_model.model_json_schema()
    call: Callable[[dict[str, Any]], str]   # ToolBus.invoke → observation_to_agent_text

def bridged_tools_for_role(role: str) -> list[BridgedTool]: ...
```

Framework adapters sit next to each backend, not in `common/`:

- `strands_backend/tools.py`: `BridgedTool` → a Strands tool spec. The tool decorator can't
  build from a runtime schema, so this uses the module-level tool spec form. Verify the
  exact API in the AWS spike task.
- `agent_framework_backend/tools.py`: `BridgedTool` → an Agent Framework function tool with
  an explicit JSON schema.

Exceptions from `ToolBus.invoke` are never raised into the framework. The bridge returns
the observation text, including errors, so every framework sees the same error wording.

## 4. Harness-owned acceptance (R3)

```
quality gate (pytest, ruff, smoke)  ──►  acceptance.evaluate(criteria, evidence)
                                              │
                         ┌────────────────────┼─────────────────────┐
                    passing              failing                unverified
                                              │
                  QA verdicts (if any) ──► compare ──► qa_disagreement spans
```

Criteria are matched to evidence by the product owner's criterion id. A criterion with no
evidence stays `unverified`, never `passing`, so the gate can't be satisfied by silence.
This lives in `backends/common/acceptance.py` and is called from the same place
`commit_pending_drafts` is called after the testing phase, once per backend.

## 5. Execution targets (R4, R6)

```python
class ExecutionTarget(StrEnum):
    LOCAL = "local"         # in-process, this Python
    CONTAINER = "container" # local Docker, same image as cloud
    CLOUD = "cloud"         # AgentCore Runtime / Azure Container Apps Job
```

For `container` and `cloud`, the backend's `run()` is a **thin client**. It starts the
remote run with the description and team profile, polls status, then downloads the
workspace and results bundle into `output/runs/<id>/`. Inside the container, the same
backend runs with `target=local`, so there is only one implementation of the pipeline.

**Why the container image is the unit:** AgentCore Runtime and Azure Container Apps both
run containers. If the local `container` target passes the smoke task, the cloud target
differs only in identity, model endpoint and observability sink, which are exactly the
parts the cloud specs test.

## 6. Local runtime (R4)

```yaml
# docker/docker-compose.yml (added profiles)
services:
  otel-collector:        # profiles: [observability]
    image: otel/opentelemetry-collector-contrib:<pinned>
    volumes: [./otel-collector.yaml:/etc/otelcol/config.yaml, ../output/otel:/otel]
    # receivers: otlp (4317/4318) · exporters: otlp→aspire, file→/otel/traces.jsonl
  aspire-dashboard:      # profiles: [observability]
    image: mcr.microsoft.com/dotnet/aspire-dashboard:<pinned>
    ports: ["18888:18888"]
  strands:               # profiles: [strands]
    build: {context: .., dockerfile: docker/strands.Dockerfile, platforms: [linux/arm64]}
    environment: [OLLAMA_HOST=http://host.docker.internal:11434, OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318]
  agent-framework:       # profiles: [agent-framework]
    build: {context: .., dockerfile: docker/agent-framework.Dockerfile}
    environment: [OPENAI_BASE_URL=http://host.docker.internal:11434/v1, OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318]
```

Images are pinned by tag in the spike task, never `latest`. The backend images include
the Python toolchain that the quality and smoke gates need (pytest, ruff), because the
agents' generated code is tested inside the container.

## 7. OTel ingest (R5)

```python
# evals/trace/otel_import.py
SPAN_KIND_MAP = {
    # (gen_ai.operation.name | span name pattern) → ai-team kind
    "chat": "llm", "text_completion": "llm",
    "execute_tool": "tool_use",       # result folded into tool_result from the span's end event
    "invoke_agent": "agent",
}
```

Fixtures are one captured OTLP file per framework, under
`evals/fixtures/otel/{strands,agent_framework}.jsonl` and stripped of content. Tests assert
kind counts. Unknown span names are kept as `other` and counted, never dropped silently.

## 8. Terraform conventions (R7)

```
infra/
  terraform/
    aws/
      modules/{ecr_repo, agentcore_runtime, iam_runtime_role, bedrock_guardrail,
               observability, budget, artifacts_bucket}
      envs/dev/{main.tf, variables.tf, outputs.tf, versions.tf, terraform.tfvars.example}
    azure/
      modules/{foundry, model_deployment, container_apps_job, identity_rbac,
               observability, key_vault, budget, artifacts_storage}
      envs/dev/{...same...}
  scripts/
    push_image_aws.sh      # docker buildx --platform linux/arm64 → ECR
    push_image_azure.sh    # docker buildx → ACR
    teardown_check.sh      # lists billable resources left by tag
.github/workflows/infra.yml  # fmt, validate (-backend=false), tflint, checkov — no creds
```

**Why Terraform and not CDK:** one tool across both clouds, which is what an AI platform
team in a multi-cloud financial company runs. This supersedes the archived CDK-based
AgentCore plan.

**Apply policy:** Cursor may run `fmt`, `validate`, `plan`. `apply` and `destroy` are run
by Rick, or by Cursor only with Rick's explicit go-ahead in that session.

## 9. What is deliberately not here

- No shared "cloud abstraction layer" over AWS and Azure. Each cloud spec uses its native
  services directly. Hiding them behind an interface would defeat the purpose.
- No production multi-tenant hosting, auth front door or UI changes. The web UI gets the
  two backend names and nothing else.
