# AI-Team: Autonomous Multi-Agent Software Development

[![CI](https://github.com/yourusername/ai-team/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/ai-team/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-pytest--cov-informational)](https://github.com/yourusername/ai-team)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Transform natural language requirements into production-ready code with a team of specialized AI agents. Built on [CrewAI](https://crewai.com) with [OpenRouter](https://openrouter.ai) for LLM and embeddings.

## Project description

AI-Team is an autonomous multi-agent system that orchestrates planning, development, testing, and deployment. You describe what you want in plain language; the system produces requirements, architecture, code, tests, and deployment artifacts with minimal human intervention. All agents use OpenRouter for inference and embeddings (one API key).

### Key features

| Feature | Description |
|---------|-------------|
| **Specialized agents** | Manager, Product Owner, Architect, Backend/Frontend/Fullstack Developers, DevOps, Cloud, QA |
| **End-to-end workflow** | Intake → Planning → Development → Testing → Deployment, driven by a single flow |
| **Enterprise guardrails** | Behavioral (role, scope), security (code safety, PII, secrets), quality (syntax, completeness) |
| **OpenRouter-only** | LLM and embeddings via OpenRouter; single API key |
| **Observable** | Structured logging, flow state, optional **Rich TUI monitor** (live agents, phases, guardrails), and optional Gradio UI for progress and output |

## Architecture (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FLOW LAYER (Orchestration)                            │
│  AITeamFlow: intake → planning → development → testing → deployment → finalize  │
│  ProjectState (Pydantic); @start, @listen, @router                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────┐             ┌───────────────┐             ┌───────────────┐
│ PlanningCrew  │             │DevelopmentCrew│             │ TestingCrew   │
│ DeploymentCrew│             │ (Manager +    │             │ (QA + tools)  │
│ (Manager, PO, │             │   Dev agents) │             │               │
│  Architect)   │             │               │             │               │
└───────┬───────┘             └───────┬───────┘             └───────┬───────┘
        │                             │                             │
        └─────────────────────────────┼─────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  TOOL LAYER: file (read/write/list) · code (gen/review/sandbox) · git · test    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  GUARDRAILS (behavioral, security, quality)  │  MEMORY (session + long-term)    │
└──────────────────────────────────────────────┴──────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full design.

## Quick start (3 commands)

```bash
git clone https://github.com/yourusername/ai-team.git && cd ai-team
cp .env.example .env   # Add OPENROUTER_API_KEY (get one at https://openrouter.ai/settings/keys)
poetry install && poetry run ai-team "Create a REST API for a todo list"
```

Optional: `./scripts/setup_openrouter.sh` prints OpenRouter env reminders. For step-by-step setup and troubleshooting, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Configuration reference

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key (required) | — |
| `AI_TEAM_ENV` | Tier: `dev`, `test`, `prod` | `dev` |
| `OPENROUTER_API_BASE` | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `OPENROUTER_EMBEDDING_MODEL` | Embedding model for crew memory | `openai/text-embedding-3-small` |
| `GUARDRAIL_MAX_RETRIES` | Max guardrail retries | `3` |
| `CODE_QUALITY_MIN_SCORE` | Min quality score (0–1) | `0.7` |
| `TEST_COVERAGE_MIN` | Min test coverage (0–1) | `0.6` |
| `MAX_FILE_SIZE_KB` | Max file size for tools (KB) | `500` |
| `GRADIO_SERVER_PORT` | Gradio UI port | `7860` |

Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`. Before each run, a pre-flight check validates that all configured OpenRouter models (LLM and embedding) exist. Agent→model mapping and guardrail behavior are documented in [docs/AGENTS.md](docs/AGENTS.md) and [docs/GUARDRAILS.md](docs/GUARDRAILS.md).

### Models by environment

Model IDs are in `openrouter/<provider>/<model>` form (see [src/ai_team/config/models.py](src/ai_team/config/models.py)). Set `AI_TEAM_ENV` to `dev`, `test`, or `prod` to choose a tier.

| Role | dev | test | prod |
|------|-----|------|------|
| Manager | `deepseek/deepseek-chat-v3-0324` | `google/gemini-3-flash-preview` | `anthropic/claude-sonnet-4` |
| Product Owner | `deepseek/deepseek-chat-v3-0324` | `google/gemini-3-flash-preview` | `openai/gpt-5.2` |
| Architect | `deepseek/deepseek-chat-v3-0324` | `deepseek/deepseek-r1-0528` | `anthropic/claude-sonnet-4` |
| Backend Developer | `mistralai/devstral-2512` | `minimax/minimax-m2` | `openai/gpt-5.3-codex` |
| Frontend Developer | `mistralai/devstral-2512` | `minimax/minimax-m2` | `anthropic/claude-sonnet-4` |
| Fullstack Developer | `mistralai/devstral-2512` | `minimax/minimax-m2` | `openai/gpt-5.3-codex` |
| Cloud Engineer | `deepseek/deepseek-chat-v3-0324` | `deepseek/deepseek-r1-0528` | `anthropic/claude-sonnet-4` |
| DevOps | `mistralai/devstral-2512` | `mistralai/devstral-2512` | `openai/gpt-5.3-codex` |
| QA Engineer | `deepseek/deepseek-chat-v3-0324` | `deepseek/deepseek-r1-0528` | `anthropic/claude-sonnet-4` |

Embeddings (crew memory) use `OPENROUTER_EMBEDDING_MODEL` (default: `openai/text-embedding-3-small`). Current IDs and pricing: [OpenRouter models](https://openrouter.ai/models).

## Demo projects

| Demo | Description | Input |
|------|-------------|--------|
| **01_hello_world** | Minimal Hello World Flask API | `project_name`, `description`, `requirements` (e.g. Flask, pytest) |
| **02_todo_app** | Full-stack TODO (backend API + frontend) | `project_name`, `description`, `stack` (e.g. Flask, SQLite, HTML/JS) |

Run a demo (when flow is wired):

```bash
poetry run python scripts/run_demo.py demos/01_hello_world
poetry run python scripts/run_demo.py demos/02_todo_app
```

Each demo directory contains `project_description.txt` or `input.json`, and optionally `expected_output.json` for validation.

**Running a demo with OpenRouter (DEV)** — Use the cheapest OpenRouter tier (dev: DeepSeek V3 + Devstral 2). Set `OPENROUTER_API_KEY` in `.env`, then:

- With cost estimate and confirmation:  
  `poetry run python -m ai_team run "$(cat demos/01_hello_world/project_description.txt)" --env dev`
- Without confirmation (e.g. CI): add `--skip-estimate`
- Progress: `--output tui` or `--monitor` for Rich TUI; default `--output crewai` for CrewAI verbose. Optionally `--project-name "Demo 01 Hello World"` when using TUI.

## Progress output (TUI vs CrewAI)

You can choose how progress is shown during a run:

- **`--output tui`** (or **`--monitor`**) — Rich TUI: a live-updating terminal dashboard (phases, agents, guardrails, metrics). CrewAI verbose is turned off so only the TUI is shown.
- **`--output crewai`** (default) — CrewAI default: CrewAI’s own verbose output (agent steps, task completion) to the terminal. No TUI.

Example: `poetry run python -m ai_team run "Create a REST API" --output crewai` uses CrewAI output; add `--output tui` or `--monitor` for the Rich dashboard. The same `--output` option is available in `scripts/run_demo.py`.

## Real-time monitor (TUI)

A Rich-based terminal dashboard shows live agent activity, phase progress, guardrail results, and execution metrics (no extra dependencies beyond `rich`).

```python
from ai_team.monitor import TeamMonitor, MonitorCallback

monitor = TeamMonitor(project_name="My Project")
monitor.start()

# Hook into your flow:
monitor.on_phase_change("planning")
monitor.on_agent_start("architect", "Designing system", "deepseek-r1:14b")
monitor.on_guardrail("security", "code_safety", "pass")
monitor.on_agent_finish("architect")

# When done:
monitor.stop()  # or monitor.stop("complete") / monitor.stop("error")
```

Or use the CrewAI callback adapter so the monitor updates from crew execution:

```python
cb = MonitorCallback(monitor)
crew = Crew(..., step_callback=cb.on_step, task_callback=cb.on_task)
```

To try the dashboard with simulated activity: `python -m ai_team.monitor`.

**Single command** to run the flow with the live TUI:

```bash
poetry run ai-team --monitor "Create a REST API for a todo list"
```

Optional: `--project-name "My Project"` to set the title in the dashboard.

From code you can still pass a `TeamMonitor` into `run_ai_team(description, monitor=monitor)`. The monitor is started before the flow and stopped when the flow completes or errors; phase changes and crew step/task callbacks update the dashboard automatically. At the very start of a phase (e.g. 0s in Planning), tasks completed and agent rows may show zero until the first crew step or task finishes.

## Testing

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=src/ai_team --cov-report=term-missing

# By layer
poetry run pytest tests/unit
poetry run pytest tests/integration
poetry run pytest tests/e2e
```

Integration full-flow tests use a manual flow driver (no `flow.kickoff()`), so they run with the rest of the suite and do not hang or spike memory.

When crews use memory (`memory=True`), they use an OpenRouter-backed embedder (see `get_embedder_config()`). In **integration tests** with `AI_TEAM_USE_REAL_LLM=1`, crew memory is forced off so tests do not depend on the embedding service.

To run **crew-level** integration tests (planning, development, testing) against **real OpenRouter** instead of mocks, set `AI_TEAM_USE_REAL_LLM=1` and `OPENROUTER_API_KEY`. Tests will skip if the key is missing. Full-flow tests remain mock-only by design.

```bash
AI_TEAM_USE_REAL_LLM=1 poetry run pytest tests/integration -m real_llm -v
```

Optional **memory/embedder** tests: set `OPENROUTER_API_KEY`, then `AI_TEAM_USE_REAL_LLM=1 AI_TEAM_TEST_MEMORY=1 poetry run pytest tests/integration -m test_memory -v`.

To run only the **OpenRouter connectivity** test (minimal cost; uses a free-tier model), set `OPENROUTER_API_KEY` in `.env` and run: `AI_TEAM_USE_REAL_LLM=1 poetry run pytest tests/integration/test_openrouter.py::TestOpenRouterGated::test_openrouter_connectivity -v`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for code style and PR requirements.

## Project structure

```
ai-team/
├── src/ai_team/
│   ├── config/          # Settings, agents.yaml
│   ├── agents/          # Agent implementations (base, manager, PO, architect, devs, QA, DevOps)
│   ├── crews/           # Planning, Development, Testing, Deployment crews
│   ├── flows/           # AITeamFlow and state
│   ├── tools/           # File, code, git, test tools
│   ├── guardrails/      # Behavioral, security, quality
│   ├── memory/          # Session and long-term memory
│   ├── utils/           # Shared utilities
│   └── ui/              # Gradio app and components
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── demos/               # 01_hello_world, 02_todo_app
├── docs/                # ARCHITECTURE, AGENTS, GUARDRAILS, FLOWS, TOOLS, MEMORY, GETTING_STARTED
└── scripts/             # setup_openrouter.sh, test_models.py, run_demo.py
```

## Code stats

Count lines of code (requires [cloc](https://github.com/AlDanial/cloc)):

```bash
cloc \
  src tests docker scripts docs demos .github \
  --exclude-dir=__pycache__,node_modules,target,dist,build,cdk.out,.git,.venv,.pytest_cache,.archive,.ruff_cache,.mypy_cache,htmlcov,.tox,.eggs,.pdm-build,.pixi \
  --vcs=git
```

## Contributing

We welcome contributions. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup and dependencies
- Code style (black, ruff, mypy)
- PR process and commit message convention
- How to add new agents, tools, or guardrails

## License and acknowledgments

- **License:** [MIT](LICENSE).
- **CrewAI:** [crewai.com](https://crewai.com) — agent and crew framework.
- **OpenRouter:** [openrouter.ai](https://openrouter.ai) — LLM and embeddings API.

This project is suitable for portfolios and demonstrations of multi-agent software development systems.
