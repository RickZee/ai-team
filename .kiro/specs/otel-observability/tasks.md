# Tasks: One OTel Shape for Every Backend

**Spec ID:** `otel-observability`
**Read first:** [`requirements.md`](./requirements.md), then [`design.md`](./design.md).
**Blocked on:** `cloud-backend-foundation` 4.2 for Phase 2; `eval-methodology-alignment` 1.7
for Phase 4. Phases 0, 1 and 3.1 work on runs already on disk.
**When done:** [`docs/observability/README.md`](../../../docs/observability/README.md) matches
what was built.

Living checklist. Check a box only when its Definition of done is literally true. Everything
here is $0.

---

## How to execute this plan (Cursor)

One task per session, on branch `feat/otel-<task-id>`. Then:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src/ evals/
uv run pytest tests/unit tests/conformance -q
# Docker tasks (2.1, 2.3) also:
AI_TEAM_DOCKER_TESTS=1 make test-otel-integration
```

---

## Phase 0: Look before building

- [x] **0.1 Payload census**
  - For one recent run per backend: span types and payload keys, the pairing keys in design
    §3.2, and whether per-call token rows exist. Record the table in design §6.
  - **Definition of done:** the table is in the design, with a "missing for R1" column and a
    confirmed (or "not available") pairing key for each merge rule.
  - _Requirements: R1, R3_

- [x] **0.2 Pin versions and check Phoenix**
  - Pin the GenAI convention version (`schemaUrl`), the OpenInference version and the Phoenix
    image. Confirm Phoenix's OTLP/HTTP path, its storage setting, its query API for tests,
    whether it reads `gen_ai.*`, and what it does with a re-sent span id. Re-check the licence
    of each image (design §0.2) and note it.
  - **Definition of done:** recorded in `docker/VERSIONS.md` with links and the date checked;
    design §7 and §10 updated if anything differs.
  - _Requirements: R1.4, R5.1_
  - **Progress 2026-10-18:** versions, licence, OTLP path, storage setting, query API and
    `gen_ai.*` handling recorded in `docker/VERSIONS.md`. Pulled on Rick's Mac the same day
    (digest in `VERSIONS.md`); a re-sent run kept 19 spans, so Phoenix doesn't duplicate.
    Design §7 and §10 updated.

## Phase 1: Shape, export, re-import

- [x] **1.1 `evals/trace/otel_export.py`**
  - The mapping, merge rules, parents, both naming schemes, content gating, ids and
    `schemaUrl` (design §3–§5).
  - **Definition of done:** `tests/unit/evals/test_otel_export.py` covers each row in design §9.
    Traces are built in code (`tests/unit/evals/otel_helpers.py`); see design §9 on fixtures.
  - _Requirements: R1, R2.3, R7.1_

- [x] **1.2 Lossless re-import in `otel_import.py`**
  - **Definition of done:** `tests/unit/evals/test_otel_import_roundtrip.py` passes, including
    the property test; the existing `test_otel_import.py` still passes unchanged (framework
    spans keep their mapping).
  - _Requirements: R3, R7.1_

- [x] **1.3 `python -m evals.cli trace export-otel <run-dir>`**
  - The file, resource attributes, batching, `--endpoint`, `--if-changed`, `--all` and
    `logs/otel.export.json`.
  - **Definition of done:** `tests/unit/evals/test_otel_export_cli.py` covers each row in
    design §9.
  - _Requirements: R2, R7.1_

- [x] **1.4 Conformance round trip for every backend**
  - `tests/conformance/test_otel_roundtrip.py`, parametrized over the registry like the rest of
    the suite.
  - **Definition of done:** passes for every registered backend at $0; a backend added later is
    covered without editing the test.
  - _Requirements: R3.3, R7.3_

## Phase 2: Local viewing

- [x] **2.1 Phoenix, collector, localhost ports, make targets**
  - Compose and collector per design §7; `make otel-up`, `otel-down`, `otel-backfill`,
    `test-otel-integration`.
  - **Definition of done:** `tests/unit/repo/test_otel_stack_config.py` passes; `make otel-up`
    shows Aspire on 18888 and Phoenix on 6006, reachable on `127.0.0.1` only; a test span sent to
    4318 appears in both and in `output/otel/traces.jsonl`; Phoenix still has it after a restart.
  - _Requirements: R5.1, R5.2, R5.3, R7.2_
  - **Progress 2026-10-18:** compose, collector config, make targets and the repo test are
    done and green. Then on Rick's Mac: 4317, 4318, 6006, 13133, 18888 listen on 127.0.0.1
    only; a real 19-span run reached `output/otel/traces.jsonl`, Phoenix and Aspire, and
    Phoenix kept it across a restart. Three fixes on the way: Aspire got 500 on gzip OTLP/HTTP
    and every span was dropped (`compression: none`); Aspire's UI asked for a token (frontend
    auth off, like Phoenix); `otel-up` also started the unprofiled `app`, which crash-looped
    (targets now name the three services).

- [x] **2.2 Tag native spans**
  - `OTEL_RESOURCE_ATTRIBUTES` on the `strands` and `agent-framework` services; the
    `otel_tags.py` helper; a line added to each of those backend specs' tasks to call it and to
    name their framework copy `logs/otel.framework.json`.
  - **Definition of done:** compose change merged; `tests/unit/harness/test_otel_tags.py`
    passes; both backend specs carry the added line.
  - _Requirements: R4_

- [x] **2.3 Integration tests**
  - `tests/integration/test_otel_local_stack.py` per design §9.
  - **Definition of done:** passes with Docker and `AI_TEAM_DOCKER_TESTS=1`; skips with a reason
    otherwise, including in the existing CI `pytest tests/integration` step; leaves no containers
    running; never writes to the real `output/`.
  - _Requirements: R7.4, R7.5_
  - **Progress 2026-10-18:** the test file is written and skips with a reason without Docker
    (checked). Green on Rick's Mac with `make test-otel-integration` (2 passed, 33 s), no
    containers left. It now starts only the three services (was 216 s building `app`) and
    fails if the collector logs a dropped export; checked by putting gzip back (it failed).

- [ ] **2.4 Smoke: every available backend in one view**
  - Run the cheapest real run per available backend, then `make otel-backfill`.
  - **Definition of done:** Phoenix shows one run per backend in the `ai-team` project,
    filterable by `ai_team.backend` and `ai_team.run_id`; screenshot saved as
    `docs/images/observability-phoenix.png`.
  - _Requirements: R5.4_

## Phase 3: The guide

- [ ] **3.1 Local section checked**
  - **Definition of done:** every command in the Local section ran as written; every diagram in
    the guide is a Mermaid block; the section's "not yet checked" note is removed.
  - _Requirements: R6_

- [ ] **3.2 AWS section checked** *(when `aws-strands-agentcore` 4.2 has a cloud run)*
  - **Definition of done:** a real AgentCore run was found in CloudWatch and brought back into
    Phoenix by following the guide; the note is removed.
  - _Requirements: R6.1, R6.3_

- [ ] **3.3 Azure section checked** *(when `azure-agent-framework` has a cloud run)*
  - **Definition of done:** the same for Application Insights; the "later" note is removed.
  - _Requirements: R6.1, R6.3_

## Phase 4 (optional): auto-export at run end

- [ ] **4.1 `otel_hook.request_otel_export` at the end of `ResultsBundle.finalize()`**
  *(blocked on `eval-methodology-alignment` 1.7)*
  - Per design §8, with `OtelExportSettings`.
  - **Definition of done:** `tests/unit/harness/test_otel_auto_export.py` passes; with the flag
    on and the stack up, a thin-slice run's spans appear in Phoenix within 10 s; with the stack
    down, the run ends normally and `otel.export.json` says `written_only`.
  - _Requirements: R8_
