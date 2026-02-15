# 🤖 AI-Team: Autonomous Multi-Agent Software Development

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CrewAI](https://img.shields.io/badge/CrewAI-0.80+-green.svg)](https://crewai.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Transform natural language requirements into production-ready code with a team of specialized AI agents.**

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **7 Specialized Agents** | Manager, Product Owner, Architect, Developers, DevOps, QA |
| 🔄 **Autonomous Workflow** | End-to-end code generation with minimal intervention |
| 🛡️ **Enterprise Guardrails** | Security, quality, and behavioral controls |
| 🏠 **Local-First** | Complete privacy with Ollama models—no API costs |
| 📊 **Observable** | Comprehensive logging and flow visualization |

## 🚀 Quick Start

```bash
# 1. Clone repository
git clone https://github.com/yourusername/ai-team.git
cd ai-team

# 2. Setup Ollama and models
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh

# 3. Install dependencies (uses Astral UV)
uv sync
uv sync --extra dev   # optional: pytest, ruff, etc.

# 4. Configure
cp .env.example .env
# Edit .env for your hardware

# 5. Run
uv run python -m ai_team.main "Create a REST API for a todo list"
```

## 🎭 Agent Roles

| Agent | Model Recommendation |
|-------|---------------------|
| **Manager** | `deepseek-r1:32b` / `qwen3:14b` (see [Hardware & model guide](docs/HARDWARE.md)) |
| **Product Owner** | `qwen3:32b` / `qwen2.5-coder:32b` |
| **Architect** | `qwen3:32b` / `qwen2.5-coder:32b` |
| **Backend Developer** | `qwen2.5-coder:32b` / `deepseek-coder-v2:33b` |
| **Frontend Developer** | `qwen2.5-coder:32b` |
| **DevOps Engineer** | `qwen2.5-coder:32b` |
| **QA Engineer** | `gemma3:27b` / `qwen2.5-coder:32b` |

See **[Hardware requirements & local LLM recommendations](docs/HARDWARE.md)** for role-specific models by hardware (M3 Pro 36 GB vs MacBook Air 24 GB) and optimization tips.

## 🛡️ Guardrails

### Behavioral
- Role adherence
- Scope control
- Reasoning enforcement

### Security
- Code safety checks
- PII redaction
- Secret detection
- Prompt injection protection

### Quality
- Syntax validation
- Completeness checks
- Output length control

<!-- Hardware & model recommendations moved to docs/HARDWARE.md -->

## 📁 Project Structure

```
ai-team/
├── src/ai_team/
│   ├── config/          # Settings
│   ├── agents/          # Agent implementations
│   ├── crews/           # Crew compositions
│   ├── flows/           # Flow orchestration
│   ├── tools/           # Agent tools
│   ├── guardrails/      # Guardrail implementations
│   └── utils/           # Utilities
├── tests/               # Test suites
├── demos/               # Example projects
└── scripts/             # Setup scripts
```

## 🧪 Testing

```bash
uv run pytest
uv run pytest --cov=src/ai_team
```

## 📄 License

MIT License - see [LICENSE](LICENSE)
