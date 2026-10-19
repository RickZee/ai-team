# Results bundle (org-grade artifacts)

This document describes the per-run workspace and output bundle layout — not
benchmark scores. Dated measurements live in [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md)
and [PERFORMANCE.md](PERFORMANCE.md).

Each `ai-team` run produces:

- An **isolated working directory**: `workspace/<project_id>/`
- A **self-contained immutable results bundle**: `output/runs/<project_id>/`

This is designed to mirror a real engineering organization: requirements, architecture, decisions, code, tests, QA reports, deployment artifacts, and traceability are all preserved per run.

## Directory layout

Both folders use the same run id, for example
`2026-10-19_102648_write-a-single-python-module_01` (`core/run_naming.py`).

```text
workspace/
└── <project_id>/                 # created by core/workspace_layout.py
    ├── docs/                     # brief, requirements, architecture, contracts/
    │   ├── CONSTRAINTS.md        # pinned constraints (harness-owned, never summarized)
    │   ├── STATE.md              # last N phase facts (harness-owned)
    │   ├── LESSONS.md            # rendered from the lesson store
    │   ├── lessons.jsonl         # structured lesson records
    │   └── qa_verdicts.jsonl     # one record per item per QA pass
    ├── src/                      # generated source
    ├── tests/                    # generated tests
    ├── infrastructure/           # optional IaC
    ├── .github/workflows/        # optional CI
    ├── .harness/drafts/          # ToolBus writes waiting for commit_write
    └── logs/
        ├── audit.jsonl           # every ToolBus call
        ├── journal.jsonl         # ToolBus allow/deny decisions
        ├── phases.jsonl          # phase transitions
        ├── costs.jsonl           # spend rows
        ├── harness_acceptance.json
        └── session.json, reasoning.jsonl   # Claude Agent SDK only

output/
├── index.json                    # registry of runs (rebuilt on finalize)
├── latest                        # link to the newest run
└── runs/
    └── <project_id>/
        ├── run.json              # run metadata (backend, team, env, models, CLI args)
        ├── state.json            # final state (CrewAI ProjectState or LangGraphProjectState)
        ├── receipt.json          # source of truth for cost, files, tests and smoke
        ├── receipt.md            # the same, for people
        ├── events.jsonl          # streamed events, when the backend streams (append-only)
        ├── artifacts/
        │   ├── intake/
        │   ├── planning/         # requirements.json, architecture.json
        │   ├── development/      # code_manifest.json
        │   ├── testing/          # test_results.json, pytest.txt, ruff.txt
        │   └── deployment/
        ├── reports/
        │   ├── scorecard.json    # guardrails + quality gates summary
        │   ├── summary.md        # human-readable summary (CrewAI)
        │   └── manager_self_improvement_report.{json,md}
        └── logs/
            ├── costs.jsonl       # run total row written by finalize()
            ├── phases.jsonl
            ├── otel.harness.jsonl   # after `evals.cli trace export-otel`
            └── otel.export.json     # export status
```

Not every run writes every file: a LangGraph `placeholder` run has empty artifact folders, and
the OTel files appear only after an export ([observability](observability/README.md)).
`ResultsBundle.finalize()` (`core/results/writer.py`) writes the receipt through
`harness/receipt.py`.

## `run.json`

Required fields:

- `project_id`
- `backend` (`crewai` | `langgraph` | `claude-agent-sdk`)
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

`output/runs/<project_id>/artifacts/development/code_manifest.json` records each generated file:

- `path` (relative to `workspace/<project_id>/`)
- `sha256`
- `bytes`
- `phase`
- `agent_role`
- `timestamp`

If a baseline exists, `diff.patch` can be generated for reproducible review.

