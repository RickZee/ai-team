# Documentation map

Four kinds of document live here. Knowing which kind you are reading tells you how
much to trust its dates.

| Kind | What it is | Kept current? |
| --- | --- | --- |
| **Start** | How to run and learn the repo | Yes, on every change that breaks a command |
| **Reference** | How a subsystem works today | Yes, checked by `tests/unit/repo/` where possible |
| **Record** | What happened on a date, with commits | No. Dated, never rewritten except to fix links |
| **Plan** | Work not done yet | Lives in [`.kiro/specs/`](../.kiro/specs/README.md), not here |

## Start

| Document | Read it when |
| --- | --- |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Setting up keys, running a backend, fixing a first-run error |
| [GLOSSARY.md](GLOSSARY.md) | A term in the code or the docs is new to you |
| [`course/`](../course/README.md) | You want the six-week, hands-on route through the whole system |
| [`docs/course/`](course/README.md) | You want the short, no-code version: *Evals Without the Jargon* (+ `minieval.py`) |
| [DEMOS.md](DEMOS.md) | Choosing or writing a demo brief |

## Reference

| Area | Document |
| --- | --- |
| System design | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Harness layers and their status | [HARNESS.md](HARNESS.md) |
| Guardrails catalogue | [GUARDRAILS.md](GUARDRAILS.md) |
| Agents and team profiles | [AGENTS.md](AGENTS.md), [TEAM_PROFILES.md](TEAM_PROFILES.md) |
| Models and routing | [MODELS.md](MODELS.md) |
| Evals: entry point | [`evals/README.md`](../evals/README.md) |
| Evals: method and limits | [EVAL_METHODOLOGY.md](EVAL_METHODOLOGY.md) |
| Evals: what may be claimed | [EVAL_GATE_STATUS.md](EVAL_GATE_STATUS.md) |
| Run bundle layout | [RUN_ARTIFACTS.md](RUN_ARTIFACTS.md) |
| Performance envelope | [PERFORMANCE.md](PERFORMANCE.md) |
| Security and threat model | [`SECURITY.md`](../SECURITY.md) |
| Cloud backends status | [CLOUD_NATIVE.md](CLOUD_NATIVE.md), [ADR-001](adr/ADR-001-cloud-native-backends.md) |
| Claude Agent SDK runbook | [claude-agent-sdk/RUNBOOK.md](claude-agent-sdk/RUNBOOK.md) |
| Self-improvement loop | [SELF_IMPROVEMENT.md](SELF_IMPROVEMENT.md) |
| UI review rubric (advisory) | [UI_QUALITY_RUBRIC.md](UI_QUALITY_RUBRIC.md) |
| External sources that shaped the repo | [resources.md](resources.md) |

## Record

| Collection | Contents |
| --- | --- |
| [journal/](journal/README.md) | Session-by-session engineering log, including corrections |
| [posts/](posts/) | Long-form write-ups: [failure taxonomy](posts/failure-taxonomy.md), [the starved harness](posts/the-starved-harness.md), [harness map](posts/harness-map.md), [fixture-only](posts/fixture-only.md) |
| [troubleshooting/](troubleshooting/README.md) | Post-mortems of non-obvious bugs |
| [eval-runs/](eval-runs/README.md) | Receipts for eval runs that executed |
| [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md) | Backend comparison data and the same-model matrix |
| [showcase/](showcase/README.md) | Standalone HTML pages built from recorded findings |
| [images/](images/README.md) | Figures used by the pages above |
