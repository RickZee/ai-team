# Team profiles

Team profiles right-size which agents and lifecycle phases run for a project. They are defined in [`src/ai_team/config/team_profiles.yaml`](../src/ai_team/config/team_profiles.yaml) and loaded by [`src/ai_team/core/team_profile.py`](../src/ai_team/core/team_profile.py).

Select a profile with `--team <name>` on the CLI, in the web dashboard run form, or via `team_profile` in a demo `input.json` (see [Demos](DEMOS.md)).

---

## Profile catalog

| Profile | Agents | Phases | Typical use |
| ------- | ------ | ------ | ----------- |
| `full` (default) | manager, product_owner, architect, backend_developer, frontend_developer, fullstack_developer, devops_engineer, cloud_engineer, qa_engineer | intake, planning, development, testing, deployment | End-to-end software project |
| `backend-api` | manager, product_owner, architect, backend_developer, qa_engineer, devops_engineer | intake, planning, development, testing, deployment | REST API / microservice (no frontend specialists) |
| `frontend-app` | manager, product_owner, architect, frontend_developer, qa_engineer, devops_engineer | intake, planning, development, testing, deployment | SPA / static site |
| `data-pipeline` | manager, product_owner, architect, backend_developer, qa_engineer | intake, planning, development, testing | ETL / data engineering (no deployment phase) |
| `prototype` | architect, fullstack_developer, qa_engineer | intake, planning, development, testing | Minimal crew: design → implement → test |
| `infra-only` | architect, devops_engineer, cloud_engineer | intake, planning, deployment | IaC / CI-CD only (no application development or QA) |
| `research-optimizer` | optimizer | optimize | Karpathy AutoOptimizer Loop (`ai-team optimize`, demo 06) |

### Optional RAG metadata

| Profile | RAG topics (when enabled) |
| ------- | ------------------------- |
| `full` | python, security, testing, api, devops |
| `research-optimizer` | performance, optimization, profiling, caching, algorithms |

---

## Backend behavior

| Backend | Profile-aware agent wiring |
| ------- | -------------------------- |
| `langgraph` | Yes — subgraphs compile only agents listed in the profile |
| `claude-agent-sdk` | Yes — subagents built from profile agents and phases |
| `crewai` | **Partial** — `team_profile` is recorded in run metadata and reports; the legacy flow may still invoke the full crew until CrewAI parity is implemented |

For the leanest real run (e.g. demo `00_smoke_test` with `prototype`), prefer:

```bash
uv run python scripts/run_demo.py demos/00_smoke_test --skip-estimate --backend langgraph
```

`team_profile` in `input.json` is picked up automatically; override with `--team` on the CLI.

---

## CLI and API

```bash
# Default full team
uv run ai-team run "Build a todo API" --backend langgraph

# Backend API profile
uv run ai-team run "Build a todo API" --backend langgraph --team backend-api

# Optimizer loop (demo 06)
uv run ai-team optimize ./workspace/... --team research-optimizer ...
```

- **REST:** `GET /api/profiles` — returns agents, phases, and model overrides per profile from YAML.
- **Demos:** `scripts/run_demo.py` and `scripts/compare_backends.py` read `team_profile` from `input.json` unless `--team` is set.

---

## Adding or changing a profile

1. Edit `src/ai_team/config/team_profiles.yaml` (agent keys must match `config/agents.yaml`).
2. Update this document and the summary table in [README.md](../README.md).
3. Add or adjust unit coverage in `tests/unit/test_team_profile.py` if behavior changes.
4. For LangGraph, confirm subgraph compilation in `tests/unit/backends/langgraph_backend/test_profile_aware_subgraphs.py`.

---

## Demo → profile mapping

| Demo | Suggested profile | Notes |
| ---- | ----------------- | ----- |
| `00_smoke_test` | `prototype` | Set in `input.json`; use `--backend langgraph` for lean agent set |
| `01`–`05` | `full` (default) | Full pipeline |
| `06_karpathy_optimization` | `research-optimizer` | Uses `ai-team optimize`, not `run_demo.py` |

See [DEMOS.md](DEMOS.md) for run commands.
