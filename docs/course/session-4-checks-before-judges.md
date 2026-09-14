# Session 4 — Let code decide what code can decide

**20 minutes.** Read [Session 3](./session-3-read-thirty.md) first — this session
builds on the categories that session produces.

---

## The idea

You have a list of failure modes from your own reading. Now you automate
detecting them, and there are exactly two tools:

- A **check** — ordinary code. Deterministic, instant, free, same answer every
  time. `if not trace.spans: return fail`.
- A **judge** — an LLM asked a question about the trace. Flexible, slow, costs
  money, gives different answers to the same input.

The ordering rule:

> **If a failure mode can be decided by code, it gets a check. A judge is the
> exception, not the default.**

Most people reach for a judge first, because the failure modes are described in
words and a language model handles words. But look at what the categories
actually turn out to be. "Didn't write any tests" is `len(test_files) == 0`.
"Retried the same phase forever" is counting. "Ran past the budget" is
arithmetic. "Claimed the tests pass without running them" is checking whether a
test-run record exists.

A surprising share of real failure modes are checkable by a `for` loop, and every
one you move from judge to check makes your suite faster, free, deterministic and
reproducible.

## Three properties that make checks worth preferring

- **Free.** You can run them on every pull request forever. The project behind
  this course runs its whole offline suite at **$0.00** per run, which means it
  runs on every PR, which means it actually runs.
- **Deterministic.** Same traces, same answer. So a change in the result means a
  change in the system, not a change in the weather.
- **Replayable.** They read recorded traces, so you can add a check today and
  score it against every run from the last six months, retroactively, for
  nothing.

That third property is why Session 2's separation mattered.

## Three outcomes, not two

A check must be able to say **"not applicable."**

A check for "did it retry too many times" cannot answer anything about a trace
with no retry records. If it returns `fail`, you have invented a failure. If it
returns `pass`, you have invented a success. The honest answer is *I could not
see*, and that has to be a first-class outcome with a reason attached.

This matters more than it sounds, and here is the receipt. That project's most
recent suite report:

```
check results ........ 1880
not applicable ....... 1435  (76.3%)
pass ...................263
fail ...................182
```

The published headline read `FAIL — 182 failed checks`. Accurate. It did not
mention that **three quarters of the suite declined to answer**, because
"not applicable" appeared in no headline, no summary, and no table. The report
format had no place to put it.

Worse, when they looked: two checks were reading a kind of record that **no code
anywhere ever writes**. Not missing from this corpus — impossible on any corpus,
ever. Those two checks could never fire, and the suite reported a verdict across
them and stayed green.

> A check that never decides anything is not coverage. Count how many of your
> checks have ever actually returned pass or fail on real data. That number is
> your real coverage, and it is usually much smaller than the number of checks
> you have.

## When you do need a judge, it has to earn it

Some things genuinely need judgment: "is this explanation clear", "did it follow
the spirit of the instruction". Fine. Then the judge becomes a component with its
own accuracy, and you measure it like any other instrument.

**Ask one binary question.** Not "rate quality 1–5." Nobody, human or model,
applies a five-point scale consistently, and you cannot compute a meaningful
error rate against it. One yes/no question per judge, from a prompt file you
version like code.

**Measure it against human labels, on two separate piles.** You need roughly
100–200 labeled examples from Session 3. Split them: one pile to tune the prompt
against, one pile you touch **once** to get an honest number. Tune on the second
pile and you've measured how well you tuned, not how well it judges.

**Two numbers, never one.** How often it catches real problems, and how often it
stays quiet on non-problems. Report both. A single "accuracy" number hides the
trade-off completely — a judge that flags everything has perfect catch rate and
is useless.

**Until it clears the bar, it advises. It does not gate.**

### The confound that is easy to miss

July 2026, same project. The LLM judge was hardcoded to one vendor's model. One
of the three systems being compared also ran on that vendor's models.

Every cross-system verdict published for weeks had an unexamined
self-preference confound sitting inside it. Not because anyone was careless about
statistics — because the judge felt like infrastructure rather than like a
participant.

> Your judge is a participant in the comparison, not furniture. If it shares a
> vendor with one of the things being compared, say so, and don't let that
> comparison settle anything.

## Your move

1. Take your categories from Session 3. For each, ask: *could a `for` loop decide
   this?* Be generous — more will qualify than you expect.
2. Write those as checks. Give each three possible outcomes, including
   "not applicable" with a reason.
3. Count how many of your existing checks have ever returned pass or fail on
   real data. Compare to how many you have.
4. For anything left that genuinely needs judgment, write down the single binary
   question. Don't build the judge yet — you need labels first.

---

## In one line

**Code decides what code can decide, every check can say "I could not see," and a
judge is a measured instrument that advises until it has been validated against
human labels — not a shortcut past having any.**

Next: [Session 5 — Every number needs its n](./session-5-every-number-needs-n.md)
