# Session 2 — Write down what happened, before you score it

**20 minutes.** Read [Session 1](./session-1-what-green-means.md) first.

---

## The idea

Before you can ask "how often does this go wrong," you need a pile of records of
it going right and wrong. One record of one run, kept exactly as it happened, is
a **trace**. The steps inside it — each tool call, each phase, each retry, each
model response — are **spans**.

The rule that makes everything else work:

> **Traces first, scores second.** Record the run once, immutably. Then compute
> every score as a function of the recording.

This sounds like bookkeeping. It is actually the foundation, for one reason: if
scoring reads the recording rather than watching the run, you can re-score. New
check, new idea, changed threshold, argument with a colleague — you re-run the
scoring over traces you already have, for free, and get an answer in seconds
instead of re-executing a system that costs money and takes twenty minutes.

Everything good about evals comes from that separation. Everything expensive
comes from not having it.

## What a trace needs to be useful

Minimal and sufficient:

- **An id**, so you can point at it in an argument.
- **When it started and ended**, so you can spot the slow ones.
- **What produced it** — which model, which version, which configuration.
- **How it ended** — succeeded, failed, gave up, escalated to a human.
- **The steps**, in order, each with a timestamp.
- **What you could not find**, recorded as missing rather than guessed.

That last one is the one people skip, and it is the difference between a trace
that admits it is thin and a trace that looks complete and is not.

## Where this actually breaks

Not in the design. In two dull places.

### Break one: the writer and the reader disagree about where logs live

Your system writes logs somewhere. Your eval reads logs from somewhere. If those
two paths are not literally the same path, you get a corpus of empty shells — and
here is the vicious part: **nothing downstream can tell.** The trace builder runs
fine. Traces get created. The count goes up. Every file is valid. They are just
hollow.

The real numbers, from a real repo, in September 2026:

```
traces indexed .................. 50
spans across all fifty .......... 0
distinct sources ................ 1
distinct outcomes ............... 1
created within a window of ...... 1.97 seconds
```

Fifty traces, zero steps between them, all made in under two seconds one
afternoon. The reader had been pointed at the directory where the system writes
its *output* — generated code — instead of the directory where it writes its
*records*. 210 complete run records covering three different systems over 69 days
were sitting on the same disk, unread, the entire time.

One argument. One default value. `--workspace-root ./workspace` instead of
`./output/runs`. Two months.

### Break two: you asked the model to write the telemetry

This one is subtler and worse. Buried in a prompt:

```
7. Write phase transition entries to workspace/logs/phases.jsonl
   (JSON lines: phase, status, timestamp).
```

That is the system's own timeline — the file nearly every interesting check needs
— requested from the AI as an instruction rather than written by code on the
execution path. Across 440 runs, the number of those files that existed was
**zero**.

Compare the two failures, because the second is the one to internalise:

| | Self-graded work | Self-reported telemetry |
| --- | --- | --- |
| What you get | A verdict you can argue with | A dataset that looks clean |
| Can you spot it? | Usually, it reads as flattery | No. Nothing downstream can tell |
| Can it be wrong? | Yes, visibly | Yes, invisibly |

Asking a model to grade its own homework is a known trap and it is *visible*.
Asking a model to write its own logs produces a file that looks exactly like a
real one, and every number computed from it inherits the problem silently.

> **Rule: telemetry is written by code, on the execution path, stamped with who
> wrote it.** If a model can decline to write a log line, that log line is not
> evidence.

## The translation, if you come from testing

You have met both of these. Break one is a test suite pointed at a stale build
directory — green, and testing nothing. Break two is a system under test that
reports its own pass/fail. Neither idea is new. What is new is that the AI
version of break two produces *plausible-looking data*, which is a category of
problem the deterministic world mostly doesn't have.

## Your move

Two commands, five minutes, no code:

1. Find the directory your system writes logs to. Write the path down.
2. Find the directory your eval reads from. Write that path down.
3. Are they the same path? If you are not certain, count the files in each.
4. Then: for each kind of log line you care about, find the line of *code* that
   writes it. If you can't find one, check whether it lives in a prompt.

[Session 6](./session-6-run-it-yourself.md) gives you a script that answers all
four in one run, on your own logs.

---

## In one line

**Record every run immutably and score from the recording — then verify that the
thing writing records and the thing reading them agree on where records live, and
that code, not the model, does the writing.**

Next: [Session 3 — Read thirty of them yourself](./session-3-read-thirty.md)
