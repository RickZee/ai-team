# Showcase

Standalone HTML pages built from repo findings. Each one is a complete document —
open it directly in a browser, no build step, no external assets beyond a Google Fonts
stylesheet.

| Page | Source of its figures |
| --- | --- |
| [`starved-harness.html`](./starved-harness.html) | The 2026-09-13 corpus audit. Every number is a query result or file count reproducible from this repo — see [`../journal/2026-09-13-eval-methodology-audit.md`](../journal/2026-09-13-eval-methodology-audit.md). |

## Rules

Anything published here follows [`../campaign/EVAL_GATE_STATUS.md`](../campaign/EVAL_GATE_STATUS.md):
every rate carries its `n` and its corpus kind (`FIXTURE-ONLY` / `CORPUS` / `LIVE`), and
no page states a quality rate while the corpus is stamped `NON-REPRESENTATIVE`.

Keep a page in sync with the audit it reports. If `index stats` changes, the page is
stale until it is regenerated.
