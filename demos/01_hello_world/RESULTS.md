# Demo 01_hello_world — Results

**Summary:** PASS

## Generated files

| File | Lines | Size |
|------|-------|------|
| app.py | 35 | 909 B |
| test_app.py | 67 | 1777 B |
| requirements.txt | 3 | 45 B |
| Dockerfile | 7 | 161 B |
## Test results

- Passed: 6, Failed: 0, Coverage: 95%

## Lint results

Clean (no violations)

## Docker

- Built successfully. Image size: 257MB

## Smoke test

All endpoints responded correctly.

- GET /health: 200, {status: ok}
- GET /items: 200, []
- POST /items: 201
- GET /items after POST: 200, [apple]

**Run duration:** 0.0 s

**Retries:** 0

**Guardrail/retry notes:** Retries: 0; per-phase: {}
