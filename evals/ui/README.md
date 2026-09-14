# Error Analysis Workbench

`workbench.html` — the human loop from Husain & Shankar, as a local page.
Open it in a browser. No server, no build, no network, no dependencies.

```bash
open evals/ui/workbench.html          # macOS
xdg-open evals/ui/workbench.html      # Linux
```

## Why this exists

`eval-methodology-alignment` R13 says the annotation friction *is* the reason open
coding never happened: an `$EDITOR` round-trip per trace, in a terminal, for 100
traces. `evals/annotations/` is still empty, and every stage downstream —
axial coding, the taxonomy, golden labels, judges — waits on it.

This is the surface for the part that cannot be delegated. It shows you traces and
gets out of the way.

## The four stages, and what unlocks each

| Stage | Does | Unlocks at |
| --- | --- | --- |
| 1 · Open code | read a trace, invent codes in your own words | always |
| 2 · Axial code | cluster your codes, accept / rename / reject | **30 unaided records** (R7.4) |
| 3 · Taxonomy | draft a failure mode per accepted category | ≥1 accepted category (R9.2) |
| 4 · Judge | scaffold a judge prompt | FM confirmed + **100 labels** (R11.1, R12.3) |

The gates are the point. They are not decoration and they are not advisory — a
locked stage explains what it is waiting for and why, so the discipline lives in
the affordances rather than in a spec nobody re-reads. Stage 4 is honestly empty:
nothing in this repo is judge-eligible yet.

## The loop

```bash
# 1. sample traces to read
uv run python -m evals.cli sample --strategy stratified -n 100 --seed 1

# 2. bundle them for the page
uv run python -m evals.cli annotate bundle --sample <sample_id> --out bundle.json

# 3. open workbench.html, drop bundle.json in, read and code, then Export

# 4. ingest what you wrote
uv run python -m evals.cli annotate --sample <sample_id> --batch-file annotations.jsonl

# 5. cluster server-side too, to confirm the page agreed
uv run python -m evals.cli taxonomy propose --from-annotations
```

`--skip-annotated` on step 2 omits traces you have already coded, so a bundle
resumes a sitting rather than restarting it.

## No model output. Ever.

Stage 1 offers **no suggestions of any kind** — no taxonomy slugs, no failure-mode
ids, no ranked guesses. Code reuse appears only after *you* have used a code.
That is `eval-harness` R3.7 and `eval-methodology-alignment` R7.3, and
`tests/unit/evals/test_annotate_bundle.py` asserts it by scanning the shipped HTML
for FM ids and known slugs.

The clustering in stage 2 is arithmetic — lowercase, snake_case, count — the same
normalisation `evals/taxonomy/propose.py` applies. Not a model. It is allowed
after 30 unaided records because by then the categories come from your reading,
not from the first three traces you happened to open.

## Keyboard

`j` / `k` next, previous · `t` codes · `n` note · `1`–`9` mark the first
divergence · `⏎` save and advance · `s` skip · `e` export · `?` help

## Ground truth lives in the repo, not in the browser

The page keeps your work in `localStorage` so a reload does not lose it, and that
is a convenience, not a record. `file://` storage is unreliable and invisible to
everything else. **Export and ingest, or it did not happen.** Step 4 is what puts
`AnnotationRecord` lines under `evals/annotations/`, and those are the only
annotations any downstream command reads.

Stage 3 emits YAML for you to read and paste. It does not write
`failure_modes.yaml` — R8.3 requires a human accept/merge/reject between the
clusterer and the taxonomy, and a taxonomy that edits itself from its own
measurements has the FM-014 problem one level up.

## What the page mirrors, and how that stays honest

Three pure functions are re-implemented in JavaScript so the page can preview what
the CLI will compute:

| Page | Python original |
| --- | --- |
| `normalizeTag` | `evals/taxonomy/propose.normalize_tag` |
| `wilson` | `evals/reliability.wilson_ci` |
| `saturationStreak` | `evals/annotate.saturation_streak` |

Verified identical: `normalize_tag` on 20 cases including unicode and
punctuation-only input, `wilson_ci` to six decimal places, `saturation_streak`
across seven sequences. `test_annotate_bundle.py` pins the values the page
hard-codes, so drift on either side fails a test rather than quietly showing you a
different number than the CLI will.

One deliberate difference: equal-count categories sort by name in the page and by
insertion order in Python's `Counter.most_common`. Display order only — same
canonicals, counts and spellings.
