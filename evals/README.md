# Eval harness (`evals/`)

Rigorous eval system for ai-team: Trace boundary, failure taxonomy FM-001…017,
deterministic checks, optional binary judges, Tier A ($0) replay gate.

Spec: `.kiro/specs/eval-harness/`. Methodology: [`docs/EVAL_METHODOLOGY.md`](../docs/EVAL_METHODOLOGY.md).

## Five-minute quickstart

```bash
# 1) Build traces from existing run workspaces (free)
uv run python -m evals.cli trace backfill --workspace-root ./workspace
uv run python -m evals.cli index rebuild
uv run python -m evals.cli index stats

# 2) Tier A offline suite ($0.00, deterministic)
uv run python -m evals.cli run --tier A --warn-only --out evals/results/tier-a-local

# 3) Read the report
open evals/results/tier-a-local/report.html   # or cat report.md / summary.txt
```

## Tests (R16)

```bash
uv run pytest tests/unit/evals tests/integration/evals -q
```

- Unit: `tests/unit/evals/` (taxonomy, checks, alignment math, judges, …)
- Integration: `tests/integration/evals/` (TraceBuilder mini workspace, Tier A determinism, gate)
- Never assert live judge quality in pytest — that is measured via the golden set.

Other useful commands:

```bash
uv run python -m evals.cli sample --strategy stratified -n 100 --seed 1
uv run python -m evals.cli annotate --sample <sample_id> --annotator $USER
uv run python -m evals.cli taxonomy coverage
uv run python -m evals.cli guardrail eval
uv run python -m evals.cli fixtures redact --lint
uv run python -m evals.cli baseline accept --tier A --reason "..."
```

## Layout

| Path | Role |
| --- | --- |
| `trace/` | models, parsers, builder, schema |
| `checks/` | deterministic FM detectors |
| `taxonomy/` | `failure_modes.yaml` + loader + COVERAGE.md |
| `judges/` | BinaryJudge, prompts, cache |
| `fixtures/traces/` | committed Tier A corpus (redacted) |
| `baselines/` | gate baselines |
| `cli.py` | `python -m evals.cli` |
| `run_evals.py` | Tier B/C live executor (subprocess + watchdogs) |

Live working dirs (gitignored): `traces/`, `annotations/`, `samples/`, `results/`.

## Coupling to ai-team

`evals/` should stay extractable. Current `from ai_team` / `import ai_team` sites
(harness + legacy backend tests):

```text
tests/integration/evals/test_claude_sdk_eval.py: from ai_team.backends.registry import get_backend
tests/integration/evals/test_crewai_eval.py: from ai_team.backends.registry import get_backend
tests/integration/evals/test_langgraph_eval.py: from ai_team.backends.registry import get_backend
tests/integration/evals/test_backend_comparison.py: from ai_team.backends.registry import get_backend
evals/checks/trajectory.py: from ai_team.flows.listener_introspection import self_triggering_listeners
evals/checks/trajectory.py: from ai_team.flows.main_flow import AITeamFlow
evals/guardrail_eval.py: from ai_team.guardrails.behavioral import (...)
evals/guardrail_eval.py: from ai_team.guardrails.corpus_metrics import ConfusionCounts, format_report, score
evals/guardrail_eval.py: from ai_team.guardrails.security import code_safety_guardrail
evals/trace/workspace.py: from ai_team.config.settings import get_settings
```

Documented coupling categories:

1. **Guardrail metrics / invoke** — `corpus_metrics`, behavioral + security guardrails (R6)
2. **Flow introspection** — shared `listener_introspection` + `AITeamFlow` for CHK-listener-self-trigger
3. **Settings** — workspace root resolution
4. **Backend registry / team profiles** — Tier B/C live execution clients under `evals/backends/`

Refresh this list with:

```bash
grep -rn "from ai_team\|import ai_team" evals/ --include='*.py' | grep -v __pycache__ | sort
```
