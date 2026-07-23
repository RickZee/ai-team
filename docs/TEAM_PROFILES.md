# Team profiles

Team profiles right-size which agents and lifecycle phases run for a project. Agent personas are documented in [AGENTS.md](AGENTS.md). Model assignment per environment tier is in [MODELS.md](MODELS.md).

Profiles are defined in [`src/ai_team/config/team_profiles.yaml`](../src/ai_team/config/team_profiles.yaml) and loaded by [`src/ai_team/core/team_profile.py`](../src/ai_team/core/team_profile.py).

Select a profile with `--team <name>` on the CLI, in the web dashboard run form, or via `team_profile` in a demo `input.json` (see [Demos](DEMOS.md)).

---

## Profile catalog

| Profile | Agents | Phases | Typical use |
| ------- | ------ | ------ | ----------- |
| `full` (default) | manager, product_owner, architect, backend_developer, frontend_developer, fullstack_developer, devops_engineer, cloud_engineer, qa_engineer | intake, planning, development, testing, deployment | End-to-end software project |
| `full-claude` | same as `full` | intake, planning, development, testing, deployment | Same-model matrix: every role pinned to `claude-sonnet-4.6` via OpenRouter |
| `backend-api` | manager, product_owner, architect, backend_developer, qa_engineer, devops_engineer | intake, planning, development, testing, deployment | REST API / microservice (no frontend specialists) |
| `frontend-app` | manager, product_owner, architect, frontend_developer, qa_engineer, devops_engineer | intake, planning, development, testing, deployment | SPA / static site |
| `data-pipeline` | manager, product_owner, architect, backend_developer, qa_engineer | intake, planning, development, testing | ETL / data engineering (no deployment phase) |
| `prototype` | architect, fullstack_developer, qa_engineer | intake, planning, development, testing | Minimal crew: design → implement → test |
| `smoke` | architect, backend_developer, qa_engineer | planning, development, testing | CI smoke checks; tight phase timeouts |
| `smoke-claude` | same as `smoke` | planning, development, testing | Same-model control for backend comparison: `smoke` roster with every role pinned to `claude-sonnet-4.6`. Use for framework-vs-framework verdicts (see caveat below) |
| `infra-only` | architect, devops_engineer, cloud_engineer | intake, planning, deployment | IaC / CI-CD only (no application development or QA) |

---

## Backend behavior

| Backend | Profile-aware agent wiring |
| ------- | -------------------------- |
| `langgraph` | Yes — subgraphs compile only agents listed in the profile |
| `claude-agent-sdk` | Yes — subagents built from profile agents and phases |
| `crewai` | **Partial** — `team_profile` is recorded in run metadata and reports; the legacy flow may still invoke the full crew until CrewAI parity is implemented |

> **Same-model caveat for `smoke-claude` / `full-claude`.** The `model_overrides` in
> these profiles are OpenRouter model ids, honored by the crewai and langgraph
> backends. The `claude-agent-sdk` backend calls the Anthropic API directly and does
> **not** read them, so the comparison is exactly model-controlled only for
> crewai-vs-langgraph. For anything involving the SDK, confirm the SDK's own configured
> model matches before treating the batch as same-model.

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

# Same-model comparison (LangGraph vs SDK with Claude held constant)
uv run ai-team run "Build a todo API" --backend langgraph --team full-claude
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
| `02_todo_app` | `full` (default) | Full pipeline |

See [DEMOS.md](DEMOS.md) for run commands.
