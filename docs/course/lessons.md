# Seven months, seven lessons

**The history behind the course.** February to September 2026, one multi-agent
system, 277 commits, one engineer. Each lesson is here because it cost something,
and each one has a receipt you can go read.

Read this after the course, or instead of it if you prefer stories to
instructions. Full detail lives in [`../journal/`](../journal/) — corrections
included, which is the point of keeping it.

---

## Feb 15 — Never trust a generated plan without checking it lands

A rainy Sunday, a genuinely well-structured build plan from a model, and an
afternoon of running it through an editor before noticing that **whole prompts
had been silently dropped.** Not mangled. Absent.

Reset, restarted from a known-good state, wrote the lesson down that night.

Seven months later the same engineer had applied that lesson to almost
everything, and to exactly one thing he had not: the tool doing the checking.
Which is lesson seven.

> **Verify that the output of a generative step actually landed.** It is not
> paranoia, it is the cheapest check available, and the failure is silent.

---

## Jul 1–2 — Audit your own wiring before you convict the framework

A retry loop had been blamed on a third-party framework across three separate
work sessions. Duplicate emissions, a loop that would not terminate, verdicts
flaky about half the time.

It was not the framework. In that framework's event model, a completed step emits
its own name as the next trigger. Ten methods had been named identically to the
event they listened for. Each was an unbounded self-loop.

Live evidence: **93,284 retry iterations in 15 minutes.**

And the retry cap everyone thought was in place? Return values from plain
listeners were discarded, so `return "escalate_to_human"` had never routed once.
A cap that had never once applied, in a system that had been reasoning about how
often it fired.

The second half of that week is the more interesting one. With the wiring fixed,
the *remaining* failures were re-tested with every role pinned to the same model
— and one model wrote **zero test files in 3 of 3 runs** where another wrote real
test suites in **4 of 4**. The "framework problem" had a model problem hiding
behind it, and the original comparison had varied framework and model together,
so it could not have separated them.

This produced the project's central thesis:

> **Fix one layer and the failures migrate up to the next.** Model → framework →
> harness → provider. With controlled evidence, the reliability budget ranked
> **harness > model > framework** — the scaffolding around the model mattered
> more than which model it was.

And the operational half:

> **Read your framework's event semantics from its source, not its docs. Before
> convicting a dependency, audit your own wiring.**

---

## Jul 21–22 — Replace a confident sentence with a narrower one plus a number

A deliberately hostile review of the author's own repo. The brief: *find the
claims that would not survive a competent skeptic.* Then fix what it finds
instead of arguing with it. Four findings were bad enough to record.

**The judge shared a vendor with a contestant.** The LLM judge was hardcoded to
one vendor's model while one of the three systems under comparison ran on that
same vendor. Every cross-system verdict published had an unexamined
self-preference confound in it. → [Session 4](./session-4-checks-before-judges.md)

**The rankings did not survive their own confidence intervals.** Point estimates
published from n=5. A 1-in-5 rate has a 95% range of roughly 4–62%; 5-in-5 gives
57–100%. They overlap. The table asserted a ranking the data could not support,
in a project whose entire pitch was honest comparison.
→ [Session 5](./session-5-every-number-needs-n.md)

**It was comparing bundles, not frameworks.** Framework and model varied
together. The existing tables were relabeled **confounded** rather than quietly
regenerated, which is the harder and better choice.

**The README led with its weakest claim.** "Multi-Backend Agent Comparison
Platform" promised a leaderboard the sample size could not defend. Retitled to
*"A Field Study of Multi-Agent Failure Modes"* — the taxonomy promoted to the
headline, the comparison numbers demoted to observations.

> Nearly every fix was replacing a confident sentence with a narrower one plus a
> number. That is uncomfortable to do to your own README, and it is the only
> version worth publishing.

---

## Jul 23 — Anything you tune must be measured on a labeled set

The comparison side of the project had insisted on n≥5 for a month. Meanwhile the
safety thresholds had been tuned on **single runs** — one floor moved off one
batch's readings.

Same mistake, pointed at the defense layer instead of the measurement layer, and
unnoticed because guardrails felt like plumbing rather than science.

Building a labeled set of real false positives immediately caught two shipped
defects:

1. **The documented threshold never reached the code.** The doc said 0.15. The
   default was still 0.5 and the caller passed no override. The fix was live only
   in the documentation. Weeks of believing a bug was fixed because someone had
   written that it was.
2. **A rule only caught the explicit form of its violation.** It detected writing
   a production file via a function call, and sailed straight past *"I wrote
   src/app.py with the full Flask app"* in prose.

> **Anything you tune has to be measured on a labeled set — including the things
> that don't feel like models.** And check that a documented fix reached the
> code, because "I wrote that it was fixed" is not "it is fixed."

---

## Jul 24 — Free is a feature

The contribution guide asked drive-by contributors to run multi-run comparison
batches. In effect: *submit a fix, and also pay for it.* Nobody was going to.

The fix was a replay mode: read a recorded bundle, run the entire reporting
pipeline — intervals, verdicts, warning banners — against recorded rows. No live
runs, no API calls, **$0.00**. Live and replay share one rendering path, so replay
cannot drift from the real thing.

> **Replay validates the measurement, not the measured.** It proves the parsing,
> the statistics and the verdict rule are right, which is exactly what a change
> to the harness needs to demonstrate, and exactly what nobody should have to buy.

A free check runs on every change. A check that costs money runs when someone
remembers. That difference is worth more than the check's sophistication.

---

## Sep 13 — The auditor audits itself, and loses

An alignment pass: read the source methodology, compare it to the project's own
methodology doc, note the gaps.

There were no gaps. The methodology was right. Then he opened the corpus.

```
traces indexed .................. 50
spans across all fifty .......... 0
distinct sources ................ 1
distinct outcomes ............... 1
created within a window of ...... 1.97 seconds
annotations by a human .......... 0
```

Three separate failures, in increasing order of how long they took to admit:

**One: the writer and the reader had never agreed on where data lives.** The
corpus builder read the directory where generated *output* lands. The system's own
records were in a different directory — 210 of them, three sources, a 69-day span
— unread the entire time. One default argument. The re-index that fixes it was
free and had been available since the day the code was written.

**Two: the one signal left to a prompt was the one everything depended on.** Most
telemetry had real code writing it. Phase timeline records were requested from the
model in an instruction. Zero of those files existed across 440 runs — and that
file is the one nearly every interesting check reads.

**Three, and the real one: building the measurement is the most comfortable way
to avoid doing the measurement.**

> The people I learned this from say they spend 60–80% of development time on
> error analysis and evaluation. I have spent close to 100% of my eval time on
> *evaluation infrastructure* and 0% on *error analysis*. Those are different
> activities. The first is engineering, which I am good at and enjoy. The second
> is sitting down and reading traces for four hours, which is boring, and cannot
> be delegated to a model without destroying the thing it produces.

There is a fourth finding, and it is the one that generalises furthest. The repo
*said all of this.* It said it in a README. It said it in the methodology doc
under a heading titled *"Open-coding status (honest)."* The author wrote the
disclosure himself — and then let the numbers travel without it, into a README, a
comparison table, and how he described the project to other people.

> **The label stayed home and the figures went out.** That is a failure mode no
> check can catch, and the only fix is to have the reporting code print the label
> so it cannot be separated from the number.

Full write-up: [`../posts/the-starved-harness.md`](../posts/the-starved-harness.md)

---

## Sep 14 — The instruments, not the data

The obvious next step after Sep 13 was: re-index the right directory, then read
thirty traces. Neither happened that day. What happened instead was the thing
sitting underneath both.

Feeding the corpus **would not have been enough.** Of 1880 check results in the
most recent report, **1435 (76.3%) were "not applicable"** — the suite declining
to answer — and that number appeared in no headline, no verdict, no table. The
report format had no field for it.

Worse: two checks read a kind of record that **no code anywhere writes.** Not
missing from this corpus. Impossible on any corpus, ever. Two checks that could
never fire, inside a suite reporting a verdict and staying green.

And eleven of twenty checks were decided by a single pair of hand-written
examples — a unit test wearing a measurement's clothes.

> **A check that never decides anything is not coverage.** Count how many of your
> checks have ever returned pass or fail on real data. That number is your real
> coverage, and "we have twenty checks" is not it.

The same day, an annotation workbench got built instead of a coverage dashboard.
The reasoning is worth keeping:

> The first instinct was a dashboard — the coverage numbers are the kind of thing
> that looks good on a page. It would have been the wrong build. A dashboard
> displaying how starved the corpus is would have been one more artifact about
> the problem instead of a way through it.

---

## What the seven have in common

Reading them in sequence, the same shape appears six times:

| The pattern | Where it showed up |
| --- | --- |
| A generative step's output was never verified to land | Feb 15 · Sep 13 (telemetry in a prompt) |
| A claim outran its evidence | Jul 21 (rankings) · Sep 13 (labels stayed home) |
| Something was tuned or trusted without a labeled set | Jul 23 (guardrails) · Jul 21 (judge) |
| A fix lived in the docs and not in the code | Jul 23 (threshold) · Sep 13 (the honest heading) |
| The measuring instrument was never itself measured | Sep 13 · Sep 14 |
| Building the tool substituted for using it | Sep 13, and it is the biggest one |

Every one of them was found by *looking on purpose* — an adversarial review, an
alignment pass, a labeled corpus, a liveness count. None was found by the system
going red. **A suite that is green because it cannot see is the failure this
whole history is about**, and the only defense is periodically auditing the
instrument rather than the output.

Which is the course. → [Start at Session 1](./session-1-what-green-means.md)
