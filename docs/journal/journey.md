# The project's background and ongoing story

## Why I created this project

My wife and I were talking about advancements of agentic systems and their use in large corporations or government organizations.

I decided to make a quick prototype for how such system would like like.

## Approach

I am using a combination of AI tools:

* SuperGrok for quick research, since I don't have any limits on tokens
* Claude Code to create in-depth architecture documents and plans
* Cursor for executing the plans and implementing the system

## Journey

### Feb 15

Raining Sunday morning, 11 AM, coffee and the original ideation :)

Created the initial plans and prompts. Opus 4.5 created very nicely designed build plan and initial prompts.

The problem was - I started running them in cursor only to realize that Claude didn't really do a good job:

![See missing prompts screenshot](images/feb-14-missing-prompts.png)

So now I have gaps in implementation and need to start from scratch.

Also there is way to run multiple agents in Cursor in parallel.

Sunday 6 PM (had to do a short Costco run): Phase 0, 1 and 2 prompts are all completed. It's great Monday is a federal holiday in the US, should be able to finish all prompts for the 6 phases Opus generated for us. Can't wait to actually start testing. Are we really going to be able to run this team using just the local models in Ollama??

Generated so far, within approximately 6 working hours:

```text
-------------------------------------------------------------------------------
Language                     files          blank        comment           code
-------------------------------------------------------------------------------
Python                          64           1675           1756           6255
Markdown                        15            690              0           2599
YAML                             3             59             15            381
Bourne Shell                     1             26             21            231
JSON                             4              0              0             20
-------------------------------------------------------------------------------
SUM:                            87           2450           1792           9486
-------------------------------------------------------------------------------
```

### Feb 16

This is very cool! After 2 hours of work, we are into running integration tests, at the end of Phase 4.

Knowing how it usually is, I expect to be stuck at this phase for several days. We'll see...

And we crushed! The integration tests successfully created the team and started executing a full flow tests. My my Mac with 36GB of unified memory got completely unresponsive. Even the resource monitor wasn't showing anything useful except that Cursor was consuming 92GB of memory. Out of available 36. And after several short minutes the computer rebooted.

Alright, we are now back to the very typical back and forth with Cursor. It runs some tests, while skipping or disabling others. When it doesn't like a failed test, it just reports a success and asks you to move on.

## Feb 18

Skipping the busy Monday Feb 17... Who doesn't like to start learning at 5 AM?!

Yes, as expected, the default Cursor Composer is quite limited. It confuses setups, stops at integration tests where Sonnet 4.6 gives clear, short and precise instructions.

Cursor keeps bossing me around. I'm telling it to run the install script, then to execute the integration test. Result: it updated the readme file to tell *me* to execute the script and run the test. Thank you Cursor.

## Feb 21

After many out of memory reboots on my mac :)... Let's do something better. Let's use one of those LLM routers and see how much it'll cost.

## Feb 22

OK so running a smaller LLM definitely affects the team's performance. Big surprise. Alright so we're saving on cost running it locally be losing big time on actually being able to achieve results.

Pivoting to using APIs, with strict cost control and monitoring today.

Also, monitoring the CrewAI using logs is awkward. Let's build a very simple UI for it. Or TUI, as most people are not doing.

OK so the basic project is now working. Now testing every step, adding more guardrails and tweaking prompts.

Let's plan to deploy it on AWS AgentCore as well.

After multiple test runs using Ollama - it's now clear that not only it's slow, but also not feasible at the moment if you really want to make any progress. Most of the test runs are very slow, the local models are way to dumb to perform tasks, and the system crashes several times a day because I don't have enough memory.

Ok so for the next time - migrate from Ollama to OpenRouter and try running again.

## Feb 27

Bright and early Friday... Finally, running a demo! And seeing agent talk to each other. This is very cool.

Also, enjoying the regular (as of late), Cursor idiosyncrasies. I'm getting a feeling that just switching to Claude full time will get a much better value, faster results. It's like arguing with a mid-level engineer, who have enough experience to have very strong opinions, but not enough experience to understand a larger context, and not willing to even try what is being asked. And - just throwing the task back at you, "here, if you're so smart why don't you do it yourself".

Ran into a problem with free OpenRouter account - the max number of tokens is 4096, and there's no way to set a larger limit?

## Fed 28

Well I can't believe this is the second weekend I'm spending on this :)

Now that the code has been integration tested, and is actually trying (quite desperately) to produce some working code, let's look at different options for production deployments.

OpenRouter is great but I think it's time to get serious and try out something enterprise-ready. Lets switch to AWS Bedrock and it's cheap Nova models. With some cost estimates to see whether it's really cheap :). Anyone out there who's been oversold by great technical sales team from vendors?

## Mar 29

One month passed and it looks look like the orchestration frameworks and harnesses are getting release at the speed of front-end libraries back in 2015 (meaning a few of the new, hot, better than all the rest every week or so).

So, what do I think about CrewAI? CrewAI got us far — it's nice for simple pipelines, and the hierarchical process handles basic delegation. But as the system grew, the limitations became clear:

- **Debugging is a black box.** When a crew fails, figuring out *which agent* misbehaved and *why* requires digging through verbose logs. We need state inspection, replay/time-travel.
- **Human-in-the-loop is bolted on.** The `awaiting_human_input` flag + polling pattern is fragile. Real production workflows need native pause/resume.
- **Persistence is DIY.** We cobbled together ChromaDB + SQLite for memory, but crash recovery means re-running from scratch.
- **Composition is rigid.** Each Crew is a monolith — you can't easily test the Product Owner agent independently from the Architect, or swap one crew's strategy without touching the others. Again, totally fine for simple systems.

So, next for us: exploring LangGraph. LangGraph gives us explicit graph-based orchestration where every agent step is a node, routing is pure functions on state, and persistence/human-in-the-loop/streaming are built-in. The supervisor pattern maps cleanly to our Manager→Specialist delegation model, and subgraphs give us the isolation we need for independent testing.

I'm **not** ripping out CrewAI. Instead I want to evaluate a multi-backend architecture. Both orchestration frameworks live behind a common `Backend` protocol. Same shared tools, guardrails, models, config. Pick your backend at runtime: `--backend crewai` or `--backend langgraph`. This lets us run the exact same demo through both and compare output quality, cost, and latency side by side.

Also added **team profiles** — not every project needs all 8 agents. A `--team backend-api` flag spins up only Manager, PO, Architect, Backend Dev, QA, and DevOps (no frontend specialists). A `--team prototype` flag uses Architect, Fullstack Dev, and QA across intake → planning → development → testing. LangGraph and Claude Agent SDK backends honor the profile roster; CrewAI records the profile in metadata while full-crew parity is still catching up. See [TEAM_PROFILES.md](TEAM_PROFILES.md).

The architecture is also designed for future frameworks: AutoGen, Claude Agent SDK, AWS Bedrock Agents, Strands — each would just be another `Backend` implementation.

Two more additions to the plan: **MCP servers** and **RAG**. Both are designed as shared, backend-agnostic layers — they work with both CrewAI and LangGraph.

Let's see what we find out after getting LangGraph working.

I'm also curious about cost - how each option would allow us to monitor and control what we spend.

OK one more before I wrap for the day. Created a full plan for a third backend: **Claude Agent SDK** (`docs/claude-agent-sdk/CLAUDE_AGENT_SDK_PLAN.md`). This one is fundamentally different from both CrewAI and LangGraph — it's session-based, not state-based. There's no explicit state graph or typed ProjectState flowing between nodes. Instead, agents write artifacts to the filesystem and downstream agents read them. The SDK handles session persistence, streaming, MCP, and cost tracking natively — things that require plugins or custom code in the other frameworks.

The architecture is nested subagents: Orchestrator (Manager) → Phase agents (planning, dev, testing, deploy) → Specialist agents (PO, architect, devs, QA, devops, cloud). Each level has its own isolated context window. Guardrails work through three layers: prompt instructions (behavioral), SDK hooks (security enforcement via PreToolUse/PostToolUse), and MCP tools (on-demand quality checks).

The interesting bit: `CLAUDE.md` becomes the shared knowledge base. The SDK loads it automatically for every agent, replacing the need for RAG-based prompt injection for static conventions. Dynamic knowledge still goes through the `search_knowledge` MCP tool.

So now we have three backend plans, all behind the same `Backend` protocol: CrewAI (crews + flows), LangGraph (state graphs + subgraphs), Claude Agent SDK (nested subagents + file-based state). Same demos, same team profiles, comparable results. The comparison framework will measure quality, cost, latency, token usage, and developer experience across all three.

Went back and audited the Claude Agent SDK plan for underutilized capabilities. Found we were leaving a lot on the table. Added Section 10 ("Advanced Claude Capabilities") and Phase 4b (5 new tasks, 33 total). The highlights:

- **Extended thinking with per-agent effort levels** — Architect gets `effort: "high"` with adaptive thinking (visible reasoning traces before architecture decisions); DevOps gets `effort: "low"` (Dockerfiles are templated, don't need deep reasoning). This is a huge differentiator vs CrewAI/LangGraph where you can't tune reasoning depth per agent.
- **Prompt caching** — automatic, up to 90% savings on input tokens. CLAUDE.md, tool schemas, and prior conversation history are all cached. For a 9-agent system with ~100 total turns, estimated input cost drops from ~$22 to ~$2.50.
- **File checkpointing** — snapshot workspace before risky phases, rollback if validation fails. Simpler than git-based rollback and built right into the SDK.
- **Vision for QA** — QA agent can analyze screenshots. Visual regression testing without external tooling.
- **ToolSearch / deferred loading** — when MCP servers expose >10 tools, defer loading and let the agent search on demand. 85% reduction in schema overhead.
- **Skills** — reusable `.claude/skills/` for code review, test analysis, API design. Agents invoke them automatically when the task matches.
- **Session forking** — branch from a planning-complete session to A/B test different architectures (monolith vs microservices vs serverless). Unique to the Claude SDK.
- **Batch API** — 50% cost savings for non-urgent bulk analysis (nightly code reviews). Stacks with prompt caching for up to 95% off.

The comparison matrix now has 11 rows where Claude Agent SDK has a ✅ and the other two have ❌. That said — the other backends have their own strengths (LangGraph's state inspection and time-travel, CrewAI's simplicity). The whole point of the multi-backend architecture is to let the data speak.

## Mar 30

Shipped a full web UI. Not a quick Streamlit thing — a proper FastAPI backend with a React/Vite frontend, WebSocket streaming for live agent updates, a phase pipeline view, a guardrail panel, and a backend comparison page. ~3,500 lines in one commit. Also moved Docker files to `docker/`, cleaned up the repo layout.

**Why FastAPI + React?** We started with a Rich TUI (still works, great for SSH). Once the system had multiple backends, team profiles, and real-time streaming from agents, we needed something that could handle WebSocket connections, show a live phase pipeline, and let you compare runs side-by-side. FastAPI + React with Vite was the pragmatic choice — we already had the API shape from the CLI, and Vite's dev experience is hard to argue with. The Textual TUI (`ai-team-tui`) now shares the same web API for full parity.

**The big architectural insight here:** the UI is a thin consumer of a shared observation API. The FastAPI server holds in-memory `TeamMonitor` state and exposes it over REST (`/api/runs`, `/api/runs/{id}`) and WebSocket (`/ws/run`, `/ws/monitor/{id}`). CLI runs also write `events.jsonl` under workspace output, but the dashboard streams live snapshots from the server rather than tailing those files today.

Alongside the UI, wired up the memory system properly. `memory/lessons.py` is the core: it captures failure records into SQLite at the end of every run, clusters recurring patterns by `(pattern_type, clustering_key)`, and promotes them into lessons that get injected into agent system prompts at the start of the next run. Both backends consume lessons from the same `LongTermStore` — CrewAI appends them to agent backstories, LangGraph injects them as a `## Lessons` section in system prompts.

Also added `scripts/extract_lessons.py` to promote patterns manually (more on this in a sec — spoiler: manual is the wrong design for an autonomous system).

The self-improvement loop is real now, not just a diagram in a doc.

**Takeaway for builders:** the hardest part of self-improvement isn't the ML — it's the plumbing. Getting failure data out of a run, into a durable store, clustered into patterns, and back into prompts in a way that works across backends and doesn't break when something goes wrong... that's 80% of the work. Every lesson-related call is wrapped in `try/except` or `contextlib.suppress(Exception)` — a broken lesson system should never break a run.

## Apr 1

Actually ran a demo end-to-end and watched the self-improvement loop close.

Here's what happened: LangGraph run `3ebc3d3a` (backend-api team, hello_world demo) failed in the testing phase. The backend developer's retry response contained full source code in its message body — `app.py`, `Dockerfile`, the works, all in markdown code blocks. The QA agent received this as input, and the behavioral guardrail flagged it: *"QA Engineer should only write test code, not modify production source"* (9 violations, relevance 36% below the 50% threshold). Classic false positive — the QA agent wasn't *writing* production code, it was *reading* a message that contained production code.

The system captured the failure, persisted it to the long-term store, and pattern-matched it against previous runs. The lesson system promoted it: *"Avoid guardrail violations: Recurring failure detected. Phase: testing. Error: GuardrailError."*

Then the manager agent wrote a self-improvement report — not a log dump, but an actual narrative: which failures occurred, what prior lessons were relevant, and concrete next steps (retry with enforced role boundaries, adjust guardrail thresholds, review workspace layout, incorporate the promoted lesson).

**This is the loop working.** Failure → structured capture → pattern clustering → lesson promotion → prompt injection → manager narrative → actionable proposals. Closed in 3 runs.

**What we learned about guardrails:** behavioral guardrails that score agent output against task scope are powerful, but they need role-specific tuning. A QA agent that *receives* production code in its input context is not the same as a QA agent that *writes* production code. The guardrail can't see the difference because it's doing content analysis, not provenance tracking. This is the kind of nuance you only discover by running real demos, not by unit testing guardrails in isolation.

One catch: lesson extraction still requires running `scripts/extract_lessons.py` manually between runs. For an "autonomous" system, that's a contradiction. The fix is trivial — call `extract_lessons(threshold=2)` at the start of every run, one SQLite query, zero LLM calls, ~1ms. It's on the list.

Also added Cursor pre-push skills (`.cursor/skills/pre-push-ruff/SKILL.md`, `.cursor/skills/pre-push-checks/SKILL.md`) and `./scripts/pre_push_check.sh` plus a `git push` hook (`.cursor/hooks.json`) that auto-runs the same gates as CI before push.

Stepped back from building and did a proper audit of the self-improvement mechanism. Not "does it work on the happy path" but "could an organization actually deploy this and trust it to improve over time?"

**The good:** the capture → extract → inject chain is genuinely working. Both backends write failure records to the same SQLite store. Lessons get promoted and injected. The manager's self-improvement report (run `3ebc3d3a`) is a real proof point — it references prior lessons, identifies the root cause, and proposes calibration. The whole system degrades gracefully: every lesson-related call is wrapped so that a broken lesson store never breaks a run. These are hard things to get right, and they're done.

**The gaps that would block production use:**

1. **Lesson extraction is manual.** The loop is open by default. An org deploys this, runs it 50 times, and unless someone remembers to run `scripts/extract_lessons.py` between runs, zero learning happens. The feature looks implemented but is effectively dormant. Fix: auto-extract at run startup, gated by `AI_TEAM_SI_AUTO_EXTRACT=true` (default on).

2. **No lesson deduplication.** Run the extract script twice, you get every lesson twice. Over time, agent prompts bloat with duplicate instructions. At 50 tokens per lesson × 20 duplicates × 9 agents, that's ~9,000 wasted prompt tokens per run. Fix: upsert semantics — check `(pattern_type, clustering_key)` before insert, increment `occurrences` on match, cap at `max_lessons_per_role=10` with LRU eviction.

3. **Quality metrics are never persisted.** The `performance_metrics` table exists in the schema. It has zero writers. The code quality guardrail computes a 0-100 score, the coverage guardrail computes pass/fail — these scores evaporate after the run. There is no way to answer "is the system getting better over time?" Fix: write metrics at the end of each phase, expose via `scripts/show_metrics.py`.

4. **Backend comparison is too thin.** The project claims to be a "framework comparison platform" but `BackendRunSnapshot` only captures: success/fail, wall-clock time, final phase, file count. You can't say "LangGraph produces better code than CrewAI" or "Claude SDK is 40% cheaper" based on a boolean and a stopwatch. Fix: extend the snapshot with token counts, cost estimates, quality scores, per-phase timing, retry counts, and require 5+ runs per backend per demo for statistical significance.

5. **No feedback on lesson quality.** Lessons are promoted based on occurrence count only. A lesson that fires 5 times but never actually prevents the failure keeps getting injected forever. Fix: track effectiveness — if a lesson is present and the same failure recurs 3+ times, mark it ineffective and stop injecting.

The full audit is in `docs/SELF_IMPROVEMENT_AUDIT.md` (maturity scorecard, risk assessment, ROI model, 12 prioritized improvements). The implementation blueprint is in `docs/SELF_IMPROVEMENT_DESIGN.md` (schemas, pseudocode, file-by-file change list).

**The meta-lesson:** building a self-improvement loop is deceptively easy to demo and deceptively hard to productionize. The flashy part — "agents learn from failures!" — takes a weekend. The boring parts — deduplication, TTL, effectiveness tracking, budget enforcement, observability — take weeks and are the difference between a portfolio demo and something an org would actually trust. We're honest about where we are: the critical path from here to production-ready is roughly 30 hours of implementation, with auto-extract + dedup + metrics persistence being the first 6.

## May 22

Goal: run demo 00 (hello world) end-to-end with `--team smoke --backend crewai`. First ever successful complete run. Took 11 attempts and most of a day.

### The runs

Runs 1–4 predated this session (previous context window). They stalled or failed in testing, left 4 zombie background monitor tasks sitting there burning attention but not tokens — harness cleans up across sessions, the tasks themselves were already dead.

Runs 5–10 were the core troubleshooting loop. Each one surfaced a different failure mode, usually in the testing or deployment phase. The pattern: 20–40 minutes to get to the failure point, then fix, rerun, next bug.

Run 11 succeeded: `--team smoke`, planning → development → testing → finalize_project (deployment skipped by profile), 10/10 tests passed, `project_complete status=complete files_generated=2 project_id=b15985e2`. Total wall-clock time was inflated to ~6 hours because the run sat in testing while other fixes were being developed in parallel — actual execution was much shorter.

### Bugs found and fixed

**1. Security guardrail false positive (runs 5–6)**

The QA agent was calling `run_pytest`, which returns coverage output including tracebacks. `guarded_run()` in `base.py` was validating both inputs *and* outputs against a security pattern list. The pattern `exec(` matched pytest traceback lines — harmless observational data, not executable code. The agent received `"Guardrail blocked output: Security violation: Dynamic code execution"` and halted.

Fix: removed output validation from `guarded_run()`. Input validation stays (attacker-controlled input can try to smuggle dangerous patterns into tool calls). Tool output is read-only observational data and should never be blocked this way.

**2. deepseek-v3 empty responses (runs 5–8)**

`cloud_engineer` and `qa_engineer` were assigned `deepseek-v3` in the DEV environment model config. Both returned `"Invalid response from LLM call - None or empty"` — the `deployment_packaging` task (large context: architecture JSON + all generated code + test results) and the `code_review` task both triggered it.

Two-part fix:
- Added `num_retries=3` and `request_timeout=120` to every LLM constructor in `llm_factory.py`.
- Switched `cloud_engineer` and `qa_engineer` to `devstral-2512` in `config/models.py`. The deployment crew context overflow was separately addressed by capping `_serialize_architecture()` and `_serialize_test_results()` to 3,000 chars each.

**3. QA over-generating tests (runs 7–8)**

After fixing the empty responses, QA started running. But the generated test suite included `test_add_invalid_inputs` — a test expecting `TypeError` from `add(a, b)`, which doesn't validate types. It never validated types. So 2 tests failed every run, blocking the coverage guardrail.

Fix: updated `TEST_GENERATION_DESCRIPTION` to explicitly say "Only test for exceptions or type errors if the implementation explicitly raises them — do NOT add defensive type-checking tests for functions that do not validate input types." This is a prompt engineering fix, but it's the right level — the guardrail can't know what the implementation does, but the task description can tell the agent what to expect.

**4. Team profile never passed from backend to flow (runs 1–10, root cause)**

This was the most consequential bug. `CrewAIBackend.run()` called `run_ai_team()` without the `team_profile` argument. Every single run — regardless of `--team smoke`, `--team prototype`, anything — executed with the `"full"` profile. The `smoke` profile skipping deployment was never honored. Every run tried to run `deployment_packaging`, which then hit the empty response bug on `cloud_engineer`, which caused the failure we were chasing for runs 5–10.

The fix is a one-liner: `team_profile=profile.name` added to the `run_ai_team()` call in `backends/crewai_backend/backend.py`. The bug was invisible because nothing logged a mismatch — `run_ai_team()` defaulted silently to "full". Added a `routing_after_testing_profile_check` debug log to make this class of mismatch visible in the future.

**5. Frontend a11y guardrail false positives**

The frontend implementation guardrail checked every output file for `aria-*` and `@media`/`flex`/`grid` patterns. `package.json`, `.env`, and markdown files never contain these patterns — so the guardrail always failed for projects that didn't generate UI components.

Fix: scoped checks to `_UI_EXTENSIONS = {".css", ".html", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte"}` and matching language tags. Non-UI projects (backend-only, infra-only) skip the checks entirely.

**6. Coverage threshold hardcoded at 80% regardless of profile**

`smoke` profile sets `min_coverage_pct: 0` — a smoke test shouldn't fail on coverage. But `_test_execution_guardrail` was a module-level constant using `MIN_COVERAGE_THRESHOLD = 0.8`. The profile setting was read into state metadata but never reached the guardrail.

Fix: replaced the constant with `_make_test_execution_guardrail(threshold)` factory pattern. `min_coverage_pct` is now threaded from profile YAML → flow metadata → `testing_crew.kickoff()` → `test_execution_task()` → guardrail closure.

### Architecture improvements shipped

**Smoke profile** (`config/team_profiles.yaml`): 3-agent team (architect, backend_developer, qa_engineer), phases = [planning, development, testing], `min_coverage_pct: 0`, `max_complexity: simple`, `phase_timeouts_seconds` for each phase. No frontend, no deployment.

**Phase timeouts** (`flows/main_flow.py`): `phase_timeout()` context manager using `threading.Timer` + `signal.SIGALRM`. Each phase has a configurable wall-clock limit from the profile. If exceeded, raises `PhaseTimeoutError` instead of hanging indefinitely. Critical for CI and unattended runs.

**LLM observability hooks** (`config/llm_observability.py`): new module, registers `register_before_llm_call_hook` / `register_after_llm_call_hook` globally (idempotent). Logs agent role, model, iteration count before each call; logs empty responses as errors. This is what would have caught the deepseek-v3 empty response issue immediately on the first run.

**Profile-aware deployment routing** (`flows/routing.py`): `route_after_testing` now loads the team profile and checks whether `"deployment"` is in `profile.phases`. If not, routes directly to `finalize_project`. Previously it always routed to `run_deployment`.

### Architecture review

Did a thorough review of the CrewAI backend design. Found 16 issues. Three were fixed today (above). Remaining 13 are documented but not yet addressed:

- Human feedback not injected into retry crew context (Finding #3) — retries have no memory of what the human said
- Test failure feedback not passed to dev crew on retry (Finding #4) — dev crew reruns from scratch, not from failure context
- `infra-only` profile still runs dev+testing phases (Finding #5) — profile phase filtering only applies at routing, not crew construction
- Race condition with `PROJECT_WORKSPACE_DIR` env var (Finding #7) — concurrent runs share a global env var for workspace path
- `retry_planning` listener unreachable from error handler (Finding #9) — error paths never trigger it
- Planning outputs matched by index not name (Finding #10) — if task order changes, wrong outputs get consumed

The race condition (#7) and feedback gaps (#3, #4) are the most operationally dangerous. The others are correctness issues that only surface on edge-case profiles.

### Post-completion anomaly

After Run 11 succeeded and `project_complete` fired, the log kept emitting `project_complete` roughly every minute. `current_phase` in state showed `"deployment"` despite deployment being skipped. Something in the flow is re-triggering after completion — likely a `@listen` on `finalize_project` that loops back, or the CrewAI Flow event loop not stopping after the terminal state. Not investigated yet; the run produces correct output so it's cosmetic for now, but it would be a real problem for cost tracking in production.

## Jun 24

Went back to the Apr 1 self-improvement audit and closed the two gaps it called "the first 6 hours" — the ones standing between a portfolio demo and something an org would actually trust.

**Gap #1 — the loop was open by default.** Lessons only got promoted when someone remembered to run `scripts/extract_lessons.py` between runs. So the headline feature ("agents learn from their failures") was effectively dormant in any real deployment. Fixed by wiring `maybe_extract_lessons_at_startup()` into `_cmd_run` right after the backend resolves — it runs for *every* backend and *every* path (run, resume, stream), gated by `AI_TEAM_SI_AUTO_EXTRACT` (default on). It's a pure SQLite pass, no LLM calls, so it's cheap enough to run unconditionally. The loop is now closed by default: failure → capture → cluster → promote → inject, with no human in the middle.

**Gap #3 — improvement was unmeasurable.** The `performance_metrics` table had a writer (`add_metric`) and zero callers in the run flow. The code-quality guardrail computed a 0–100 score and the coverage guardrail computed pass/fail, and both evaporated when the run ended. There was no way to answer the only question that matters for a self-improving system: *is it actually getting better over time?* Fixed by `persist_run_metrics(result)` at run end — it pulls run-level KPIs (success, files generated, tests total/passed, derived pass rate, coverage, quality score, cost, duration) out of the normalized `ProjectResult` defensively (backends surface different fields) and writes them against a sentinel `_run` role. Added `LongTermStore.get_metrics_timeseries()` (time-ordered, unlike the existing aggregate-only `get_metrics_summary`) and `scripts/show_metrics.py`, which prints a per-metric trend arrow comparing the latest third of runs to the earliest third.

**Design discipline carried over from the audit's own warnings.** Both functions are wrapped so a broken self-improvement subsystem can never abort a run — the same `try/except` + structured-log convention the rest of the SI code already follows. The env flags fall back to their default on garbage input rather than raising. One bad metric doesn't block the others. Memory-disabled and SI-disabled are honored explicitly.

**Tests:** 21 new unit tests covering happy paths, both env-flag toggles, the division-by-zero edge on pass rate, time-ordering of the series, and three adversarial cases proving the run survives when extraction blows up, settings access blows up, or memory is off. All green; ruff and mypy clean on the new modules.

**Meta-note for the writeup:** this is exactly the "boring 80%" the Apr 1 audit flagged. The flashy part — agents learning from failures — took a weekend back in March. Closing the loop so it runs unattended, and making the improvement *legible* as a trend line, is what turns it from a demo into something you'd deploy. Roughly the first 6 of the audit's estimated 30 hours, done.

## Jun 28

Spent the day chasing why the LangGraph todo-app demo would run for 10+ minutes and produce nothing. Turned out to be the most interesting failure of the project so far, and it's not a bug in my code — it's the model refusing to *be* an agent.

**The model writes code as prose and asks permission.** deepseek-v3 (via OpenRouter) given a `file_writer` tool and told *"call file_writer — do not output code as plain text"* does exactly the opposite. It writes the whole Flask app as a markdown code block and ends with: *"Would you like me to proceed with saving these files?"* There's nobody to say yes. It's behaving like a chat assistant in a conversation, not an autonomous worker in a loop. The code is *correct* — it just never leaves the transcript.

**Why that quietly destroys the pipeline.** Phases hand off through files on disk, not the chat history (deliberate design — it's how real teams coordinate). So when dev writes `main.py` as prose: workspace has no app → QA runs real pytest → `ImportError` → routing retries development → dev writes the same prose again → loop. Each lap is a full dev+testing phase on a slow model. Pre-fix this looked like a 10-minute hang ending in failure, having generated perfectly good code the whole time and thrown all of it away.

**The fix is salvage, not a better model.** If the model won't call the tool, parse its prose and write the files myself. Sounds hacky; it's actually the right call — the whole project is about comparing backends including open models, so the orchestration *has* to survive non-compliant models. Three iterations:
- Caught the QA phase first (smoke test now passes — QA was doing the same prose thing on a 2-file calculator).
- Then the dev supervisor used *numbered* headers — ``### 1. `main.py` (Flask Application)`` — that my regex missed because the filename wasn't right after the `#`s. Widened it (require backticks around the filename so I don't grab prose that merely *mentions* a file).
- Then the real loop-driver: dev-phase salvage was gated on "workspace empty", but once any file existed (a test from a prior retry) it skipped — silently dropping `main.py`. Now it always extracts. After that, the app code finally lands on disk.

**Found a path-traversal hole while writing the salvage tests.** The existing extractor did `fname.lstrip("./")` — which strips *any* leading dot/slash chars, so `../escape.py` becomes `escape.py` and sails past the `..` check. My own adversarial test caught it. Fixed to strip at most one `./` and reject absolute paths, `..` segments, dotfiles.

**Money was unbounded on a looping run.** The retry caps bound the *count* of loops, but nothing bound *spend*. A crash-loop on a slow model just burns dollars. Added a per-run ceiling (`AI_TEAM_RUN_BUDGET_USD`) fed by the real per-call cost OpenRouter reports — and the same thing for CrewAI via a LiteLLM callback, since CrewAI only had an *error-count* budget, not a dollar one. The fun design detail: the budget-exceeded exception subclasses `BaseException`, not `Exception`. Sounds pedantic, but both the LangGraph phase nodes *and* LiteLLM wrap their callbacks in `except Exception` and treat failures as non-blocking. Making it a `BaseException` is the only way the abort actually stops the run instead of getting swallowed and retried — i.e. the very loop we're trying to kill would otherwise eat its own kill signal.

**The honest verdict on the todo demo:** still doesn't fully pass on LangGraph. The salvage lands the files now, but the agents don't agree on a project layout — QA writes `from main import app`, dev writes `todoapp/app.py` — because no agent *owns* the structure; each phase invents its own paths. That's the next real problem, and it's an agent-*coordination* problem, not a parsing one. Probably needs the planning phase to pin a file layout and inject it into both dev and QA prompts so the imports line up.

**Meta-note:** every guardrail I added this session is defending against the model not doing what it's told. Timeout, spend cap, salvage, retry-routing — all of it is "the agent misbehaved, don't let that hang/bankrupt/crash the run." The uncomfortable takeaway: a big chunk of "building an agent system" is really *building the harness that survives the agent*. The smarter the model, the less of this you need — Claude via the SDK shows almost none of it — but you can't assume the model, so you build the harness anyway.

## Jun 30

Came back with one question: **do we keep CrewAI at all, or is it the wrong tool for this kind of file-handoff orchestration?** Ran the documented smoke-test eval — `add(a, b)` plus one pytest, the most trivial scenario we have — across all three backends and let the numbers answer.

| Backend | Result | Wall time |
|---|---|---|
| langgraph | ✅ 12 passed, 4 skipped | **60s** |
| claude-agent-sdk | ✅ 10 passed, 2 skipped | **200s** |
| crewai | ❌ never produced a result — hung inside the first test | killed by hand at ~12 min |

The two graph/SDK backends were green and fast. CrewAI **hung on the calculator** — collected its 12 tests, entered the run, and stopped emitting progress. Worse: it didn't even respect its own `--timeout=1100`. The `signal`-based pytest timeout couldn't reap it because the live CrewAI `Live`/event-bus threads swallow the alarm (open item #6 from the 06-28 handoff, now reproduced cleanly). I had to `kill -9` the process group; it would have sat there forever.

**The verdict: CrewAI is the wrong abstraction for *this* workflow, but not worthless.** The reason is structural, not a model quirk:

- **Our coordination model is file-on-disk handoff between phases.** LangGraph's `StateGraph` makes every transition explicit, so "dev wrote nothing → route to retry" is a first-class, observable, *interruptible* edge. The Claude SDK runs each phase as a real subagent that reliably calls tools. CrewAI's `Flow` + `Crew` model wants to coordinate through *agent conversation and structured task outputs* — which is exactly the layer that breaks when the model emits prose instead of tool calls, and which we then have to fight with salvage + verified-pytest guardrails.
- **CrewAI fights the harness.** The non-TTY Rich console recursion, the `RecursionError` on `json.dumps` of flow state, the embedder segfault, the post-`project_complete` re-trigger loop, and now a timeout it can ignore — every one of those was *CrewAI's runtime*, not the LLM. We've spent two full sessions adding CrewAI-specific defenses (`_disable_crewai_console`, `_flatten_crewai_payload`, `crew_memory_enabled`, orchestrated-pytest-outside-the-crew) and the smoke test *still* won't go green. That's a bad effort-to-reliability ratio.
- **It is not a model problem.** Same model (deepseek-v3 via OpenRouter) passes on LangGraph in 60s. So "use a better model" doesn't rescue CrewAI here; the orchestration runtime itself is the blocker on the trivial case.

**Path forward (decided):** keep CrewAI as a **comparison datapoint, demoted from a supported path**. Concretely:
- It stays in the eval matrix precisely *because* it fails — "the framework whose runtime fights non-TTY orchestration" is a real finding worth showing, not something to hide.
- It is **not** a recommended backend for production file-handoff pipelines. LangGraph is the default for reliability+speed; Claude SDK for safety/Anthropic-native.
- We stop pouring fix-effort into making CrewAI smoke-green. The remaining open items (#6 thread-hang, #5 false-pytest retry loop) get a single bounded attempt — a hard `subprocess`-level kill wrapper and a "tests-exist-on-disk → don't retry" short-circuit — and if that doesn't land it green, CrewAI is documented as *known-red on file-handoff workflows* and we move on. No more whack-a-mole against its event bus.

**Why not drop it entirely?** The whole thesis of the project is honest multi-backend comparison, and "we tried CrewAI for autonomous file-handoff orchestration and it fought us at the runtime level" is the most useful thing we can tell someone evaluating these frameworks. Deleting it would erase the finding. Keeping it *as a supported production path* would be dishonest given the data. Demoting-but-documenting is the truthful middle.

**Updated the substack post** accordingly — the old "Use CrewAI if you have an existing CrewAI codebase" verdict undersold the problem (it framed CrewAI as merely *slower*). The corrected verdict says the runtime actively fights non-interactive, file-handoff orchestration and hangs on a task the other two finish in a minute.

---

## Chapter: The correction — it was our wiring, and it *was* the model (2026-07-01 → 07-02)

The previous chapter ended with a confident verdict: *"It is not a model problem… the
orchestration runtime itself is the blocker."* This week forced a correction on both
halves — and the correction is more interesting than the original claim.

**Half one: the infinite retry loop was ours.** The "CrewAI deadlocks in retry" thread
that ran through three handoffs — the 8× duplicate emissions, the `retrying_development`
loop, the ~50% flaky verdict — root-caused to *our* flow wiring, not CrewAI's runtime.
In CrewAI Flows, a completed method emits its own name as the next trigger, and
completed listeners are deliberately cleared to allow cycles. Ten of our methods were
named identically to their own `@listen` trigger; each was an unbounded self-loop.
Live evidence: 93,284 retry iterations in 15 minutes. And the retry cap we thought we
had? Plain-listener return values are discarded — `return "escalate_to_human"` had
never routed once. One rename convention + real routers + a meta-test later: zero
runaway retries in every run since. Lesson we wrote on the wall: **read your
framework's event semantics from its source, not its docs — and before convicting a
framework, audit your own wiring.** (What *does* remain CrewAI's: the non-TTY Rich
console recursion class, and its overall pace — those held up under re-testing.)

**Half two: LangGraph's QA failures were a model problem after all.** Three clean
comparison runs (after the wiring fix, two guardrail false-positive classes fixed, and
subprocess isolation ending a GIL-starvation saga) left every backend failing or
succeeding for *real* reasons — and LangGraph+deepseek still ended in human escalation
every time, because deepseek's QA never called `file_writer`. So we broke the confound:
same framework, same brief, same guardrails, all nine roles pinned to claude-sonnet-4.
**deepseek wrote zero test files in 3/3 runs. Claude wrote real test suites in 4/4.**
The "framework failure" was a model property. What blocked the claude runs instead was
a new *stratum* of failures: OpenRouter routing the model through Google Vertex whose
translation layer rejects tool-call ids (133 retry-400s per run until we steered away),
spend ceilings calibrated for deepseek prices, and a quality gate that runs pytest in
the harness venv without installing the generated requirements.

**The synthesis** (now the thesis of the whole project): with each layer fixed, failures
migrate up the stack — model → framework → harness → provider. Reliability budget
ranking, with controlled evidence: **harness > model > framework**. Ten failure classes,
all with receipts, live in [posts/failure-taxonomy.md](../posts/failure-taxonomy.md);
the matrix data is in [COMPARISON_RESULTS.md](../COMPARISON_RESULTS.md).

A journal that never corrects itself is marketing. This entry is the reason the journal
exists.

## Jul 3 — four parallel worktrees, one Compare tab

Ran four Claude Code sessions in parallel worktrees against bugs surfaced while
exercising the web UI's Compare tab (all three backends side by side). Each session
owned a different bug, all branched from the same `main` commit (`daf3c95`), all
finished clean with no file overlap between them:

| Branch | Bug | Fix |
|---|---|---|
| `claude/elegant-shannon-9481b8` | Compare launches 3 backends in parallel on a **fresh** workspace; `allocate_run_id`'s mkdir-based reservation was skipped whenever none of the search roots existed yet, so all 3 callers raced an empty listing and returned the same run_id | Create the first search root before reserving, not just when it already exists |
| `claude/nice-albattani-6d02b7` | `CrewAIBackend.run()` fell back to `nullcontext()`/`get_settings()` when no `workspace_dir` override was given — a stale `PROJECT_WORKSPACE_DIR` left by an earlier run in the same long-lived process (web server, multi-backend comparison) leaked in and nested the new run under the old run's directory. `ResultsBundle` separately double-nested `workspace/<project_id>/<project_id>` when constructed from inside an already-scoped path | Always scope explicitly to the literal `"./workspace"`; `ResultsBundle` now checks whether `workspace_dir` already ends in `project_id` before appending it again |
| `claude/interesting-brahmagupta-95c0af` | CrewAI runs subprocess-isolated with no live `TeamMonitor` streaming, so its Compare column showed a frozen "Starting…" and permanent zeros for the whole run | Set phase to `DEVELOPMENT` on `run_started`; backfill files/tasks/tests totals from the subprocess result payload on `run_finished` via new `_apply_crewai_result_to_monitor()` |
| `claude/distracted-taussig-2ce7dd` | Compare run state lived only in React state — a page reload mid-run dropped to empty columns even though the server was still tracking the run | Persist `comparison_id` + `run_ids` to `localStorage`; reattach via `GET /comparisons/{id}` on mount, seeding terminal runs directly and reconnecting live ones through `/ws/monitor/{run_id}` |

All four merged into `main` with `--no-ff`, one at a time, tests run between each
(26/26 green on the touched suites: `test_run_naming`, `test_crewai_backend`,
`test_results_bundle`, `test_web_websocket`). Worktrees and branches deleted after
merge — all fully merged, nothing lost.

**Why four parallel sessions worked cleanly here:** each bug lived in a disjoint file
set (run_naming vs. crewai_backend+results/writer vs. web/server vs.
frontend/Compare.tsx+useApi.ts) despite all four surfacing from the *same* Compare-tab
exercise. No merge conflicts, no coordination overhead — the file-level isolation that
makes file-based agent handoff work (see the rest of this journal) applies just as well
to parallel human-directed debugging sessions.
