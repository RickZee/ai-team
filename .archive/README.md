# Archive

Kept in the working tree on purpose. Git history is not a substitute for
opening these files while reading the demos and backend-migration docs.

**Retention:** do not delete this directory. `.gitignore` lists `.archive/` so
*new* debris (`compare-debug/`, screenshot dumps) stays untracked; the paths
below stay in git. Local-only files (phase plans, drafts) may also sit here —
they are not deleted by this spec.

## Tracked survivors

| Path | Why it stays |
| --- | --- |
| `demos-removed-2026-06-28/01_hello_world/` | Retired demo 01; cited from `docs/DEMOS.md` |
| `demos-removed-2026-06-28/03_data_pipeline/` | Retired demo 03 |
| `demos-removed-2026-06-28/04_ml_api/` | Retired demo 04 |
| `docs/DATA_INTEGRITY_FIXES.md` | Historical integrity notes |
| `docs/claude-agent-sdk/CLAUDE_AGENT_SDK_PLAN.md` | SDK adoption plan (PROMPT 7 / AgentCore thread) |
| `docs/langgraph/LANGGRAPH_MIGRATION_PLAN.md` | LangGraph migration plan |
| `docs/ui-ux/UI_UX_IMPROVEMENT_PLAN*.md` | Pre-dashboard UI plans |

Do not add new product docs here — use `docs/` or `.kiro/specs/`.
