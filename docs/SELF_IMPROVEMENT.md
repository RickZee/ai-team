# Runtime self-improvement loop

## Problem

The testing phase ran pytest and reported `test_results.json: PASS` while the
generated app **500'd on every real request**. Unit tests exercise route
handlers with an in-process Flask test client, which bypasses the production
logging/middleware chain — so "tests pass" did not mean "the app works".
Nothing in the pipeline ever *ran* the app, and the acceptance contract's
"`docker compose up` starts the stack" was never verified.

The team was supposed to catch this collaboratively (QA → dev fix → re-test).
It didn't, because no agent had a way to observe the *running* app, and the
recovery loop only retried on SDK/CLI transients (budget, rate-limit, timeout),
never on artifact quality.

## Design: a shared gate + per-backend loops

The **gate** is backend-agnostic and filesystem-based. The **loop wiring**
differs per backend (each owns its orchestration), but every backend reports the
same contract so the Compare tab stays apples-to-apples.

### Shared (all backends)

- **`ai_team.tools.smoke_tools.run_app_smoke(workspace)`** — boots the generated
  app and probes real HTTP endpoints. Launch priority:
  1. `docker-compose.yml` → `docker compose up -d --build`, probe the published
     host port; torn down after.
  2. A Flask `module:app` (or `create_app()`) under `src/` → boot with the
     stdlib server on a free port; terminated after.
  Probes default to `GET /health`; a demo may declare a `smoke` list in
  `expected_output.json` (`{method, path, body}`) for richer CRUD probes.
  Skips cleanly (`ran=false`) when there's no bootable entrypoint or Docker is
  unavailable — an environment gap, not an app defect. Subprocess calls use
  argument lists with `shell=False` (project security rule).

- **`docs/smoke_results.json`** — the contract: `{ran, success, entrypoint,
  base_url, probes[], message, logs}`.

- **`runtime_smoke_guardrail(workspace, phases)`** — no-op pass when `testing`
  isn't a phase or the smoke was skipped; fail when `ran && !success`. Wired into
  the shared post-run path in `main.py` (`_run_post_run_quality_gates`), which
  also **produces** the evidence: if a backend's agents never smoked the app, the
  post-run path boots it so LangGraph/CrewAI get the same coverage as the SDK
  agents. Warn-only at this layer; the loop is what makes it blocking.

### Per-backend loop

| Backend | Loop mechanism | Status |
|---------|----------------|--------|
| claude-agent-sdk | `run_orchestrator_with_recovery` applies the smoke gate between attempts; on failure feeds `{endpoint, status, traceback, logs}` back as a fix prompt and retries. Gated by `settings.anthropic.smoke_loop_enabled` (default on) / `smoke_max_attempts` (default 2). QA + DevOps agents also get the `run_app_smoke` MCP tool to self-correct *within* an attempt. | **Done** |
| langgraph | A `smoke` node sits between `testing` and `deployment`: `route_after_testing` sends a passing test suite to `smoke`, and `route_after_smoke` returns `deployment` (pass/skip) or `retry_development` (fail), bounded by `retry_count`/`max_retries`, then `human_review`. Results land in `metadata.smoke_results`. Placeholder mode records a skip so unit tests stay deterministic; full mode calls `run_app_smoke`. | **Done** |
| crewai | Demoted (comparison-only); covered by the shared post-run gate, no inner loop. | n/a |

## Why this closes the gap

A run can no longer report success over an app that doesn't serve traffic:

1. QA agent (SDK) calls `run_app_smoke` after pytest; a 500 is a release blocker.
2. If it slips through, the recovery loop re-runs dev with the concrete failure.
3. If *that* exhausts its budget, the post-run guardrail still flags it.
4. Every backend is smoked by the shared post-run path regardless of its agents.

Verified end-to-end against the real broken to-do app: pytest reported 70/70
pass, `run_app_smoke` caught `GET /health -> 500`.
