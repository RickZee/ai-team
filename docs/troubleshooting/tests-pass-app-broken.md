# 70/70 Tests Passed. The App 500'd on Every Single Request.

*I was showcasing a generated to-do app to prove the pipeline worked. It didn't boot.
The test suite it shipped with had no idea.*

---

## The demo that wasn't

An autonomous team of nine AI agents had just finished building a Flask + SQLite +
Docker to-do app end-to-end: requirements, architecture, backend, frontend, tests,
deployment config. The run reported `success: true`. Every phase green. **70 out of 70
pytest tests passed.**

I opened the app to show someone. `GET /health` returned a 500.

Every endpoint returned a 500. The app was completely broken, and the pipeline that
built it — including its own QA agent, running its own tests — had no idea.

## Why the tests didn't catch it

The generated test suite used Flask's in-process test client. That's the standard,
recommended way to test a Flask app, and it's fast, and it's exactly what a
conscientious QA agent should write. It's also, structurally, incapable of catching
this class of bug: an in-process test client short-circuits the parts of Flask that
handle a real request lifecycle, including how the app's own logging gets initialized
under the actual WSGI server.

The actual bug: `structlog.stdlib.add_logger_name` was configured alongside
`PrintLoggerFactory`, and `PrintLoggerFactory`'s logger objects don't have a `.name`
attribute. First real log call, crash. Every request hit at least one log call. Every
request 500'd. The in-process test client never exercised that code path, so 70 tests
sailed through a completely non-functional application.

The uncomfortable generalization: **no agent, on any backend, had ever actually run the
app it built.** Every backend's "verification" step was some flavor of static or
in-process check. Nothing had booted the thing and sent it a real HTTP request.

## The fix: verify behavior, not artifacts

The fix isn't "write better tests" — you can't guardrail against every way a generated
test suite might miss a runtime issue, and telling an agent to "test more thoroughly"
is not a real instruction. The fix is a gate that doesn't trust the generated tests at
all: **boot the actual application and probe it over real HTTP**, as a step the
pipeline runs regardless of what the agents claim.

`run_app_smoke(workspace)`:

- Boots the app for real — `docker compose up -d --build` if the app shipped one, else
  a plain Flask `module:app` / `create_app()` entrypoint under the stdlib server.
- Probes real HTTP endpoints, not function calls.
- Supports a **stateful probe sequence**: a `POST` can capture a field (like a new
  record's id) from its JSON response, and later steps interpolate it into their own
  path or body. So the gate can drive a full create → read → update → delete round-trip
  against a real database, not just confirm the process didn't crash on boot.
- Skips cleanly — not a failure — when there's genuinely nothing to boot, or when
  Docker isn't available, or when the target port is already bound by something else
  (so it never produces a false verdict by accidentally probing a foreign service).
- Caches a fresh result for a few minutes so multiple consumers (an agent calling it
  mid-run, the retry loop, the final gate) don't each trigger their own
  `docker compose up --build` cycle.

Wired as a `runtime_smoke_guardrail` that fails whenever the app ran and didn't pass —
and made backend-agnostic: it runs after every backend's own pipeline, booting the app
itself if that backend's agents never did, so LangGraph and CrewAI get the identical
coverage the Claude SDK path gets natively.

## Making it self-correcting, not just self-reporting

A gate that only reports "broken" is a smoke *test*. Closing the loop into a smoke
*gate* meant feeding the failure back in as a fix prompt, per backend:

- **Claude Agent SDK**: the orchestration loop runs the smoke check between attempts
  and feeds `{endpoint, status, traceback, server logs}` back to the agent as a
  concrete fix prompt — not "the app is broken," but the actual 500 and stack trace.
  Bounded to a couple of attempts, not an unbounded retry loop. The QA and DevOps
  agents also got the smoke tool directly, so they can self-correct mid-run before the
  gate ever has to intervene.
- **LangGraph**: a new `smoke` node sits between `testing` and `deployment` in the
  graph. A passing test suite now routes to `smoke`, not straight to deployment; smoke
  failure retries through the graph's existing bounded retry edge and escalates to
  human review once that's exhausted — the same honest, designed failure path every
  other guardrail in the system uses, not a special case.
- **CrewAI**: the shared post-run gate only, no inner retry loop — deliberate, since
  CrewAI was already comparison-only for reasons unrelated to this bug (see the
  self-trigger and GIL-starvation posts), and an inner loop wasn't worth building for a
  backend not being recommended for production use.

## Verification, on the exact defect that motivated the whole thing

Ran the finished gate against the original broken to-do app. `GET /health -> 500`,
caught immediately — the exact defect 70 green pytest tests had missed. Then a live
create→read→delete round-trip against a real running Flask app, with the id genuinely
threaded from the `POST` response into the follow-up `GET` and `DELETE` calls — not a
mock, an actual database row. Then the LangGraph loop, driven with a real
fail-then-pass smoke sequence: looped through `development` once on the injected
failure, then reached `complete` with the retry counter correctly incremented.

A self-review of the change (I run my own review pass on my own diffs, deliberately)
found four more issues before it shipped: a foreign-port collision that could probe
someone else's service by accident, redundant reboots across consumers, a log-drain
routine that could block on a partial line instead of reading what was available, and
a gap in the stateless-probe design that the create→read→delete sequence above was
built specifically to close.

## The lesson

"Tests pass" is a claim about the test harness, not the application. An in-process test
client is a claim about what code ran, not what a user's request would actually hit. If
your pipeline's only verification step never leaves the process, you don't have
verification — you have a very convincing simulation of verification, and the gap
between the two is exactly where bugs like this live. The fix generalizes past this one
logging misconfiguration: **anything that can pass without ever running is a
place your comparison, your CI, or your demo can be lying to you.**
