# Web Dashboard — User Journeys

The ai-team web UI is a FastAPI + React observability console for multi-agent runs. Four pages share one design system (GitHub-dark theme).

**UI parity:** `ai-team-tui` uses the same REST + WebSocket API when `ai-team-web` is running (run history, cancel/delete, HITL, compare, artifacts). The Rich CLI monitor (`--monitor`) shows the same live metrics during `ai-team run` but has no separate pages. Start the web server for full terminal parity: `ai-team-web &` then `ai-team-tui`.

## Pages

| Page | Route | Mode |
|------|-------|------|
| Dashboard | `/`, `/runs/:id` | **Operational** — live monitor, run history sidebar |
| Run | `/run` | **Launch** — configure, estimate, start; handoff to Dashboard |
| Compare | `/compare` | **Analytical** — parallel backends, summary table |
| Artifacts | `/artifacts?project=` | **Drill-down** — files, tests, architecture, download |

## Primary journeys

### 1. Zero-cost demo

1. Run or Dashboard → **Launch Demo**
2. Auto-navigate to `/runs/{id}`
3. Watch phase pipeline, agents, log, guardrails
4. On complete: **Run summary** card (demo runs have no disk artifacts)

### 2. Start a real run

1. **Run** → backend, profile, description → **Run**
2. Redirect to Dashboard when the run starts
3. Monitor via WebSocket until complete or HITL pause
4. **Run summary** → View artifacts / start another run

### 3. Human-in-the-loop (LangGraph)

1. Run pauses with **Human review required**
2. Structured context (phase, reason) + presets (Approve / Request changes / Reject)
3. **Submit & Resume** → `POST /api/runs/{id}/resume`
4. Compare columns can each show their own HITL panel

### 4. Compare backends

1. **Compare** → description → optional **Estimate Cost** (×3 total shown)
2. **Run All Backends** → pre-flight confirms 3 paid runs (skippable for 24h via session)
3. Or **Compare Demo ($0)** — three demo monitors, no LLM
4. Summary table highlights best value per metric

### 5. Browse artifacts

1. **Artifacts** or Dashboard link → unified run picker (session + disk registry)
2. Files / Tests / Architecture / Download tabs
3. Code viewer: highlight search, markdown preview for `.md`

## Command palette

Press **⌘K** (Ctrl+K on Windows/Linux) to jump to pages, launch demo, or open recent runs.

## API reference (artifact + monitor)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/registry/runs` | Disk-backed runs |
| `GET /api/projects/{id}/tree` | File tree (`root=workspace\|bundle`) |
| `GET /api/projects/{id}/file` | File content |
| `GET /api/projects/{id}/tests` | Test results panel |
| `GET /api/projects/{id}/architecture` | Architecture panel |
| `GET /api/projects/{id}/download.zip` | Workspace ZIP |

Monitor WebSocket payloads may include `token_estimate`, `cost_usd`, and `session_id` when the backend reports them.

## Known limitations

- **Demo runs** do not write workspace/bundle files — Artifacts shows an explanatory empty state.
- **In-memory runs** (`GET /api/runs`) are lost on server restart; disk registry persists separately.
- **Web default backend** is LangGraph; CLI default may differ (`crewai`) — set explicitly per run.

## UX design notes (2025–2026 trends applied)

- **Calm dashboard**: collapsible guardrails during live runs; sticky phase header
- **Progressive disclosure**: summary hub before full Artifacts browser
- **Agentic status**: phase-aware copy, model column, `awaiting_human` in pipeline
- **Trust**: cost pre-flight for compare, estimate budget warning on Run
- **Power users**: command palette, log filters, search highlight in code viewer
