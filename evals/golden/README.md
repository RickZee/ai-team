# Golden set for LLM judges (R8)

This directory holds append-only JSONL files: one per failure mode
(`FM-###.jsonl`) containing human `LabelingUnit` records.

## Honesty constraint

**Do not invent human open-coding annotations** or claim model-generated labels
came from a domain expert reviewing real runs. Model-generated ground truth
corrupts the harness.

| Task | Who | Status |
| --- | --- | --- |
| 5.1 Annotation TUI | tooling (this repo) | implemented in `evals/annotate.py` |
| **5.2 Open coding pass** | **human** | **not automated** — sample real traces and annotate yourself |
| 5.3 Axial coding tooling | tooling + human review | `taxonomy propose` clusters tags; humans accept/merge/reject |
| 5.4 Golden set machinery | tooling | `evals/golden.py` + CLI; empty while all FMs are `detection: check` |
| 5.5 Check validation | tooling | uses **synthetic** check fixtures (`fail`/`pass`), not production labels |

Taxonomy `positive_examples` / `negative_examples` currently point at committed
check fixtures under `evals/fixtures/traces/` (copied from
`tests/fixtures/traces/`). Those are synthetic fail/pass pairs for deterministic
checks — **not** production open-coding labels.

When a failure mode uses `detection: judge`, populate golden JSONL here via:

```bash
python -m evals.cli golden label --fm FM-00X
```

Splits are assigned once by `assign_split()` (`test` if `sha256(id) % 100 < 40`).
