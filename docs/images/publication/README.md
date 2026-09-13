# Publication assets

Authored (or exported) images used outside this repository — Substack posts,
LinkedIn headers, work-sample screenshots. They are not referenced by the
product docs. The drift guard allowlists this directory.

Do not add run screenshots here; those belong in `docs/journal/` or should be
deleted.

## Eval audit series (Sept 2026)

Five pieces for the [eval-audit campaign](../../campaign/2026-09-eval-audit-campaign.md).
SVG source beside each PNG; PNGs render at 2x so they stay sharp on retina timelines.

**Social-only cards** (SVG + PNG here; embedded in no repo doc):

| File | Size | Shows |
| --- | --- | --- |
| `eval-three-zeros` | 1200x627 | 0 spans / 0 annotations / 0 of 17 observed, each with its query |
| `eval-industry-gap` | 1200x627 | Four survey percentages, and the question nobody asks |

**PNG exports** of diagrams whose SVG lives in `../` because the essay embeds them —
same split as `substack-harness-layers`:

| File | Size | SVG source |
| --- | --- | --- |
| `eval-two-trees.png` | 1200x680 | `../eval-two-trees.svg` |
| `eval-seven-months.png` | 1200x690 | `../eval-seven-months.svg` |
| `eval-built-vs-fed.png` | 1200x560 | `../eval-built-vs-fed.svg` |

House palette, shared with the older Substack assets: ground `#faf9f5`, accent `#1d9e75`,
ink `#1a1a2e`, rule `#d3d1c7`, alarm `#b4462f`.

Regenerate a PNG after editing an SVG — they are not built at publish time.
