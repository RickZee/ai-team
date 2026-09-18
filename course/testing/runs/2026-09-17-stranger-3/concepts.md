# Concept ledger — 2026-09-17-stranger-3

| Concept | Where the course teaches it | What I could explain afterwards | Verdict |
| --- | --- | --- | --- |
| A team of agents is mostly glue | W1.S1, W2.S2 | The Protocol is ~30 lines; the recorded 26-minute failure was four harness bugs, not a model. Claude vs LangGraph today differed by preflight and timeouts, not by the brief. | taught |
| Tool calls are the only thing that changes the world | W1.S2, W2.S2 | Dry run "succeeds" with empty logs. PATHFIX: a silent rewrite of `test_calc.py` into `tests/` is a tool lying about the path. | taught |
| Writes are staged, not saved (draft → commit) | W2.S2 | `3509ca3`: draft-then-commit was on, nothing promoted drafts, pytest collected 0. I watched `draft_staged` in the B5 timeout log and still saw `calc.py` on disk — so this SHA does save, but the lesson is the earlier hole. | taught |
| Guardrails can fail correct work | W2.S2 | Last-12 chat concat scored QA at 8% against files that were already right. Live W1 still logs `decision=fail` three times with `retry_count=0`. | taught |
| Retries are a cost multiplier, not a safety net | W1.S3, W2.S1 | Morning snapshot burned 3/3 retries. Mine completed with retry 0 and still cost 5× last evening. CrewAI paid 15 minutes for no tests and no `costs.jsonl`. | taught |
| Telemetry has a writer and a reader, and they disagree | W3.S1–S3 | Default backfill reads `./workspace` (unknown×4, 143 spans). `output/runs` labels frameworks. minieval says `timeout`; evals.cli says `killed`. Claude's phase log lives under workspace, backfill looks under output/runs. | taught |
| A check that can't see anything abstains, it doesn't pass | W3.S4, W5.S3 | First liveness: 0 live / 15 blind / na 88% on 4 traces. `spend.py` returns `na` when there is no cost. After my check: thin then live, still 0 pass on the corpus. | taught |
| Failure modes are a taxonomy you build, not a list you're given | W4 | Mechanics work (sample 4 of 30, empty taxonomy). I did not read thirty traces. Two `SIMULATED:` notes only. The idea is asserted. | asserted |
| A pass rate means nothing without its corpus kind and `n` | W5.S1–S2, W6.S4 | Tier A 182 fail is FIXTURE-ONLY. Replay 5/5 vs 1/5 overlaps. My CORPUS 0/6 vs 0/12 pass also overlaps. | taught |
| Deterministic checks before LLM judges | W5.S3 | 20 checks, zero validated judges. I wrote one. The suite is the teacher, once the check is imported. | taught |
| A fix is a claim until you measure it twice | W6.S2–S4 | Tightening to two spans moved FIXTURE-ONLY 228→257 fails (predicted 70 fail / 23 pass / 4 na — hit exactly). CORPUS pass rate 0% did not move. Intervals overlap. Backfill duplicates made `n` a bit fictional. | taught |
| Monitoring is the same eval on a cadence | W6.S5 | minieval audit on 5 runs: floors unmet, 20% abstain. Pytest did not pollute `output/runs` this SHA. | taught |
| Empty env vars beat `.env`, but not every settings class loads `.env` | W1.S2–S3, W2.S1 (hit in practice) | Unset empty OpenRouter → LangGraph works. Unset Anthropic → Claude preflight says "not set" even with `.env` present. Week 1 documents the OpenRouter half. | missing |
