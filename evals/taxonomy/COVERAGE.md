# Failure-mode coverage

Taxonomy version: `1.2.0`

| ID | Slug | Layer | Harness layer | Detection | Checks | Judges | Labels | Rate | Status |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| FM-001 | `tool_call_omission` | model | tools | check | CHK-tool-call-emitted | — | 0 | — | active |
| FM-002 | `self_triggering_retry_loop` | framework | — | check | CHK-phase-repeat-bounded, CHK-listener-self-trigger | — | 0 | — | active |
| FM-003 | `runtime_coupling_starvation` | harness | observability | check | CHK-interrupt-latency | — | 0 | — | active |
| FM-004 | `run_id_collision` | harness | observability | check | CHK-workspace-isolation | — | 0 | — | active |
| FM-005 | `guardrail_false_positive` | harness | guardrails | check | CHK-guardrail-fp-budget | — | 0 | — | active |
| FM-006 | `runtime_verification_gap` | harness | verification | check | CHK-runtime-smoke-present | — | 0 | — | active |
| FM-007 | `unbounded_spend` | harness | guardrails | check | CHK-spend-ceiling | — | 0 | — | active |
| FM-008 | `metric_source_drift` | harness | observability | check | CHK-metric-source-agreement | — | 0 | — | active |
| FM-009 | `provider_dialect_mismatch` | provider | — | check | CHK-provider-error-rate | — | 0 | — | active |
| FM-010 | `gate_environment_mismatch` | harness | verification | check | CHK-gate-env-fidelity | — | 0 | — | active |
| FM-011 | `constraint_drop` | harness | context | check | CHK-constraint-survival | — | 0 | — | active |
| FM-012 | `uncommitted_write` | harness | tools | check | CHK-draft-commit | — | 0 | — | active |
| FM-013 | `lesson_ineffective` | harness | feedback | check | CHK-lesson-effectiveness | — | 0 | — | active |
| FM-014 | `acceptance_criteria_mutation` | model | tools | check | CHK-acceptance-monotonic | — | 0 | — | active |
| FM-015 | `premature_termination_under_context_pressure` | model | context | check | CHK-premature-termination | — | 0 | — | active |
| FM-016 | `self_graded_verification` | harness | verification | check | CHK-verifier-independence | — | 0 | — | active |
| FM-017 | `evaluator_capitulation` | model | verification | check | CHK-evaluator-capitulation | — | 0 | — | active |

## Uncovered (detection: check, no implementation)

_None — every check-detected FM has a named implementation._

## Reserved (not yet implemented)

_None — no reserved failure modes._

## Example provenance

Positive/negative examples currently reference **synthetic** check
fixtures under `evals/fixtures/traces/` (fail/pass pairs from
`tests/fixtures/traces/`). They are harness wiring evidence, **not**
production open-coding labels from task 5.2 (human-only).

All seeded FMs remain `active` with fixture examples. Retire an FM
only with an explicit `retired_reason` when the corpus truly cannot
support it — do not retire merely because live open-coding has not
run yet.
