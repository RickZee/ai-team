# Getting Started with AI-Team

This guide walks you through prerequisites, installation, your first run, and common troubleshooting.

## Prerequisites checklist

- [ ] **Python 3.11 or 3.12** — Check with `python3 --version`.
- [ ] **Poetry** (or uv) — [Install Poetry](https://python-poetry.org/docs/#installation) or [uv](https://docs.astral.sh/uv/).
- [ ] **Ollama** (for local LLMs) — [Install Ollama](https://ollama.com) and ensure it is running.
- [ ] **Enough disk space** — Model pulls can be several GB per model; see [scripts/setup_ollama.sh](scripts/setup_ollama.sh) for recommended models.
- [ ] **Optional:** Adequate RAM/VRAM for your chosen models (see [Hardware & model guide](HARDWARE.md) if present, or the setup script).

## Step-by-step installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/ai-team.git
cd ai-team
```

### 2. Install Ollama and pull models

```bash
chmod +x scripts/setup_ollama.sh
./scripts/setup_ollama.sh
```

The script can install Ollama if missing, start the service, and pull recommended models (e.g. qwen3, qwen2.5-coder, deepseek-r1, deepseek-coder-v2). Use `--small` for smaller variants (e.g. 14B) if you have limited VRAM/RAM.

### 3. Create the project environment

```bash
poetry install
```

Or with uv:

```bash
uv sync
uv sync --extra dev   # for pytest, ruff, mypy, etc.
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `OLLAMA_BASE_URL` — usually `http://localhost:11434`.
- Optional: per-role models (e.g. `MANAGER_MODEL`, `BACKEND_DEV_MODEL`) if you want to override defaults.

### 5. Verify setup

```bash
# Quick test that the package runs
poetry run python -c "import ai_team; print('OK')"

# Run tests (no Ollama required for unit tests)
poetry run pytest tests/unit -v
```

## First run walkthrough

1. **Ensure Ollama is running** and the models you need are pulled (see Troubleshooting below).

2. **Run the CLI** with a short prompt:
   ```bash
   poetry run ai-team "Create a minimal Hello World Flask API"
   ```
   Or use the entry point:
   ```bash
   poetry run python -m ai_team.main "Create a minimal Hello World Flask API"
   ```

3. **Optional: run the Gradio UI**
   ```bash
   poetry run ai-team-ui
   ```
   Then open the URL shown (default `http://127.0.0.1:7860`).

4. **Run a demo** (when the flow is wired to the demo runner):
   ```bash
   python scripts/run_demo.py demos/01_hello_world
   ```

## Troubleshooting common issues

### Ollama not running

**Symptom:** Connection errors to `http://localhost:11434` or “Ollama not available”.

**Fix:**

- Start Ollama: `ollama serve` (or start the Ollama app on macOS/Windows).
- Check: `curl http://localhost:11434/api/tags` should return a JSON list of models.
- If you use a remote Ollama host, set `OLLAMA_BASE_URL` in `.env` to that URL.

### Model not found

**Symptom:** Errors like “model not found” or “model XYZ is not available”.

**Fix:**

- List models: `ollama list`.
- Pull the model: `ollama pull <model_name>` (e.g. `ollama pull qwen2.5-coder:7b`).
- In `.env`, set the role-specific variable to a model you have (e.g. `BACKEND_DEV_MODEL=qwen2.5-coder:7b`).
- Ensure the model name in config matches exactly (including tag, e.g. `:7b` or `:32b`).

### VRAM / out-of-memory errors

**Symptom:** Ollama or the app fails with OOM or GPU memory errors.

**Fix:**

- Use smaller models: run `scripts/setup_ollama.sh --small` to pull 14B (or smaller) variants.
- In `.env`, assign lighter models to each role (e.g. 7B or 14B instead of 32B).
- Close other GPU-heavy applications.
- If you have only CPU, prefer smaller models and expect slower runs; see [docs/HARDWARE.md](HARDWARE.md) if available for hardware-specific notes.

### Tests hang or time out

**Symptom:** `pytest` hangs, especially in `tests/integration` or `tests/e2e`.

**Fix:**

- Integration/e2e tests may call Ollama; ensure Ollama is running and the required model is pulled.
- Increase timeout: `poetry run pytest --timeout=60` (or set in `pyproject.toml`).
- Run only unit tests when developing: `poetry run pytest tests/unit`.

### Import or dependency errors

**Symptom:** `ModuleNotFoundError` or version conflicts.

**Fix:**

- Recreate the environment: `poetry install` (or `uv sync`).
- Ensure you are in the project directory and using the project’s virtualenv: `poetry shell` then run commands, or always use `poetry run`.

---

For more detail on architecture, agents, and configuration, see [ARCHITECTURE.md](ARCHITECTURE.md), [AGENTS.md](AGENTS.md), and the main [README.md](../README.md).
