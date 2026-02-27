# Getting Started with AI-Team

This guide walks you through prerequisites, installation, your first run, and common troubleshooting.

## Prerequisites checklist

- [ ] **Python 3.11 or 3.12** — Check with `python3 --version`.
- [ ] **Poetry** (or uv) — [Install Poetry](https://python-poetry.org/docs/#installation) or [uv](https://docs.astral.sh/uv/).
- [ ] **OpenRouter API key** — Get one at [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys); add to `.env` as `OPENROUTER_API_KEY`.

## Step-by-step installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/ai-team.git
cd ai-team
```

### 2. Create the project environment

```bash
poetry install
```

Or with uv:

```bash
uv sync
uv sync --extra dev   # for pytest, ruff, mypy, etc.
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:

- `OPENROUTER_API_KEY` — your key from https://openrouter.ai/settings/keys.
- Optional: `AI_TEAM_ENV=dev` (default), `test`, or `prod`.

### 4. Verify setup

```bash
# Quick test that the package runs
poetry run python -c "import ai_team; print('OK')"

# Run unit tests (no real LLM required)
poetry run pytest tests/unit -v
```

## First run walkthrough

1. **Ensure `OPENROUTER_API_KEY` is set** in `.env` (see Troubleshooting below if you see auth errors).

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

### OpenRouter not configured

**Symptom:** "OpenRouter not configured" or auth/401 errors.

**Fix:**

- Add `OPENROUTER_API_KEY=sk-or-v1-...` to `.env` (get a key at https://openrouter.ai/settings/keys).
- Ensure `OPENROUTER_API_BASE` is `https://openrouter.ai/api/v1` unless using a proxy.

### Model not found / does not exist

**Symptom:** Before the run starts, you see an error listing one or more model IDs that are "not available on OpenRouter".

**Fix:**

- Before each run, AI-Team checks that all configured OpenRouter models (LLM per role and the embedding model) exist. If any are missing, it fails immediately and lists the invalid model IDs.
- Set `OPENROUTER_EMBEDDING_MODEL` (or `MEMORY_EMBEDDING_MODEL`) to a valid OpenRouter embedding model (e.g. `openai/text-embedding-3-small`).
- Fix the model IDs for your `AI_TEAM_ENV` in `config/models.py` so they match models available on OpenRouter.

### ChromaDB: "Embedding function conflict: new: openai vs persisted: ollama"

**Symptom:** Memory search fails with `ValueError: An embedding function already exists in the collection configuration... new: openai vs persisted: ollama`.

**Cause:** ChromaDB data was created when the app used Ollama for embeddings. The app now uses OpenRouter/OpenAI; ChromaDB does not allow changing the embedding function on an existing collection.

**Fix:** Remove existing ChromaDB data so new collections use the current embedder.

1. **AI-Team short-term store** (if you use it): remove `./data/chroma` (or `MEMORY_CHROMADB_PATH` if set), e.g. `rm -rf ./data/chroma`.
2. **CrewAI’s internal RAG storage** (default): CrewAI stores Chroma in the app data directory. On macOS: `~/Library/Application Support/<project_dir_name>/` (project dir name is your current working directory name, or set `CREWAI_STORAGE_DIR`). Remove the ChromaDB files there: `chroma.sqlite3` and `chromadb-*.lock`. Example (macOS, project name `ai-team`):  
   `rm -f "$HOME/Library/Application Support/ai-team/chroma.sqlite3" "$HOME/Library/Application Support/ai-team/chromadb-"*.lock`

Back up first if you need to keep old memory data.

### OpenRouter 402: "This request requires more credits, or fewer max_tokens"

**Symptom:** `LLM Failed`, `OpenrouterException`, or `litellm.APIError` with message like "You requested up to 65536 tokens, but can only afford 11841".

**Cause:** Your OpenRouter API key has a per-request or total token limit. The app (or CrewAI/LiteLLM) is requesting more output tokens than your key allows.

**Fix:**

- **Increase key limit:** In [OpenRouter Settings](https://openrouter.ai/settings/keys), create or edit your key and raise the total limit so requests fit.
- **Lower max_tokens:** The app caps agent LLMs at 8192 tokens; if you still see 402, another component (e.g. CrewAI memory) may be using a higher default. Set a lower limit on your OpenRouter key so that even large defaults stay under the limit, or update your CrewAI version if it exposes max_tokens for memory.

### Model or rate limits

**Symptom:** Errors from OpenRouter about model or rate limits.

**Fix:**

- Use `AI_TEAM_ENV=dev` for cheaper/dev models; see `config/models.py` for tier model IDs.
- Check OpenRouter dashboard for usage and limits.

### Tests hang or time out

**Symptom:** `pytest` hangs, especially in `tests/integration` or `tests/e2e`.

**Fix:**

- Integration/e2e tests may call OpenRouter when `AI_TEAM_USE_REAL_LLM=1`; ensure `OPENROUTER_API_KEY` is set.
- Increase timeout: `poetry run pytest --timeout=60` (or set in `pyproject.toml`).
- Run only unit tests when developing: `poetry run pytest tests/unit`.

### Import or dependency errors

**Symptom:** `ModuleNotFoundError` or version conflicts.

**Fix:**

- Recreate the environment: `poetry install` (or `uv sync`).
- Ensure you are in the project directory and using the project's virtualenv: `poetry shell` then run commands, or always use `poetry run`.

---

For more detail on architecture, agents, and configuration, see [ARCHITECTURE.md](ARCHITECTURE.md), [AGENTS.md](AGENTS.md), and the main [README.md](../README.md).
