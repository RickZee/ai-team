# Requirements: One OTel Shape for Every Backend, Viewable Locally

**Spec ID:** `otel-observability`
**Status:** In progress — Phase 1 and tagging done; Docker checks, smoke and guide open
**Owner:** Rick Zakharov
**Created:** 2026-10-18
**Revised:** 2026-10-18, after a review against the source: lossless round trip, both naming
schemes, content gating for tool data, correct CLI, localhost-only ports, auto-export moved to
an optional Phase 4.
**Budget:** **$0.00.** Everything runs offline or against the local Docker stack. Checking the
AWS and Azure sections of the guide happens inside those backends' specs and budgets.
**Depends on:** [`../eval-harness/`](../eval-harness/) (Trace model),
[`../cloud-backend-foundation/`](../cloud-backend-foundation/) (5.1 `import-otel`, done; 4.2
compose profiles, open), [`../eval-methodology-alignment/`](../eval-methodology-alignment/)
(R1.6 per-call token rows; 1.7 every run path finalizes, for Phase 4 only).
**Executed by:** Cursor, one task per session.
**Guide (written ahead, true once this spec is done):** [`docs/observability/README.md`](../../../docs/observability/README.md)

---

## Introduction

Only `strands` and `agent-framework` are meant to emit OpenTelemetry, each in its own shape.
LangGraph, CrewAI and the Claude Agent SDK emit none. So five backends can't be looked at side
by side, and instrumenting each framework would compare instrumentation libraries, not backends.

ai-team already records every backend the same way: the harness writes the ToolBus audit,
phases, spend and QA verdicts, and `TraceBuilder` turns them into one `Trace`. This spec
**exports that trace as OpenTelemetry**, reads it back without loss, and adds a local viewer
that keeps history.

Decisions carried over, not reopened:

1. **No OTel SDK in `src/`** (2026-09-13). The export writes OTLP JSON itself.
   `tests/unit/repo/test_import_direction.py::test_src_does_not_import_evals` keeps `src/` from
   importing `evals/` (added with this spec).
2. **OpenInference-shaped telemetry** (2026-09-13). This spec writes OpenInference names and
   the OTel GenAI names on every span: Phoenix reads the first, Aspire and the cloud consoles
   the second.
3. **The harness record is primary.** Framework spans are a second source, never used to score.
4. **No external tool in the eval critical path.** Viewers are for looking; `evals/` scores.

## Who owns what

| Piece | Owned by |
| --- | --- |
| Per-call token and dollar rows in `costs.jsonl` (the source of `llm_call` spans) | `eval-methodology-alignment` R1.6 |
| Every run path (CLI included) ends with `ResultsBundle.finalize()` | `eval-methodology-alignment` 1.7 |
| `import-otel` for framework spans | `cloud-backend-foundation` 5.1 (done); this spec extends it for its own exports (R3) |
| Base compose profiles | `cloud-backend-foundation` 4.2 |
| **Span shape, `export-otel`, lossless re-import, Phoenix, tagging, the guide, tests** | **this spec** |
| CloudWatch, Transaction Search | `aws-strands-agentcore` 3.1 |
| Harness stream events → spans | `aws-agentcore-harness` 1.6 |
| Application Insights, Foundry tracing | `azure-agent-framework` |

---

## R1: One span shape

1. Each exported span SHALL carry both naming schemes for what it describes:

   | Meaning | OpenInference | OTel GenAI |
   | --- | --- | --- |
   | span kind | `openinference.span.kind` (`LLM`, `TOOL`, `AGENT`, `CHAIN`) | `gen_ai.operation.name` (`chat`, `execute_tool`, `invoke_agent`) |
   | model | `llm.model_name` | `gen_ai.request.model` |
   | tokens in / out | `llm.token_count.prompt` / `llm.token_count.completion` | `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` |
   | tool | `tool.name` | `gen_ai.tool.name` |
   | agent | `agent.name` | `gen_ai.agent.name` |

2. Every span SHALL carry `ai_team.span.type` (the original ai-team type), and a merged span
   SHALL carry `ai_team.span.merged` (the list of types it stands for).
3. **Content is off by default.** That covers model messages **and** tool arguments and
   results, which hold whole file contents and test output. Without `--with-content`, a span
   keeps only names, sizes and a SHA-256 of each value. With it, each value is cut to 2 KB with
   `ai_team.truncated = true`.
4. Resource and scope SHALL carry a `schemaUrl` for the pinned GenAI convention version, and
   the OpenInference version SHALL be recorded in the design.
5. Where an `llm_call` has no token counts (no per-call rows yet, see R1.6 of the methodology
   spec), the span SHALL say `ai_team.tokens_missing = true` rather than omit the field silently.

## R2: `python -m evals.cli trace export-otel`

1. `export-otel <run-dir>` SHALL write `logs/otel.harness.jsonl` (OTLP JSON) beside the run's
   other logs.
2. Resource attributes on every span: `service.name = ai-team.<backend>`,
   `openinference.project.name = ai-team`, `ai_team.backend`, `ai_team.run_id`,
   `ai_team.source = harness`, `ai_team.model_tier`.
3. Export SHALL be deterministic. Span ids SHALL be derived from content that doesn't move
   (type, role, phase, start time, tool name, and an occurrence counter for exact repeats), not
   from the builder's order-based `span_NNNN` ids.
4. `--endpoint URL` SHALL POST to an OTLP/HTTP endpoint (default `http://localhost:4318`) in
   batches of at most 512 spans. A refused or slow endpoint SHALL print a warning and exit 0.
5. Every export SHALL record its outcome in `logs/otel.export.json`: `posted`,
   `written_only` or `failed`, with counts, SHA-256, endpoint and error.
6. `--if-changed` SHALL skip the POST when the bytes match the last export already posted to
   the same endpoint.
7. `--all` SHALL export every run under `output/runs/` whose `otel.export.json` is missing or not
   `posted`, skipping runs that can't be built and listing them at the end.

## R3: Lossless re-import of our own exports

1. `import_otlp` SHALL use `ai_team.span.type` when present, and SHALL expand a span carrying
   `ai_team.span.merged` back into one ai-team span per listed type (the first at the span's
   start, the last at its end).
2. Spans without those attributes (framework spans) SHALL keep today's mapping.
3. For any trace, `import_otlp(export(trace))` SHALL give the same span types, counts, roles,
   phases and start times as the trace (span ids may differ).

## R4: Native framework spans tagged the same way

1. The `strands` and `agent-framework` compose services SHALL set `OTEL_RESOURCE_ATTRIBUTES`
   with `ai_team.backend=<name>`, `ai_team.source=framework`,
   `openinference.project.name=ai-team`.
2. Those backends SHALL put `ai_team.run_id` on their root span through a shared helper
   (`harness/otel_tags.py`), called from their own specs' tasks.
3. A backend that saves a copy of its framework spans with the run SHALL name it
   `logs/otel.framework.json`.

## R5: Local viewing

1. The compose `observability` profile SHALL add **Arize Phoenix** (pinned image, data kept in
   `output/phoenix/`) next to Aspire. The collector SHALL send every span to Aspire, Phoenix and
   `output/otel/traces.jsonl`, through the `memory_limiter` and `batch` processors, and expose a
   `health_check` extension.
2. Every published port in the profile SHALL bind to `127.0.0.1` only.
3. `make otel-up`, `make otel-down` and `make otel-backfill` SHALL start the stack, stop it,
   and push runs into it.
4. A smoke check SHALL show one run per available backend in Phoenix, filterable by
   `ai_team.backend` and `ai_team.run_id`.

## R6: The guide

1. `docs/observability/README.md` SHALL cover local viewing, AWS and Azure (marked "later"
   until that backend runs), using the real commands (`uv run python -m evals.cli …`).
2. Every diagram in it SHALL be a Mermaid code block.
3. Each section SHALL be checked against a real run before its "not yet checked" note is removed.

## R7: Tests

1. **Unit** (`tests/unit/evals/`, marker `eval_unit`, no network, no Docker): the mapping and
   both naming schemes, content gating and truncation, stable ids, `schemaUrl`, batching, the
   CLI flags and `otel.export.json`, lossless re-import, and the run-id helper.
2. **Repo** (`tests/unit/repo/`, beside `test_dockerfile.py`): the compose and collector files.
   Phoenix is pinned, the processors and fan-out are present, and every port binds to
   `127.0.0.1`.
3. **Conformance** (`tests/conformance/`, $0): for every registered backend's scripted thin
   slice, export then re-import gives back the same trace (R3.3).
4. **Integration** (`tests/integration/`, markers `integration`, `slow`): against the real
   Docker stack. These skip with a reason unless Docker is available and
   `AI_TEAM_DOCKER_TESTS=1`, which also keeps them a no-op in the existing CI
   `pytest tests/integration` step.
5. Unit, repo and conformance tests SHALL run in CI on every PR. Integration tests SHALL run
   with `make test-otel-integration`.

## R8: Optional, Phase 4: auto-export at run end

1. With `AI_TEAM_OTEL_EXPORT=1`, the end of `ResultsBundle.finalize()` SHALL start the exporter
   as a detached child process, so a slow, missing or broken viewer never changes a run's
   outcome, exit code or timing (design §8). Off by default.
2. Blocked on `eval-methodology-alignment` 1.7. Until every run path calls `finalize()`, CLI runs
   of LangGraph and CrewAI would be silently missed, so the hook isn't built before then.

## Non-goals

- An OTel SDK dependency in `src/`, or native instrumentation for LangGraph, CrewAI or the
  Claude Agent SDK.
- Metrics and logs. Traces only.
- Langfuse, Grafana/Tempo or a hosted viewer. The guide may mention them; nothing is built.
- Deploying anything to AWS or Azure.
