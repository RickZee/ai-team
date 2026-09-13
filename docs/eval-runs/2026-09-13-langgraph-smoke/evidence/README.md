# Evidence freeze

Mid-run copy **2026-09-13T18:52:46Z** (PID 83885 still alive). Process then
exited **14:53:26 EDT**, wall **1600 s**, CLI exit **1**, LangGraph
`interrupt()` → `human_review`. Full structlog: `/tmp/ai-team-bench-9.1/harness.out`.

| File | What it is |
| --- | --- |
| `run.json` | Harness run record; `completed_at` still null after exit |
| `terminal-state.json` | Slim `state.json`: `phase_history`, `retry_count=3`, pytest exit 5 |
| `scorecard.json` | `status: partial`, `test_passed: false` |
| `test_results.json` | ruff ok; pytest collected 0 |
| `wall_s.txt` / `exit_code.txt` | 1600 / 1 |
| `journal.jsonl` | 22 ToolBus lines; `run_id`/`backend` always null |
| `audit.jsonl` | Matching audit trail |
| `structlog-excerpt.txt` | `info`/`error` lines (not the traceback body) |
| `workspace-tree.txt` | Nested `workspace/<id>/workspace/<id>/workspace/<id>` |
| `bare-openrouter.json` | Same-model control call: 1.528 s, $0.0000716 |
| `process-at-handoff.txt` | `ps` snapshot before exit |

Screenshots are not duplicated here:
[`.kiro/specs/production-hardening/screenshots/9.1/`](../../../../.kiro/specs/production-hardening/screenshots/9.1/README.md).
