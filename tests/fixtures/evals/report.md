# Eval suite report — `golden_suite_001`

**Verdict:** fail — FAIL — 1 failed check(s) across suite

Tier `A` · generated_at `2026-08-16T12:00:00+00:00`

## 1. Headline verdict

FAIL — 1 failed check(s) across suite

## 2. Scorecard

| Backend | Scenario | Outcome | pass^k | pass_rate | n | 95% CI |
| --- | --- | --- | --- | --- | --- | --- |
| claude-agent-sdk | smoke-test | indeterminate | 1.000 | 1.000 | 2 | [0.342, 1.000] |
| crewai | smoke-test | indeterminate | 1.000 | 1.000 | 2 | [0.342, 1.000] |
| langgraph | smoke-test | indeterminate | 0.000 | 0.500 | 2 | [0.095, 0.905] |

## 3. Regressions vs baseline

_See gate / CI summary._

## 4. Failure-mode incidence

| FM | Layer | Raw rate | Bias-corrected | Fails |
| --- | --- | --- | --- | --- |
| FM-001 | model | 0.500 (n=2, 95% CI [0.095, 0.905]) | — | 1 |
| FM-009 | provider | 0.000 (n=1, 95% CI [0.000, 0.793]) | — | 0 |

## 5. Reliability budget by layer

- **model**: 0.500 (n=2, 95% CI [0.095, 0.905]) (fails=1)
- **framework**: n/a (n=0) (fails=0)
- **harness**: n/a (n=0) (fails=0)
- **provider**: 0.000 (n=1, 95% CI [0.000, 0.793]) (fails=0)

## 6. Judge alignment

| Judge | Eligible | TPR | TNR | κ |
| --- | --- | --- | --- | --- |
| fm-001-tool-call-omission | False | 0.85 | 0.8 | 0.6 |

### Suppressed

- `judge:fm-001-tool-call-omission: below eligibility thresholds (R8.6)`
- `guardrail:scope_relevance: provisional (n=5 below min_cases)`

## 7. Guardrail precision-recall

| Guardrail | n | Precision | Recall | FPR | Provisional |
| --- | --- | --- | --- | --- | --- |
| scope_relevance | 5 | 0.8 | 0.75 | 0.1 | True |

## 8. Cost and latency

- Cost: `$0.0000`
- Latency p95: 2.00s (n=3)

## 9. Flaky cells

- `langgraph/smoke-test`

## 10. Failed checks

- `CHK-tool-call-emitted` · trace=`trace_fail_001` · span=`span_0001`

## 11. Provenance

```json
{
  "git_dirty": false,
  "git_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "harness_version": "0.1.0",
  "model_ids": {
    "judge": "test-model"
  },
  "platform": "test-platform",
  "pricing_table_version": "2026-08-16",
  "python_version": "3.12.0",
  "scenario_content_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "seed": 0,
  "taxonomy_version": "1.0.0",
  "tier": "A"
}
```
