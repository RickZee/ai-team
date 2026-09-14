# Session 1 — What a green run actually proves

**15 minutes.** No prerequisites.

---

## The idea

Ordinary software gives the same answer every time. Ask it to add 2 and 2, it
returns 4 forever, so one test is enough. AI systems don't work that way. Ask the
same question twice and you get two different answers, both plausible, one
possibly wrong.

That single fact breaks testing as you know it:

- One passing run proves nothing, because the next one might fail.
- There is no single correct output to compare against.
- "It worked when I tried it" is a sample of size one.

So an eval is a test suite that copes with this by measuring **rates** instead of
checking **results**. Not "did it work" but "how often, out of how many, and how
sure are we."

## The sentence exercise

Here is the most useful ten seconds in this course. Find your test suite, your
eval dashboard, whatever green checkmark you currently trust, and finish this
sentence out loud:

> **"When this passes, it proves that ______."**

Most people reach for "…the system works." Almost nobody can defend that. The
honest answers are usually one of these, and they are very different:

| What green really proves | What it does not prove |
| --- | --- |
| My test code runs without crashing | That it tested anything |
| My checks behave the way I wrote them | That the checks are the right checks |
| The system handled these 12 examples | That it handles the next 12 |
| The system handled these 12 examples, 9 times out of 10 | That it handles anything unlike them |

The fourth row is a real eval. The first row is what a lot of eval suites
actually deliver, including expensive ones.

## Three kinds of data, and why the label has to be automatic

A rate is meaningless until you know what data produced it. There are three
kinds, and mixing them up is the single most common way an eval misleads its own
author:

| Label | Where the data came from | What a rate over it means |
| --- | --- | --- |
| **FIXTURE-ONLY** | Examples you wrote by hand to test your tests | "My check code behaves as written." Useful. Not a quality claim. |
| **CORPUS** | Real recorded runs from your system | "The system behaved this way on this sample." |
| **LIVE** | A run you just executed | "The system behaves this way now." |

Here is the part that matters, and it is a design instruction rather than a good
intention: **the label has to be printed by the reporting code, not remembered by
the person.**

In the project behind this course, the distinction was documented honestly — in
the methodology doc, under a heading literally titled *"Open-coding status
(honest)"*. And then the numbers travelled into a README, a comparison table, and
conversations with other people, while the label stayed home. The author wrote
the disclosure and then let the figures out without it.

> A caveat in prose protects the person who wrote it. A label printed by the code
> protects everyone who reads the number.

## What it cost

**September 2026.** A 13,000-line eval harness. A green gate on every pull
request for a month. Trace store, sampling strategies, annotation tool, judge
alignment with confidence intervals, bias correction. All of it real, all typed,
all unit-tested.

Then somebody asked what the green gate asserted.

The answer was: *94 hand-written example files make 21 pieces of check code
behave the way they were written to behave.* Every word of that is worth having.
None of it is a statement about whether the agents work. The suite had never
scored a real run.

The gap between what it proved and what everyone assumed it proved had been open
for a month, in public, with a badge on it.

## Your move

Three minutes, right now:

1. Finish the sentence for your own suite. Write it down.
2. Ask which of the three labels your data deserves. Be strict: hand-written
   examples are FIXTURE-ONLY even if they are very good hand-written examples.
3. If the sentence and the label are less than you'd been implying, that is
   normal and it is now fixed, because you know.

You do not need to fix anything yet. You need the sentence.

---

## In one line

**Say what green proves, label what data proved it, and make the code print the
label — because prose caveats stay home and numbers travel.**

Next: [Session 2 — Write down what happened, before you score it](./session-2-traces-before-scores.md)
