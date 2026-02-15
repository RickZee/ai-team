# AI-Team: Autonomous Multi-Agent Software Development

[![CI](https://github.com/yourusername/ai-team/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/ai-team/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-pytest--cov-informational)](https://github.com/yourusername/ai-team)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Transform natural language requirements into production-ready code with a team of specialized AI agents. Built on [CrewAI](https://crewai.com) with local-first Ollama models.

## Project description

AI-Team is an autonomous multi-agent system that orchestrates planning, development, testing, and deployment. You describe what you want in plain language; the system produces requirements, architecture, code, tests, and deployment artifacts with minimal human intervention. All agents run against local LLMs via Ollama—no cloud API keys or usage costs.

### Key features

| Feature | Description |
|---------|-------------|
| **Specialized agents** | Manager, Product Owner, Architect, Backend/Frontend/Fullstack Developers, DevOps, Cloud, QA |
| **End-to-end workflow** | Intake → Planning → Development → Testing → Deployment, driven by a single flow |
| **Enterprise guardrails** | Behavioral (role, scope), security (code safety, PII, secrets), quality (syntax, completeness) |
| **Local-first** | Ollama-backed models; optional cloud LLMs via configuration |
| **Observable** | Structured logging, flow state, and optional Gradio UI for progress and output |

## Architecture (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           FLOW LAYER (Orchestration)                             │
│  AITeamFlow: intake → planning → development → testing → deployment → finalize   │
│  ProjectState (Pydantic); @start, @listen, @router                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
┌───────────────┐             ┌───────────────┐             ┌───────────────┐
│ PlanningCrew  │             │DevelopmentCrew│             │ TestingCrew   │
│ DeploymentCrew│             │ (Manager +    │             │ (QA + tools)  │
│ (Manager, PO,  │             │  Dev agents) │             │               │
│  Architect)   │             │               │             │               │
└───────┬───────┘             └───────┬───────┘             └───────┬───────┘
        │                             │                             │
        └─────────────────────────────┼─────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  TOOL LAYER: file (read/write/list) · code (gen/review/sandbox) · git · test    │
└─────────────────────────────────────────────────────────────────────────────────┘
        │
┌───────┴───────────────────────────────────────────────────────────────────────┐
│  GUARDRAILS (behavioral, security, quality)  │  MEMORY (session + long-term)   │
└──────────────────────────────────────────────┴─────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full design.

## Quick start (3 commands)

```bash
git clone https://github.com/yourusername/ai-team.git && cd ai-team
./scripts/setup_ollama.sh    # Install Ollama and pull recommended models
cp .env.example .env && poetry install && poetry run ai-team "Create a REST API for a todo list"
```

For step-by-step setup and troubleshooting, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Configuration reference

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama API base URL | `http://localhost:11434` |
| `*_MODEL` (e.g. `MANAGER_MODEL`) | Per-role Ollama model name | Role default from settings |
| `GUARDRAIL_MAX_RETRIES` | Max guardrail retries | `3` |
| `CODE_QUALITY_MIN_SCORE` | Min quality score (0–1) | `0.7` |
| `TEST_COVERAGE_MIN` | Min test coverage (0–1) | `0.6` |
| `MAX_FILE_SIZE_KB` | Max file size for tools (KB) | `500` |
| `GRADIO_SERVER_PORT` | Gradio UI port | `7860` |

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
