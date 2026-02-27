# E2E Tests

End-to-end tests run a real AITeamFlow (no mocks) and require **OpenRouter** (OPENROUTER_API_KEY set).

## Running the Hello World E2E test

1. **Set `OPENROUTER_API_KEY`** in your environment or `.env` (get one at https://openrouter.ai/settings/keys).

2. Run the e2e test:
   ```bash
   poetry run pytest tests/e2e/test_e2e_hello_world.py -v -s
   ```

3. The test can take several minutes (full flow: planning → development → testing → deployment).

To skip e2e/slow tests in normal runs:
```bash
poetry run pytest -m "not e2e and not slow"
```
