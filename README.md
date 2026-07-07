# AI-Team: Multi-Backend Agent Comparison Platform

[![CI](https://github.com/RickZee/ai-team/actions/workflows/ci.yml/badge.svg)](https://github.com/RickZee/ai-team/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**The same nine-agent software team, run through three orchestration frameworks —
CrewAI, LangGraph, Claude Agent SDK — side by side, with real cost and real failure
data.** Not a demo. An operational harness: a runtime smoke gate that catches "tests
pass, app 500s"; spend guards and subprocess isolation that survived a live 93,000-
iteration runaway and a GIL-starvation incident; guardrails calibrated from real
false-positive data. Every finding has a commit and a receipt in the
[engineering journal](docs/journal/README.md).

![AI-Team architecture — multi-backend agent pipeline with shared tools, guardrails, and workspace output](docs/images/architecture_diagram.svg)

## The headline result

A controlled experiment settles the question this project exists to ask: is a
comparison-tab failure a framework problem or a model problem? Same framework
(LangGraph), same brief, same guardrails — only the model changed.

![Same framework, same brief — deepseek wrote zero test suites in 3 runs, claude wrote them in all 4](docs/images/same-model-matrix.svg)

**deepseek wrote zero test files in 3/3 runs. Claude wrote real test suites in 4/4.**
The "framework failure" was a model property. Full data:
[COMPARISON_RESULTS.md](docs/COMPARISON_RESULTS.md). Full write-up:
[failure-taxonomy.md](docs/posts/failure-taxonomy.md) — ten failure classes across
model, framework, harness, and provider layers, each with a live trace and a shipped
fix.

## Quick start

```bash
git clone https://github.com/RickZee/ai-team.git && cd ai-team
cp .env.example .env        # add OPENROUTER_API_KEY (+ ANTHROPIC_API_KEY for the SDK backend)
uv sync                     # install deps (uv: https://astral.sh/uv)
bash scripts/quickstart.sh  # smoke-test every available backend, print a results table
```

Or drive the web dashboard directly:

```bash
uv run ai-team-web &                              # FastAPI on :8421
cd src/ai_team/ui/web/frontend && npm run dev      # React on :5173 (proxies API)
```

Open `http://localhost:5173/compare`, describe a project, click **Run All Backends** —
three orchestrators race the same brief, live. For step-by-step setup and
troubleshooting, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Orchestration backends

All three implement the same `Backend` protocol over the same tools, guardrails, and
workspace layout — swap at runtime with `--backend`.

| Backend | Status | Orchestration model | Notes |
|---|---|---|---|
| **[LangGraph](https://langchain-ai.github.io/langgraph/)** | Recommended | `StateGraph`, explicit conditional edges, checkpointing | Default for reliability + speed |
| **[Claude Agent SDK](https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk)** | Recommended | Nested subagents, native tool-calling | Most reliable end-to-end completion in the comparison data |
| **[CrewAI](https://crewai.com)** | Comparison-only | Crews + Flows (`@start`, `@listen`, `@router`) | Kept specifically *because* it surfaced real findings — see the journal |

```bash
uv run ai-team run "Build a REST API" --backend langgraph
uv run ai-team run "Build a REST API" --backend claude-agent-sdk
uv run ai-team run "Build a REST API" --backend crewai
```

CrewAI stays in the matrix on purpose — demoting a backend because it fails is a data
point, not a reason to hide it. See
[docs/posts/failure-taxonomy.md](docs/posts/failure-taxonomy.md) #2/#3 for what its
failures actually taught the harness.

## Team profiles

Not every project needs all nine agents. Select a profile with `--team`:

| Profile | Agents | Use case |
|---|---|---|
| `full` (default) | All 9 agents, all phases | Full software project |
| `full-claude` | All 9, pinned to `claude-sonnet-4` via OpenRouter | Same-model comparison runs |
| `backend-api` | Manager, PO, Architect, Backend Dev, QA, DevOps | REST API / microservice |
| `frontend-app` | Manager, PO, Architect, Frontend Dev, QA, DevOps | SPA / static site |
| `data-pipeline` | Manager, PO, Architect, Backend Dev, QA | ETL / data engineering |
| `prototype` | Architect, Fullstack Dev, QA | Minimal design → build → test |
| `infra-only` | Architect, DevOps, Cloud | IaC / CI-CD only |

Source: [`src/ai_team/config/team_profiles.yaml`](src/ai_team/config/team_profiles.yaml).

## What's actually in the harness

The comparison thesis only means something if the runs are honest. These are the
pieces that make them honest — every one of them earned its place by catching a real
bug, documented in the journal:

| Guardrail | Catches | Journal reference |
|---|---|---|
| **Runtime smoke gate** | "70/70 pytest green, app 500s on every request" — boots the real app, probes real HTTP, drives a create→read→update→delete round-trip | [docs/GUARDRAILS.md](docs/GUARDRAILS.md) |
| **Per-run spend guard** | Runaway retry loops that are also billing loops; scoped per-run (`contextvars`) so concurrent Compare runs don't share a budget | [COMPARISON_RESULTS.md](docs/COMPARISON_RESULTS.md) |
| **Subprocess isolation + hard kill** | A hung backend thread starving the GIL for every other backend in the same process (traced live: a 78-minute false report) | [docs/COMPARISON_RESULTS.md](docs/COMPARISON_RESULTS.md) |
| **Calibrated behavioral guardrails** | Lexical scope checks that flagged correct QA output for using test vocabulary — fixed from measured false-positive/true-negative distributions, not guessed thresholds | [failure-taxonomy.md](docs/posts/failure-taxonomy.md) #5 |
| **Flow-wiring regression test** | A CrewAI event-bus self-trigger bug that produced 93,284 runaway iterations in 15 minutes — a meta-test now fails the build if any flow method ever listens to its own name again | [failure-taxonomy.md](docs/posts/failure-taxonomy.md) #2 |
| **Atomic run-id allocation** | Concurrent Compare launches colliding on the same run id and workspace (a classic TOCTOU race) | [failure-taxonomy.md](docs/posts/failure-taxonomy.md) #4 |

Full behavioral/security/quality guardrail catalog: [docs/GUARDRAILS.md](docs/GUARDRAILS.md).

## Architecture

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                            Web Dashboard (FastAPI + React)                   │
│           /run · /compare · /artifacts   --backend <name>  --team <profile>  │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Backend Protocol (core/)                             │
│           run(description, team, env) → ProjectResult                       │
│           stream(description, team, env) → AsyncIterator[StreamEvent]        │
└──────┬───────────────────────┬───────────────────────┬───────────────────────┘
       ▼                       ▼                       ▼
┌──────────────┐   ┌───────────────────┐   ┌─────────────────────┐
│   CrewAI     │   │    LangGraph      │   │  Claude Agent SDK   │
│  subprocess- │   │  StateGraph+nodes │   │ Nested subagents    │
│  isolated,   │   │  conditional      │   │ session persistence │
│  hard-killed │   │  edges, subgraphs │   │ native tool calling │
│  on timeout  │   │  checkpointing    │   │                      │
└──────┬───────┘   └─────────┬─────────┘   └──────────┬──────────┘
       └─────────────────────┼────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  SHARED LAYERS                                                               │
│  Tools: file · code · git · test  │  Runtime smoke gate (real HTTP probes)   │
│  Guardrails: behavioral · security · quality  │  Per-run spend guard         │
│  Long-term memory + lessons (SQLite)  │  Team profiles                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full design.

## Demo projects

```bash
uv run python scripts/run_demo.py demos/00_smoke_test
uv run python scripts/run_demo.py demos/02_todo_app --skip-estimate
```

| Demo | Description |
|---|---|
| `00_smoke_test` | Trivial calculator + pytest — cheapest possible end-to-end pipeline check |
| `02_todo_app` | Full-stack TODO app — Flask + SQLite backend, HTML/JS frontend, Docker, pytest — the brief used in every comparison run above |

Each demo directory has `input.json` (the project spec) and `expected_output.json` (an
acceptance contract). See [docs/DEMOS.md](docs/DEMOS.md) for the full schema.

## Testing

```bash
uv run pytest                 # everything
uv run pytest tests/unit      # fast, no live API calls
uv run pytest tests/integration
```

The flow-wiring regression test — the one that guards against another 93,284-iteration
self-trigger loop — is worth running on its own after any change to `main_flow.py`:

```bash
uv run pytest tests/unit/flows/test_flow_wiring.py -q
```

To run against real OpenRouter (crew-level integration) instead of mocks:

```bash
AI_TEAM_USE_REAL_LLM=1 uv run pytest tests/integration -m real_llm -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for code style and PR requirements.

## Configuration reference

| Variable | Description | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key (CrewAI / LangGraph backends) | — |
| `ANTHROPIC_API_KEY` | Anthropic API key (Claude Agent SDK backend) | — |
| `AI_TEAM_ENV` | Model tier: `dev`, `test`, `prod` | `dev` |
| `AI_TEAM_BACKEND` | Default backend: `crewai`, `langgraph`, `claude-agent-sdk` | `crewai` |
| `AI_TEAM_RUN_BUDGET_USD` | Per-run spend ceiling before a non-retryable abort | `5.0` |
| `CREWAI_HARD_TIMEOUT_SECONDS` | Wall-clock kill deadline for the CrewAI subprocess | `900` |
| `AI_TEAM_LANGGRAPH_POSTGRES_URI` | Postgres URI for LangGraph checkpointing (optional) | SQLite |
| `GUARDRAIL_MAX_RETRIES` | Max guardrail retries | `3` |

Copy `.env.example` to `.env` and set the key for your chosen backend. Guardrail
behavior is documented in [docs/GUARDRAILS.md](docs/GUARDRAILS.md); agent→model
mapping lives in [`src/ai_team/config/agents.yaml`](src/ai_team/config/agents.yaml)
and [`models.py`](src/ai_team/config/models.py).

## Project structure

```
ai-team/
├── src/ai_team/
│   ├── core/                # Backend protocol, ProjectResult, TeamProfile loader, spend guard
│   ├── config/               # Settings, agents.yaml, team_profiles.yaml, models.py
│   ├── backends/
│   │   ├── registry.py       # Backend discovery and instantiation
│   │   ├── crewai_backend/   # CrewAI: subprocess-isolated, hard-killed on timeout
│   │   ├── langgraph_backend/  # LangGraph: graphs, nodes, routing, subgraphs
│   │   └── claude_agent_sdk_backend/  # Claude Agent SDK: orchestrator, subagents, MCP
│   ├── tools/                 # File, code, git, test tools, runtime smoke gate
│   ├── guardrails/            # Behavioral, security, quality
│   ├── memory/                 # Long-term memory (SQLite) + lessons loop
│   ├── monitor.py              # TeamMonitor — thread-safe event collector
│   └── ui/web/                 # FastAPI server + React/TypeScript/Vite dashboard
├── tests/
├── evals/                      # JSON scenario specs, LLM judge, backend eval suites
├── demos/                      # 00_smoke_test, 02_todo_app
├── docs/
│   ├── journal/                 # Session-by-session engineering record
│   ├── posts/                    # Failure taxonomy + individual write-ups
│   └── *.md                      # ARCHITECTURE, GUARDRAILS, DEMOS, EVALS, GETTING_STARTED
└── scripts/                      # quickstart, run_demo, compare_backends, pre_push_check
```

## Documentation

| Document | Description |
|---|---|
| [Engineering journal](docs/journal/README.md) | Session-by-session debugging record, including corrections |
| [Comparison results](docs/COMPARISON_RESULTS.md) | Live 3-way comparison data and the same-model matrix |
| [Failure taxonomy](docs/posts/failure-taxonomy.md) | Ten failure classes with receipts |
| [Troubleshooting](docs/troubleshooting/README.md) | Deep-dive post-mortems of non-obvious bugs |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [GUARDRAILS.md](docs/GUARDRAILS.md) | Behavioral, security, quality guardrails |
| [DEMOS.md](docs/DEMOS.md) | Demo projects, schema |
| [EVALS.md](docs/EVALS.md) | Eval methodology |
| [GETTING_STARTED.md](docs/GETTING_STARTED.md) | Setup, configuration, troubleshooting |

## License and acknowledgments

- **License:** [MIT](LICENSE).
- **[CrewAI](https://crewai.com)** — agent and crew framework.
- **[LangGraph](https://langchain-ai.github.io/langgraph/)** — graph-based agent orchestration.
- **[Claude Agent SDK](https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk)** — Anthropic's agent framework.
- **[OpenRouter](https://openrouter.ai)** — LLM API.
