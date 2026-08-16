# Failure-mode coverage

Taxonomy version: `1.0.0`

| ID | Slug | Layer | Detection | Checks | Judges | Labels | Rate | Status |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| FM-001 | `tool_call_omission` | model | check | CHK-tool-call-emitted | — | 0 | — | active |
| FM-002 | `self_triggering_retry_loop` | framework | check | CHK-phase-repeat-bounded, CHK-listener-self-trigger | — | 0 | — | active |
| FM-003 | `runtime_coupling_starvation` | harness | check | CHK-interrupt-latency | — | 0 | — | active |
| FM-004 | `run_id_collision` | harness | check | CHK-workspace-isolation | — | 0 | — | active |
| FM-005 | `guardrail_false_positive` | harness | check | CHK-guardrail-fp-budget | — | 0 | — | active |
| FM-006 | `runtime_verification_gap` | harness | check | CHK-runtime-smoke-present | — | 0 | — | active |
| FM-007 | `unbounded_spend` | harness | check | CHK-spend-ceiling | — | 0 | — | active |
| FM-008 | `metric_source_drift` | harness | check | CHK-metric-source-agreement | — | 0 | — | active |
| FM-009 | `provider_dialect_mismatch` | provider | check | CHK-provider-error-rate | — | 0 | — | active |
| FM-010 | `gate_environment_mismatch` | harness | check | CHK-gate-env-fidelity | — | 0 | — | active |

## Uncovered (detection: check, no implementation)

_None — every check-detected FM has a named implementation._

## Example provenance

Positive/negative examples currently reference **synthetic** check
fixtures under `evals/fixtures/traces/` (fail/pass pairs from
`tests/fixtures/traces/`). They are harness wiring evidence, **not**
production open-coding labels from task 5.2 (human-only).

All seeded FMs remain `active` with fixture examples. Retire an FM
only with an explicit `retired_reason` when the corpus truly cannot
support it — do not retire merely because live open-coding has not
run yet.
