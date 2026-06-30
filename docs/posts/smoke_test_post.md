# The Cheapest Test I Run Tells Me the Most

*One trivial task — write `add(a, b)` and test it — sent through three AI orchestration frameworks. The cheapest run in the whole project, and it exposed more than any flagship demo.*

---

Before I spend a dollar on a real demo, I run the smoke test.

It is the most boring task imaginable: write a Python module `calc.py` with `add`, `subtract`, `multiply`, and `divide` (raise `ValueError` on divide-by-zero), plus a `test_calc.py` with pytest cases. Two files. A first-year CS exercise.

It is boring on purpose. The smoke test does not ask *"can the AI write good code?"* — every model alive can write a calculator. It asks the only question that matters before you commit budget: **does the pipeline actually run end-to-end — keys, routing, model access, tool wiring, file writes — without hanging, crashing, or silently lying?**

This week I ran that one task through all three of ai-team's orchestration backends and captured everything. The results were more interesting than the flagship demos. Here is the goal, what happened, and what it taught me.

---

## The goal

ai-team is a multi-agent system: specialized AI agents (Architect, Fullstack Developer, QA Engineer for this run) hand a software requirement down a pipeline — **plan → develop → test** — coordinating through files on disk, not a shared chat. I support three interchangeable backends so I can compare them honestly:

- **LangGraph** — explicit StateGraph, runs the open **deepseek-v3** via OpenRouter
- **Claude Agent SDK** — native Claude subagents, runs **Opus** via the Anthropic API
- **CrewAI** — role-based Flows + Crews, also deepseek-v3 via OpenRouter

Same task. Same profile. Same acceptance contract: two files, all four functions, divide-by-zero raises, and `pytest` exits clean.

What I wanted out of the run: a green pipeline, and apples-to-apples comparison data — wall-clock, cost, and whether each backend's *own* quality gate told me the truth.

---

## What happened

| Backend | Model | Outcome | Wall time | Cost | Tests (self-reported / I re-ran) |
|---|---|---|---|---|---|
| **LangGraph** | deepseek-v3 | ✅ Clean pass | **77s** | **$0.004** | 5 / 5 ✅ |
| **Claude Agent SDK** | Opus | ✅ Clean pass | **242s** | **$0.82** | 23 / 23 ✅ |
| **CrewAI** | deepseek-v3 | ⚠️ Completed — but lied about it | **318s** | ~$0.01 | **0** / 28 ✅ |

All three **wrote correct code.** When I ran pytest myself against each output, everything passed — 5, 23, and 28 tests respectively. The differences were never about whether the model can write a calculator. They were about everything around the model.

**LangGraph was the unglamorous winner.** 77 seconds, less than half a cent, zero retries, and its self-reported test count matched reality. Interesting detail: even here the developer agent *narrated* instead of acting — it wrote *"Let me write these files…"* as prose — but the salvage layer caught the code and wrote it to disk anyway, and the QA agent then called its tool properly. The harness absorbed the model's bad habit and the run stayed green.

**The Claude SDK was the most thorough and the most expensive.** Opus wrote 23 tests to deepseek's 5, organized them into a proper `src/` + `tests/` layout, and its reported results were honest. It cost ~200× more than LangGraph and took ~3× longer. You pay for rigor.

**CrewAI is the one worth dwelling on.** It *finished* — reached `project_complete` in 318 seconds, wrote both correct files. But its own orchestrated pytest reported **`passed=0, total=0`** and waved the run through with a green quality gate anyway. The code was fine — I re-ran the exact same files and got **28 passing tests** — but the framework's verification step collected zero of them and called that success.

> A pipeline that ships correct code while telling you it ran zero tests is more dangerous than one that loudly fails. The loud failure you fix. The quiet false-positive you ship.

---

## The troubleshooting (and a process lesson)

This is where the smoke test earned its keep.

CrewAI has a history in this project of *hanging* — in past eval runs it wedged on the first test and **ignored its own wall-clock timeout**, because its live console threads swallow the abort signal. So going in, I knew not to trust the in-process `--timeout` for that backend. I wrapped every CrewAI run in an **external** process-group hard-kill (`set -m` + `kill -9` on the whole group), the one thing that reliably reaps it.

Then I made the timeout itself data-driven instead of a guess. I pulled per-call latency from historical logs — deepseek-via-OpenRouter runs **~4–31s per call**, so a healthy smoke run (≈5–12 calls across phases) lands in the **1–6 minute** range. That set honest budgets: ~180s for LangGraph, ~480s for the SDK, and a generous 900s ceiling for CrewAI — long enough for a genuinely-slow legit run, short enough to catch a hang before it burned an hour like it had before.

The payoff: this time CrewAI didn't hang. It exposed a *different* failure — the false-negative quality gate — that the old hang had been masking. **You only find the second bug after you stop the first one from eating the whole run.**

(One more lesson, this one about my own tooling: long runs launched in the background were getting reaped early by a premature "done" signal — it killed the 242s SDK run at the 200s mark. The fix was boring: run anything over ~2 minutes in the foreground with a real timeout. Sized guards, again.)

---

## What I learned

**1. The model is the bottleneck for *quality*; the framework is the bottleneck for *trust*.** All three produced working code. What separated them was whether the orchestration ran fast, stayed cheap, died cleanly, and — most of all — told the truth about its own results. That last property is a framework property, not a model one.

**2. A green checkmark is a claim, not a fact.** CrewAI's `quality_gate_passed=True` sat directly above `passed=0`. If I trusted the summary I'd have shipped on a verification that never happened. Re-running the tests myself is not paranoia; it is the job.

**3. Size your guardrails from data, not vibes.** "Give it 5 minutes" is how you either kill a healthy slow run or wait an hour on a hung one. Per-call latency × expected calls × headroom gives you a number you can defend — and the right number changes per backend.

**4. The boring test is the high-signal test.** A calculator can't tell you if your AI is smart. It tells you, in under five minutes and for under a dollar across three frameworks, exactly which layer of your stack is broken. That is worth more than another impressive-looking demo.

---

## Where this leaves things

LangGraph stays the default for reliability and speed. The Claude SDK is the choice when thoroughness and honest reporting are worth the cost. CrewAI is demoted to a comparison-only datapoint — kept in the matrix precisely *because* its failures are instructive, not because I'd run production on it.

And the smoke test keeps its job: the first thing I run, every time, before I spend real money finding out the hard way.

---

*ai-team is a working multi-agent code-generation system with three pluggable backends, layered guardrails, and a self-improvement loop. Every number above is from a real run with real API calls — logs, not estimates. If you're building agent systems, I'd love to compare notes on the part nobody screenshots: making the harness survive the agent.*
