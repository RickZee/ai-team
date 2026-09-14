# Session 6 — Do it: the audit and your own harness

**10 minutes for the audit. An hour for the harness.** The only session with
homework, and the only one that changes anything.

---

## Part 1 — The ten-minute audit

Five questions. Answer them about your own setup, out loud, before you build
anything. The author of the project behind this course failed all five on a
system he was proud of.

### 0. Is the thing that writes your traces pointed at the same place as the thing that reads them?

This would not have been on the list a week before the audit. It is first now.

Count the files in both directories. If your corpus has traces but no steps
inside them, this is your answer. → [Session 2](./session-2-traces-before-scores.md)

### 1. How many real traces are in it, and how diverse are they?

Group by every dimension you have: model, configuration, scenario, outcome, day.
**If one value dominates a column, your n is a fiction.** Fifty traces from one
source in a two-second window is one sample recorded fifty times.
→ [Session 3](./session-3-read-thirty.md)

### 2. How many has a human actually read?

Not scored. **Read**, with notes. If the answer is zero, every category in your
taxonomy came from your imagination, and that is worth knowing before you defend
a number derived from it. → [Session 3](./session-3-read-thirty.md)

### 3. Where did your failure categories come from?

If you cannot point from a category to the specific traces that produced it, you
are testing your imagination. That is a legitimate starting point. It is not
evidence, and the distinction should be recorded next to each category.
→ [Session 3](./session-3-read-thirty.md)

### 4. What does a green run actually assert? Say it in one sentence.

If the sentence is *"my check code behaves as written,"* that is real and useful,
it is **not** a quality claim, and you should stop letting it travel as one.
→ [Session 1](./session-1-what-green-means.md)

**Questions 0, 1 and 4 are free and take minutes. Questions 2 and 3 cost an
afternoon and are the ones that matter.** That asymmetry is why 2 and 3 are the
ones that never happen.

---

## Part 2 — A harness you own

[**`minieval.py`**](./minieval.py) — one file, standard library only, about 370
lines of which half are comments. No install, no API key, no network, no cost.

It answers questions 0, 1 and 4 automatically and tells you honestly that it
cannot answer 2 and 3.

### What it does

```bash
python3 minieval.py ingest --logs ./path/to/your/runs --out ./traces
python3 minieval.py stats  --traces ./traces
python3 minieval.py run    --traces ./traces --kind CORPUS
python3 minieval.py audit  --traces ./traces
```

`ingest` wants a directory whose subdirectories are runs. In each it reads any
`*.jsonl` as steps (one JSON object per line) and, if present, `run.json` or
`meta.json` for run-level fields. **Nothing is required.** Whatever is missing is
reported as missing rather than guessed — that is the whole design.

### The three checks are about your instrument, not your application

They are, deliberately, the three defects the 13,000-line harness turned out to
have:

| Check | Catches |
| --- | --- |
| `CHK-trace-has-spans` | A trace with no steps is a shell. Nothing can read it. |
| `CHK-writer-is-code` | Steps the model was asked to write are not evidence. |
| `CHK-run-record-complete` | A run with no end time or status poisons every denominator it touches. |

If those three pass on your logs, your instrument can see. That is a much lower
bar than "my system works," and it is the bar almost nobody checks first.

### What a starved corpus looks like

Real output, run against a corpus of runs that hold generated output and no
telemetry — the shape of the original failure:

```
stamps    FIXTURE-ONLY · NON-REPRESENTATIVE · EVIDENCE-STARVED
corpus    12 traces, 0 spans
results   36 total, 24 abstained (66.7%), 2 check(s) blind

check                       pass  fail   n/a  decided  rate
----------------------------------------------------------------------------
CHK-trace-has-spans            0    12     0       12  0.00 [95% CI 0.00, 0.24]
CHK-writer-is-code             0     0    12        0  BLIND — no_spans
CHK-run-record-complete        0     0    12        0  BLIND — no_run_record

A green run here asserts exactly one thing:
  "my instrument can see these three signals on this corpus."
It asserts nothing about whether the system under test is any good.
```

Two checks **BLIND** — never decided anything, on any trace. Three stamps. And
the closing sentence, printed by the code every single time, because Session 1.

### What a working corpus looks like

Same script, against runs that record properly — 40 runs, three sources, 68 days:

```
stamps    CORPUS · NON-REPRESENTATIVE
corpus    40 traces, 164 spans
results   120 total, 0 abstained (0.0%), 0 check(s) blind

check                       pass  fail   n/a  decided  rate
----------------------------------------------------------------------------
CHK-trace-has-spans           40     0     0       40  1.00 [95% CI 0.91, 1.00]
CHK-writer-is-code            35     5     0       40  0.88 [95% CI 0.74, 0.95]
CHK-run-record-complete       34     6     0       40  0.85 [95% CI 0.71, 0.93]

  FAIL CHK-writer-is-code  ...run05: 4 of 4 spans written by the model, not by code
  FAIL CHK-run-record-complete  ...run03: run record missing ended_at
```

Note it still says `NON-REPRESENTATIVE`: 40 traces against a floor of 100. The
instrument can see, and the sample is still too small to generalise from. Those
are different problems and the stamps keep them separate.

### The audit, automated

```
The ten-minute audit

0. Writer and reader agree on where logs live?      PASS
     164 spans across 40/40 traces
1. Enough traces, and diverse enough?               FAIL
     traces 40/100
2. How many has a human read, with notes?           ASK YOURSELF
     This file cannot answer it and neither can any model.
3. Where did your failure categories come from?     ASK YOURSELF
     If you cannot point from a category to specific traces, you are
     testing your imagination.
4. What does a green run assert, in one sentence?   PASS
     0.0% of check results abstained

Questions 2 and 3 are the ones that matter and the only ones that cost
an afternoon. Questions 0, 1 and 4 are free and were the ones I failed.
```

The script refuses to answer 2 and 3 and says why. That refusal is a feature —
see [Session 3](./session-3-read-thirty.md).

### The correction this session needed, live

The first run of `minieval.py` against this repo's own `output/runs/` reported that the
run records had **no final-status field at all** — 308 of 308 failing, every diversity
floor unmet.

It was wrong. The field was there the whole time, one level down, inside an `extra`
wrapper the script did not look inside. Same 324 files, same afternoon: a four-line
change to the reader turned *"all floors unmet, 308 failures"* into *"all floors met,
214 failures."*

Which is [Session 2](./session-2-traces-before-scores.md) arriving uninvited — a reader
and a writer disagreeing about where a value lives, producing confident numbers about a
system that was fine.

The tell was that the numbers were *too* damning: a field the project's own notes said
existed, absent from every single record. **When a measurement indicts everything,
suspect the measurement.** The script now looks one level into `extra`, `meta` and
`metadata`, with a comment saying why. If your records nest deeper, widen that list.

### Where to go from here

`minieval.py` is a starting point, not a destination. Grow it in this order:

1. **Add checks for your own failure modes** — the ones from your thirty traces.
   Keep the three-outcome rule.
2. **Add your own dimensions** to the diversity floors. `FLOORS` is a dict at the
   top of the file.
3. **Run it in CI.** It costs nothing, so it can run on every change. Start in
   warn-only mode and leave it there until a week of honest green.
4. **Only then** consider a bigger framework, and only for something specific you
   have proven you need. Adopting a second eval framework before the first has
   run on real data repeats the exact mistake this course is about.

---

## Part 3 — The cadence, or it decays

Everything above is a one-time pass. A taxonomy from one afternoon describes the
system as it was that afternoon.

| Pass | How often | Why |
| --- | --- | --- |
| **Open coding** | ≥100 fresh traces every 2–4 weeks | the system changes; your categories follow |
| **Outlier review** | 10–20 traces weekly between passes | cheap early warning |
| **Forced review** | regardless of calendar, when the model changes, a component is added, or a configuration is toggled | the thing you changed is exactly the thing your old sample can't see |

Report staleness; never gate on it. A gate that fires because nobody read traces
last week gets disabled in a fortnight, and then you have neither the reading nor
the gate.

**Anchor it to a date.** "Every 2–4 weeks" with no anchor is unfalsifiable, which
is another way of saying it will not happen.

---

## You're done

You can now:

- say what a green run proves, and label the data behind it
- record runs so scoring is free and repeatable
- read traces the way that produces real categories
- prefer code to judges, and measure a judge before trusting it
- report rates with n, uncertainty, and what could not be seen
- run all of it on your own logs today

The one thing left is the afternoon. It is question 2, it is the only step nobody
can do for you, and it will change what you build next more than everything else
on this list combined.

---

## In one line

**Run the five questions today, run the script on your own logs today, then block
the afternoon — because the free parts are not the parts that matter.**

Back to [the course index](./README.md) · Or read
[seven months, seven lessons](./lessons.md)
