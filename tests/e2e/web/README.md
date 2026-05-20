# Web dashboard E2E tests

Zero-LLM-cost coverage for the FastAPI + React dashboard. Real backend runs are **not**
executed in the default suite (use demo simulation and mocked WebSocket execution).

## What is covered

| Suite | File | Cost |
|-------|------|------|
| API E2E | `test_api_e2e.py` | $0 — demo + mocked `/ws/run` |
| Browser E2E | `test_browser_e2e.py` | $0 — Playwright + demo only |

## Run locally

```bash
poetry install
poetry run playwright install chromium

# API + browser (builds frontend on first run)
poetry run pytest tests/e2e/web -m web_e2e -v --timeout=120

# API only (faster; no npm build)
poetry run pytest tests/e2e/web/test_api_e2e.py -m web_e2e -v --timeout=120

# Skip frontend build (browser tests skipped)
AI_TEAM_SKIP_FRONTEND_BUILD=1 poetry run pytest tests/e2e/web -m web_e2e -v
```

## Optional: real LLM run (costs money)

Not part of this suite. Use CLI integration tests with `AI_TEAM_USE_REAL_LLM=1` or run
manually from the Run page with API keys in `.env`.

## Troubleshooting

- **Port in use**: tests pick a random free port automatically.
- **Frontend build fails**: `cd src/ai_team/ui/web/frontend && npm ci && npm run build`
- **Playwright missing**: `poetry run playwright install chromium`
- **Demo timeout**: demo simulation takes ~30–60s; tests allow 90s.
