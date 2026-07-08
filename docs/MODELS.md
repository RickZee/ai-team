# Models and provider configuration

LLM assignment is **three-layered**:

1. **Environment tier** — `AI_TEAM_ENV=dev|test|prod` selects a cost/quality matrix in
   [`src/ai_team/config/models.py`](../src/ai_team/config/models.py) (`ENV_MODELS`).
2. **Agent role** — each persona gets the model for its role key (see [AGENTS.md](AGENTS.md)).
3. **Team profile overrides** — optional per-role model IDs in
   [`team_profiles.yaml`](../src/ai_team/config/team_profiles.yaml) (`model_overrides`).

**Orchestration backend** determines *which API* is called:

| Backend | API / routing | Env var |
| ------- | ------------- | ------- |
| `crewai`, `langgraph` | OpenRouter (LiteLLM `openrouter/<provider>/<model>` IDs) | `OPENROUTER_API_KEY` |
| `claude-agent-sdk` | Anthropic Messages API (direct) | `ANTHROPIC_API_KEY` |

There is **no automatic cross-provider fallback**. See [Failure modes](#failure-modes-no-provider-failover).

Model IDs and list prices were verified against OpenRouter `/models` (2026-07-08).
Re-check [openrouter.ai/models](https://openrouter.ai/models) before budgeting a prod run.

---

## Design principles

1. **Tier = question, not brand.** `dev` answers “does the pipeline wire?”; `test` answers
   “do role-fit mid-tier models produce usable artifacts?”; `prod` answers “can we ship
   portfolio-quality output?”
2. **Match strengths to the job.** Coordination and specs need fast structured writing;
   architecture and QA need deep disambiguation; developers need multi-file coding and tool
   loops; DevOps prefers a strong cheaper coding workhorse than the absolute frontier.
3. **Spend the premium where a wrong answer is expensive.** Architect wrong → every
   downstream agent is taxed. DevOps wrong → still recoverable. Hence Opus for architect
   only in prod, not for every role.
4. **One OpenRouter key for CrewAI/LangGraph.** Direct Anthropic is a *separate* backend
   (Claude Agent SDK), not a per-role failover path.

---

## Model roster (what each model is good / bad at)

### DeepSeek V4 Flash — `deepseek/deepseek-v4-flash`

| | |
| --- | --- |
| **Price (OR)** | $0.09 / $0.18 per 1M |
| **Context** | 1M |
| **Strengths** | High-throughput coding against a clear spec; 1M context; ~79% SWE-bench Verified in public reports; ~5× cheaper than Sonnet-class for still-competitive everyday code; old `deepseek-chat` aliases now map here |
| **Weaknesses** | Falls behind Pro (~8 pts SWE-Verified / larger agentic gaps) when the brief is ambiguous, when 10+ tool calls span a long horizon, or when competing causes must be weighed; can confidently emit the wrong fix |
| **Why we use it** | Default **entire DEV tier** — cheapest way to exercise all nine roles and tool wiring without pretending quality is the goal |

### DeepSeek V4 Pro — `deepseek/deepseek-v4-pro`

| | |
| --- | --- |
| **Price (OR)** | $0.435 / $0.87 per 1M |
| **Context** | 1M |
| **Strengths** | Frontier-adjacent open-weight reasoner (~80–81% SWE-Verified; strong LiveCodeBench / Codeforces); better long-horizon agentic tool use than Flash; good multi-file structural reasoning at a fraction of Opus price |
| **Weaknesses** | Still trails closed Opus/GPT-5.5 on the hardest SWE-Bench Pro / Terminal-Bench rows; thinking modes cost tokens; not a “set and forget” for security-critical auth logic |
| **Why we use it** | **TEST** architect, cloud, QA — mid-tier work that needs disambiguation and review depth without prod pricing |

### Gemini 3.5 Flash — `google/gemini-3.5-flash`

| | |
| --- | --- |
| **Price (OR)** | $1.50 / $9.00 per 1M |
| **Context** | 1M |
| **Strengths** | Built for agent orchestration and multi-step tool loops (strong MCP Atlas / Terminal-Bench for Flash-class); very high output throughput; multimodal; excellent for parallel sub-agent coordination and structured writing at scale |
| **Weaknesses** | Trails Opus/GPT-5.5 on the hardest pure-reasoning / SWE-Pro rows; long-context retrieval can lag best-in-class on some retrieval benchmarks |
| **Why we use it** | **TEST** manager + product owner — coordination and specs: speed, structure, and tool fluency matter more than last-mile coding score |

### MiniMax M3 — `minimax/minimax-m3`

| | |
| --- | --- |
| **Price (OR)** | $0.30 / $1.20 per 1M |
| **Context** | 1M (sparse attention; cheaper long-context) |
| **Strengths** | Leading open-weight long-horizon coding/agent model for mid-tier budgets; native multimodal (UI/screenshot flows); competitive SWE-Pro / Terminal-Bench at ~1/10 frontier cost-per-task in independent audits |
| **Weaknesses** | Step below true frontier (Opus 4.8 / GPT-5.5) on subtle systems bugs; can be verbose / reasoning-heavy (effective cost rises); license/self-host caveats; vendor launch benchmarks compared against older rivals — validate on your own harness |
| **Why we use it** | **TEST** backend / frontend / fullstack / devops — volume coding and IaC generation where Mid-tier coding matters more than Opus-level judgment |

### Claude Sonnet 4.6 — `anthropic/claude-sonnet-4.6`

| | |
| --- | --- |
| **Price (OR)** | $3 / $15 per 1M |
| **Context** | 1M |
| **Strengths** | Best default for iterative coding, codebase navigation, polished docs, computer-use / web QA, and agent pipelines; closes most of the Opus gap on everyday work at lower cost |
| **Weaknesses** | Trails Opus (~9 pts SWE-Verified / larger on SWE-Pro) on the hardest multi-step architecture and ambiguous long-horizon tasks; not the cheapest coordinator |
| **Why we use it** | **PROD** manager, frontend, cloud, QA — production default where reliability + judgment matter; manager needs coherent phase orchestration without Opus premium |

### Claude Opus 4.8 — `anthropic/claude-opus-4.8`

| | |
| --- | --- |
| **Price (OR)** | $5 / $25 per 1M |
| **Context** | 1M |
| **Strengths** | Best Anthropic model for ambiguous multi-step reasoning, large-codebase comprehension, architecture/trade-off analysis, and agentic self-correction; highest SWE-Pro among Claude family |
| **Weaknesses** | Expensive; slower; overkill for well-specified generative tasks where Sonnet quality is “good enough” |
| **Why we use it** | **PROD architect only** — a wrong architecture taxes every downstream developer/QA turn; that is where the premium pays for itself |

### GPT-5.4 — `openai/gpt-5.4`

| | |
| --- | --- |
| **Price (OR)** | $2.50 / $15 per 1M |
| **Context** | ~1M |
| **Strengths** | Strong all-around tool-calling / professional coding workhorse; absorbed prior Codex coding strengths; good CI/CD and structured operational output at half GPT-5.5 token price |
| **Weaknesses** | Trails GPT-5.5 on Terminal-Bench / long-horizon Expert-SWE; not the flagship for hardest multi-file agentic coding |
| **Why we use it** | **PROD product_owner + devops** — PO needs excellent structure/docs more than terminal mastery; DevOps pipelines are well-scoped generative work where 5.4’s cost/quality balance wins |

### GPT-5.5 — `openai/gpt-5.5`

| | |
| --- | --- |
| **Price (OR)** | $5 / $30 per 1M |
| **Context** | ~1M |
| **Strengths** | OpenAI’s current coding flagship (Codex default); SOTA Terminal-Bench 2.0 (~82.7%); better long-context retrieval; more disciplined / less-over-refactoring patches; fewer tokens per Codex task than 5.4 in OpenAI’s reports |
| **Weaknesses** | Highest OpenAI rate card; Claude Opus often still leads SWE-Bench Pro / large-repo issues in third-party tables — pick by task shape, not brand loyalty |
| **Why we use it** | **PROD backend + fullstack** — implementation density, tool/CLI loops, and multi-file discipline; replaces deprecated dedicated `gpt-5.3-codex` IDs |

### Claude Haiku 4.5 (SDK default for devops/cloud) — `anthropic/claude-haiku-4.5`

| | |
| --- | --- |
| **Price (OR)** | $1 / $5 per 1M |
| **Context** | 200k |
| **Strengths** | Fast executor (~near prior Sonnet-4 coding at a fraction of cost); good for bulk CI stubs, Docker boilerplate, parallel subagents |
| **Weaknesses** | Shallower multi-file architecture coherence; misses security/perf edge cases; shorter context than Sonnet/Opus |
| **Why we use it** | **Claude Agent SDK** devops/cloud defaults in `builder.py` (not `ENV_MODELS`) — executor roles under an Anthropic-orchestrated tree |

---

## Environment matrices (`ENV_MODELS`)

LiteLLM IDs in code are prefixed with `openrouter/`. Temperatures are in `models.py`.

### DEV — cheapest pipeline validation

Goal: exercise the full flow at minimum spend. All roles on one inexpensive model.

| Role | Model | Temp | Why this model for this role |
| ---- | ----- | ---- | ---------------------------- |
| manager | DeepSeek V4 Flash | 0.7 | Coordination text is cheap to get wrong at this tier; Flash is enough to drive phase transitions |
| product_owner | DeepSeek V4 Flash | 0.7 | Spec drafts for smoke/demos — clarity over MoSCoW sophistication |
| architect | DeepSeek V4 Flash | 0.7 | Dev architectures are throwaway; spend zeros |
| backend_developer | DeepSeek V4 Flash | 0.4 | Flash is strong on *clear-spec* implementation (smoke calculator / todo stubs) |
| frontend_developer | DeepSeek V4 Flash | 0.4 | Same: HTML/JS against a short brief |
| fullstack_developer | DeepSeek V4 Flash | 0.4 | Same; file_writer loops stay affordable |
| cloud_engineer | DeepSeek V4 Flash | 0.4 | One model for whole crew → predictable routing and cost; IaC depth not the goal |
| devops | DeepSeek V4 Flash | 0.4 | Dockerfile/README stubs for smoke are Flash-class work |
| qa_engineer | DeepSeek V4 Flash | 0.4 | Pytest happy-paths against a tiny module |

**Intentionally rejected for DEV:** Gemini Flash (higher $/M), MiniMax M3 (mid-tier spend), any Claude/GPT frontier (antithetical to “cheapest gate”).

Typical use: local iteration, `demos/00_smoke_test`, CI with real LLM off (mocks).

### TEST — mid-tier role-fit sweep

Goal: better reasoning and coding without prod pricing. Split by job class.

| Role | Model | Temp | Why this model for this role |
| ---- | ----- | ---- | ---------------------------- |
| manager | Gemini 3.5 Flash | 0.7 | Agent orchestration + speed; Flash leads tool/orchestration metrics vs peers at this price |
| product_owner | Gemini 3.5 Flash | 0.7 | Structured requirements / acceptance criteria; multimodal unused but cheap agentic writing is the fit |
| architect | DeepSeek V4 Pro | 0.3 | Needs reasoning mode for trade-offs; Pro’s coding+reasoning gap over Flash pays off here |
| backend_developer | MiniMax M3 | 0.4 | Mid-tier long-horizon coding at M3’s cost curve; volume API work without GPT-5.5 |
| frontend_developer | MiniMax M3 | 0.4 | Multimodal + coding → UI flows; still cheaper than Sonnet |
| fullstack_developer | MiniMax M3 | 0.4 | Sustained multi-file edits against a real brief (`02_todo_app`) |
| cloud_engineer | DeepSeek V4 Pro | 0.3 | IaC + security/cost trade-offs need Pro-class reasoning |
| devops | MiniMax M3 | 0.4 | Compose/CI generation is coding-shaped; M3’s agentic coding beats routing devops to reasoning-only Pro |
| qa_engineer | DeepSeek V4 Pro | 0.3 | Test strategy + edge cases: Pro’s disambiguation > Flash’s confident wrong tests |

**Intentionally rejected for TEST:** all-Flash (underfits architect/QA); all-MiniMax (underfits ambiguous design); Sonnet/Opus (belongs in prod budgets).

Typical use: comparison batches, `scripts/compare_backends.py --env test`, regression before prod.

### PROD — portfolio / demo quality

Goal: best-fit frontier mix. Premium only where wrong answers cascade.

| Role | Model | Temp | Why this model for this role |
| ---- | ----- | ---- | ---------------------------- |
| manager | Claude Sonnet 4.6 | 0.5 | Reliable phase orchestration, memory-friendly project management; Opus premium not needed for routing |
| product_owner | GPT-5.4 | 0.5 | Strong structured knowledge-work / docs at half GPT-5.5 price; PO is writing-heavy, not Terminal-Bench-heavy |
| architect | Claude Opus 4.8 | 0.3 | Highest ambiguity cost in the crew; Opus wins sustained multi-step design and trade-off analysis |
| backend_developer | GPT-5.5 | 0.2 | Current OpenAI coding flagship; Terminal-Bench / agentic implementation discipline; replaces retired Codex variants |
| frontend_developer | Claude Sonnet 4.6 | 0.3 | UI polish, a11y judgment, iterative component work — Sonnet’s sweet spot |
| fullstack_developer | GPT-5.5 | 0.2 | Same coding flagship as backend when one agent owns both sides |
| cloud_engineer | Claude Sonnet 4.6 | 0.3 | IaC + least privilege judgment; Opus reserved for architecture, not every Terraform module |
| devops | GPT-5.4 | 0.3 | CI/CD / Docker are well-scoped generative tasks; 5.4 = coding workhorse without 5.5 rate card |
| qa_engineer | Claude Sonnet 4.6 | 0.3 | Thorough, conservative tests and review tone; Sonnet reliable for “find what’s wrong” |

**Intentionally rejected for PROD:** pinning everything to Opus (spend without ROI); all GPT-5.5 (leaves architectural / UI judgment on a model weaker than Claude on some SWE-Pro / repo-scale comparisons); DeepSeek V4 at prod tier (leave for test/dev).

Requires `AI_TEAM_PROD_CONFIRM=true` (default) — CLI prompts before prod runs.

---

## Same-model profile (`full-claude`)

For framework-vs-framework comparisons, every OpenRouter role is pinned to
`openrouter/anthropic/claude-sonnet-4.6` via `team_profiles.yaml` `model_overrides`.
That holds the **model** constant so differences are attributable to CrewAI / LangGraph /
harness, not tier mix. See [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md).

```yaml
model_overrides:
  manager: openrouter/anthropic/claude-sonnet-4.6
  # … every role
```

---

## Provider comparison

### OpenRouter (CrewAI + LangGraph)

| Aspect | Detail |
| ------ | ------ |
| **What it is** | Unified gateway; one key, 300+ models, OpenAI-compatible API |
| **How we use it** | `create_llm_for_role()` → CrewAI `LLM(model="openrouter/...")` → LiteLLM |
| **Billing** | OpenRouter credits; per-model input/output pricing |
| **Pros** | Single key for mixed-provider tiers; instant model swaps; comparison experiments |
| **Cons** | Extra hop; OpenRouter outage hits all roles; IDs/pricing drift with catalog |
| **Retries** | LiteLLM `num_retries=3` for **transient** HTTP/5xx only — not model/provider failover |

### Anthropic direct (Claude Agent SDK)

| Aspect | Detail |
| ------ | ------ |
| **What it is** | Native Claude Agent SDK + Claude Code runtime |
| **How we use it** | `ANTHROPIC_API_KEY`; subagents get `sonnet` / `opus` / `haiku` short names |
| **Default mapping** | architect→`opus`; dev roles→`sonnet`; devops/cloud→`haiku`; orchestrator phases→`sonnet` |
| **Pros** | Native tool-calling, session persistence, MCP; best measured consistency in our comparison matrix |
| **Cons** | Highest cost; **only Anthropic models** — no OpenAI/Gemini fallback |
| **Env** | `AI_TEAM_ENV` does **not** change SDK model picks (SDK path ignores `ENV_MODELS`) |

Dated API strings: `ANTHROPIC_MESSAGES_MODEL_*` in `models.py` (`claude-sonnet-4-6`,
`claude-opus-4-8`, `claude-haiku-4-5`).

### OpenAI direct (not a first-class backend)

| Aspect | Detail |
| ------ | ------ |
| **What it is** | `api.openai.com` Chat Completions |
| **How we use it today** | **Indirectly** via OpenRouter (`openai/gpt-5.4`, `openai/gpt-5.5` in prod) and embeddings (`openai/text-embedding-3-small` for CrewAI memory) |
| **Pros** | Lowest latency to OpenAI; direct billing |
| **Cons** | No built-in multi-model routing for our crews; needs a new backend to orchestrate entirely on OpenAI |
| **When to choose** | If you want OpenAI without OpenRouter markup for coding roles only — still routed via OpenRouter IDs today |

### Quick contrast

| Concern | OpenRouter | Anthropic direct | OpenAI direct |
| ------- | ---------- | ---------------- | ------------- |
| Keys needed | `OPENROUTER_API_KEY` | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` (not wired for orchestration) |
| Model variety | All providers | Claude only | GPT only |
| Per-role model mix | Yes (`ENV_MODELS`) | Yes (SDK defaults + overrides) | Would need custom wiring |
| Cost transparency | OpenRouter dashboard | Anthropic console | OpenAI usage page |
| Failure blast radius | All OpenRouter-backed roles | All SDK subagents | N/A today |

---

## Failure modes (no provider failover)

**If one provider fails, the whole team can fail.** There is no automatic downgrade
to a different provider or model when a call errors.

### What happens today

| Failure | System behavior | Whole-team impact |
| ------- | --------------- | ----------------- |
| OpenRouter 401/403 (bad key) | LLM call fails immediately | **All agents** on CrewAI/LangGraph stop |
| OpenRouter 402 (credits / max_tokens) | Request rejected | Affected agent fails; phase may retry then abort |
| OpenRouter 429 (rate limit) | LiteLLM retries up to 3× (transient) | May recover; sustained 429 → phase failure |
| OpenRouter 5xx / timeout | LiteLLM retries 3×, 120s timeout | Agent fails after retries; flow may route to error handler |
| Model deprecated / 404 on OpenRouter | Hard fail for that model ID | Every role using that ID fails |
| Anthropic API outage (SDK backend) | SDK `query()` errors | **Entire SDK run** fails; recovery limited to `recovery_max_attempts` |
| Single agent bad output | Guardrails + phase retries (`retry_development`, etc.) | Other agents unaffected until retry exhausts |
| Unknown role in `ENV_MODELS` | Falls back to **manager's model** (same provider) | Wrong model, not a different provider |

### What is **not** implemented

- Cross-provider failover (e.g. Claude down → GPT)
- Cross-model failover within a tier (e.g. sonnet-4.6 → haiku-4.5)
- Per-role backup model lists
- OpenRouter routing-mode selection (`nitro`, `exacto`) in our code

### Mitigations (operational)

1. **Dev tier for smoke** — `AI_TEAM_ENV=dev` limits blast radius on spend.
2. **Spend guard** — `AI_TEAM_RUN_BUDGET_USD` aborts runaway retry loops (non-retryable).
3. **Profile overrides** — pin a known-good model without editing `ENV_MODELS`.
4. **Backend choice** — if OpenRouter is degraded, switch to `--backend claude-agent-sdk` (requires `ANTHROPIC_API_KEY`, different cost profile).
5. **Same-model matrix** — use `full-claude` profile to isolate framework vs model failures.
6. **Pre-flight** — `uv run ai-team estimate --env prod` before paid runs.

### Embedding dependency (CrewAI memory only)

CrewAI’s internal memory uses OpenRouter embeddings (`MEMORY_EMBEDDING_MODEL`,
default `openai/text-embedding-3-small`). If embeddings fail, CrewAI memory ops fail
even when chat models work. LangGraph and Claude SDK backends do not depend on this
path for orchestration.

---

## Configuration reference

| Variable | Purpose |
| -------- | ------- |
| `AI_TEAM_ENV` | `dev` \| `test` \| `prod` — selects `ENV_MODELS` tier |
| `OPENROUTER_API_KEY` | Required for CrewAI / LangGraph |
| `OPENROUTER_API_BASE` | Default `https://openrouter.ai/api/v1` |
| `ANTHROPIC_API_KEY` | Required for `claude-agent-sdk` |
| `MEMORY_EMBEDDING_MODEL` | OpenRouter embedding model for CrewAI memory |
| `AI_TEAM_MAX_COST_PER_RUN` | Pre-run estimate ceiling |
| `AI_TEAM_RUN_BUDGET_USD` | Runtime spend abort |

Token budget estimates per role: `ROLE_TOKEN_BUDGETS` in `models.py` (used by cost estimator).

---

## Live dashboards (pick a model for the work)

There is **no in-repo model-picker UI**. Use public leaderboards for market signals,
then confirm on our demos / [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md). One
leaderboard ≠ one winner — match the metric to the *role*.

| Work type (our role) | Sort / filter by | Primary dashboards |
| -------------------- | ---------------- | ------------------ |
| Coordination, specs (manager, PO) | Tool use / agentic index, speed, price | [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models), [WhatLLM Explore](https://whatllm.org/explore) (agentic fit) |
| Architecture / hard reasoning (architect) | Intelligence Index, GPQA-class reasoning, SWE-Pro | [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models), [LM Arena](https://lmarena.ai/) (secondary) |
| Implementation / multi-file coding (backend, fullstack, frontend) | SWE-bench Verified / Pro, Terminal-Bench, Aider | [SWE-bench](https://www.swebench.com/), [Skiln](https://skiln.co/leaderboard), [WhatLLM coding](https://whatllm.org/explore) |
| CI/CD / Docker stubs (devops) | Coding + cost/speed, not Arena Elo | Artificial Analysis (price × speed), OpenRouter pricing |
| Cost-sensitive smoke (dev tier) | $/M + long-context | [OpenRouter models](https://openrouter.ai/models) (live price + context) |
| “What are people actually paying for?” | Real token share | [OpenRouter rankings](https://openrouter.ai/rankings) |

**Caveats**

- Chatbot Arena Elo measures *human chat preference*, not “ships a green Flask API.” Prefer SWE / Terminal / agentic for our agents.
- Vendor launch benches are often vs *older* rivals — treat as directional.
- OpenRouter availability ≠ Anthropic-direct (SDK backend) availability; SDK models are short names (`sonnet` / `opus` / `haiku`).
- Coverage is incomplete: a brand-new ID may lack SWE-Pro for weeks.

---

## Promote a model (checklist)

Use this when changing a candidate in `ENV_MODELS`, a `model_overrides` pin, or the
Claude SDK short-name defaults. Public benches alone are **not** a ship gate.

### 0. Scope the change

- [ ] Name the **role(s)** and **tier** (`dev` / `test` / `prod`) — or “all roles, same model” (`full-claude`).
- [ ] Write one sentence of intent (e.g. “cheaper DEV smoke”, “better TEST coding”, “PROD architect judgment”).
- [ ] Note whether the change is OpenRouter (`crewai` / `langgraph`) or Anthropic direct (`claude-agent-sdk`).

### 1. Market signal (dashboards)

- [ ] On [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models), filter open vs proprietary; compare Intelligence Index, blended $/1M, and speed for the shortlist.
- [ ] Match the role to the right metric (table above) — SWE / Terminal / agentic for coding agents; not Arena Elo alone.
- [ ] Cross-check coding claims on [SWE-bench](https://www.swebench.com/) and/or [Skiln](https://skiln.co/leaderboard) (Aider / SWE columns).
- [ ] For agent orchestration roles (manager), skim an agentic/tool-use ranking ([WhatLLM Explore](https://whatllm.org/explore)).

Reject candidates that only win on chat preference or vendor launch slides vs obsolete rivals.

### 2. Catalog + cost (OpenRouter / Anthropic)

- [ ] Confirm the **exact slug** on [OpenRouter models](https://openrouter.ai/models) (or Anthropic docs for SDK). LiteLLM needs `openrouter/<provider>/<model>`.
- [ ] Record live **input/output $/1M** and context window.
- [ ] Sanity-check against the tier goal: DEV should stay near Flash-class cost; PROD may use Opus/GPT-5.5 only where the wrong answer is expensive (see design principles).
- [ ] Run a pre-flight cost estimate for the target env:
  ```bash
  uv run ai-team estimate --env <dev|test|prod> --complexity medium
  ```

### 3. Pin without melting the default matrix (optional first)

Prefer a **profile override** for A/B before editing `ENV_MODELS`:

```yaml
# team_profiles.yaml — temporary profile or adjust full-claude / a fork
model_overrides:
  backend_developer: openrouter/openai/gpt-5.5
```

- [ ] Or edit `ENV_MODELS` + `_PRICES` in [`models.py`](../src/ai_team/config/models.py) when promoting the tier default.
- [ ] For Claude SDK: change short-name defaults in `builder.py` / profile overrides — `AI_TEAM_ENV` does not apply.

### 4. Gate A — smoke (must pass)

Cheap wiring / tool-call check. Prefer LangGraph + lean profile.

`scripts/run_demo.py` **always forces** `AI_TEAM_ENV=dev`. For `test` / `prod`
candidates, use `ai-team run` (or `compare_backends.py --env`) instead.

```bash
# DEV-tier candidate (or override already pinned in a profile)
uv run python scripts/run_demo.py demos/00_smoke_test \
  --skip-estimate --backend langgraph

# TEST / PROD-tier candidate (do not use run_demo — it resets env to dev)
uv run ai-team run --backend langgraph --team prototype --env test \
  --skip-estimate "$(jq -r .description demos/00_smoke_test/input.json)"
```

Pass criteria:

- [ ] Process exit 0; phases complete without budget abort.
- [ ] Workspace / demo `output/` contains expected artifacts (or matches `expected_output.json` for demo runs).
- [ ] Generated smoke tests run green (`pytest` on the produced module).
- [ ] No systematic tool non-compliance (model narrates tools instead of calling them — known failure mode for weaker models).

### 5. Gate B — vertical slice (required before `test`/`prod` promotion)

```bash
# DEV path
uv run python scripts/run_demo.py demos/02_todo_app \
  --skip-estimate --backend langgraph

# TEST / PROD path
uv run ai-team run --backend langgraph --team full --env test \
  --skip-estimate "$(jq -r .description demos/02_todo_app/input.json)"
```

Pass criteria:

- [ ] Exit 0 (or only *designed* HITL you intentionally accept).
- [ ] CRUD-capable app + tests present; acceptance contract met.
- [ ] Manual or container smoke of the generated app when Docker is in scope.
- [ ] Spend within `AI_TEAM_RUN_BUDGET_USD` / estimate ceiling.

### 6. Gate C — variance / confound (required for claims or PROD defaults)

Single runs are anecdotes (same backend can swing minutes). Before calling a model
“better” in docs or making it the prod default:

- [ ] **n ≥ 5** on the same brief + backend + tier (see journal / COMPARISON_RESULTS practice), **or**
- [ ] Same-model matrix (`--team full-claude`) when comparing *frameworks*, so model is held constant, **and**
- [ ] Optional backend sweep:
  ```bash
  uv run python scripts/compare_backends.py demos/00_smoke_test --env <tier>
  ```
- [ ] Record wall-clock, cost, green/red, and failure class in [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md) (or a PR note).
### 7. Gate D — product evals (optional, when evals cover the scenario)

Our harness evaluates *runs*, not leaderboards — see [EVALS.md](EVALS.md):

```bash
AI_TEAM_USE_REAL_LLM=1 uv run python -m evals.run_evals --backend langgraph --scenario <name>
```

- [ ] Only if a scenario exercises the role you changed; skip if no matching scenario.

### 8. Ship the config + docs

- [ ] Update `_PRICES` from OpenRouter if you edited `ENV_MODELS`.
- [ ] Update this file’s matrix tables and the per-model “Why we use it” row.
- [ ] Update `full-claude` pins if the same-model comparison ID moved.
- [ ] `uv run pytest tests/integration/test_openrouter.py tests/unit/test_settings.py -q`
- [ ] Mention intentional rejects (what you *didn’t* pick and why) in the PR.

### Tier promotion rules (summary)

| Promote to | Minimum gates | Notes |
| ---------- | ------------- | ----- |
| `dev` default | 1 + 2 + 4 | Prefer one cheap generalist; cost is the feature |
| `test` default | 1–5 | Role-fit mid-tier OK; still no Opus “because shiny” |
| `prod` default | 1–6 (7 if eval exists) | Premium only where cascade cost is high (architect / core coding) |
| Profile override only | 1–2 + 4 | Enough for a personal A/B; do not claim matrix victory |

### Out of scope for this checklist

- Automatic cross-provider failover (not implemented — see [Failure modes](#failure-modes-no-provider-failover)).
- Replacing Anthropic SDK models via `AI_TEAM_ENV` (ignored on that backend).
- Treating Chatbot Arena #1 as automatic PROD for every role.

## Research notes / sources (2026)

Selections above synthesize public OpenRouter pricing/catalog, provider launch notes, and
third-party coding/agentic comparisons (SWE-bench family, Terminal-Bench, MCP Atlas,
cost-per-task audits). Bench numbers move; treat them as **directional** and re-validate
with the promote checklist (Gates A–C) before trusting a new ID in CI.

Useful starting points:

- [Artificial Analysis LLM leaderboard](https://artificialanalysis.ai/leaderboards/models)
- [OpenRouter models + rankings](https://openrouter.ai/models)
- [SWE-bench](https://www.swebench.com/)
- [LM Arena](https://lmarena.ai/)
- [DeepSeek V4 Flash vs Pro (coding agents)](https://www.coderouter.io/blog/deepseek-v4-pro-vs-v4-flash-coding)
- [Claude Sonnet vs Opus routing](https://www.cosmicjs.com/blog/claude-sonnet-vs-opus)
- [Introducing GPT-5.5 (OpenAI)](https://openai.com/index/introducing-gpt-5-5/)
- [Gemini 3.5 Flash (Google)](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash)
- [OpenRouter: open-weight models that matter (Jun 2026)](https://openrouter.ai/blog/insights/the-open-weight-models-that-matter-june-2026/)

---

## Related docs

- [AGENTS.md](AGENTS.md) — persona registry
- [TEAM_PROFILES.md](TEAM_PROFILES.md) — which agents run per profile
- [GETTING_STARTED.md](GETTING_STARTED.md) — setup and 402 troubleshooting
- [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md) — measured backend outcomes
- [EVALS.md](EVALS.md) — run/scenario eval harness (complements this checklist; does not replace Gates A–C)
- [claude-agent-sdk/RUNBOOK.md](claude-agent-sdk/RUNBOOK.md) — SDK backend ops
