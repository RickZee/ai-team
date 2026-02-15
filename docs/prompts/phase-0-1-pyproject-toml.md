# Prompt 0.1: Generate pyproject.toml (UV / PEP 621)

**Source:** PROJECT_PLAN_OPUS_4_5.md — Phase 0 (Preparation & Research)

---

Create a pyproject.toml for a CrewAI multi-agent project using [Astral UV](https://docs.astral.sh/uv/) (PEP 621 `[project]` format). Dependencies:
- crewai>=0.80.0
- crewai-tools
- langchain-ollama
- pydantic>=2.0
- gradio
- python-dotenv
- structlog
- pytest
- pytest-asyncio

Include optional dev dependencies for testing and linting. Use `uv add <pkg>` to add packages; lockfile is uv.lock.
