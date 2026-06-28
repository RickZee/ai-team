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
| 3 | [Microservices system](#scenario-3--microservices-system) | Agent coordination across service boundaries | `full` | all 3 | ~8–20 min |
| 4 | [AutoOptimizer loop (Karpathy)](#scenario-4--autooptimizer-loop-karpathy) | A governed edit→measure→keep/revert loop with a budget | `research-optimizer` | claude-agent-sdk | ~5–15 min |

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
| Docker | Scenarios 2 & 3 build/run containers | `docker --version` |
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

```bash
uv run python scripts/capture_demo.py \
  --output-dir demos/00_smoke_test/output \
  --demo-id 00_smoke_test --skip-docker
```

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
all runnable with **one command**. This is the flagship "agents replaced a short
contractor engagement" demo, and the optimization target for Scenario 4.

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

```bash
uv run python scripts/capture_demo.py \
  --output-dir demos/02_todo_app/output --demo-id 02_todo_app
```

`capture_demo.py` runs, in order: required-file check → pytest (≥80% coverage) →
ruff (fails >50 violations) → Docker build → container smoke test (health + CRUD).
It stops at the first failure.

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

## Scenario 3 — Microservices system

**Folder:** `demos/05_microservices` · **Profile:** `full`

The highest-complexity scenario. It tests whether agents can produce a coherent
**multi-service** layout — not just one API — with a single public entry point and
independently deployable services, using current best practices.

### Brief

> Build a microservices system with three Flask services and a single public entry
> point.
> **API Gateway** (port 8080) routes requests to the internal services and is the
> only port exposed to clients.
> **User Service** (port 5001) owns user data — CRUD backed by SQLite.
> **Notification Service** (port 5002) sends notifications via a mock SMTP client and
> can change without touching user code.
> Services communicate over HTTP. Apply current best practices: per-service
> `Dockerfile` and `requirements.txt`, health-check endpoints, environment-based
> config (no hardcoded hosts/secrets), structured logging, graceful error handling
> on inter-service calls, and pytest unit tests per service. Provide a
> `docker-compose.yml` that orchestrates all three locally and a README.

### Run it

```bash
# CrewAI
uv run python scripts/run_demo.py demos/05_microservices --backend crewai --skip-estimate

# LangGraph
uv run python scripts/run_demo.py demos/05_microservices --backend langgraph --skip-estimate

# Claude Agent SDK
uv run python scripts/run_demo.py demos/05_microservices --backend claude-agent-sdk --skip-estimate
```

### Expected output

```
gateway/               Flask gateway, Dockerfile, requirements.txt, tests
user_service/          Flask CRUD + SQLite, Dockerfile, requirements.txt, tests
notification_service/  Flask + mock SMTP, Dockerfile, requirements.txt, tests
docker-compose.yml     orchestrates all three
README.md
```

Acceptance (`expected_output.json`): three services with clear boundaries, gateway
as the only public port, HTTP inter-service calls, health checks, per-service tests,
and a working compose file.

### Verify

```bash
uv run python scripts/capture_demo.py \
  --output-dir demos/05_microservices/output --demo-id 05_microservices
```

### Try it

```bash
cd demos/05_microservices/output
docker compose up --build
# everything routes through the gateway (8080); internal ports stay internal:
curl localhost:8080/health
curl -X POST localhost:8080/users -H 'content-type: application/json' \
  -d '{"name":"Ada","email":"ada@example.com"}'
curl localhost:8080/users
```

### Screenshots (web UI)

Run the brief via the **Run** tab (`full` profile). Capture:

1. **Run** tab — brief pasted (note the multi-service spec), `full` profile.
2. **Dashboard** — live pipeline with multiple agents active during *Development*.
3. **Dashboard** — Guardrails panel (expanded) showing security/quality checks.
4. **Dashboard** — *Run summary* card.
5. **Artifacts → Files** — three service folders + `docker-compose.yml`.
6. **Artifacts → Architecture** — service-boundary view.
7. **Compare** (optional) — same brief across all three backends, summary table.

---

## Scenario 4 — AutoOptimizer loop (Karpathy)

**Folder:** `demos/06_karpathy_optimization` · **Profile:** `research-optimizer`
· **Backend:** `claude-agent-sdk`

A governed, budgeted **edit → run → measure → keep/revert** loop that optimizes an
existing codebase one change at a time, logging every experiment and injecting prior
lessons via RAG. It optimizes the **Scenario 2 to-do app**, so build that first.

### Run it

```bash
# 1. Build the optimization target (Scenario 2) if you haven't:
uv run python scripts/run_demo.py demos/02_todo_app --backend claude-agent-sdk --skip-estimate

# 2. Run the optimizer against that workspace:
ai-team optimize ./demos/02_todo_app/output \
  --metric demos/06_karpathy_optimization/metric.yaml \
  --strategy demos/06_karpathy_optimization/strategy.md \
  --backend claude-agent-sdk \
  --budget 2.00 \
  --max-experiments 10
```

### Expected output

Experiments are appended to the target workspace at `logs/experiments.jsonl`.
Acceptance (`expected_output.json`): at least one experiment runs, no regression to
the API contract or test suite, and each experiment is logged. Positive movement on
the target metric (`test_pass_rate`) when infra supports it.

The scenario ships with `metric.yaml` (the `test_pass_rate` metric via pytest),
`strategy.md` (prioritized optimization hints), and `input.json` (workspace
description).

### Screenshots

This scenario is CLI-driven. Capture the terminal showing budget/experiment counters
and the tail of `logs/experiments.jsonl` (keep/revert decisions). See
[SCREENSHOTS.md](SCREENSHOTS.md) → *CLI captures*.

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
- [ ] For Scenarios 2 & 3: Docker is running.
- [ ] You ran the brief from the **Run** tab (not the Demo button) for real artifacts.
- [ ] `capture_demo.py` reports green for the scenario you ran.

---

## Adding a new scenario

1. Create `demos/NN_name/` (next sequential number).
2. Write `BUSINESS_USE_CASE.md` (problem, users, objectives, success criteria).
3. Write `input.json` (`project_name`, `description`, optional `team_profile` / `stack`).
4. Write `expected_output.json` (intended artifacts + one-line summary).
5. Run `scripts/run_demo.py demos/NN_name` to exercise the flow.
6. Run `scripts/capture_demo.py --output-dir demos/NN_name/output --demo-id NN_name` to verify.
7. Add a section here and (optionally) commit the generated `RESULTS.md` as a baseline.

See [SCREENSHOTS.md](SCREENSHOTS.md) for capturing clean, junk-free screenshots and
[../docs/UX_REVIEW.md](../docs/UX_REVIEW.md) for the web-UI design notes.
