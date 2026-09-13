# Runbook — eval audit campaign

The execution guide. Open this on a posting day; everything you need is one path away.
Strategy, drafts and reasoning live in
[`2026-09-eval-audit-campaign.md`](./2026-09-eval-audit-campaign.md) — this file is the
doing.

---

## Before anything ships

Four things gate the whole campaign. None of them takes long; all four block post 1.

- [ ] **Substack exists**, with the promise as its tagline and About text:
      *one measurement from a real multi-agent system every week, with the query that
      produced it.* Four posts end on `[link]` and cannot ship until this URL is real.
- [ ] **Confirm the promise wording.** It is the sign-off in every LinkedIn post. Changing
      it after week 1 breaks the repetition that makes it work.
- [ ] **Decide on the repo link.** No post currently links `github.com/RickZee/ai-team`.
      The art says *"every finding is reproducible from the repository."* Either make the
      repo public-facing and link it in S1 and the L2 closing slide, or pull that claim
      off the art.
- [ ] **Post from the personal profile, not an ArqiSoft page.** Company pages absorb the
      external-link penalty; personal profiles do not. This is why the link goes in the
      post body.

---

## Where everything is

### Copy

| Piece | Where |
| --- | --- |
| All six LinkedIn drafts | [`2026-09-eval-audit-campaign.md`](./2026-09-eval-audit-campaign.md), one section per post |
| S1 — The Starved Harness | [`../posts/the-starved-harness.md`](../posts/the-starved-harness.md) |
| S2 — FIXTURE-ONLY | [`../posts/fixture-only.md`](../posts/fixture-only.md) |
| S3 — What thirty traces found | not written; gated |

### Art — upload the **PNG**, never the SVG (both platforms strip or refuse SVG)

| Post | File |
| --- | --- |
| L1 | `../images/publication/eval-industry-gap.png` |
| L2 | `../images/publication/carousels/l2-two-trees.pdf` ← **PDF, document post** |
| L3 | `../images/publication/carousels/l3-five-questions.pdf` ← **PDF, document post** |
| L4 | `../images/publication/eval-corpus-kinds.png` |
| L5 | `../images/publication/eval-telemetry-writers.png` |
| S1 embeds | `eval-self-review-cadence`, `eval-two-trees`, `eval-infra-vs-evidence` (already in the markdown) |
| S2 embeds | `eval-corpus-kinds` (already in the markdown) |

Contact sheets (`carousels/*-sheet.png`) show a whole deck at a glance — use them to
check a deck before uploading, not as the upload itself.

### Evidence, if anyone asks

| | |
| --- | --- |
| The raw audit with queries | [`../journal/2026-09-13-eval-methodology-audit.md`](../journal/2026-09-13-eval-methodology-audit.md) |
| What may and may not be claimed | [`EVAL_GATE_STATUS.md`](./EVAL_GATE_STATUS.md) |
| The remediation spec | [`../../.kiro/specs/eval-methodology-alignment/`](../../.kiro/specs/eval-methodology-alignment/) |
| Current honest state of the harness | [`../EVAL_METHODOLOGY.md`](../EVAL_METHODOLOGY.md) |

---

## The schedule

| Wk | Day | Channel | Post | Ready |
| --- | --- | --- | --- | --- |
| 1 | Tue | LinkedIn | L1 — The question nobody's dashboard answers | yes |
| 1 | Thu | Substack | S1 — The Starved Harness | yes |
| 1 | Thu | LinkedIn | L2 — Two trees, one reader *(carousel)* | yes |
| 2 | Tue | LinkedIn | L3 — Five questions *(carousel)* | yes |
| 2 | Thu | Substack | S2 — FIXTURE-ONLY | yes |
| 2 | Thu | LinkedIn | L4 — FIXTURE-ONLY | yes |
| 3 | Tue | LinkedIn | L5 — Self-reported telemetry | yes |
| 3 | Thu | Substack | S3 — What thirty traces found | **gated** |
| 3 | Thu | LinkedIn | L6 — What thirty traces found *(carousel)* | **gated** |

**The week 3 gate:** `evals/annotations/` must hold ≥30 records with `unaided: true`.
It currently holds none — the directory does not exist. Week 3 does not get written from
expectations; if the annotation pass slips, week 3 slips with it.

---

## Posting a LinkedIn post

1. **Paste the body from the campaign doc.** Do not re-type it or lightly reword — the
   character counts are tuned and the sign-off must match across posts.
2. **Attach the art.** PNG for a normal post; PDF for L2 and L3, which are document posts.
3. **Put the Substack link in the post body**, at the end, after the promise line. Not in
   the first comment.
4. **No hashtags.** 3–5 slightly reduce reach, 6+ clearly reduce it.
5. **Post Tue or Wed, 8–10am your time.** After 90 days use your own analytics instead.
6. **Stay for 30 minutes and reply to every comment.** Threaded replies reach further than
   the post did; this is distribution, not manners.
7. **Never two posts in one day** — they compete in the same testing window.

The first 60–90 minutes decide the post. If you cannot be present, post another day.

## Publishing a Substack issue

1. Paste from the markdown file. Images are already embedded and will carry over.
2. Keep the sign-off paragraph identical every issue.
3. Publish Thursday, then let that morning's LinkedIn post carry the link.
4. Do not paywall anything. Free list first; the funnel top is what matters this year.

## Between posts

- **15 minutes a day in Substack Notes**, as a person, not a link dump.
- **Recommendations are the biggest growth lever on Substack** — bigger than anything in
  these drafts. Find the AI-engineering and eval newsletters adjacent to this work and
  build real reciprocal relationships. Worth more than a fourth LinkedIn post.

---

## Rules that survive every edit

1. **No pass rate, accuracy figure, or quality claim.** There is no `CORPUS` rate in
   existence. "$0 per-PR eval gate in CI" is publishable; "94% of evals pass" is not, in
   any phrasing, ever, until a corpus exists.
2. **Every rate carries its corpus kind and its `n`** — including in slide text.
3. **Do not describe** the taxonomy as validated, the judges as aligned, or the gate as
   hard. All three are false and all three are checkable by anyone who clones the repo.
4. **The gap is the story.** Describing the harness as finished would be a worse claim
   than describing it as built and starving.

If a draft ever conflicts with [`EVAL_GATE_STATUS.md`](./EVAL_GATE_STATUS.md), that file
wins.

---

## Editing the materials

- **LinkedIn copy** → the campaign doc, in the post's own section.
- **Substack essays** → the markdown files in [`../posts/`](../posts/).
- **A diagram** → the SVG is the source; re-export the PNG after changing it.
- **A carousel** → slide copy lives in the `art-build` toolkit kept outside this repo, in
  `carousel/build.py`. Rebuild there and copy the PDF back. Never hand-edit a PDF.
- **A figure in any of the above** → check it against the repo first. Every number in this
  campaign is a query result or a file count, and that is the entire credential.

## After week 3

There is nothing scheduled, and that is the real gap. Two candidates, in order:

1. **Survey ten public agent repos and classify their eval suites by corpus kind.** Turns
   `FIXTURE-ONLY` from a coinage into a finding and removes the n=1 exposure. This is the
   strongest single piece available.
2. **Mine [`../posts/failure-taxonomy.md`](../posts/failure-taxonomy.md)** — ~2,500 words
   on seventeen ways multi-agent builds break, attributed by layer, currently unused by
   this campaign. Three issues of material already written.
