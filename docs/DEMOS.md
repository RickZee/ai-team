# Demos

The `demos/` folder contains self-contained project scenarios used to exercise and validate the full `AITeamFlow` pipeline. Each demo provides a natural-language project spec as input; the system is expected to autonomously produce working, tested, deployable code as output.

> **Start here:** [demos/DEMO_SCENARIOS.md](../demos/DEMO_SCENARIOS.md) is the
> reproducible, screenshot-ready walkthrough for every scenario (all three backends).
> This page is the reference for the per-demo file layout and tooling.

---

## Demo catalog

| # | Directory | Team profile | Scope | Business use case |
| - | --------- | ------------ | ----- | ----------------- |
| 0 | `00_smoke_test` | `prototype` | **Setup validator** — calculator module (4 ops) + pytest; minimum token spend | [BUSINESS_USE_CASE.md](../demos/00_smoke_test/BUSINESS_USE_CASE.md) |
| 2 | `02_todo_app` | `full` | Full-stack TODO app — Flask REST API + SQLite, HTML/JS UI, Dockerized | [BUSINESS_USE_CASE.md](../demos/02_todo_app/BUSINESS_USE_CASE.md) |

> Folder numbers are kept stable for git history; `01_hello_world`, `03_data_pipeline`,
> and `04_ml_api` were retired to `.archive/demos-removed-2026-06-28/`.

Team profiles are documented in [TEAM_PROFILES.md](TEAM_PROFILES.md). Set `team_profile` in `input.json` or pass `--team` to `run_demo.py` / `compare_backends.py`.

---

## Per-demo file layout

```text
demos/NN_name/
  BUSINESS_USE_CASE.md   # Business context: problem, users, objectives, success criteria.
  input.json             # Required. Project spec fed to the flow.
  expected_output.json   # Recommended. Acceptance contract (status, artifacts, summary).
  output/                # Generated source files produced by the flow (git-ignored).
```

### Committed fixtures (checked in)

| File | Purpose | Who creates it |
| ---- | ------- | -------------- |
| `BUSINESS_USE_CASE.md` | Stakeholder-facing problem statement, personas, objectives, risks | Hand-authored |
| `input.json` | Project description, name, stack passed to `run_ai_team()` | Hand-authored |
| `expected_output.json` | High-level acceptance contract; documents intended artifacts and status | Hand-authored |

### Generated on run (not committed, git-ignored via `demos/.gitignore`)

| File / Dir | Purpose | Who creates it |
| ---------- | ------- | -------------- |
| `output/` | Generated source files (app.py, tests, Dockerfile, etc.) | `run_demo.py` / flow on success |
| `run_report.json` | Machine-readable run summary: duration, retries, phase, files generated | e2e test (`tests/e2e/`) on success |
| `failure_report.json` | Structured failure snapshot: exception type, message, phase, last agent output | e2e test (`tests/e2e/`) on failure |

> **Note:** generated run artifacts are intentionally ignored by default. If a
> demo result is meant for documentation, publish a curated summary rather than
> committing raw generated workspaces.

---

## `input.json` schema

```json
{
  "project_name": "snake_case_name",
  "description": "Full natural-language spec passed to the flow as the project description.",
  "team_profile": "prototype",
  "requirements": ["Flask", "pytest"],
  "stack": ["Flask", "SQLite", "HTML/JS"]
}
```

| Field | Required | Purpose |
| ----- | -------- | ------- |
| `project_name` | Recommended | Short id for logs and reports |
| `description` | Required* | Natural-language spec for the flow |
| `team_profile` | Optional | Profile key from `team_profiles.yaml` (default `full`; CLI `--team` overrides) |
| `requirements` | Optional | Python packages hint |
| `stack` | Optional | Technology labels |

\*Or `project_name` + `stack` if `description` is omitted.

`demo_input.py` reads `input.json` for `description` and `team_profile`. If `project_description.txt` exists it takes precedence for the description only — team profile still comes from `input.json` when present.

## `expected_output.json` schema

```json
{
  "status": "success",
  "artifacts": ["app.py", "tests/", "requirements.txt", "README.md", "Dockerfile"],
  "summary": "One-sentence description of what was produced."
}
```

No production code currently reads `expected_output.json` — it is documentation-level contract for human reviewers and future automated validators.

---

## Running a demo

```bash
# Validate setup first — cheapest profile-aware run (prototype crew via LangGraph)
uv run python scripts/run_demo.py demos/00_smoke_test --skip-estimate --backend langgraph

# Run a demo end-to-end (requires OPENROUTER_API_KEY in .env)
uv run python scripts/run_demo.py demos/02_todo_app

# Skip the cost-estimate prompt (useful in CI or scripted runs)
uv run python scripts/run_demo.py demos/02_todo_app --skip-estimate

# Optional: Rich CLI live monitor during the run
uv run python scripts/run_demo.py demos/00_smoke_test --monitor --backend langgraph

```

## Verifying demo output

After the flow completes and files are written to `output/`, verify the result
against the acceptance contract in `expected_output.json` (required artifacts,
status, and summary). For code demos, run the generated tests and, where the demo
ships a `Dockerfile`, build and smoke-test the container manually:

```bash
cd demos/02_todo_app/output
python -m pytest -q                 # generated test suite
docker compose up --build           # for Dockerized demos; then probe the API
```

`run_demo.py` exits non-zero if the flow itself fails; `expected_output.json` is the
human-facing acceptance contract (no production code reads it yet).

## Cross-backend comparison

Run the same demo spec through multiple backends and compare output quality, cost, latency, and token usage:

```bash
uv run python scripts/compare_backends.py demos/00_smoke_test --env dev
uv run python scripts/compare_backends.py demos/02_todo_app --team backend-api --markdown out.md
```

---

## Adding a new demo

1. Create `demos/NN_name/` (use the next sequential number).
2. Write `BUSINESS_USE_CASE.md` (problem, users, business objectives, success criteria).
3. Write `input.json` with `project_name`, `description`, and optionally `requirements` / `stack`.
4. Write `expected_output.json` documenting the intended artifacts and a one-line summary.
5. Run `scripts/run_demo.py demos/NN_name` to exercise the flow.
6. Verify `demos/NN_name/output/` against `expected_output.json` (required files, tests, and any Docker/runtime checks).
7. Commit `BUSINESS_USE_CASE.md`, `input.json`, and `expected_output.json` as the reference baseline.
