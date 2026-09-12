# Mapping Stencil's harness constraints to AI-Team's seven layers

*Companion to [HARNESS.md](../HARNESS.md) and the Substack essay
"The harness is not the plugin." Diagrams:
[substack-harness-layers.svg](../images/substack-harness-layers.svg).*

## Three different jobs

| Reference | Job |
| --- | --- |
| [ECC](https://github.com/affaan-m/ECC) | Install a developer-facing process (skills, hooks, agents) into Claude/Codex/Cursor. |
| [Tencent teamai-cli](https://github.com/Tencent/teamai-cli) | Git-sync one team harness (skills, rules, MCP, learnings) to every member's tools. |
| [Stencil Harness Playbook](https://stencil.so/blog/harness-playbook) | Architecture constraints for a production agent **engine** (journaled session, control plane, projections). |
| **AI-Team** | Field study: same nine-role org on three orchestrators; failure taxonomy + shared harness. |

We borrow Stencil's constraints as tests. We do not become ECC or teamai.

## Stencil's five consequences → our layers

Stencil's design envelope forces five consequences. Here is how they land on the
seven-layer bar in [HARNESS.md](../HARNESS.md) (status as of R19.3 / 2026-09).

| Stencil constraint | Meaning | AI-Team mapping | Status |
| --- | --- | --- | --- |
| **One authoritative session** | Rewind/fork/resume must derive from one journaled state | Change `receipt.json` is post-run authority; `logs/journal.jsonl` reconstructs tool allow/deny. **No** interactive rewind/fork — eval fixtures + receipt are the replay path | Observability **enforced** for dashboard quotes; session DOM out of scope |
| **Trusted control plane** | Policy stays on the host; sandboxes get bounded requests | ToolBus + guardrails + spend ceiling; irreversible ops gated | Tools + Guardrails **enforced** |
| **Bounded work** | Cancellable streams with central limits | Spend guard, iteration limits, subprocess hard-kill (CrewAI), circuit breakers | Guardrails **enforced**; cancellation depth varies by backend |
| **Explicit compatibility** | Provider quirks as structured knowledge | FM-009 provider dialect; models via settings/profiles; LiteLLM/OpenRouter vs Anthropic SDK | Documented in taxonomy; not a full quirk registry |
| **Views are projections** | TUI/web must not become a second authority | Dashboard prefers `receipt.json` for cost/smoke/files; WebSocket is progress UX only | Observability **enforced** for metrics |

## Seven layers (copy of the bar)

| Layer | Status | One-line |
| --- | --- | --- |
| Tools | **enforced** | Structured observations; draft-then-commit; irreversible gated |
| Verification | **enforced** | Cheap pytest/ruff/smoke vs strong judge; HTTP smoke on every backend |
| Context | **enforced** | Pinned `CONSTRAINTS.md`; `STATE.md` last-N facts |
| Guardrails | **enforced** | Risk-class subsets; global spend ceiling |
| Observability | **enforced** | Receipt is source of truth; live stream is a projection |
| Routing | **instrumented** | `task_routes.yaml`; not every call site uses `resolve_route` yet |
| Feedback | **closed-loop** | Lessons → pin `CST-lesson-*`; effectiveness window |

## What we deliberately do not claim

- ECC-style skill marketplace or multi-IDE plugin install.
- teamai-style git sync of skills/rules across a team.
- Stencil-style XML session DOM with rewind/fork parity.
- Hard CI taxonomy gate until [campaign/EVAL_GATE_STATUS.md](../campaign/EVAL_GATE_STATUS.md)
  says the soak is complete (Tier A is still `--warn-only`).

## Further reading

- [failure-taxonomy.md](failure-taxonomy.md) — ten failure classes with receipts
- [resources.md](../resources.md) — why ECC / teamai / Stencil are not our product
- [EVALS.md](../EVALS.md) — Tier A $0 replay
