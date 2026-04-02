# Claude Agent SDK backend — runbook

## Prerequisites

- `ANTHROPIC_API_KEY` in the environment, or `anthropic.api_key` in app settings (same env var is loaded into nested settings).
- Claude Code CLI available to the SDK (per Anthropic Claude Agent SDK install docs).

## CLI

```bash
ai-team run --backend claude-agent-sdk --team full "Your project description"
```

- **Budget:** `--claude-budget` or `--budget` (USD cap).
- **Resume:** `--resume <session_id>`; optional `--fork-session`.
- **Recovery:** pass `recovery_max_attempts` only via programmatic `ClaudeAgentBackend.run(..., recovery_max_attempts=3)` (default `1` = single pass).
- **HITL default:** set `FEEDBACK_DEFAULT_RESPONSE` (human feedback settings) to auto-answer `AskUserQuestion` with that text when non-empty.

## Workspace artifacts

| Path | Purpose |
|------|---------|
| `docs/CLAUDE_PROFILE.md` | Profile agents, phases, RAG topics |
| `logs/costs.jsonl` | Per-run cost rows (`orchestrator`, `orchestrator_recovery_attempt`) |
| `logs/reasoning.jsonl` | Extended thinking blocks when `log_reasoning=true` |
| `logs/audit.jsonl` | Tool + subagent lifecycle |
| `logs/session.json` | Last session id and outcome |

## Optional kwargs (`ClaudeAgentBackend.run` / `stream`)

- `workspace_snapshot` / `workspace_snapshot_tag` — snapshot `docs`, `src`, `tests`, `infrastructure` before run.
- `restore_workspace_on_failure` — restore snapshot after exception or `ResultMessage.is_error`.
- `log_reasoning` — default `true`; set `false` to skip `reasoning.jsonl`.
- `use_tool_search` — override auto `ToolSearch` (default: on if ≥3 MCP servers or `metadata.claude_agent_sdk.use_tool_search`).

## Manual verification (T8.3)

Run `demos/01_hello_world` and `demos/02_todo_app` with `--backend claude-agent-sdk` and team profiles `full` and `backend-api`; record `total_cost_usd` from `logs/costs.jsonl` or CLI JSON output `session_id` / workspace.
