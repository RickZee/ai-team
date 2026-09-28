# Tasks: Cloud Backend Foundation

**Spec ID:** `cloud-backend-foundation`
**Read first:** [`requirements.md`](./requirements.md), then [`design.md`](./design.md).

Living checklist. Check a box only when its Definition of done is literally true.
**Every task here is $0.** No task needs a cloud account.

---

## How to execute this plan (Cursor)

One task per session, on a branch named `feat/cloud-foundation-<task-id>`. Then:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ evals/
uv run pytest tests/unit tests/conformance tests/integration/evals -q
```

Rules for every task:
- Don't edit the harness (`tools/bus.py`, `tools/draft.py`, `core/spend_guard.py`,
  `guardrails/`) to make a backend pass. If the harness really is wrong, stop and write it
  up in the task's notes.
- Respect the repo ratchets: functions over 150 lines get extracted, never raised.
- Never commit secrets or `.tfvars`. Never run `terraform apply`.
- End each task with a short entry in `docs/journal/` in the repo's journal voice.

**Order:** Phase 0 → 1 → 2 → 3 are blocking for both cloud specs. Phases 4–6 can run in
parallel with the cloud specs' Phase 0.

---

## Phase 0: The decision and the contract

- [ ] **0.1 ADR: cloud-native backends**
  - Write `docs/adr/ADR-00N-cloud-native-backends.md`. Cover:
    - why Strands + AgentCore and Agent Framework + Foundry, rather than models-only;
    - the execution-target model: local, container, cloud;
    - why Terraform, superseding the archived CDK plan;
    - a table of which harness pieces each cloud's native service could replace (memory,
      guardrails, tracing, identity) and what this project decides for each.
  - **Definition of done:** the ADR is merged and linked from `docs/ARCHITECTURE.md`.
  - _Requirements: R1, R7_

- [ ] **0.2 Thin-slice script and fake-model contract**
  - Add `tests/conformance/scripts/thin_slice.yaml` and `fake_models.py`, as in design §2.
  - **Definition of done:** a unit test loads the script and replays it against a
    framework-free stub that calls `ToolBus.invoke` directly; the stub produces `calc.py`
    and a passing test in a temp workspace.
  - _Requirements: R1.1_

- [ ] **0.3 Conformance suite over the three existing backends**
  - Implement `tests/conformance/test_*.py` (design §2) parametrized over `crewai`,
    `langgraph`, `claude-agent-sdk`.
  - **Definition of done:** the suite runs in under 3 minutes offline. Every failure is
    either fixed or listed in `tests/conformance/KNOWN_GAPS.md` with an owner task in
    this spec. Nothing is skipped silently.
  - _Requirements: R1.2, R1.3_

- [ ] **0.4 Close the gaps 0.3 found**
  - One commit per gap, each with a test.
  - **Definition of done:** `KNOWN_GAPS.md` is empty, and the suite is green for all three.
  - _Requirements: R1.3_

- [ ] **0.5 Conformance in CI**
  - Add a `conformance` job to `.github/workflows/ci.yml`.
  - **Definition of done:** the job is required on PRs and green on `main`.
  - _Requirements: R1.4_

## Phase 1: Harness-owned acceptance (the QA-acceptance fix)

- [ ] **1.1 `backends/common/acceptance.py`**
  - Build `evaluate(criteria, evidence) -> list[AcceptanceResult]`, as in design §4.
  - **Definition of done:** unit tests cover the passing, failing and unverified cases, and
    that a criterion with no evidence is never passing.
  - _Requirements: R3.1_

- [ ] **1.2 Wire it after the testing phase in all three backends**
  - **Definition of done:** the conformance suite asserts accepts are recorded on the thin
    slice for all three backends.
  - _Requirements: R3.1, R3.3_

- [ ] **1.3 `qa_disagreement` spans**
  - **Definition of done:** a fixture run where QA rejects a criterion that has passing
    evidence yields exactly one `qa_disagreement` span, and `TraceBuilder` exposes it.
  - _Requirements: R3.2_

- [ ] **1.4 Regression test from the September finding**
  - **Definition of done:** a test replays a September LangGraph trace pattern (passing
    tests, QA with no accept tool) and asserts at least one accept. It fails on the old code.
  - _Requirements: R3.4_

## Phase 2: Tool bridge and shared roles

- [ ] **2.1 `backends/common/tool_bridge.py`**
  - **Definition of done:** `bridged_tools_for_role(r)` returns, for every role in
    `agents.yaml`, the same tool names that role has today. A test compares against the
    existing mapping.
  - _Requirements: R2.1, R2.4_

- [ ] **2.2 `backends/common/roles.py`**
  - Load role goals, backstories and prompts from the existing config, so the new backends
    don't copy prompts.
  - **Definition of done:** a unit test shows the new loader and the LangGraph backend
    produce identical system prompts for all nine roles.
  - _Requirements: R2.4_

## Phase 3: Execution targets, registry and CLI

- [ ] **3.1 `ExecutionTarget` and the thin-client base**
  - Add `backends/common/targets.py` with `RemoteRunClient`, an abstract class with
    `start`, `status` and `fetch_artifacts` (design §5).
  - **Definition of done:** a fake remote client passes the conformance suite as its own
    parametrized case, `fake-remote`.
  - _Requirements: R6.2_

- [ ] **3.2 Register `strands` and `agent-framework` as stubs**
  - Update `BackendName`, `registry.py`, the CLI, `run_smoke_batch.py` and the web catalog.
    Each stub raises a clear "not implemented yet: see .kiro/specs/<spec>" error.
  - **Definition of done:** `--backend strands --target cloud` fails before any spend,
    naming the spec. Tests cover both names and an unsupported target.
  - _Requirements: R6_

## Phase 4: Local runtime

- [ ] **4.1 Spike: pin images and the local model**
  - Pin the OTel Collector and Aspire dashboard image tags.
  - Choose and pin the Ollama model: tool-calling capable, and able to run on a 16 GB+
    Apple Silicon Mac.
  - **Definition of done:** the versions are recorded in `docker/VERSIONS.md` with the date
    checked, and `ollama run <model>` answers a tool-call prompt on the Mac.
  - _Requirements: R4.2_

- [ ] **4.2 Compose profiles `observability`, `strands`, `agent-framework`**
  - Add `docker/otel-collector.yaml` (design §6). The backend services start as stubs that
    print "ready".
  - **Definition of done:** `docker compose --profile observability up` shows the Aspire
    dashboard at `localhost:18888`, and a test span sent with `otel-cli` or a Python
    snippet appears in the dashboard and in `output/otel/traces.jsonl`.
  - _Requirements: R4.1_

- [ ] **4.3 `local-smoke` command**
  - **Definition of done:** `make local-smoke BACKEND=langgraph` runs the thin slice against
    Ollama and prints pass/fail per step. It's recorded as `model_tier: local`, and the
    documented total is $0.
  - _Requirements: R4.3, R4.4_

## Phase 5: OTel ingest

- [ ] **5.1 `evals trace import-otel`**
  - Implement `evals/trace/otel_import.py` with the mapping table (design §7).
  - **Definition of done:** it imports a hand-written OTLP fixture with known kind counts.
    Unknown spans are counted as `other`.
  - _Requirements: R5.1, R5.2_

- [ ] **5.2 Two-reader rule**
  - **Definition of done:** when harness spans and OTel spans both exist for a run, the
    builder uses the harness spans and records the OTel count as a second reader. A test
    covers a deliberate mismatch.
  - _Requirements: R5.3_

## Phase 6: Terraform conventions and CI

- [ ] **6.1 `infra/` skeleton, both clouds**
  - Create the layout in design §8, with empty modules that have `versions.tf` pinned,
    tags wired and `README.md` generated by `terraform-docs`.
  - **Definition of done:** `terraform init -backend=false && terraform validate` passes
    in both `envs/dev`.
  - _Requirements: R7.1, R7.2, R7.5_

- [ ] **6.2 Budget modules**
  - AWS: `aws_budgets_budget`. Azure: `azurerm_consumption_budget_resource_group`.
    Alerts at 50% and 100% of `monthly_budget_usd`, default 25.
  - **Definition of done:** both validate, and `terraform plan` in each env lists the
    budget. Rick runs `plan` once with credentials and pastes the summary into the task notes.
  - _Requirements: R7.3_

- [ ] **6.3 `infra.yml` workflow**
  - fmt, validate, tflint (with the aws and azurerm rulesets) and checkov, all without
    credentials.
  - **Definition of done:** green on the PR, with every checkov skip carrying a reason.
  - _Requirements: R7.6_

- [ ] **6.4 `teardown_check.sh`**
  - List resources tagged `project=ai-team` in each cloud (AWS Resource Groups Tagging
    API; Azure `az resource list --tag`).
  - **Definition of done:** with nothing deployed, the script prints "0 billable resources"
    for both clouds.
  - _Requirements: R7.7_

## Phase 7: Surfaces

- [ ] **7.1 `docs/CLOUD_NATIVE.md`**
  - Status table per R8, with every cell `not yet` at the start. Link it from the README.
  - **Definition of done:** a repo test fails if any cell is blank or if the README claims
    a cell that isn't `green`.
  - _Requirements: R8_
