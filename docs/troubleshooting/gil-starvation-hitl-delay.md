# The 78-Minute Bug That Was Never in the Code I Was Debugging

*A LangGraph interrupt took 78 minutes to show up in an API response. I spent the first
hour convinced it was a checkpointer bug. It wasn't in LangGraph at all — it was a
different, unrelated backend, spinning silently, in the same process.*

---

## The symptom

Running a 3-way Compare (CrewAI, LangGraph, Claude Agent SDK, same brief, same web
server) I watched LangGraph do exactly what it was supposed to do: exhaust its retry
budget on a genuine test failure, and escalate to human review by firing a real
LangGraph `interrupt()`. The escalation showed up instantly in the server's own event
log.

The API endpoint that's supposed to report that escalation — `GET /api/runs/{id}` —
kept saying `status: running, hitl_payload: null`. For **78 minutes.**

That's not a slow response. That's a live production system silently lying about its
own state for over an hour, while a human is theoretically waiting to review something.

## The wrong hypothesis (the first hour)

The obvious read: something in the HITL-detection path is broken. I traced it fully.

`_stream_langgraph_events_to_ws` only reports the interrupt after the producer
thread's `iter_stream_events()` generator finishes. So maybe the generator was stuck?

It wasn't. The generator *did* finish — `g.stream()`'s loop ended cleanly right after
the interrupt chunk. `record_run_failures` ran and logged its completion **on
schedule**. Everything up to that point was correct, timestamped, and fast.

What came *after* that — writing final state, writing artifacts, writing a scorecard —
was plain synchronous Python with no I/O, no locks, nothing that should ever take more
than milliseconds. And it took over an hour.

That's the moment a "trace the code path" debugging session stops being useful. The
code path was fine. Something else was happening.

## The actual cause

The same server process was also running **CrewAI**, in the same Compare batch. CrewAI
was deep in a known retry-recovery deadlock — pinned at ~95% CPU, in a Python thread
(`asyncio.to_thread`), producing zero log output.

Python threads share one GIL. A thread that's spinning hard enough — Rich console
redraw loops are a classic case: lots of pure-Python work, not I/O-bound, so the
interpreter never gets a natural excuse to hand the GIL to anyone else — can starve
every other thread in the process almost indefinitely. LangGraph's post-interrupt
bookkeeping was pure Python. It had no I/O to release the GIL during. It just... waited
its turn, for 78 minutes, because CrewAI's thread wasn't giving it one.

Confirmation wasn't circumstantial. I watched LangGraph's own resolution and a
diagnostic status check both land in the log within the same second — right after
CrewAI's thread finally yielded. There was no LangGraph defect to fix. The fix belonged
to CrewAI.

## Why it was scary, not just annoying

This wasn't "CrewAI is slow, comparison-only, don't wait for it." It was: **an
unrelated, already-demoted backend, doing something wrong in its own corner, could
silently corrupt the correctness of a completely different backend's API responses.**
Nobody debugging a LangGraph problem would think to check what CrewAI's thread was
doing. I almost didn't.

## The fix

CPython threads can't be forcibly killed from outside. `pytest`'s own `--timeout`
(SIGALRM-based) had already been observed failing against this exact CrewAI
deadlock — the same Rich-console/event-bus threads that spin also swallow the signal.
An in-process timeout mechanism was never going to work here.

The fix is a process boundary. `CrewAIBackend.stream()` now runs the flow in a real OS
subprocess via `multiprocessing` (spawn context), with a wall-clock deadline that calls
`terminate()`, then `kill()` if the process is still alive past it. An OS-level kill
works regardless of what the target's threads are doing — there's no cooperation
required.

Trade-off, accepted deliberately: CrewAI lost its live progress streaming (a
`TeamMonitor` object can't cross a process boundary, and building a file-polling
bridge to reconstruct one was scoped out as a separate, larger feature with no existing
infrastructure). CrewAI's Compare column now shows *started → finished/killed* instead
of granular phase updates. Acceptable, since CrewAI is comparison-only in this project
already.

## The verification, which turned out to matter more than the fix

The next live run's retry loop went fully runaway — not the single hang from before,
but an actively looping bug, `dev_retry_count` reaching **93,284** (the flow-wiring
self-trigger bug covered in
[the self-trigger post](https://github.com/RickZee/ai-team) — a second, independent
finding this same investigation surfaced). The hard-kill fired exactly at the 900-second
deadline. The subprocess died cleanly.

And the number that actually mattered: the main server's `/api/runs` endpoint stayed
under 30 milliseconds, the entire time CrewAI's subprocess was spinning at full CPU.
That's the real proof. Not "the kill worked" — kills are easy to fake with a demo.
*The rest of the system stayed responsive while the broken part was actively broken.*
That's the property the fix was actually for.

One more bug fell out of verifying this properly: the timeout error wasn't propagating
into the persisted run status — a kill would report `status: complete` with
`error: null`, which is its own kind of lie. Fixed in the same pass, because "verify
the fix worked" turned into "verify the fix worked *and the observability around it is
honest*," which is usually where the second bug is hiding.

## The lesson

Co-hosting agent runtimes in one interpreter couples their failure modes in ways that
don't show up until one of them actually fails. The debugging instinct — "the bug is in
the code path that's exhibiting the symptom" — is usually right, and was wrong here in
a way that cost an hour of tracing correct code before I widened the search. The rule I
took away: **anything that can hang gets a process boundary and a kill switch**, not
because you expect it to hang, but because when it does, you don't want to spend an
hour debugging a different, innocent system first.
