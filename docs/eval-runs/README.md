# Eval run notes

Receipts for eval work that actually executed (or froze mid-run). These are
not published rates. Claim rules:
[`campaign/EVAL_GATE_STATUS.md`](../campaign/EVAL_GATE_STATUS.md).

| Note | Kind | What happened |
| --- | --- | --- |
| [2026-08-16](./2026-08-16/) | `FIXTURE-ONLY` | Tier A offline; live Tier C / judge align deferred |
| [2026-09-13 LangGraph smoke](./2026-09-13-langgraph-smoke/) | live failure, unlabeled | 1600 s → HITL; retry amplification after a successful write; 9.1 not published |
| [2026-09-13 check liveness](./2026-09-13-check-liveness/) | `FIXTURE-ONLY` instruments | 8 live / 11 thin / 1 unreachable on fixtures; 19 blind on the 50-trace corpus |
