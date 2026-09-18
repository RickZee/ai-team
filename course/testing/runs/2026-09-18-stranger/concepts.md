# Concept ledger — 2026-09-18-stranger

Scoped run (weeks 4–5). Weeks 1–3 and 6 not re-taught.

| Concept | Where the course teaches it | What I could explain afterwards | Verdict |
| --- | --- | --- | --- |
| A team of agents is mostly glue | W1.S1, W2.S2 | — | — (SKIPPED-SCOPE) |
| Tool calls are the only thing that changes the world | W1.S2, W2.S2 | Four placeholder dry runs completed with empty logs. | taught (from W4 corpus setup) |
| Writes are staged, not saved (draft → commit) | W2.S2 | B5 timeout still logged `draft_staged` for calc.py. | taught |
| Guardrails can fail correct work | W2.S2 | — | — (SKIPPED-SCOPE) |
| Retries are a cost multiplier, not a safety net | W1.S3, W2.S1 | B5 hit the 900 s stop, not a retry budget. | taught |
| Telemetry has a writer and a reader, and they disagree | W3.S1–S3 | Default workspace backfill labelled `unknown`. `output/runs` labelled langgraph. Sample inspect uses alpha sort; bundle uses mtime. | taught |
| A check that can't see anything abstains, it doesn't pass | W3.S4, W5.S3 | Watchdog-killed B5 → `na` on CHK-trace-has-spans. Dry runs fail (0 spans). | taught |
| Failure modes are a taxonomy you build, not a list you're given | W4 | Mechanics work. I did not read thirty traces. Two `SIMULATED:` notes only. At n=4 empty, there is nothing to open-code. | asserted |
| A pass rate means nothing without its corpus kind and `n` | W5.S1–S2, W6.S4 | FIXTURE-ONLY 182 then 228. CORPUS 0/4 dry, then 0 pass / 4 fail / 1 na after a timeout. | taught |
| Deterministic checks before LLM judges | W5.S3 | 20 checks, then 21. First pytest now names an unimported module. | taught |
| A fix is a claim until you measure it twice | W6.S2–S4 | Tighten 228→257. B5 timeout did not add a CORPUS pass. | taught (B3/B5 only) |
| Monitoring is the same eval on a cadence | W6.S5 | — | — (SKIPPED-SCOPE) |
| A sampler always returns n; readable n is a different question | W4.S1 (new) | n_selected=4 of 30 requested; --min-spans n_eligible=0. 355/24/30 is dated as this repo. | taught |
| A baseline answers "did this change?"; fixtures answer "is this right?" | W5.S4 | Delete pass fixture → exit 1. | taught |
