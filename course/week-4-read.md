# Week 4 · Read — thirty runs, by hand

**By the end:** you've read thirty runs yourself, written down what went wrong in your own
words, and let categories *emerge* from your notes.
**Time:** one afternoon (~3 hours) · **Cost:** $0 · [← Course home](./README.md)

---

## Why this week matters most

Surveys ask teams whether they *have* observability — most say yes. None asks the number that
decides whether it means anything:

> **How many traces has a human on your team actually read?**

![Seven stages get built; the one that makes them count is reading](../docs/images/eval-infra-vs-evidence.svg)

Installing observability is procurement. Reading traces is the work — and the one step you
can't build your way through. The project behind this course built 13,000 lines of eval code
and read zero traces. Don't copy that.

![Read first, categories come last](./images/reading-loop.png)

## The rules

1. **You read. Not a model.** If a model pre-labels the runs, you'll anchor on its guesses and
   lose the ground truth everything else rests on.
2. **No categories up front.** Don't open the failure catalogue yet. Write what you see:
   *"QA retried three times after the file already existed."*
3. **Note the first thing that went wrong,** not every symptom after it.
4. **Thirty is enough** to change what you build next.

This is **open coding** (Husain & Shankar). In testing terms: exploratory testing with notes,
before the test plan.

## Step 1 — Pick thirty (10 min)

Uses the corpus you built in week 3 (`course/.work/traces`).

> **You need at least 30 runs with something in them** — which is not the same as 30 runs, as
> step 1 is about to show you. A fresh clone has neither, and dry runs are all
> identical.
> Either do real runs in weeks 1–2 (about $1 each, capped), read the recorded case
> in `docs/eval-runs/` instead, or use a checkout that already has a run history. A shipped
> teaching corpus is planned (`.kiro/specs/eval-testbed/`) but doesn't exist yet.

**Predict.** Thirty random runs from your corpus. How many do you expect to be informative?
Write down a number. Then write down how you would *check* that answer before spending three
hours reading.

**Run.**

```bash
uv run python -m evals.cli sample --strategy stratified -n 30 --seed 1 \
  --traces-root course/.work/traces --samples-root course/.work/samples
```

**Observe the sampler's own output before you open anything.** It prints `n_corpus`,
`n_eligible` and `n_selected`. Then name the manifest you just made, once, and use that name
for the rest of the step:

```bash
SAMPLE=$(ls -t course/.work/samples/*.json | head -1); echo "$SAMPLE"
```

Now ask what is actually *inside* the thirty it picked:

```bash
python3 -c "
import json, sys
m = json.load(open(sys.argv[1]))
c = sorted(len(json.load(open('course/.work/traces/%s.json' % t)).get('spans') or [])
           for t in m['selection'])
print('spans per trace:', c)
print('empty:', c.count(0), 'of', len(c))
" "$SAMPLE"
```

> Pass the path in rather than letting the snippet guess. The first version of this step
> picked the file with `sorted(glob(...))[-1]`, which is alphabetical — and sample filenames
> end in a content hash, so "last alphabetically" is not "the one I just made". It reported
> `empty: 0 of 0` for a sample of four. It was found on 2026-09-18 by someone running this
> step, after I had run it myself and seen the right answer, because in my directory the two
> hashes happened to sort the right way. Instruments that are correct by coincidence are the
> subject of week 3.

**Explain.** Stratification balances on backend x scenario x status. None of those notice that
a run recorded *nothing*. On 2026-09-18 this repo's own corpus — 355 real traces — produced a
stratified thirty in which **24 had zero spans**. The full distribution: 257 empty, 95 with
exactly one span, and **3** with enough in them to read. On a fresh clone you will see
something much smaller and probably all zeros; the shape is the lesson, not the counts.

A sampler will always hand you thirty. Whether thirty readable runs exist is a different
question, and it is the one worth asking first.

This is week 3 in a new costume. There, two readers disagreed about the data. Here, one
reader is confident about a corpus that is mostly hollow — in exactly the tone it would use
if the corpus were fine.

**Change.** Ask for traces that contain something:

```bash
uv run python -m evals.cli sample --strategy stratified -n 30 --seed 1 --min-spans 1 \
  --traces-root course/.work/traces --samples-root course/.work/samples
SAMPLE=$(ls -t course/.work/samples/*.json | head -1); echo "$SAMPLE"
```

`n_eligible` is now the size of your readable pool, and `n_selected` is what you got.
`$SAMPLE` now points at this second manifest — re-run the inspect snippet above to see the
difference, and note that it is the same command reading a different file rather than a
different command.

**If `n_selected` is 0, stop here — that is the finding.** You have no runs worth reading, so
there is nothing to open in the workbench and nothing to annotate. Keep the sample id from
before if you want to compare, go make runs, and come back:

```bash
AI_TEAM_ENV=dev AI_TEAM_RUN_BUDGET_USD=1 \
  uv run python scripts/run_demo.py demos/00_smoke_test \
  --backend langgraph --skip-estimate --timeout 900   # one run, ~5-15 min, cents

uv run python scripts/run_smoke_batch.py --n 10 --backends langgraph  # ten, ~1 hour
```

Then rebuild the corpus (week 3, step 2) and sample again. Reading thirty stubs teaches you
nothing and convinces you otherwise, which is worse than not reading at all.

The check you write in week 5 — *fail any trace with no spans* — is this same question asked
by a machine, on every run, forever. That is not a coincidence. It is what the course is for.

```bash
SAMPLE_ID=$(basename "$SAMPLE" .json); echo "$SAMPLE_ID"
uv run python -m evals.cli annotate bundle --sample $SAMPLE_ID --out course/.work/bundle.json \
  --traces-root course/.work/traces --samples-root course/.work/samples \
  --annotations-root course/.work/annotations
```

Open `evals/ui/workbench.html` in a browser (it's one local file — no server) and drop in
`course/.work/bundle.json`.

## Step 2 — Read (2–3 hours)

Most traces are thin (week 3), so keep the raw record open next to the workbench:

```bash
# the run folder for the trace you're reading (the workbench shows its workspace path)
ID=$(ls -t output/runs | head -1)   # newest run; replace with the one you're reading
python3 -m json.tool output/runs/$ID/run.json
grep -E '"(current_phase|retry_count|errors)"' output/runs/$ID/state.json
ls output/runs/$ID/logs workspace/$ID
```

Write one short note per run and a few tags in your own words. Export from the workbench when
you're done (it saves `annotations.jsonl`).

> A run that tells you nothing is still a note: *"no spans, no cost, can't tell what happened."*
> If a third of your notes say that, you've just measured your instrument.

**Observe.** Before moving on, count your own notes: informative vs. uninformative. Compare
with your prediction.

## Step 3 — Save and cluster (20 min)

**Run.**

```bash
NOTES=~/Downloads/annotations.jsonl       # wherever your browser saved the export
if [ -f "$NOTES" ]; then
  uv run python -m evals.cli annotate --sample $SAMPLE --batch-file "$NOTES" \
    --traces-root course/.work/traces --samples-root course/.work/samples \
    --annotations-root course/.work/annotations
else
  echo "No export at $NOTES — export your notes from the workbench first"
fi
uv run python -m evals.cli taxonomy propose --from-annotations \
  --annotations-root course/.work/annotations
```

**Observe.** A table of candidate categories built from *your* tags:

```
canonical              n  in_tax  variants
mislabeled_backend     2  no      mislabeled-backend
```

**Explain.** These are suggestions. For each: accept, rename, merge, or discard. Only now open
[the failure catalogue](../docs/posts/failure-taxonomy.md) and compare:

| | Count |
| --- | --- |
| Your categories that match a documented failure | |
| Documented failures you never saw in thirty runs | |
| Your categories with **no** documented failure | |

The last row is the valuable one: failures nobody found by reasoning from memory.

**Change.** Pick your most frequent category and write one sentence a *program* could check —
no model involved. That sentence is next week's code.

## ✅ Checkpoint

- [ ] 30 notes saved: `cat course/.work/annotations/*.jsonl | wc -l`
- [ ] A short list of categories, each pointing at specific run ids, with counts out of 30
- [ ] The comparison table above

When you report your categories, say what they are: **`CORPUS`, n = 30, a stratified sample of
one system.** They show you what *can* go wrong. They don't tell you how often it does
everywhere.

> Doing this on the real project? Use `--annotations-root evals/annotations` so your notes land
> in the project's own store.

**Next:** [Week 5 · Evaluate →](./week-5-evals.md)
