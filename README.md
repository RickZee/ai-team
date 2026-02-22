# AI-Team: Autonomous Multi-Agent Software Development

[![CI](https://github.com/yourusername/ai-team/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/ai-team/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-pytest--cov-informational)](https://github.com/yourusername/ai-team)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Transform natural language requirements into production-ready code with a team of specialized AI agents. Built on [CrewAI](https://crewai.com) with local-first Ollama models.

## Project description

AI-Team is an autonomous multi-agent system that orchestrates planning, development, testing, and deployment. You describe what you want in plain language; the system produces requirements, architecture, code, tests, and deployment artifacts with minimal human intervention. All agents run against local LLMs via Ollama—no OpenAI or other cloud APIs, and no API keys required.

### Key features

| Feature | Description |
|---------|-------------|
| **Specialized agents** | Manager, Product Owner, Architect, Backend/Frontend/Fullstack Developers, DevOps, Cloud, QA |
| **End-to-end workflow** | Intake → Planning → Development → Testing → Deployment, driven by a single flow |
| **Enterprise guardrails** | Behavioral (role, scope), security (code safety, PII, secrets), quality (syntax, completeness) |
| **Local-first** | Ollama-backed models only; no OpenAI or cloud LLM usage |
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
./scripts/setup_ollama.sh    # Install Ollama and pull recommended models + embedding model (nomic-embed-text)
cp .env.example .env && poetry install && poetry run ai-team "Create a REST API for a todo list"
```

The setup script pulls the LLM models and the embedding model (`nomic-embed-text`), so crew memory and `AI_TEAM_TEST_MEMORY` tests work without a separate `ollama pull nomic-embed-text`.

For step-by-step setup and troubleshooting, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Configuration reference

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama API base URL | `http://localhost:11434` |
| `OLLAMA_MEMORY_PRESET` | `default` or `32gb` (7B/8B models, ~8–10 GB peak) | `default` |
| `*_MODEL` (e.g. `OLLAMA_MANAGER_MODEL`) | Per-role Ollama model name | Role default from settings |
| `GUARDRAIL_MAX_RETRIES` | Max guardrail retries | `3` |
| `CODE_QUALITY_MIN_SCORE` | Min quality score (0–1) | `0.7` |
| `TEST_COVERAGE_MIN` | Min test coverage (0–1) | `0.6` |
| `MAX_FILE_SIZE_KB` | Max file size for tools (KB) | `500` |
| `GRADIO_SERVER_PORT` | Gradio UI port | `7860` |

### Model configuration and 32 GB RAM

Default models (14b/16b) load **one at a time** (planning → development → testing → deployment). Peak usage is ~16–18 GB for the largest model plus embedding and overhead, so a **32 GB** system is sufficient. Set `OLLAMA_MEMORY_PRESET=32gb` to use 7B/8B variants (qwen3:8b, deepseek-r1:8b, qwen2.5-coder:7b, etc.) for a **~8–10 GB peak** on constrained or shared machines; per-role env vars override the preset when set. Pull the preset models with `ollama pull qwen3:8b` and similar before using the 32gb preset.

Copy `.env.example` to `.env` and adjust. Agent→model mapping and guardrail behavior are documented in [docs/AGENTS.md](docs/AGENTS.md) and [docs/GUARDRAILS.md](docs/GUARDRAILS.md).

## Demo projects

| Demo | Description | Input |
|------|-------------|--------|
| **01_hello_world** | Minimal Hello World Flask API | `project_name`, `description`, `requirements` (e.g. Flask, pytest) |
| **02_todo_app** | Full-stack TODO (backend API + frontend) | `project_name`, `description`, `stack` (e.g. Flask, SQLite, HTML/JS) |

Run a demo (when flow is wired):

```bash
python scripts/run_demo.py demos/01_hello_world
python scripts/run_demo.py demos/02_todo_app
```

Each demo directory contains `input.json` and `expected_output.json` for validation.

## Real-time monitor

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

In **production**, when crews use memory (`memory=True`), they are given an explicit Ollama embedder (from `MemorySettings`: `embedding_model`, `ollama_base_url`) so CrewAI never falls back to an API-key-based embedder. In **integration tests** with `AI_TEAM_USE_REAL_LLM=1`, crew memory is forced off so tests do not depend on the embedding service; production behavior remains local-only.

To run **crew-level** integration tests (planning, development, testing) against **real Ollama** instead of mocks, set `AI_TEAM_USE_REAL_LLM=1`. Tests will skip if Ollama is unreachable and assert on structure only. Full-flow tests remain mock-only by design. For planning tests to pass (rather than skip), use models that return valid JSON and non-empty responses—**14B+ recommended**; smaller models (e.g. 7B–8B) may cause parse or empty-response skips.

```bash
AI_TEAM_USE_REAL_LLM=1 poetry run pytest tests/integration -m real_llm -v
```

Optional **memory/embedder** tests: run `./scripts/setup_ollama.sh`, then `AI_TEAM_USE_REAL_LLM=1 AI_TEAM_TEST_MEMORY=1 poetry run pytest tests/integration -m test_memory -v`.

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
└── scripts/             # setup_ollama.sh, test_models.py, run_demo.py
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
- **Ollama:** [ollama.com](https://ollama.com) — local LLM runtime.

This project is suitable for portfolios and demonstrations of multi-agent software development systems.
