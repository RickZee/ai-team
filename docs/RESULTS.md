# Results bundle (org-grade artifacts)

Each `ai-team` run produces:

- An **isolated working directory**: `workspace/<project_id>/`
- A **self-contained immutable results bundle**: `output/<project_id>/`

This is designed to mirror a real engineering organization: requirements, architecture, decisions, code, tests, QA reports, deployment artifacts, and traceability are all preserved per run.

## Directory layout

```text
workspace/
└── <project_id>/
    ├── src/                      # generated source (or app root, per project)
    ├── tests/                    # generated tests
    ├── infra/                    # optional IaC
    └── ...                       # additional project files

output/
└── <project_id>/
    ├── run.json                  # run metadata (backend, team, env, models, CLI args)
    ├── state.json                # final state (CrewAI ProjectState or LangGraphProjectState)
    ├── events.jsonl              # streaming events / monitor updates (append-only)
    ├── artifacts/
    │   ├── intake/               # validated prompt, flags, risk notes
    │   ├── planning/             # requirements + architecture + ADRs
    │   ├── development/          # file manifest + patch/diff + hashes
    │   ├── testing/              # test and coverage reports
    │   └── deployment/           # Docker/CI/IaC and ops docs
    ├── reports/
    │   ├── scorecard.json        # guardrails + quality gates summary
    │   └── summary.md            # human-readable execution summary
    └── logs/                     # optional (copied or linked subset)
```

## `run.json`

Required fields:

- `project_id`
- `backend` (`crewai` | `langgraph` | ...)
- `team_profile`
- `env` (`dev` | `test` | `prod`)
- `started_at`, `completed_at`
- `workspace_dir`, `output_dir`
- `models` (role → model id), when available
- `argv` (CLI args, redacted when needed)

## `state.json`

The serialized final state for the backend:

- CrewAI: `ProjectState`
- LangGraph: `LangGraphProjectState`

This is the canonical machine-readable summary of the run outcome.

## `events.jsonl`

Append-only JSON Lines stream of state updates and notable events (phase changes, guardrail outcomes, tool calls). This is designed for later replay/debugging.

## Development manifest

`output/<project_id>/artifacts/development/code_manifest.json` records each generated file:

- `path` (relative to `workspace/<project_id>/`)
- `sha256`
- `bytes`
- `phase`
- `agent_role`
- `timestamp`

If a baseline exists, `diff.patch` can be generated for reproducible review.

