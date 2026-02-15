# Prompt 1.3: Generate Dockerfile

**Source:** PROJECT_PLAN_OPUS_4_5.md — Phase 1 (Repository Setup & Environment)

---

Create a multi-stage Dockerfile that:
1. Uses Python 3.11-slim base
2. Installs system deps (git, build-essential)
3. Uses [Astral UV](https://docs.astral.sh/uv/) for dependency management
4. Creates non-root user
5. Optimizes for caching and small size
6. Exposes Gradio port 8501
