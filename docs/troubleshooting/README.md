# Troubleshooting

Deep-dive post-mortems of non-obvious bugs found running this system — the kind
where the symptom points at the wrong component. Each is a self-contained war
story with the wrong hypothesis, the root cause, and the fix. Sourced from the
[engineering journal](../journal/README.md).

| Symptom | Root cause | Write-up |
|---|---|---|
| A LangGraph HITL interrupt takes 78 minutes to appear in `GET /api/runs/{id}` | A *different* backend (CrewAI) running in the same process starved the GIL, stalling LangGraph's pure-Python post-interrupt state write | [gil-starvation-hitl-delay.md](gil-starvation-hitl-delay.md) — journal [2026-07-01](../journal/2026-07-01.md) §11b/§11c |
| 70/70 pytest green, `success: true`, but the app 500s on every request | Tests used Flask's in-process test client, which never boots the real WSGI logging path where a `structlog` misconfig crashed every request | [tests-pass-app-broken.md](tests-pass-app-broken.md) — journal [2026-07-01](../journal/2026-07-01.md) §2 |
| LangGraph 1/5 green on smoke while other backends pass; retries burn on import/layout or lint noise | Dev/QA `src/` layout mismatch, lint gate W293 kills, gate errors not injected into retry prompts | [langgraph-reliability-investigation.md](langgraph-reliability-investigation.md) — journal [2026-07-06](../journal/2026-07-06.md) |

For the cross-cutting taxonomy (ten failure classes), see [failure-taxonomy.md](../posts/failure-taxonomy.md).
