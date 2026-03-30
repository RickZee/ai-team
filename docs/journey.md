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

![See missing prompts screenshot](feb-14-missing-prompts.png)

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

Also added **team profiles** — not every project needs all 8 agents. A `--team backend-api` flag spins up only Manager, PO, Architect, Backend Dev, QA, and DevOps. Skip the frontend. A `--team prototype` flag skips formal planning entirely and goes straight to Architect → Fullstack Dev → QA. This works across both backends.

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
