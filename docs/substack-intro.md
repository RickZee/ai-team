# Building the harness that survives the agent

*A field report on running the same nine-agent software team across three orchestration frameworks — and what breaks when you do.*

---

## What this project is

**ai-team** is an autonomous software-delivery pipeline: you hand it a one-line brief — *"Build a Flask REST API"* — and a team of nine specialized agents (Manager, Product Owner, Architect, Backend/Frontend/Fullstack developers, QA, DevOps, Cloud) takes it through intake → planning → development → testing → deployment. It writes the code, writes the tests, runs them, and produces the deployment artifacts.

That part isn't new. Plenty of projects will spit out a Flask app from a prompt.

What makes this one worth writing up is the rule I set for myself: **the same team, the same phases, and the same "what counts as done" contract all have to run on three completely different orchestration backends** — CrewAI, LangGraph, and the Claude Agent SDK — behind one `Backend` protocol. One team profile in YAML. One CLI flag, `--backend`, swaps the whole engine underneath.

The reason for that rule is honesty. If you only ever run one framework, you genuinely can't tell which of your problems are *yours* and which belong to the framework. Run all three on the same task and the arguments stop being opinion. They turn into data.

This is the intro to a series about that data — what breaks, how I figured out why, and how you can jump in if this kind of thing is your idea of fun.

---

## The thesis: most of "building an agent system" is building the harness that survives the agent

Here's the uncomfortable bit, said plainly, because it changes what this project even is.

Once you clear away the demos, most of the engineering in a real agent pipeline is **not** prompt-wrangling and **not** picking the right model. It's the harness — the plain, deterministic, non-LLM code whose whole job is to survive the model when the model does something dumb. Timeouts, spend ceilings, retry limits, output salvage, path validation, subprocess isolation, guardrail tuning. None of that is "AI." All of it is boring systems engineering, and all of it is load-bearing.

The smarter the model, the less of this you need — Claude via the SDK barely trips any of the wires below. But you don't get to *assume* the model, especially not when half the point is comparing open-weight models against frontier ones. So you build the harness anyway, and you build it to fail safe.

The rest of this post is a tour of what specifically breaks, because the failures are more instructive than any architecture diagram.

---

## Where multi-agent systems actually fail

Across three weeks of live runs I ended up cataloguing ten distinct failure classes. The thing that surprised me is how few of them were the LLM being *dumb*. Almost all of them were plain systems problems wearing an AI costume. A few of the sharpest:

### 1. The model writes code as prose and asks permission

Give deepseek-v3 a `file_writer` tool and tell it, explicitly, *"call file_writer — do not output code as plain text."* It does the exact opposite: it writes a complete, **correct** Flask app as a markdown code block and ends with *"Would you like me to proceed with saving these files?"*

There is nobody to say yes. It's behaving like a chat assistant in a conversation instead of an autonomous worker in a loop.

Why it quietly destroys the pipeline: phases hand off through **files on disk**, not chat history — a deliberate design choice, because that's how real teams coordinate. So when dev writes `main.py` as prose, the workspace stays empty → QA runs real pytest → `ImportError` → routing retries development → dev writes the same prose again. Each lap is a full dev-plus-test cycle on a slow model. Pre-fix, this presented as a ten-minute hang that ended in failure — having generated perfectly good code the whole time and thrown all of it away.

**The fix is salvage, not a better model.** If the model won't call the tool, parse its prose and write the files myself. That sounds hacky. It's actually the right call: the whole project exists to compare backends *including* non-compliant open models, so the orchestration has to survive them. It took three iterations to get right, and one of those iterations exposed a security bug (below) in my own salvage code.

### 2. A budget exception that gets swallowed and retried

Retry caps bound the *number* of loops. Nothing bound the *dollars*. A crash-loop on a metered model just burns money. So I added a per-run spend ceiling fed by the real per-call cost the provider reports.

The subtle part — and the reason I'm including it — is the exception type. The budget-exceeded exception subclasses `BaseException`, **not** `Exception`. That looks pedantic until you notice that both the LangGraph phase nodes and LiteLLM's callbacks wrap their bodies in `except Exception` and treat failures as non-blocking. If the abort were an ordinary `Exception`, the very loop you're trying to kill would catch its own kill signal, swallow it, and retry. Making it a `BaseException` is the only way the stop actually stops.

That's a one-line change that only makes sense once you've traced the control flow through two libraries you didn't write. It's exactly the kind of thing no amount of prompt-tweaking will ever surface for you.

### 3. A path-traversal hole — in my own guardrail

While writing adversarial tests for the salvage extractor, one of my own tests caught it: the extractor did `fname.lstrip("./")`, which strips *any* leading dot or slash character. So `../escape.py` becomes `escape.py` and sails straight past the `..` traversal check. The fix strips at most one `./` and rejects absolute paths, `..` segments, and dotfiles.

The lesson isn't "I wrote a bug" — everyone writes bugs. The lesson is that **the security guardrail needs its own adversarial test suite pointed straight at it**, because the guardrail is the last line of defense, and a guardrail you *think* is safe is worse than no guardrail at all.

### 4. A framework that fights the harness

This one took two full sessions to pin down with any confidence, and I want to be careful with it, because it's the kind of finding that's easy to turn into a cheap dunk on a framework.

On the most trivial scenario the project has — `add(a, b)` plus one pytest — LangGraph finished green in ~60s and the Claude SDK in ~200s. CrewAI collected its tests, entered the run, went quiet, and **ignored its own `--timeout`**. Its `Live`/event-bus threads ate the `signal`-based alarm, so I had to `kill -9` the process group. Left alone, it would've sat there forever.

Same model, same task — so "just use a better model" doesn't rescue it. It's structural. My coordination model is file-on-disk handoff between phases; CrewAI's Flow/Crew abstraction really wants to coordinate through agent *conversation* and structured task outputs — which is exactly the layer that falls apart when a model emits prose instead of tool calls. I'd spent two sessions writing CrewAI-specific patches (non-TTY console suppression, flow-state flattening, running pytest outside the crew) and the smoke test *still* wouldn't go green. Bad effort-to-reliability ratio.

**The part I'm actually proud of is what I did with that, not the finding itself.** I did *not* delete CrewAI. The whole point of the project is honest comparison, and "I tried this framework for autonomous file-handoff work and it fought me at the runtime level" is one of the most useful things I can hand someone who's evaluating these tools. Deleting it erases the finding. Keeping it as a *recommended* backend would be dishonest given the data. So it stayed in as a documented, demoted datapoint — known-red on this kind of workflow, still in the matrix precisely *because* it failed.

And then that decision aged in a direction I did not expect — which is the whole reason I want to talk about method.

---

## The method: one run is an anecdote, five runs is a measurement

Early on, every comparison table in the project came from a single run per backend. Then I noticed those single runs **disagreed with themselves inside the same hour** — CrewAI at 6m50s on one run and 10m41s on the next, LangGraph sailing through cleanly once and escalating to human review the next time, same config both times.

A single run is an anecdote. I'd been publishing anecdotes and calling them results.

So I built `scripts/run_smoke_batch.py`: run it N times per backend, read tests and spend back out of the (now actually-working) result bundles, and print a **variance table** — min / median / max, not a single hero number. The moment I did that, the picture sharpened, and it promptly reversed one of my own confident verdicts. CrewAI's "runtime hang" turned out to be fixable after all — a workspace-scoping bug and an environment-leak bug, not the abstraction itself — and it went on a multi-run green streak on the exact scenario I'd demoted it over. Meanwhile LangGraph's single-run "winner" status did *not* survive n=5: it dropped runs on auto-fixable lint noise and on a dev/QA test-layout mix-up.

That's the one habit I'd underline for anyone doing this: **your framework verdicts have a shelf life, and the run-to-run variance is big enough here that you owe your readers a distribution, not a single point.** Three journal entries in a row now, the data walked back something I'd said confidently the week before. I leave those reversals in the record on purpose. The corrections are the credibility.

---

## Tips if you're building something like this

Distilled from the failures above, for anyone standing up their own multi-agent pipeline:

- **Coordinate through the filesystem, not chat history.** Files on disk are inspectable, durable, and survive a crashed session. It's also how real teams hand off. The workspace *is* the state.
- **Assume the model won't call your tools.** Build a salvage path that parses prose output and does the write itself. Non-compliance is a *when*, not an *if*, especially with open models.
- **Bound spend, not just loop count.** And make the abort a `BaseException` so a well-meaning `except Exception:` somewhere in your dependency tree can't eat the kill signal.
- **Point your security tests at your own guardrails.** The traversal bug was in the validator, not the agent. Adversarial tests on the defense layer are non-negotiable.
- **Isolate the runtime you don't trust in a subprocess.** One hung framework thread can starve the GIL and make an *unrelated* backend look slow — I misattributed a stall exactly this way before subprocess isolation fixed it.
- **Report variance.** Run it five times. Publish the spread. Retract yourself in public when the distribution disagrees with your earlier take.

---

## How the system is actually built

If you like architecture, the shape is pretty clean, and it's documented in full in [`docs/architecture.md`](architecture.md):

- A `Backend` protocol (`run()` / `stream()` → normalized `ProjectResult`) that all three engines implement, so the CLI, the web dashboard, and the comparison scripts never care which one is running.
- A single `TeamProfile` in YAML defining the nine agents and the phase list — shared verbatim across backends, no per-framework agent definitions to keep in sync.
- Four guardrail layers — **Security** (blocks `eval`/`os.system`/traversal), **Behavioral** (role adherence, scope control), **Quality** (coverage, complexity, placeholder detection), and **Operational** (spend cap, wall-clock timeout, retry bound, prose-salvage) — the last of which is the harness this whole post is about.
- A self-improvement loop that captures failures to SQLite, clusters them into patterns, distills lessons, and injects them back into prompts on the next run.
- A shared, backend-agnostic deliverable contract enforced from a common post-run path, so a *new* backend is automatically checked without writing new enforcement code.

The three backends talk to themselves in three genuinely different ways — CrewAI through typed Pydantic documents in a shared `ProjectState`, LangGraph through reducer-merged graph channels, the Claude SDK through the session transcript plus workspace files — and getting all three to live under one contract is honestly most of the design work. There are seven ADRs in the architecture doc walking through each decision and, more usefully, each *consequence* I had to eat.

---

## Contributing

The most valuable contributions are the ones that turn an anecdote into a measurement or an opinion into a test.

- **Add a backend.** Implement the `Backend` protocol, register it in `backends/registry.py`, and the deliverable contract checks it for free. A fourth framework in the matrix is directly useful.
- **Break a guardrail.** If you can get a traversal, an unsafe exec, or a spend overrun past the current defenses, that's a high-value PR — bring the adversarial test with it.
- **Reproduce a variance claim.** Run `scripts/run_smoke_batch.py` on your own hardware and models and tell me where my numbers don't hold. Disagreement with data attached is exactly what this project is for.
- **Fix a coordination failure.** The open one worth stealing: no agent currently *owns* the project's file layout, so dev and QA sometimes disagree on import paths. The fix is likely to have the planning phase pin a layout and inject it into both prompts. That's an agent-coordination problem, not a parsing one, and it's unsolved.

Start with [`docs/GETTING_STARTED.md`](GETTING_STARTED.md), run the smoke test across all three backends, and watch them disagree. That disagreement is the whole point.

---

*More posts in this series will go deep on individual failure classes, the n=5 variance methodology, and the guardrail-precision problem — the surprisingly hard question of how a scope guardrail is supposed to tell "the QA agent is doing its job" apart from "the agent is expanding scope," when the words are literally the same.*
