# Field notes, November 2026

Sequel to the October notes. Each note follows a fix on `feature/field-notes-sequel`. Publish a note only after its proof file is on `main`. The October series stays in `.archive/` and is not part of this branch.

| | Note | Fix |
| --- | --- | --- |
| 1 | A zero-dollar run still leaves a cost log | `finalize` always writes `logs/costs.jsonl`, including `spent_usd: 0` |
| 2 | The phase log is written by the harness | LangGraph records `phase_history`; `TelemetryWriter` writes `phases.jsonl`. The prompt line that asked the model to do it is deleted |
| 3 | The gate marks the work done | A passing quality gate sets `passes` on `ACCEPTANCE.json`. The verifier is `_harness` |
| 4 | Twenty-two fixtures were counted twice | Deleted 22 byte-identical `__fixture.json` copies. 72 ids, 72 files |
| 5 | What a run costs, per role | `scripts/role_cost.py` |
| 6 | Two CrewAI failures, one page | `docs/FRAMEWORKS.md` keeps the listener loop and the GIL hang apart |

## Not in this branch

The October close wanted a second 30-run batch after a timeout fix, with a new finish rate and a new interval. The seven September timeouts have a cost row and no `state.json`, so the cause is not readable from phase history. Re-running the batch spends money. This branch does not invent an after number and does not start that batch.
