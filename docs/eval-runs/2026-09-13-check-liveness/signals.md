# Signal chain — harness writer → parser → check

| Span type | Harness writers | Parsers | Consumers | Flags |
| --- | --- | --- | --- | --- |
| `error` | — | **none** | `CHK-premature-termination`, `CHK-provider-error-rate` | unreachable_signal, no_producer |
| `guardrail_check` | guardrails/* (structlog only — no JSONL writer) | parse_audit_jsonl | `CHK-guardrail-fp-budget` | ok |
| `human_interrupt` | — | **none** | `CHK-interrupt-latency` | unreachable_signal, no_producer |
| `llm_call` | core/results/writer.py, claude_agent_sdk_backend/costs.py | parse_costs_jsonl | `CHK-provider-error-rate` | ok |
| `phase_end` | harness/context_pressure.py, agents/prompts.py (AGENT-WRITTEN — FM-018) | parse_phases_jsonl | `CHK-draft-commit`, `CHK-premature-termination`, `CHK-tool-call-emitted` | ok |
| `phase_start` | harness/context_pressure.py, agents/prompts.py (AGENT-WRITTEN — FM-018) | parse_phases_jsonl | `CHK-constraint-survival`, `CHK-phase-repeat-bounded` | ok |
| `qa_verdict` | harness/qa_verdicts.py | parse_qa_verdicts_jsonl | — | orphan_signal |
| `regression_check` | harness/session_loop.py | parse_sessions_jsonl | — | orphan_signal |
| `retry` | harness/context_pressure.py | parse_phases_jsonl | `CHK-provider-error-rate` | ok |
| `session_end` | harness/session_loop.py | parse_sessions_jsonl | `CHK-premature-termination` | ok |
| `session_start` | harness/session_loop.py | parse_sessions_jsonl | — | orphan_signal |
| `smoke_probe` | tools/smoke_tools.py | parse_smoke_report, parse_ui_smoke_report | `CHK-runtime-smoke-present` | ok |
| `spend_event` | core/results/writer.py, claude_agent_sdk_backend/costs.py | parse_costs_jsonl | `CHK-premature-termination`, `CHK-spend-ceiling` | ok |
| `subagent_start` | claude_agent_sdk_backend/orchestrator.py | parse_audit_jsonl | — | orphan_signal |
| `subagent_stop` | claude_agent_sdk_backend/orchestrator.py | parse_audit_jsonl | — | orphan_signal |
| `tool_result` | tools/bus.py | parse_audit_jsonl | `CHK-draft-commit`, `CHK-verifier-independence` | ok |
| `tool_use` | tools/bus.py | parse_audit_jsonl | `CHK-draft-commit`, `CHK-tool-call-emitted`, `CHK-verifier-independence` | ok |

## Flags

- `error` — unreachable_signal, no_producer
- `human_interrupt` — unreachable_signal, no_producer
- `qa_verdict` — orphan_signal
- `regression_check` — orphan_signal
- `session_start` — orphan_signal
- `subagent_start` — orphan_signal
- `subagent_stop` — orphan_signal
