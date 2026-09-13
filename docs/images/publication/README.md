# Publication assets

Authored (or exported) images used outside this repository — Substack posts,
LinkedIn headers, work-sample screenshots. They are not referenced by the
product docs. The drift guard allowlists this directory.

Do not add run screenshots here; those belong in `docs/journal/` or should be
deleted.

## Eval audit series (Sept 2026)

Art for the [eval-audit campaign](../../campaign/2026-09-eval-audit-campaign.md). The set is
**method-forward**: each piece is about a diagnostic other people can use, with the repo's own
numbers as the worked example rather than the subject.

**Social cards** (SVG + PNG here; embedded in no repo doc):

| File | Size | Shows |
| --- | --- | --- |
| `eval-audit-checklist` | 1200x690 | The five questions, as an instrument anyone can run |
| `eval-industry-gap` | 1200x627 | Four survey percentages, and the question nobody asks |

**PNG exports** of diagrams whose SVG lives in `../` because the essay embeds them —
same split as `substack-harness-layers`:

| File | Size | SVG source |
| --- | --- | --- |
| `eval-two-trees.png` | 1200x680 | `../eval-two-trees.svg` |
| `eval-self-review-cadence.png` | 1200x660 | `../eval-self-review-cadence.svg` |
| `eval-infra-vs-evidence.png` | 1200x630 | `../eval-infra-vs-evidence.svg` |

House palette, shared with the older Substack assets: ground `#faf9f5`, accent `#1d9e75`,
ink `#1a1a2e`, rule `#d3d1c7`.

**Carousels** (LinkedIn document posts) live in [`carousels/`](carousels/) as PDF, with a
contact sheet beside each for review.

These are finished assets. The SVG is the editable source for a diagram; the PNG is its 2x
export for social. Carousel decks are generated from a small toolkit kept **outside this
repo** — ask Rick for `art-build` if a deck needs re-cutting. Do not hand-edit a carousel
PDF.

Files written through the desktop bridge arrive carrying a C2PA provenance manifest (a
`caBX` PNG chunk, a `<metadata>` block in SVG); strip it before publishing so the committed
file matches the render.
