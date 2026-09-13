# Check liveness — tierA_4671d49ae035_eb36475d7c/report.json

**20 checks, 8 live, 11 thin, 0 blind, 1 unreachable over 72 traces [FIXTURE-ONLY · EVIDENCE-STARVED, na 76%]**

| Check | FM | pass | fail | n/a | err | na% | rate | liveness |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `CHK-interrupt-latency` | FM-003 | 2 | 2 | 90 | 0 | 96% | n=4 | UNREACHABLE |
| `CHK-acceptance-monotonic` | FM-014 | 1 | 1 | 92 | 0 | 98% | n=2 | thin |
| `CHK-constraint-survival` | FM-011 | 1 | 1 | 92 | 0 | 98% | n=2 | thin |
| `CHK-evaluator-capitulation` | FM-017 | 1 | 1 | 92 | 0 | 98% | n=2 | thin |
| `CHK-gate-env-fidelity` | FM-010 | 2 | 2 | 90 | 0 | 96% | n=4 | thin |
| `CHK-guardrail-fp-budget` | FM-005 | 2 | 2 | 90 | 0 | 96% | n=4 | thin |
| `CHK-hallucination-density` | — | 1 | 1 | 92 | 0 | 98% | n=2 | thin |
| `CHK-lesson-effectiveness` | FM-013 | 1 | 1 | 92 | 0 | 98% | n=2 | thin |
| `CHK-metric-source-agreement` | FM-008 | 2 | 2 | 90 | 0 | 96% | n=4 | thin |
| `CHK-premature-termination` | FM-015 | 1 | 1 | 92 | 0 | 98% | n=2 | thin |
| `CHK-verifier-independence` | FM-016 | 1 | 1 | 92 | 0 | 98% | n=2 | thin |
| `CHK-workspace-isolation` | FM-004 | 2 | 2 | 90 | 0 | 96% | n=4 | thin |
| `CHK-draft-commit` | FM-012 | 20 | 1 | 73 | 0 | 78% | 95% (n=21) | live |
| `CHK-listener-self-trigger` | FM-002 | 83 | 2 | 9 | 0 | 10% | 98% (n=85) | live |
| `CHK-phase-repeat-bounded` | FM-002 | 28 | 2 | 64 | 0 | 68% | 93% (n=30) | live |
| `CHK-provider-error-rate` | FM-009 | 8 | 2 | 84 | 0 | 89% | 80% (n=10) | live |
| `CHK-required-artifacts` | — | 15 | 65 | 14 | 0 | 15% | 19% (n=80) | live |
| `CHK-runtime-smoke-present` | FM-006 | 2 | 82 | 10 | 0 | 11% | 2% (n=84) | live |
| `CHK-spend-ceiling` | FM-007 | 76 | 6 | 12 | 0 | 13% | 93% (n=82) | live |
| `CHK-tool-call-emitted` | FM-001 | 14 | 5 | 75 | 0 | 80% | 74% (n=19) | live |

## Unreachable — no corpus can fix these

- `CHK-interrupt-latency` (FM-003) — no parser produces human_interrupt

## EVIDENCE-STARVED

`not_applicable` is 76.3% of all check results. Top abstainers:

- `CHK-acceptance-monotonic` — 92 abstentions
- `CHK-constraint-survival` — 92 abstentions
- `CHK-evaluator-capitulation` — 92 abstentions

## Why checks abstained

| Check | Reason | Count |
| --- | --- | ---: |
| `CHK-acceptance-monotonic` | inconclusive: no acceptance artifacts | 92 |
| `CHK-constraint-survival` | no phase_start spans | 64 |
| `CHK-constraint-survival` | no intake constraint_ids | 28 |
| `CHK-evaluator-capitulation` | no qa verdicts | 92 |
| `CHK-hallucination-density` | no workspace_dir or hallucination_count | 87 |
| `CHK-hallucination-density` | workspace_dir missing: /tmp/ws-a | 3 |
| `CHK-hallucination-density` | workspace_dir missing: /tmp/shared | 2 |
| `CHK-lesson-effectiveness` | no lessons in trace.raw_result | 92 |
| `CHK-premature-termination` | no phase_end/session_end spans | 75 |
| `CHK-premature-termination` | inconclusive: context_pressure is None | 17 |
| `CHK-verifier-independence` | no passes transitions | 92 |
| `CHK-gate-env-fidelity` | no requirements.txt artifact | 90 |
| `CHK-guardrail-fp-budget` | no guardrail_check spans | 90 |
| `CHK-interrupt-latency` | no human_interrupt spans | 90 |
| `CHK-metric-source-agreement` | no event_metrics on trace for comparison | 90 |
| `CHK-workspace-isolation` | no suite_workspace_dirs context on trace | 90 |
| `CHK-provider-error-rate` | no error/llm_call/retry spans to score | 84 |
| `CHK-tool-call-emitted` | no development phase in trace | 75 |
| `CHK-draft-commit` | no development phase | 71 |
| `CHK-draft-commit` | backend emits no tool-level audit | 2 |
| `CHK-phase-repeat-bounded` | no phase_start spans | 64 |
| `CHK-required-artifacts` | scenario has no expected.files | 14 |
| `CHK-spend-ceiling` | no budget configured and no spend_event | 11 |
| `CHK-spend-ceiling` | no cost or spend_event data | 1 |
| `CHK-runtime-smoke-present` | status=failed; smoke gate only required on complete runs | 4 |
| `CHK-runtime-smoke-present` | status=budget_abort; smoke gate only required on complete runs | 3 |
| `CHK-runtime-smoke-present` | status=killed; smoke gate only required on complete runs | 3 |
| `CHK-listener-self-trigger` | listener self-trigger check applies to crewai flows only | 9 |
