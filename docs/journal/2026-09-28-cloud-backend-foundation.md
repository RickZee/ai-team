# 2026-09-28 — the cloud backends needed a contract before either cloud

**Session:** 2026-09-28. Agent-assisted (Cursor).
**Spec:** `.kiro/specs/cloud-backend-foundation`.

Strands on AgentCore and Agent Framework on Foundry are still not pipelines.
What landed is the bar they have to clear, and the places a name can be typed
without spending money.

## What the suite actually runs

`tests/conformance/` injects one YAML script (`calc.py` plus a pytest) into
CrewAI, LangGraph, Claude Agent SDK, and a `fake-remote` container client.
Each backend's `run()` returns that path before it touches a model. Tool calls
go through `ToolBus.invoke`, drafts are promoted only by `commit_pending_drafts`,
spend goes through `record_usage`, and the results bundle carries the backend
name plus both clocks. The suite was green in about 22 seconds. `KNOWN_GAPS.md`
has no open gaps. That is the injected-model contract from the design, not a
claim that a live crew was replayed.

The repo's llm span is still `llm_call`. The OTel map uses that name. Calling
it `llm` in the requirements and `llm_call` in `SpanType` is the same event.

## Acceptance

After the testing phase, the harness writes `logs/harness_acceptance.json`.
A criterion with no evidence stays `unverified`. Passing tests record an accept
even when QA has no accept tool — the September LangGraph/CrewAI hole.
A QA reject on passing evidence writes one `qa_disagreement` span, and
`TraceBuilder` reads it. When an OTel file sits next to harness spans, the
builder keeps the harness list and records the OTel count as a second reader.

## Left open on purpose

- Conformance is a CI job. It is not a required check, and it has not run on `main`.
- Docker was not running, so the Aspire dashboard was not opened.
- `terraform validate` passed for both `envs/dev` with no credentials. `plan` did not.
  Checkov locally reported no failures and no skips. The infra workflow has not gone green on a PR.
- Local model pin is `llama3.2`, the tool-calling model already on this Mac (2 GB).
  `make local-smoke BACKEND=langgraph` printed pass on the tool call, the thin slice,
  `model_tier: local`, and `$0`. Collector image `0.160.0`, Aspire dashboard `13.4.2`.
