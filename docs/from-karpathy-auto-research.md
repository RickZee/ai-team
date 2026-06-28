**Proposed Extension: Add a "Karpathy AutoOptimizer Loop" (AutoResearch Mode) to ai-team**

Andrej Karpathy’s lets a simple AI agent autonomously iterate on a single editable file (or small harness) inside a tight constraint: fixed experiment budget/time, a single clear metric (e.g., training speed, validation loss, benchmark score), edit → run → measure → git commit/revert. In the demo, it ran ~700 experiments overnight on a nanochat training setup and delivered 11%+ speedups (plus a critical bug fix) that beat what 20-person human teams had achieved—for roughly $300 in API costs. The video frames this as the practical “local hard takeoff” pattern for agentic systems: AI as maintainer, not oracle.

Your `ai-team` repo is *already* the perfect foundation for this. It already ships:
- Specialized agents (Manager, devs, QA, DevOps, etc.)
- Pluggable backends (CrewAI default, LangGraph, Claude Agent SDK)
- Rich toolset (git, filesystem, Docker, tests)
- Guardrails, RAG, session + long-term memory
- Self-improvement reports + lesson injection
- Observability (web dashboard, TUI, CLI, structured logs, cost tracking)
- Eval/demo scaffolding

So the extension is **not** a rewrite—it’s a natural, high-leverage addition that turns your one-shot autonomous builder into a **self-improving autonomous research lab**.

### What the New Feature Looks Like (User Experience)

```bash
# 1. Normal build (unchanged)
uv run ai-team "Build a fast REST API for todo lists" --team backend-api

# 2. New optimization mode (the extension)
uv run ai-team "Optimize the todo API we just built" \
  --mode=karpathy-loop \
  --metric="requests-per-second-under-100ms-p99" \
  --budget="4 hours OR 50 experiments" \
  --base-dir="./output/todo-api" \
  --strategy-file="./strategy.md"   # optional high-level guidance
```

Or as a post-build phase:
```bash
uv run ai-team ... --optimize --metric=... --budget=...
```

### Core Components of the Extension (Minimal & Clean)

1. **New Agent Role: `Optimizer / Researcher`**  
   - Prompted exactly like Karpathy’s agent: “You are an autonomous researcher. Your only job is to edit the target files, run the experiment, extract the metric, and decide keep/revert. Stay inside the budget.”
   - Can be added to any existing team profile or used standalone (`--team=research-optimizer`).

2. **New Backend-Agnostic Module** (`src/ai_team/optimizers/karpathy_loop/`)
   - `KarpathyLoop` class that implements the tight loop:
     - Parse strategy + metric definition
     - Snapshot current codebase (git worktree or branch)
     - Agent proposes edit(s) → applies via existing FS/Git tools
     - Spins up isolated Docker sandbox (you already have Docker tooling)
     - Runs evaluation script / benchmark / load test
     - Parses metric from stdout/JSON/logs
     - If improvement → `git commit` with experiment log; else `git reset`
     - Logs full experiment (diff, metric delta, cost, duration) to RAG + long-term memory
   - Reuses your existing `monitor.py`, guardrails, and OpenRouter embeddings.

3. **Metric & Experiment DSL** (simple YAML or Pydantic model)
   ```yaml
   metric: "rps_p99_latency"
   evaluation_command: "docker compose run --rm loadtest"
   success_threshold: 1200
   timeout_per_experiment: 300   # seconds
   max_experiments: 50
   editable_files: ["src/main.py", "src/config.py"]   # or "all" with safety
   ```

4. **Integration Points (almost zero friction)**
   - Hook into the existing `ProjectResult` and `TeamProfile` system.
   - Manager agent already writes self-improvement reports → extend it to also synthesize “optimization lessons” that get injected into RAG (exactly like your current self-improvement loop, but now data-driven from hundreds of real experiments).
   - Works with *any* backend (CrewAI, LangGraph, Claude SDK) because the loop is orchestration-agnostic.
   - Add to the web dashboard: new “Experiments” tab showing live progress, metric charts, git history of winning versions.

5. **New Demo**  
   Add `demos/06_karpathy_optimization/` (e.g., optimize one of your existing Flask/FastAPI demos or a tiny ML training loop). Include the `strategy.md`, metric extractor, and a ready-to-run `compare_before_after.sh` script. This becomes the killer demo for the repo.

### Why This Is a *Meaningful* Extension

- **Directly inspired by the video** that’s blowing up (41k bookmarks on Karpathy’s wiki tweet + massive discussion).
- Elevates `ai-team` from “autonomous code generator” → “autonomous code *improver* / research engine”.
- Plays perfectly to your existing strengths (tools, Docker, git, observability, self-improvement).
- Low implementation cost: ~300-500 LOC + config + one new agent role + demo.
- Huge differentiation vs. other CrewAI/LangGraph templates.
- Opens future doors: multi-metric Pareto optimization, parallel experiments (if you add GPU/ray support later), applying the loop to *ai-team’s own prompts and orchestration code*.

### Suggested Implementation Roadmap (PR-ready)

1. Add `src/ai_team/optimizers/karpathy_loop/` (core loop + metric parser).
2. Extend `agents.yaml` and `team_profiles.yaml` with `optimizer` role.
3. Add `--mode=karpathy-loop` flag + argument parsing in CLI/core.
4. Update `README.md` + docs/ with new section and example.
5. Add the demo + CI test (mocked LLM mode so it’s cheap to run).
6. (Bonus) Add a hybrid memory note in docs tying back to the video’s wiki vs. OpenBrain discussion—your RAG + experiment logs naturally form the “write-time synthesis” Karpathy advocates.

This extension keeps the repo’s clean architecture while making it *feel* like the future the video is describing: a $300 AI team that doesn’t just ship code once, but keeps getting better every night while you sleep.
