# Session 5 — Every number needs its n

**15 minutes.** The only session with arithmetic in it, and there is very little.

---

## The idea

Your subject is nondeterministic, so every result you report is a rate. And a
rate needs three things attached or it misleads:

1. **How many** it was computed from (`n`).
2. **How uncertain** it is (a range, not a point).
3. **What kind of data** produced it (Session 1's label).

Drop any one and the number becomes a vibe wearing a decimal point.

## "4 out of 5" is not 80%

Here is the whole of the statistics you need, as an example.

You run two configurations five times each. A gets 1 pass, B gets 5. B wins,
obviously — 20% versus 100%.

Except with five samples, the honest range for "1 out of 5" is roughly **4% to
62%**, and for "5 out of 5" it is roughly **57% to 100%**.

```
A:  1/5   ├────────────────────────┤           4% ── 62%
B:  5/5                  ├──────────────────┤ 57% ── 100%
                                  ^^^^^^
                                  they overlap
```

Those ranges overlap. The data does not support the ranking. You may not say B is
better; you may only say you don't have enough runs to tell.

That range is a **Wilson interval**. You do not need to understand the formula —
it is six lines of code, it is in [`minieval.py`](./minieval.py), and every
language has one. You need to understand the habit: **never publish a rate
without its range, and never rank two things whose ranges overlap.**

### What it cost

July 2026. That project had been publishing a ranking table of three systems from
n=5 runs each. Its whole pitch was honest comparison.

The adversarial review found the rankings did not survive their own confidence
intervals. Fix: the report generator now computes the interval, applies a
**no-verdict-when-intervals-overlap rule**, and prints *"no significant
difference at this n"* when that is the truth. One of the new tests asserts
exactly the embarrassing claim — that 1/5 versus 5/5 is not separable at n=5 —
so the mistake cannot come back quietly.

The through-line of that whole review, worth more than any single fix:

> Nearly every correction was replacing a confident sentence with a narrower one
> plus a number.

## Small n is not a reason to round up

If you have four results, do not print a percentage. Print `n=4`.

A confidence interval over four results is arithmetic performing a confidence it
does not have, and the percentage is the part readers remember. Below about ten
decided results, show the count and nothing else. This one rule removed eleven of
seventeen percentages from that project's report, and the removal was the
improvement — eleven of its twenty checks turn out to be decided by a single pair
of examples.

## Report what you could not see

Session 4 gave checks a third outcome. This session is where it gets printed.

Two reports, same underlying data:

```
FAIL — 182 failed checks across suite
```

```
FAIL — 182 failed, 1435 abstained (76.3%), 2 checks structurally blind
        [FIXTURE-ONLY · NON-REPRESENTATIVE · EVIDENCE-STARVED]
```

The first is what shipped. Both are accurate. Only the second lets you decide how
much to care.

Three independent labels, and a real report can need all three at once:

| Label | Answers |
| --- | --- |
| **FIXTURE-ONLY / CORPUS / LIVE** | What kind of data is this? |
| **NON-REPRESENTATIVE** | Is the data varied enough to generalise? |
| **EVIDENCE-STARVED** | Could the instruments see anything? |

They are orthogonal. Fixing the data does nothing for the third one. That is why
they are three labels and not one.

## The mechanism, not the intention

Every one of those labels must be **computed and printed by the reporting code**,
with a test on the boundary condition.

Not written in a doc. Not remembered. Not added by the author when they feel the
number needs context — because the times a number most needs context are exactly
the times its author is least inclined to add it.

This is the same lesson as Session 1 from the other end, and it generalises past
evals entirely:

**July 2026, same project.** A guardrail threshold had been documented as fixed
— the value written down in the docs, the change described in a journal entry.
The actual default in the code was still the old value, and the runtime caller
passed no override. The fix lived only in the documentation. Weeks of believing a
bug was fixed because someone had written that it was.

> Anything you tune has to be measured on a labeled set, including the things
> that don't feel like models. And anything you claim has to be printed by the
> code, not by you.

## Your move

1. Find one rate you have published or shown someone. Compute its interval —
   `minieval.py` has the function, or any stats library, or a web calculator.
2. If you have ever ranked two options, check whether their intervals overlap.
3. Find every place a rate is rendered in your system. Make the code print `n`,
   the range, and the data label. Then make one test assert it cannot render one
   without them.

---

## In one line

**Every rate carries its n, its uncertainty range, and a machine-printed label
saying what kind of data produced it — and if two ranges overlap, you have no
ranking, you have a sample-size problem.**

Next: [Session 6 — Do it: the audit and your own harness](./session-6-run-it-yourself.md)
