# Reference Resources

Curated external materials that shaped this repo — articles, posts, talks, and related
projects — with **how and why** we used each one. Companion deep-dives live in
[HARNESS.md](HARNESS.md), [EVAL_METHODOLOGY.md](EVAL_METHODOLOGY.md),
[posts/harness-map.md](posts/harness-map.md), and
[posts/failure-taxonomy.md](posts/failure-taxonomy.md).

AI-Team stays a **research harness** (three backends + failure taxonomy). We borrow
constraints and methods; we do not clone other products' distribution models.

---

## Harness design

### [Lilian Weng — Harness Engineering](https://lilianweng.github.io/posts/2026-07-04-harness/?utm_source=tldrai)

**What:** Survey of harness engineering for self-improving agent systems (tools,
verification, memory/context, feedback loops).

**How we used it:** Vocabulary and framing for treating the harness — not the
orchestrator — as the product. Informed the seven-layer bar in [HARNESS.md](HARNESS.md)
and the lessons / feedback layer (`CHK-lesson-effectiveness`, `CST-lesson-*` pins).

**Why:** We needed a shared language for "what surrounds the model" when comparing
CrewAI, LangGraph, and Claude Agent SDK on equal footing.

### [ClaudeDevs — Getting started with loops](https://x.com/ClaudeDevs/status/2074208949205881033?utm_source=tldrai)

**What:** Short thread on agent loops as the unit of reliability (observe → act →
verify → retry), not one-shot prompts.

**How we used it:** Reinforced runtime smoke + recovery loops
([SELF_IMPROVEMENT.md](SELF_IMPROVEMENT.md)) and "tests green ≠ app works" gates
(FM-006).

**Why:** Portfolio demos fail when the loop stops at pytest. The thread is a compact
reminder that verification must close on real behavior.

### [choopyplug1 — Production checklist](https://x.com/choopyplug1/status/2088973320964215253)

**What:** Checklist of production agent-harness layers (tools, verification, context,
guardrails, observability, routing, feedback).

**How we used it:** Direct source for the seven-layer map in
[`.kiro/specs/seven-layer-harness/`](../.kiro/specs/seven-layer-harness/) and the
status table in [HARNESS.md](HARNESS.md). Paired with our failure taxonomy: the
checklist names the layers; FM-001…013 prove what happens when a layer is skipped.

**Why:** Gave a concrete "instrumentation bar" instead of inventing layer names ad hoc.

### [Stencil Harness Playbook](https://stencil.so/blog/harness-playbook)

**What:** Architecture essay: one authoritative session, trusted control plane,
bounded work, explicit provider quirks, views as projections.

**How we used it:** Constraint tests mapped onto our layers in
[posts/harness-map.md](posts/harness-map.md) (e.g. `receipt.json` as authority,
ToolBus as control plane, dashboard as projection-only).

**Why:** Sharpened non-goals (no XML session DOM rewind/fork) while keeping the
discipline we do want (single source of truth for cost/smoke/files).

---

## Eval methodology

### [Husain & Shankar — Analyzing the Analyzers](https://eugeneyan.com/writing/eval-analysis/)

**What:** Error-analysis-first eval practice: traces → open coding → axial coding →
taxonomy → checks / judges, with human ground truth.

**How we used it:** Explicit methodology for
[`.kiro/specs/eval-harness/`](../.kiro/specs/eval-harness/) and
[EVAL_METHODOLOGY.md](EVAL_METHODOLOGY.md): Trace boundary, annotation TUI
(`evals/annotate.py`), taxonomy YAML, deterministic Tier A checks before LLM judges,
binary gates with TPR/TNR/κ thresholds.

**Why:** Stops "LLM judges all the way down." Failure modes must come from observed
errors, not invented scorecards. The first live LangGraph smoke we are putting
through that loop (unlabeled; not a rate) is
[eval-runs/2026-09-13-langgraph-smoke](eval-runs/2026-09-13-langgraph-smoke/README.md).

### [Lenny's Podcast — Why AI evals are the hottest new skill (YouTube)](https://www.youtube.com/watch?v=BsWxPI9UM4c)

**What:** Hamel Husain & Shreya Shankar walk through the same workflow on a real
product: inspect traces, open/axial coding, code-based evals vs LLM-as-judge,
validate judges against humans, treat evals as living requirements.
([Written companion](https://www.lennysnewsletter.com/p/why-ai-evals-are-the-hottest-new-skill).)

**How we used it:** Pedagogue for the eval-harness loop — especially "humans first in
error analysis," cheap checks before judges, and judge alignment against a held-out
human split. Complements the written essay with a concrete demo of the annotation
rhythm we encode in `evals/cli sample` → `annotate` → `taxonomy propose`.

**Why:** Makes the methodology teachable (and honest about task 5.2 remaining human
work). Same authors as the essay; this is the long-form walkthrough we point people at
when the written piece is too dense.

---

## Anthropic references (measurement arms)

Used by [`.kiro/specs/harness-alignment/`](../.kiro/specs/harness-alignment/) to turn
"the harness is the deliverable" into a ladder with shared scenarios and checks.

| Source | What it supplies | How we used it |
| --- | --- | --- |
| [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps) (Rajasekaran) | Solo control ideas: contract before code, context resets over compaction, context anxiety, self-evaluation bias | Inspired `solo` / `harnessed_solo` arms and FM-014…017 (`CHK-acceptance-monotonic`, `CHK-premature-termination`, `CHK-verifier-independence`, `CHK-evaluator-capitulation`) |
| [`anthropics/claude-quickstarts/autonomous-coding`](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding) @3313e97 (MIT) | Minimal published harness: session loop, monotonic checklist, default-deny bash | Vendored as the `reference` arm — pinned, never edited; adaptations recorded as divergences |

**Why:** Without external control arms, three-backend comparisons confound harness
with agent count and model mix. The ladder isolates what the harness buys.

---

## Related projects (not this product)

Useful references. We measure the same nine-role org across three orchestrators; we
do not ship their distribution models.

| Project | What it is | Why it is not our product / how we still use it |
| --- | --- | --- |
| [ECC](https://github.com/affaan-m/ECC) | Skill/plugin overlay for Claude Code, Codex, Cursor (agents, skills, hooks, AgentShield) | Optimizes the *developer-facing* agent in one workspace. Contrast case in [posts/harness-map.md](posts/harness-map.md). |
| [Tencent teamai-cli](https://github.com/Tencent/teamai-cli) | Git-synced team skills, rules, MCP, hooks, friction learnings | Team admin / knowledge sync CLI. We are a field-study harness, not a distribution tool. |
| [Stencil Harness Playbook](https://stencil.so/blog/harness-playbook) | Engine design constraints (see above) | Borrow constraints as tests; do not fork the product. |

---

## Model selection (operational)

Leaderboards and provider docs used when choosing OpenRouter / SDK models — not design
sources for the harness itself. Full checklist and citations live in
[MODELS.md](MODELS.md) (Artificial Analysis, SWE-bench, OpenRouter rankings, etc.).

---

## See also (in-repo)

| Doc | Role |
| --- | --- |
| [HARNESS.md](HARNESS.md) | Seven-layer instrumentation bar |
| [EVAL_METHODOLOGY.md](EVAL_METHODOLOGY.md) | Error-analysis-first eval loop |
| [eval-runs/2026-09-13-langgraph-smoke](eval-runs/2026-09-13-langgraph-smoke/README.md) | First live case for that loop (unlabeled; not a published rate) |
| [EVALS.md](EVALS.md) / [EVALS_ROADMAP.md](EVALS_ROADMAP.md) | Suite tiers; future role-eval calibrations (e.g. DPIaC-Eval, RealVuln) |
| [posts/failure-taxonomy.md](posts/failure-taxonomy.md) | Observed failure classes with receipts |
| [posts/harness-map.md](posts/harness-map.md) | Stencil → AI-Team layer mapping |
