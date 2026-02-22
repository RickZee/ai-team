# E2E Tests

End-to-end tests run a real AITeamFlow (no mocks) and require **Ollama** to be running locally.

## Running the Hello World E2E test

1. **Start Ollama** and pull the models used by ai-team (see project docs or `config/settings.py`), e.g.:
   - `qwen3:14b`
   - `deepseek-r1:14b`
   - `deepseek-coder-v2:16b`
   - `qwen2.5-coder:14b`

2. **Unset `OPENAI_API_KEY`** for the test run so all CrewAI LLM paths use Ollama:
   ```bash
   unset OPENAI_API_KEY
   poetry run pytest tests/e2e/test_e2e_hello_world.py -v -s
   ```

3. The test can take several minutes (full flow: planning → development → testing → deployment).

To skip e2e/slow tests in normal runs:
```bash
poetry run pytest -m "not e2e and not slow"
```
