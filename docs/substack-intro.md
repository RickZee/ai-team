# Building the harness that survives the agent

*Same nine-agent software team, three different orchestration frameworks, one honest question: which of my problems are actually mine?*

---

## What this is

You hand **ai-team** a one-line brief — "Build a Flask REST API" — and nine agents (Manager, Product Owner, Architect, three flavors of developer, QA, DevOps, Cloud) take it from intake through planning, development, testing, and deployment. It writes the code, writes the tests, runs them, ships the Docker bits.

That part isn't interesting. Anything will spit out a Flask app from a prompt these days.

Here's the part I actually care about. The same team, the same phases, and the same definition of "done" have to run on three completely different backends: CrewAI, LangGraph, and the Claude Agent SDK. All of them behind one `Backend` protocol. One team profile in YAML. One flag, `--backend`, swaps the whole engine out.

Why bother? Because if you only ever run one framework, you can't tell your bugs from its bugs. You just have opinions. Run all three on the same task and the opinions turn into numbers you can argue with. That's the whole point, and as you'll see, it cuts against me as often as it cuts for me.

This is the intro to a series. The rest goes into what broke and how I figured out why.

---

## Most of "building an agent" is building the thing that babysits it

Let me say the uncomfortable part first, because it changes what this project even is.

Strip out the demos and most of the code in a real agent pipeline isn't prompts and it isn't model choice. It's the harness. The plain, boring, non-AI code whose only job is to survive the model when the model does something stupid. Timeouts. Spend caps. Retry limits. Salvaging output the model refused to save properly. Path validation. Subprocess isolation. None of that is "AI." All of it is the difference between a demo and something you'd leave running unattended.

The smarter the model, the less of this you need. Claude through the SDK barely trips any of the wires I'm about to describe. But I don't get to assume the model — comparing open-weight models against frontier ones is half the point — so I build the harness anyway and I build it to fail safe.

Rest of this post is a tour of what breaks. The failures teach more than any diagram.

---

## Where these systems actually break

Three weeks of live runs, ten distinct failure classes. What got me is how few were the model being dumb. Nearly all of them were ordinary systems bugs wearing an AI costume. The sharp ones:

### 1. The model writes the code, then asks permission to save it

Hand deepseek-v3 a `file_writer` tool. Tell it, in plain words, "call file_writer, do not output code as text." It does the opposite. It writes a complete, working Flask app as a markdown block and finishes with "Would you like me to proceed with saving these files?"

Nobody's there to say yes. It thinks it's in a chat. It's supposed to be in a loop.

And this quietly wrecks everything, because phases hand off through files on disk, not chat history. That's deliberate — it's how real teams work. So dev writes `main.py` as prose, the workspace stays empty, QA runs real pytest, gets `ImportError`, routing retries dev, dev writes the same prose again. Round and round on a slow model. Before I fixed it, this looked like a ten-minute hang that ended in nothing — after generating perfectly good code every single lap and throwing all of it away.

The fix is not a better model. The fix is salvage: if the thing won't call the tool, parse its prose and write the files myself. Feels like a hack. It isn't. The whole project exists to compare backends including the models that don't behave, so the orchestration has to survive them. Took three passes to get right, and one of those passes turned up a security bug in my own salvage code (see #3).

### 2. A kill signal that gets swallowed and retried

Retry caps limit the number of loops. Nothing limited the dollars. A crash-loop on a metered model just burns money while you're not looking. So I added a per-run spend ceiling off the real per-call cost the provider reports.

The bit worth your time is the exception type. The budget-exceeded error subclasses `BaseException`, not `Exception`. Sounds like pedantry until you notice both the LangGraph phase nodes and LiteLLM's callbacks wrap everything in `except Exception` and treat a failure as "carry on." Make the abort a normal `Exception` and the exact loop you're trying to kill catches its own kill signal, eats it, and retries. `BaseException` is the only way the stop actually stops.

One line. Only makes sense after you've read the control flow through two libraries you didn't write. No amount of prompt-tweaking ever finds that for you.

### 3. A path-traversal hole. In my own guardrail.

Writing adversarial tests for the salvage extractor, one of my own tests caught it. The extractor did `fname.lstrip("./")`, which strips *any* leading dot or slash. So `../escape.py` becomes `escape.py` and walks right past the `..` check. Fixed to strip one `./` at most and reject absolute paths, `..`, and dotfiles.

Point isn't "I wrote a bug." Everyone writes bugs. Point is the security guardrail needs its own adversarial tests aimed straight at it, because a guardrail you think is safe is worse than no guardrail. You stop watching the thing you trust.

### 4. A framework that fights the harness

This one took two full sessions to be sure about, and I'll be careful with it, because it's easy to turn into a cheap dunk.

Simplest task the project has — `add(a, b)` and one pytest. LangGraph, green in about a minute. Claude SDK, green in about three. CrewAI collected its tests, started the run, went silent, and ignored its own `--timeout`. Its live-display and event-bus threads ate the alarm, so I had to `kill -9` the process group. Left alone it sits there forever.

Same model, same task. So "use a better model" doesn't save it. It's structural. My handoff is files on disk between phases. CrewAI's Flow/Crew model wants to coordinate through agent conversation and structured task outputs — the exact layer that falls apart the moment a model emits prose instead of tool calls. Two sessions of CrewAI-specific patches later and the smoke test still wouldn't go green. Bad ratio of effort to reliability.

Here's what I did with it, which matters more than the finding. I didn't delete CrewAI. "I tried this framework for autonomous file-handoff work and it fought me at the runtime level" is one of the more useful things I can tell someone sizing up these tools. Deleting it hides the finding. So it stayed in as a documented datapoint, demoted but present, precisely because it failed.

And then that call aged in a direction I didn't see coming. Which is the actual lesson.

---

## One run is a story. Five runs is barely a measurement.

Early on, every comparison table came from a single run per backend. Then I caught the single runs disagreeing with themselves inside the same hour — CrewAI at 6m50s on one run, 10m41s on the next. LangGraph clean once, escalating to human review the next time. Same config both times.

A single run is a story. I'd been publishing stories and calling them results.

So I built a batch runner: N runs per backend, read tests and spend back out of the result bundles, print min/median/max instead of one hero number. First thing it did was reverse a verdict I'd stated with confidence. That CrewAI "runtime hang" was fixable after all — a workspace-scoping bug and an env-leak bug, both mine, not the framework — and it went on a green streak on the exact task I'd demoted it over. Meanwhile LangGraph, my single-run "winner," didn't survive five runs. It dropped runs on auto-fixable lint noise and a dev-vs-QA file-layout disagreement.

Then I pushed on it harder and it got worse for me. Five runs isn't enough either. A 1-out-of-5 green rate has a 95% confidence interval running from about 4% to 62%. That overlaps almost anything. So when the batch runner now compares two backends, it either prints "no significant difference at this n" or it stays quiet. Ran it against my own published table and every ranking in it collapsed. None of them held.

That's the habit I'd tattoo on anyone doing this work: **trust nothing until it builds, and trust no verdict until the numbers separate.** Three journal entries running, the data walked back something I'd said the week before. I leave every one of those reversals in the record on purpose. The corrections *are* the credibility. If a writeup never shows the author being wrong, don't trust the writeup.

---

## If you're building one of these

Straight from the wreckage above:

- **Hand off through the filesystem, not chat history.** Files are inspectable, durable, and survive a dead session. The workspace is the state.
- **Assume the model won't call your tools.** Build the prose-salvage path now. It's a when, not an if, especially with open models.
- **Cap spend, not just loop count.** And make the abort a `BaseException` so some well-meaning `except Exception:` in a dependency can't eat the kill.
- **Point your security tests at your own guardrails.** The traversal bug was in the validator, not the agent.
- **Isolate the runtime you don't trust in a subprocess.** One hung thread can starve the GIL and make an unrelated backend look slow. I blamed the wrong backend for a stall exactly this way.
- **Run it five times, then don't believe five either.** Publish the spread, print the confidence interval, and don't rank two things whose intervals overlap.

---

## How it's actually built

If you like architecture, the shape is clean. Full detail in [`docs/architecture.md`](architecture.md):

- A `Backend` protocol (`run()` / `stream()` → normalized `ProjectResult`) so the CLI, the dashboard, and the comparison scripts never care which engine is running.
- One `TeamProfile` in YAML defining the nine agents and the phases. Shared across backends, no per-framework agent definitions to keep in sync.
- Four guardrail layers — Security (`eval`/`os.system`/traversal), Behavioral (role adherence, scope control), Quality (coverage, complexity, no placeholder code), and Operational (spend cap, timeout, retry bound, prose-salvage). That last one is the harness this whole post is about.
- A self-improvement loop that logs failures to SQLite, clusters them, and feeds the lessons back into the next run's prompts. Honest status: half-built. It works, it's not finished, and I say so in the docs.
- A shared deliverable contract enforced from one post-run path, so a new backend gets checked for free.

The three backends talk to themselves in three genuinely different ways. CrewAI through typed Pydantic docs in a shared state object, LangGraph through reducer-merged graph channels, the Claude SDK through the session transcript plus workspace files. Getting all three under one contract is most of the actual work. Seven ADRs in the architecture doc walk through each call and, more usefully, each consequence I had to live with.

---

## Want to help

Best contributions turn a story into a measurement, or an opinion into a test.

- **Add a backend.** Implement the protocol, register it, and the deliverable contract checks it for free. A fourth framework in the matrix is genuinely useful.
- **Break a guardrail.** Get a traversal, an unsafe exec, or a spend overrun past the current defenses and I want the PR. Bring the test.
- **Reproduce a claim.** Run the batch on your own models and tell me where my numbers don't hold. Disagreement with data attached is the entire point of the project.
- **Fix a coordination bug.** The open one worth stealing: no agent owns the file layout, so dev and QA sometimes disagree on import paths. Probably wants the planning phase to pin a layout and inject it into both prompts. It's a coordination problem, not a parsing one, and it's unsolved.

Start with [`docs/GETTING_STARTED.md`](GETTING_STARTED.md), run the smoke test across all three, and watch them disagree. That disagreement is the product.

---

*Next posts go deep on the individual failure classes, on why five runs still isn't enough, and on the guardrail I keep losing sleep over — the one that has to tell "the QA agent is doing its job" apart from "the agent is expanding its scope" when the two look identical on the page.*
