# Configuration reference

Every environment variable the code reads, grouped by what it controls. Defaults are the values
in code. Put local values in `.env` (copy [`.env.example`](../.env.example)); never commit it.

Two loading mechanisms are in play:

- **Pydantic Settings** in [`config/settings.py`](../src/ai_team/config/settings.py) and
  [`config/models.py`](../src/ai_team/config/models.py). These read `.env` as well as the
  process environment. Each nested settings class has a prefix, so the variable name is the
  prefix plus the field name, which sometimes repeats a word (`MEMORY_MEMORY_ENABLED`,
  `LOG_LOG_LEVEL`).
- **Direct `os.environ` reads** for feature flags in the harness, backends and evals. These see
  the process environment only, so `export` them or prefix the command. `.env` does not set them.

Booleans read directly accept `1`, `true`, `yes`, `on` (case-insensitive) unless noted.

## Keys and providers

| Variable | Default | Effect | Read in |
| --- | --- | --- | --- |
| `OPENROUTER_API_KEY` | empty | Model access for CrewAI and LangGraph | `config/models.py` |
| `OPENROUTER_API_BASE` | `https://openrouter.ai/api/v1` | OpenRouter endpoint | `config/models.py` |
| `OR_SITE_URL`, `OR_APP_NAME` | empty, `AI-Team-Capstone` | Identification headers sent to OpenRouter | `config/models.py` |
| `ANTHROPIC_API_KEY` | empty | Model access for `claude-agent-sdk`. OpenRouter keys do not work there | `config/settings.py` |

## Models and spend

| Variable | Default | Effect | Read in |
| --- | --- | --- | --- |
| `AI_TEAM_ENV` | `dev` | Model tier: `dev`, `test`, `prod` ([MODELS.md](MODELS.md)). `--env` overrides | `config/models.py` |
| `AI_TEAM_MAX_COST_PER_RUN` | `5.0` | Pre-run estimate ceiling (USD). The run aborts before starting if the estimate is higher | `config/models.py` |
| `AI_TEAM_SHOW_COST_ESTIMATE` | `true` | Print the estimate before a run. `--skip-estimate` bypasses it | `config/models.py` |
| `AI_TEAM_PROD_CONFIRM` | `true` | Ask for confirmation before a `prod`-tier run | `config/models.py` |
| `AI_TEAM_RUN_BUDGET_USD` | `5.0` | Runtime spend guard. Crossing it raises `BudgetExceededError` (not retried). `0` disables. For `claude-agent-sdk` it also caps the SDK's own budget | `core/spend_guard.py`, `claude_agent_sdk_backend/costs.py` |

## Paths

| Variable | Default | Effect |
| --- | --- | --- |
| `PROJECT_WORKSPACE_DIR` | `./workspace` | Root for per-run workspaces |
| `PROJECT_OUTPUT_DIR` | `./output` | Root for run bundles (`output/runs/<run_id>/`) |
| `MEMORY_SQLITE_PATH` | `./data/memory.db` | Long-term memory and lessons store |
| `LOG_LOG_LEVEL`, `LOG_LOG_FORMAT`, `LOG_LOG_FILE` | `INFO`, `json`, `./logs/ai-team.log` | structlog settings |

Other `PROJECT_*` fields (`MAX_ITERATIONS`, `DEFAULT_TIMEOUT`, `CREW_VERBOSE`, `CREW_MAX_RPM`,
`PLANNING_SEQUENTIAL`) tune the CrewAI crews; see `ProjectSettings` in `config/settings.py`.

## Backend-specific

| Variable | Default | Backend | Effect |
| --- | --- | --- | --- |
| `CREWAI_HARD_TIMEOUT_SECONDS` | `900` | crewai | Wall-clock kill for the CrewAI subprocess |
| `AI_TEAM_LANGGRAPH_GRAPH_MODE` | `placeholder` | langgraph | `placeholder` runs stub nodes and spends nothing; `full` runs the LLM subgraphs. `--langgraph-mode` overrides |
| `AI_TEAM_LANGGRAPH_RECURSION_LIMIT` | `50` | langgraph | Graph superstep cap |
| `AI_TEAM_LANGGRAPH_SQLITE_PATH` | in-memory (CLI); `workspace/.langgraph_checkpoints.sqlite` (web server) | langgraph | Checkpoint database. Needed for `--resume` across processes |
| `AI_TEAM_LANGGRAPH_POSTGRES_URI` | unset | langgraph | Use a Postgres checkpointer instead of SQLite |
| `ANTHROPIC_SMOKE_LOOP_ENABLED` | `true` | claude-agent-sdk | After a clean run, boot the app, probe it, and retry with the defect if the probe fails |
| `ANTHROPIC_SMOKE_MAX_ATTEMPTS` | `2` | claude-agent-sdk | Orchestrator attempts when the smoke loop is on (1–5) |
| `AI_TEAM_DENY_NATIVE_TOOLS` | off | claude-agent-sdk | PreToolUse hook denies native `Write`/`Bash`, so writes must go through the MCP tools and the ToolBus |
| `AI_TEAM_BASH_ALLOWLIST` | off | claude-agent-sdk | Default-deny `Bash`: only commands on the role's allowlist (`tools/permissions.py`) |
| `AI_TEAM_BASH_ROLE` | `developer` | claude-agent-sdk | Which allowlist the Bash hook checks |
| `FEEDBACK_DEFAULT_RESPONSE` | empty | claude-agent-sdk, crewai | Auto-answer for human-in-the-loop questions when non-empty |
| `FEEDBACK_TIMEOUT_SECONDS` | `300` | crewai | Wait for human input (`0` = no timeout) |

## Harness

| Variable | Default | Effect | Read in |
| --- | --- | --- | --- |
| `AI_TEAM_DRAFT_WRITES` | on (`1`) | ToolBus stages writes under `.harness/drafts/` until committed. `0` writes live | `tools/draft.py` |
| `AI_TEAM_ALLOW_IRREVERSIBLE` | off (`0`) | Let `delete_file`, `execute_shell` and lockfile overwrites run without a human or profile token | `tools/draft.py` |
| `AI_TEAM_CONSTRAINT_CANARY` | unset | Seed a `CST-canary` constraint into `docs/CONSTRAINTS.md` at run start | `harness/context.py` |
| `AI_TEAM_CONTRACT_GATE` | off | Claude SDK PreToolUse hook denies writes under `src/` until a build contract in `docs/contracts/` is accepted | `harness/contracts.py`, `claude_agent_sdk_backend/hooks/security.py` |
| `AI_TEAM_CONTEXT_WINDOW_TOKENS` | unset | Context window used for the context-pressure metric. Unset means the metric is not computed | `harness/context_pressure.py` |
| `AI_TEAM_SESSION_LOOP` | off | Dormant multi-session continuation; also needs `max_sessions > 1` passed in code | `harness/session_loop.py` |

## After a run

| Variable | Default | Effect | Read in |
| --- | --- | --- | --- |
| `AI_TEAM_SKIP_POST_RUN` | unset | Skip lesson extraction at start, and the manager report, metrics, deployment-README check and runtime smoke after the run. `quickstart.sh` and `run_evals.py` set it | `cli_run.py`, `langgraph_backend/post_run.py`, `crewai_backend/flows/main_flow.py` |
| `AI_TEAM_SI_AUTO_EXTRACT` | `true` | Extract lessons from stored failures at run start (SQLite only, no LLM) | `memory/self_improvement_runtime.py` |
| `AI_TEAM_SI_PERSIST_METRICS` | `true` | Store per-run KPIs in the memory database | `memory/self_improvement_runtime.py` |
| `AI_TEAM_MANAGER_REPORT_LLM` | `true` | Add an LLM narrative to the manager report when `OPENROUTER_API_KEY` is set | `reports/manager_self_improvement.py` |
| `MEMORY_MEMORY_ENABLED` | `true` | Master switch for long-term memory | `config/settings.py` |
| `MEMORY_RETENTION_DAYS` | `90` | Memory retention | `config/settings.py` |
| `MEMORY_EMBEDDING_MODEL`, `MEMORY_EMBEDDING_API_BASE` | `openai/text-embedding-3-small`, OpenRouter | Embeddings for CrewAI's own memory | `config/settings.py` |

## Guardrails

All read by `GuardrailSettings` in `config/settings.py`. What each guardrail does:
[GUARDRAILS.md](GUARDRAILS.md).

| Variable | Default |
| --- | --- |
| `GUARDRAIL_BEHAVIORAL_ENABLED`, `GUARDRAIL_SECURITY_ENABLED`, `GUARDRAIL_QUALITY_ENABLED` | `true` |
| `GUARDRAIL_BEHAVIORAL_MAX_RETRIES`, `GUARDRAIL_SECURITY_MAX_RETRIES`, `GUARDRAIL_QUALITY_MAX_RETRIES` | `3` |
| `GUARDRAIL_CODE_QUALITY_MIN_SCORE` | `0.7` |
| `GUARDRAIL_TEST_COVERAGE_MIN` | `0.6` |
| `GUARDRAIL_MAX_FILE_SIZE_KB` | `500` |
| `GUARDRAIL_DANGEROUS_PATTERNS`, `GUARDRAIL_PII_PATTERNS` | lists in code (JSON to override) |

## Web control plane

| Variable | Default | Effect |
| --- | --- | --- |
| `AI_TEAM_WEB_TOKEN` | empty | Shared operator token (header `X-AI-Team-Token`). Empty allows loopback only; binding any other host requires it |
| `AI_TEAM_CORS_ORIGINS` | `localhost`/`127.0.0.1` on 5173 and 8421 | Comma-separated allowed origins |
| `CALLBACK_WEBHOOK_URL`, `CALLBACK_WEBHOOK_ENABLED` | unset, `false` | POST on CrewAI phase transitions |

`ai-team-web` takes `--host` (default `127.0.0.1`) and `--port` (default `8421`). Threat model:
[SECURITY.md](../SECURITY.md).

## Tests and evals

| Variable | Default | Effect |
| --- | --- | --- |
| `AI_TEAM_USE_REAL_LLM` | unset | Enable `real_llm` integration tests and live evals. Costs money |
| `AI_TEAM_TEST_MEMORY` | unset | Enable memory/embedder integration tests (needs `OPENROUTER_API_KEY`) |
| `AI_TEAM_DOCKER_TESTS` | unset | Enable the local OTel stack integration test (needs Docker) |
| `AI_TEAM_BENCHMARK_FULL` | unset | Run performance benchmarks against a real model |
| `AI_TEAM_EVAL_BUDGET_USD` | `5.00` | Ceiling for live eval Tiers B and C. Tier A is always $0 |
| `AI_TEAM_JUDGE_PROVIDER`, `AI_TEAM_JUDGE_MODEL` | `anthropic`, provider default | Legacy continuous judge in `evals/fixtures/` |
| `EVAL_NO_JUDGE` | unset | Skip LLM judge scoring in `evals/metrics.py` |
| `EVALS_ANNOTATE_BATCH` | unset | JSONL file for non-interactive `evals.cli annotate` |
| `AI_TEAM_REFERENCE_OFFLINE` | unset | Mark the reference arm unavailable (no network) |
| `AI_TEAM_DEFAULT_MODEL` | unset | Model name stamped on ablation results |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama endpoint for `scripts/local_smoke.py` |

## Command-line flags that matter

`uv run ai-team --help` and `uv run ai-team run --help` list them all. The ones you will reach
for first:

| Flag | Effect |
| --- | --- |
| `--backend` | `crewai` (default), `langgraph`, `claude-agent-sdk` (alias `claude-sdk`), `strands`, `agent-framework`. The default is still `crewai`, which is now a comparison datapoint, so pass it explicitly |
| `--target` | `local` (default), `container`, `cloud`. The three working backends support `local` only |
| `--team` | Team profile from `config/team_profiles.yaml` (default `full`) |
| `--env` | Model tier for this run |
| `--skip-estimate` | No pre-run estimate prompt (CI, scripts) |
| `--langgraph-mode` | `placeholder` or `full` |
| `--resume`, `--resume-input`, `--thread-id` | Resume a LangGraph thread or a Claude session |
| `--claude-budget` | USD cap for the Claude orchestrator query |
