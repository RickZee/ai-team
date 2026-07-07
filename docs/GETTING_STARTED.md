# Getting Started with AI-Team

This guide walks you through prerequisites, installation, your first run, and common troubleshooting.

## Prerequisites checklist

- [ ] **Python 3.11 or 3.12** — Check with `python3 --version`.
- [ ] **uv** — [Install uv](https://docs.astral.sh/uv/getting-started/installation/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- [ ] **OpenRouter API key** — Get one at [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys); add to `.env` as `OPENROUTER_API_KEY`.

## Step-by-step installation

### 1. Clone the repository

```bash
git clone https://github.com/RickZee/ai-team.git
cd ai-team
```

### 2. Create the project environment

```bash
uv sync
```

This creates `.venv` and installs runtime + dev dependencies from `uv.lock`.

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set the key for the backend you plan to run:

- `OPENROUTER_API_KEY` — your key from [OpenRouter settings](https://openrouter.ai/settings/keys).
- `ANTHROPIC_API_KEY` — optional; required only for the Claude Agent SDK backend.
- Optional: `AI_TEAM_ENV=dev` (default), `test`, or `prod`.

### 4. Verify setup

```bash
# Quick test that the package runs
uv run python -c "import ai_team; print('OK')"

# Run unit tests (no real LLM required)
uv run pytest tests/unit -v
```

## First run walkthrough

1. **Ensure `OPENROUTER_API_KEY` is set** in `.env` (see Troubleshooting below if you see auth errors).

2. **Run the CLI** with a short prompt:

   ```bash
   uv run ai-team run "Create a minimal Hello World Flask API"
   ```

   Or use the module entry point:

   ```bash
   uv run python -m ai_team.main run "Create a minimal Hello World Flask API"
   ```

3. **Optional: run the web dashboard**

   ```bash
   uv run ai-team-web   # FastAPI on http://127.0.0.1:8421
   cd src/ai_team/ui/web/frontend && npm run dev   # React on :5173 (proxies API)
   ```

4. **Run a demo**:

   ```bash
   uv run python scripts/run_demo.py demos/00_smoke_test --skip-estimate --backend langgraph
   ```

5. **Smoke-test all backends** (optional):

   ```bash
   bash scripts/quickstart.sh
   ```

## Deleting old runs

Runs accumulate under `workspace/<run_id>/` and `output/runs/<run_id>/`. To remove a run as a unit (workspace, artifact bundle, and registry entry):

```python
from ai_team.core.results import delete_run

result = delete_run("my-run-id")
print(result.existed, result.workspace_deleted, result.bundle_deleted)
```

- **Idempotent** — safe to call on a run that is already gone.
- **Cancel is not delete** — stopping a run via the Dashboard (`POST /api/runs/{id}/cancel`) does not remove its files.

If you use the web dashboard and want to drop a finished run from the in-memory sidebar (without restarting the server), call `RunState.remove_run(run_id)` on a terminal run (`complete`, `error`, or `cancelled`) after `delete_run()`.

REST `DELETE /api/runs/{id}` and a CLI `clean` subcommand are not implemented yet.
Full detail: [README — Managing runs](../README.md#managing-runs).

## Troubleshooting common issues

### OpenRouter not configured

**Symptom:** "OpenRouter not configured" or auth/401 errors.

**Fix:**

- Add `OPENROUTER_API_KEY=sk-or-v1-...` to `.env` (get a key at [OpenRouter settings](https://openrouter.ai/settings/keys)).
- Ensure `OPENROUTER_API_BASE` is `https://openrouter.ai/api/v1` unless using a proxy.

### Model not found / does not exist

**Symptom:** Before the run starts, you see an error listing one or more model IDs that are "not available on OpenRouter".

**Fix:**

- Before each run, AI-Team checks that all configured OpenRouter models (LLM per role and the embedding model) exist. If any are missing, it fails immediately and lists the invalid model IDs.
- Set `OPENROUTER_EMBEDDING_MODEL` (or `MEMORY_EMBEDDING_MODEL`) to a valid OpenRouter embedding model (e.g. `openai/text-embedding-3-small`).
- Fix the model IDs for your `AI_TEAM_ENV` in `src/ai_team/config/models.py` so they match models available on OpenRouter.

### ChromaDB: "Embedding function conflict" (CrewAI backend only)

**Symptom:** Memory search fails with `ValueError: An embedding function already exists in the collection configuration... new: openai vs persisted: ollama`.

**Cause:** CrewAI internal RAG storage was created when embeddings used a different provider. AI-Team no longer maintains a project-level Chroma short-term store (`memory_config.py` uses SQLite long-term memory + lessons).

**Fix:** Remove CrewAI Chroma files in the app data directory. On macOS: `~/Library/Application Support/<project_dir_name>/` (or set `CREWAI_STORAGE_DIR`). Remove `chroma.sqlite3` and `chromadb-*.lock`. Example:

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

- Use `AI_TEAM_ENV=dev` for cheaper/dev models; see `src/ai_team/config/models.py` for tier model IDs.
- Check OpenRouter dashboard for usage and limits.

### Tests hang or time out

**Symptom:** `pytest` hangs, especially in `tests/integration` or `tests/e2e`.

**Fix:**

- Integration/e2e tests may call OpenRouter when `AI_TEAM_USE_REAL_LLM=1`; ensure `OPENROUTER_API_KEY` is set.
- Increase timeout: `uv run pytest --timeout=60` (or set in `pyproject.toml`).
- Run only unit tests when developing: `uv run pytest tests/unit`.

### Import or dependency errors

**Symptom:** `ModuleNotFoundError` or version conflicts.

**Fix:**

- Recreate the environment: `uv sync`.
- Ensure you are in the project directory and use `uv run <command>` (or `source .venv/bin/activate` then run commands directly).

---

For more detail on architecture and configuration, see [ARCHITECTURE.md](ARCHITECTURE.md), [GUARDRAILS.md](GUARDRAILS.md), [troubleshooting/README.md](troubleshooting/README.md), and the main [README.md](../README.md).
