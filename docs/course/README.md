# Evals Without the Jargon

**A short course on how to tell whether an AI system actually works — and how to
know when your own measurement is lying to you.**

Six sessions. About two hours of reading, one afternoon of doing. No statistics
background, no machine-learning background, no API key, no budget. At the end you
own a working test harness for AI systems that fits in one file you can read.

The course is built from one real project's mistakes: a multi-agent system with
13,000 lines of eval code that its author audited in September 2026 and found had
never once measured the thing it was built to measure. Every lesson here has a
receipt — a file path, a query, a count — and most of them cost somebody a month.

---

## Read this if you are…

| You are | Start at | Skip |
| --- | --- | --- |
| **A QA or test lead** — you own quality but not AI | [Session 1](./session-1-what-green-means.md), then the translation table below | Nothing. This is your job with new nouns. |
| **An engineering manager or founder** — deciding whether to trust a number | [Session 1](./session-1-what-green-means.md) and [Session 5](./session-5-every-number-needs-n.md), then the [five questions](./session-6-run-it-yourself.md) | Sessions 2–4 unless you want the mechanics |
| **A developer shipping an AI feature** — no eval discipline yet | Session 1 and read straight through | Nothing, then run the kit |
| **In a hurry** | [The five questions](./session-6-run-it-yourself.md) — ten minutes | Everything else, for now |

### If you come from software testing, you already know most of this

The ideas are not new. The vocabulary is.

| AI eval word | What you already call it |
| --- | --- |
| **Trace** | A recorded test run — inputs, steps, outputs, kept immutably |
| **Span** | One step inside that run, with a timestamp |
| **Failure mode** | A defect class, the thing a bug taxonomy is made of |
| **Check** | An assertion. Deterministic, cheap, no model involved |
| **Judge** | A test oracle that happens to be an LLM, so it needs its own accuracy measured |
| **Golden set** | Expected results, labeled by a human |
| **Open coding** | Exploratory testing, with notes, before you write the test plan |
| **Corpus** | Your test data set |
| **Eval suite** | A regression suite whose subject is nondeterministic |

The one genuinely new thing: your subject gives different answers to the same
input, so a single pass proves nothing and every result is a rate with a
confidence interval. That is the whole difference. If you have ever argued about
flaky tests, you have the instinct already.

---

## The six sessions

| # | Session | Time | The one line |
| --- | --- | --- | --- |
| 1 | [What a green run actually proves](./session-1-what-green-means.md) | 15 min | Say out loud what a passing run asserts. It is usually less than you think. |
| 2 | [Write down what happened, before you score it](./session-2-traces-before-scores.md) | 20 min | You cannot measure what you did not record — and recording is where it breaks. |
| 3 | [Read thirty of them yourself](./session-3-read-thirty.md) | 40 min | The part that cannot be automated is the part that decides everything else. |
| 4 | [Let code decide what code can decide](./session-4-checks-before-judges.md) | 20 min | Cheap deterministic checks first. An LLM judge has to earn its place. |
| 5 | [Every number needs its n](./session-5-every-number-needs-n.md) | 15 min | A rate without a denominator is not a measurement, it is a vibe. |
| 6 | [Do it: the audit and your own harness](./session-6-run-it-yourself.md) | 60 min | Five questions, then one file you run on your own logs. |

**Published page:** <https://claude.ai/code/artifact/1c00c6db-96d1-4f91-8af8-5940afb2993b> — the whole course on one scroll, with the
audit readout, the interval chart and the real terminal output. Share that link; use these
files to edit it.

Plus: **[Seven months, seven lessons](./lessons.md)** — the project history, each
lesson with the receipt that produced it. Read it after Session 6, or instead of
the whole course if you prefer stories to instructions.

And: **[`minieval.py`](./minieval.py)** — the harness. One file, standard library
only, about 370 lines of which half are comments. It reads your existing logs and
tells you whether your instrument can see anything at all.

---

## The shortest possible version

If you read nothing else:

1. **An eval is a test suite whose subject is nondeterministic.** That is all.
   Everything else follows from "the same input gives different answers."
2. **Record the run before you score it.** The recording is where most eval
   systems silently fail, and nothing downstream can detect it.
3. **A human has to read some of the recordings.** Thirty is enough to change
   what you build next. A model reading them for you destroys the thing you
   wanted.
4. **If code can decide it, code decides it.** Save the expensive nondeterministic
   judge for the questions code genuinely cannot answer, and measure that judge
   against human labels before you trust it.
5. **Every number carries how many things it was computed from.** And a label
   saying what kind of data it came from.

Number 2 is the one nobody checks and the one that hides all the others.

---

## A note on honesty, because it is the point

This course teaches measurement, so it would be absurd to overstate what the
project behind it has measured. As of **2026-09-14**, in that project:

- The **$0 offline eval gate runs on every pull request.** True, and the useful
  part.
- **Zero traces have been read by a human.** The annotation directory is empty.
- **Zero of its seventeen failure modes have been observed** in real data. They
  came from reading and reasoning, which is a legitimate start and is not
  evidence.
- Every rate it can currently produce is **fixture-only** — it proves the check
  code behaves as written, and says nothing about whether the agents work.

That gap *is* the curriculum. A project that had quietly fixed everything would
have nothing to teach, and you would have no way to check it.

Claim rules for anything published from this work live in
[`../campaign/EVAL_GATE_STATUS.md`](../campaign/EVAL_GATE_STATUS.md).

---

## Sources

The methodology is Hamel Husain's and Shreya Shankar's — traces before scores,
binary verdicts over Likert scales, true-positive *and* true-negative rates
rather than accuracy, one domain expert rather than a committee, and open coding
that shows the human no model output. This course is a plain-language route into
their material plus one project's receipts, not a replacement for it.

- [Husain & Shankar — *A Field Guide to Rapidly Improving AI Products*](https://eugeneyan.com/writing/eval-analysis/)
- [Lenny's Podcast — *Why AI evals are the hottest new skill*](https://www.lennysnewsletter.com/p/why-ai-evals-are-the-hottest-new-skill)
- The audit that started this course: [`../posts/the-starved-harness.md`](../posts/the-starved-harness.md)

MIT licensed, like the repo. Take it, teach it, change it.
