# AI-Team Demo Scenarios

Reproducible, screenshot-ready walkthroughs that show the AI-Team multi-agent
pipeline turning a plain-English brief into working, tested, deployable code.

Anyone who clones the repo should be able to follow a scenario end-to-end and get
the same result. Each scenario lists the exact brief, the commands for **all three
backends**, what to expect, and which web-UI stages to screenshot.

> New here? Read the 10-minute [Quickstart](#quickstart) first, run the
> [Smoke test](#scenario-1--smoke-test-calculator), then pick a real scenario.

---

## Scenario catalog

| # | Scenario | What it proves | Team profile | Backends | Time¹ |
|---|----------|----------------|--------------|----------|-------|
| 1 | [Smoke test — calculator](#scenario-1--smoke-test-calculator) | The pipeline runs end-to-end on minimum spend | `prototype` | all 3 | ~1–2 min |
| 2 | [To-do REST API + web UI (Dockerized)](#scenario-2--to-do-rest-api--web-ui-dockerized) | A real vertical slice: API + DB + UI, one command to run | `full` | all 3 | ~5–12 min |

¹ Wall-clock varies with model, network, and complexity. Smoke test is the cheapest possible run.

Each scenario lives in its own folder under `demos/` with a hand-authored brief
(`BUSINESS_USE_CASE.md`), the input spec (`input.json`), and an acceptance
contract (`expected_output.json`). Generated source lands in `output/` and is
git-ignored.

---

## Quickstart

### Prerequisites

| Need | Why | Check |
|------|-----|-------|
| Python 3.11+ | Runtime | `python --version` |
| uv | Dependency + script runner | `uv --version` |
| Node 18+ & npm | Web UI frontend | `node --version` |
| Docker | Scenario 2 builds/runs containers | `docker --version` |
| **One** LLM key | CrewAI/LangGraph use `OPENROUTER_API_KEY`; Claude Agent SDK uses `ANTHROPIC_API_KEY` | see `.env.example` |

```bash
git clone https://github.com/RickZee/ai-team.git
cd ai-team
cp .env.example .env          # then add your key(s)
uv sync
```

> **Pick your backend by the key you have.** Don't assume an OpenRouter key works
> for the Claude Agent SDK backend — it needs `ANTHROPIC_API_KEY` + the Claude Code
> runtime. (See `CLAUDE.md` → Backends.)

### Two ways to run every scenario

**A. CLI** — fastest, scriptable, no UI needed:

```bash
uv run python scripts/run_demo.py demos/00_smoke_test --skip-estimate
```

**B. Web UI** — the visual path, and the source of all screenshots in this guide:

```bash
# Terminal 1 — API (defaults to http://localhost:8421)
uv run ai-team-web

# Terminal 2 — frontend dev server (http://localhost:5173, proxies the API)
cd src/ai_team/ui/web/frontend && npm install && npm run dev
```

Open **http://localhost:5173**. Four tabs: **Dashboard** (live monitor),
**Run** (configure + start), **Compare** (3 backends side-by-side), **Artifacts**
(browse generated files).

> **About the "Launch Demo" button.** The Dashboard/Run **Demo** button plays a
> fixed *zero-cost simulation* of a generic Flask API — it does **not** read the
> scenario folders and writes **no files to disk**. Use it only to verify the UI
> renders. For real, reproducible per-scenario runs use the **Run** tab (or the CLI)
> and paste the scenario brief. See [Screenshot capture guide](SCREENSHOTS.md) for
> which path produces which screenshots.

---

## How to read each scenario

Every scenario below follows the same shape:

1. **Brief** — the exact natural-language spec (copy/paste into the Run tab).
2. **Run it** — CLI commands for **CrewAI**, **LangGraph**, and **Claude Agent SDK**.
3. **Expected output** — artifacts and the acceptance contract.
4. **Verify** — capture/lint/test/Docker checks.
5. **Try it (run the generated app)** — prove the output actually works.
6. **Screenshots** — the web-UI stages worth capturing (details in
   [SCREENSHOTS.md](SCREENSHOTS.md)).

---

## Scenario 1 — Smoke test (calculator)

**Folder:** `demos/00_smoke_test` · **Profile:** `prototype` (Architect + Fullstack + QA)

The cheapest possible run. Use it to confirm keys, routing, model access, tool
wiring, and workspace writes **before** spending budget on a real scenario. If this
passes, the pipeline works.

### Brief

> Write a single Python module `calc.py` exposing `add(a, b)`, `subtract(a, b)`,
> `multiply(a, b)`, and `divide(a, b)` (raising `ValueError` on divide-by-zero),
> with type hints and docstrings. Include `test_calc.py` with pytest cases covering
> each function and the divide-by-zero error. Output `calc.py` and `test_calc.py` only.

### Run it

```bash
# CrewAI (OPENROUTER_API_KEY)
uv run python scripts/run_demo.py demos/00_smoke_test --backend crewai --skip-estimate

# LangGraph (OPENROUTER_API_KEY)
uv run python scripts/run_demo.py demos/00_smoke_test --backend langgraph --skip-estimate

# Claude Agent SDK (ANTHROPIC_API_KEY + Claude Code runtime)
uv run python scripts/run_demo.py demos/00_smoke_test --backend claude-agent-sdk --skip-estimate
```

Add `--monitor` for a live Rich TUI in the terminal.

### Expected output

```
calc.py
test_calc.py
```

Acceptance (`expected_output.json`): `calc.py` defines all four functions,
`test_calc.py` has ≥1 test per function plus the divide-by-zero case, and
`pytest` exits 0.

### Verify

`run_demo.py` prints a result JSON and exits non-zero on failure. Check the output
against the acceptance contract in `expected_output.json`, then run the generated
tests directly (below).

### Try it

```bash
cd demos/00_smoke_test/output && python -m pytest -q
```

### Screenshots (web UI)

Run the brief via the **Run** tab (`prototype` profile), then capture:

1. **Run** tab — brief pasted, profile = `prototype`, backend selected.
2. **Dashboard** — phase pipeline at *Development*, Agents table, Activity log.
3. **Dashboard** — *Run summary* card on completion.

---

## Scenario 2 — To-do REST API + web UI (Dockerized)

**Folder:** `demos/02_todo_app` · **Profile:** `full`

A real vertical slice: REST backend + persistent storage + a simple browser UI,
all runnable with **one command**. This is the flagship end-to-end demo.

### Brief

> Build a full-stack TODO application.
> **Backend:** Flask REST API exposing `GET /health`, `GET /todos`, `POST /todos`
> (create), `PATCH /todos/{id}` (toggle complete), and `DELETE /todos/{id}`,
> persisting to SQLite so data survives restarts. Return JSON, validate input, and
> use proper status codes.
> **Frontend:** a single-page HTML/JS UI served by the app that lists todos and lets
> the user add, complete, and delete them via the API.
> **Packaging:** a `Dockerfile` and a `docker-compose.yml` so the whole stack starts
> with `docker compose up`. Include pytest API tests, `requirements.txt`, and a
> README with run instructions.

### Run it

```bash
# CrewAI
uv run python scripts/run_demo.py demos/02_todo_app --backend crewai --skip-estimate

# LangGraph
uv run python scripts/run_demo.py demos/02_todo_app --backend langgraph --skip-estimate

# Claude Agent SDK
uv run python scripts/run_demo.py demos/02_todo_app --backend claude-agent-sdk --skip-estimate
```

### Expected output

```
backend/ (or app.py)   Flask API + SQLite
frontend/              index.html + app.js (or templates/ + static/)
tests/                 pytest API tests
requirements.txt
Dockerfile
docker-compose.yml
README.md
```

Acceptance (`expected_output.json`): CRUD + health endpoints present, SQLite
persistence, a browser UI, `docker compose up` starts the stack, and tests pass.

### Verify

Check the generated tree against the acceptance contract in `expected_output.json`
(CRUD + health endpoints, SQLite persistence, a browser UI, a working
`docker compose up`, and passing tests), then exercise the app with the commands
under **Try it** below.

### Try it

```bash
cd demos/02_todo_app/output
docker compose up --build
# Check the generated README/compose for the published port (commonly 8000 or 5000),
# then open the UI and smoke the API (substitute the actual port):
open http://localhost:8000        # macOS  (xdg-open on Linux)
curl localhost:8000/health
curl -X POST localhost:8000/todos -H 'content-type: application/json' -d '{"title":"demo task"}'
curl localhost:8000/todos
```

### Screenshots (web UI)

Run the brief via the **Run** tab (`full` profile). Capture:

1. **Run** tab — brief pasted, `full` profile, backend chosen, **Estimate Cost** shown.
2. **Dashboard** — live: phase pipeline mid-*Development*, Agents, Metrics, Activity log.
3. **Dashboard** — *Run summary* card on completion.
4. **Artifacts → Files** — generated tree with `app.py`/`backend/`, `frontend/`, `Dockerfile`.
5. **Artifacts → Tests** — passing test panel.
6. **Artifacts → Architecture** — generated architecture panel.
7. **(Bonus)** the *running app* in a browser — the to-do UI with a couple of items.

---

## Compare backends on one brief

Any scenario brief can be run through all three backends at once to benchmark output
quality, cost, latency, and tokens.

**CLI:**

```bash
uv run python scripts/compare_backends.py demos/02_todo_app --env dev
uv run python scripts/compare_backends.py demos/02_todo_app --env dev --with-claude
```

**Web UI:** the **Compare** tab runs CrewAI + LangGraph + Claude Agent SDK in
parallel columns and highlights the best value per metric. Use **Compare Demo ($0)**
for a zero-cost simulated comparison, or **Run All Backends** for a real (paid)
3-way run — a pre-flight confirms the spend.

---

## Reproducibility checklist

- [ ] `.env` has the key matching your chosen backend (`OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`).
- [ ] `uv sync` completed without errors.
- [ ] Smoke test (Scenario 1) passes before running paid scenarios.
- [ ] For Scenario 2: Docker is running.
- [ ] You ran the brief from the **Run** tab (not the Demo button) for real artifacts.
- [ ] The generated `output/` meets `expected_output.json` (files present, tests pass).

---

## Adding a new scenario

1. Create `demos/NN_name/` (next sequential number).
2. Write `BUSINESS_USE_CASE.md` (problem, users, objectives, success criteria).
3. Write `input.json` (`project_name`, `description`, optional `team_profile` / `stack`).
4. Write `expected_output.json` (intended artifacts + one-line summary).
5. Run `scripts/run_demo.py demos/NN_name` to exercise the flow.
6. Verify the generated output in `demos/NN_name/output/` against `expected_output.json` (required files, tests, and any Docker/runtime checks).
7. Add a section here and (optionally) commit the generated `RESULTS.md` as a baseline.

See [SCREENSHOTS.md](SCREENSHOTS.md) for capturing clean, junk-free screenshots.
