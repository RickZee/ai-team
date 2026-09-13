# Campaign — the eval audit (Sept–Oct 2026)

**Anchor:** [`docs/posts/the-starved-harness.md`](../posts/the-starved-harness.md)
**Showcase:** [`docs/showcase/starved-harness.html`](../showcase/starved-harness.html)
**Claim rules:** [`EVAL_GATE_STATUS.md`](./EVAL_GATE_STATUS.md) — read before editing any post.
**To execute:** [`RUNBOOK.md`](./RUNBOOK.md) — schedule, file paths, posting mechanics.
This doc is the strategy and the drafts; the runbook is the doing.
**Art:** [`docs/images/publication/`](../images/publication/) — five pieces, house style, 1200-wide.

---

## The frame

**Industry-first. The repo is the evidence, not the subject.**

The failure mode to avoid is a series whose subject is Rick's system not working. That reads
as a confession, and a confession is not a credential. Every piece here leads with a pattern
other people are living inside, and uses this repo as the worked example that proves the
pattern was actually investigated rather than asserted.

The test for any draft: **would this still be worth reading by someone who does not care
whose repo it is?** If the answer is no, the framing has slipped back to confession.

### The term to own

Thought leadership runs on vocabulary other people borrow. This work produced one worth
pushing: **the corpus kind** that every pass rate must carry — `FIXTURE-ONLY`, `CORPUS`,
`LIVE`. It is immediately usable by a stranger, it names a confusion the whole field has
(a green eval suite read as evidence the system works), and nobody has named it.

`FIXTURE-ONLY` is the word that does the work. *"Most eval suites are FIXTURE-ONLY and
their owners don't know it"* is a sentence people repeat. Introduce it properly in S2/L4,
use it consistently everywhere else, and never publish a rate without it — the discipline
is what makes the term credible rather than a coinage for its own sake.

Secondary candidates, already in the repo, worth keeping consistent but not pushing:
`self_reported_telemetry` (FM-018) and *the instrument is the last thing anyone audits*.

| Reads as confession | Reads as expertise |
| --- | --- |
| "My eval system had zero traces" | "Here are five questions most eval setups fail" |
| "I never checked" | "The instrument is the last thing anyone audits" |
| A timeline of my mistakes | A timeline of what auditing on a cadence catches |
| Three red zeros | The writer/reader split, drawn so anyone can check for it |

The personal material does not disappear — it is what makes the piece credible, and it is
the reason the numbers are real. It moves from headline to evidence: one paragraph inside a
post, one figure inside the essay, never the hero.

## The story underneath

Still a three-act arc, and still true — it just runs under the surface rather than being the
pitch.

**Act I.** 15 February, day one. A generated build plan, whole prompts silently dropped, and
a lesson written down that night: *never trust a generated plan end-to-end without checking
it lands.*

**Act II.** Seven months of applying it. 277 commits. Four self-audits, each catching what
the last could not — including a July review that found the judge sharing a vendor with a
contestant and rankings that did not survive their own confidence intervals.

**Act III.** 13 September: the same scrutiny pointed at the instrument, which had never been
checked that *it* landed.

The line that does the work — used **once**, in the essay, never as a post headline:

> The instrument is the last thing anyone audits, and the only one whose failure hides every
> other.

### The rhyme

The series has a second callback that costs nothing and lands hard, because it is
documented in the journal rather than constructed for the post:

| | |
| --- | --- |
| **23 July** | n=1 mistake found in the **defense layer** — during a review he ran on himself |
| **13 September** | the same n=1 mistake in the **measurement layer** — the thing that was supposed to catch it |

Use it once, in the essay, and phrase it as a property of instruments rather than a property
of Rick. Repeating it across posts turns a rhyme into a tic.

## Where this sits in the industry conversation

The alignment is what turns a personal confession into a claim other people have to
answer. From LangChain's *State of Agent Engineering* (n = 1,340 practitioners):

| | |
| --- | --- |
| Have observability for agents | **89%** |
| Detailed step-level tracing | **62%** |
| Run offline evals | **52%** |
| Use human review | **60%** |
| Traces a human has actually read | **not a question anyone asks** |

Every one of those percentages measures whether you *installed* the thing. None measures
whether anyone *looked at what it produced*. Rick was inside the 89% and functionally
outside all of it — which is almost certainly true of a large share of that 89%, and
nobody has said so with their own numbers attached.

**Headline available because of this:** *Installing observability is procurement. Reading
traces is the work.*

## The techniques in use

Worth naming, so edits don't accidentally undo them.

1. **Open on the reader's problem, not mine.** L1 starts with a number the reader can
   check against their own team, and only then says what happened here. The old draft opened
   inside my discovery; that made me the subject.
2. **Sandwich the personal material.** Evidence goes in the middle, between two paragraphs
   about everyone else. A confession at the top is a confession; the same paragraph in the
   middle is a citation.
3. **The antagonist is a mechanism, not a person.** `default="./workspace"` — a writer and a
   reader that disagree, with no test between them. Blaming the mechanism generalizes;
   blaming yourself does not.
4. **The reversal.** "The cause was not laziness and it was not missing instrumentation."
   The root cause being *better* than feared — the data existed all along — is a more
   interesting shape than "I logged nothing," and it is the version that is true.
5. **Specificity as proof.** 1.97 seconds, not "about two seconds." 211 dated directories,
   not "a couple hundred." 210 run records, 69 days. Precision is what says *I actually
   looked* — it is the whole credential, and it is why vague drafts of these posts are
   worthless.
6. **State the thesis once, at the end of post 1.** "Installing observability is
   procurement. Reading traces is the work." L3 then hands over the instrument. A reader
   who gets the principle in week one and the tool in week two has been given something
   twice.
7. **Open loop, then close it.** L1 promises the write-up. S1 pays it. L1 also
   implies a follow-up on what reading traces found, which S3/L6 pays — and that second
   promise is the only reason the gate on S3/L6 is non-negotiable.
8. **Every claim is checkable.** Every figure in the series is a query result, a file count,
   or a commit in a public repo. That is the difference between this and the opinion posts
   it will sit next to in the feed.

## What may not be said

- No pass rate, accuracy figure, or quality claim of any kind. There is no `CORPUS` rate
  in existence.
- "$0 per-PR eval gate in CI" is publishable. "94% of evals pass" is not, in any phrasing,
  until the corpus exists.
- Do not describe the taxonomy as validated, the judges as aligned, or the gate as hard.
  All three are false and all three are checkable by anyone who clones the repo.
- Every rate that appears carries its `n` and its corpus kind.

---

## Channel mechanics

Researched 2026-09-13. Figures are from vendor studies, not audited research — directionally
useful, individually soft. Where sources disagreed I have said so rather than picking the
convenient one.

### The division of labour

**LinkedIn is the discovery engine. Substack is the home base.** LinkedIn has the audience
and none of the relationship; Substack has the list, which is the only asset here that
cannot be taken away by an algorithm change. Every LinkedIn post exists to be worth reading
on its own **and** to move a few people onto the list.

### LinkedIn

| | |
| --- | --- |
| **Post from the personal profile, never a company page** | Personal profiles reportedly out-reach company pages by a wide margin, and — see below — they do not absorb the link penalty. ArqiSoft's page is not the vehicle. |
| **Length** | Sources cluster at **1,200–2,000 characters**. One recommends 1,250–3,000, another 1,200–1,800, another 800–1,000 as a floor. Treat 1,500 as the target. |
| **Structure beats length** | Posts under 7 paragraphs reportedly performed **66% worse** than those with 14+. Short paragraphs, one idea each, heavy line breaks. Our drafts already read this way — keep them that way. |
| **Plain words** | Posts whose average word ran over five letters performed **~40% worse**. This is a real constraint on a technical post; keep the jargon in the code blocks, not the prose. |
| **Format** | **Documents / carousels lead every format** (~6.6% engagement; ~1.45× reach). Text-only is the weakest. This is the biggest single change to make: the checklist and the two-trees diagram should ship as multi-page carousels, not single images. |
| **Saves are the strongest signal** | Roughly: a comment ≈ 2× a like, a save ≈ 2× a comment. L3 is built to be saved; that is the one to optimise. |
| **Replying matters** | Threaded replies reportedly reach up to 2.4× further. Budget 30 minutes after posting to answer every comment properly — this is not politeness, it is distribution. |
| **Golden hour** | First 60–90 minutes, LinkedIn tests with ~2–5% of your network. A post that stalls there is finished. Post when you can be present. |
| **Hashtags** | 0–2 neutral; 3–5 slightly negative; 6+ clearly negative. Use none. |
| **Cadence** | **2–5 posts/week**, never two in a day. Two per week, sustained, is the plan. |
| **Timing** | Tue–Wed, 8–10am local is the conventional answer. Check your own analytics after 90 days and ignore generic advice thereafter. |
| **Long tail** | A post that lands keeps being distributed for **2–3 weeks**, so the series does not need to be dense to compound. |

### The link question — reversed

Earlier drafts of this doc said "no link in the post; put it in the first comment." **That was
wrong for this account.** The sources genuinely conflict — one claims posts with external
links get *more* reach, several claim a penalty of 5–36% — but the largest segmented analysis
resolves it: **company pages absorb the link penalty; personal profiles show almost none.**
And link-in-first-comment is no longer a free workaround — the platform now detects the
pattern — while reliably costing clicks.

**So: Rick posts from his personal profile, and the Substack link goes in the post.** Burying
it trades the conversion this whole exercise exists for against a penalty he does not pay.

### Substack

| | |
| --- | --- |
| **Define the promise, not the niche** | Finish the sentence *"Every time I land in your inbox, you get ___."* Proposed: **one measurement from a real multi-agent system, with the query that produced it.** That promise is defensible, unusual, and it is the thing the whole eval-audit series demonstrates. |
| **Cadence** | Weekly, and specifically *the cadence you can hit on your worst week*. Consistency correlates with subscriber growth more than any individual post does. |
| **Recommendations are the biggest lever** | The single largest growth mechanism on the platform. Worth deliberate effort: find the AI-engineering and eval newsletters adjacent to this work and build real reciprocal relationships. This outranks anything in the post drafts. |
| **Notes** | ~15 minutes a day being a person in Notes, not dumping links. |
| **Free list first** | Do not paywall anything yet. Free→paid runs roughly 1 in 20, and the funnel top is what matters for the first year. |
| **Expect slow** | The first 1,000 subscribers is the slowest stretch by a wide margin; it compounds after. Judge this series on list growth, not on any single post's impressions. |

## Sequence — LinkedIn twice a week, Substack weekly

Three weeks, six LinkedIn posts, three Substack issues. X is dropped: two channels done
properly beats three done thinly, and the LinkedIn audience is the one that hires.

| Wk | Day | Channel | Piece | Format | Art |
| --- | --- | --- | --- | --- | --- |
| 1 | Tue | LinkedIn | **L1 — The question nobody's dashboard answers** | text + image | `eval-industry-gap` |
| 1 | Thu | Substack | **S1 — The Starved Harness** | full essay | cadence hero, two-trees, infra-vs-evidence |
| 1 | Thu | LinkedIn | **L2 — Two trees, one reader** | **carousel** | `eval-two-trees`, split to 5 slides |
| 2 | Tue | LinkedIn | **L3 — Five questions before you trust a green check** | **carousel** | `eval-audit-checklist`, one slide per question |
| 2 | Thu | Substack | **S2 — What a green eval run actually asserts** | full essay | new: corpus-kind diagram |
| 2 | Thu | LinkedIn | **L4 — FIXTURE-ONLY** | text + image | new: corpus-kind diagram |
| 3 | Tue | LinkedIn | **L5 — Self-reported telemetry** | text + image | `eval-two-trees` detail crop |
| 3 | Thu | Substack | **S3 — What thirty traces found** | full essay | frequency table | 
| 3 | Thu | LinkedIn | **L6 — What thirty traces found** | **carousel** | frequency table, per-category |

**S3 and L6 are gated** on `evals/annotations/` holding ≥30 records with `unaided: true`.
If the annotation pass slips, week 3 slips — S3 and L6 do not get written from expectations.
Everything in weeks 1 and 2 is already backed by work that exists.

### Two new pieces this plan needs

- **S2 / L4 — the corpus-kind piece.** `FIXTURE-ONLY` / `CORPUS` / `LIVE` currently lives in
  a paragraph of post 4. It deserves its own essay and its own LinkedIn post, because it is
  the term this series is trying to plant (see *The term to own*). The material exists in
  [`EVAL_GATE_STATUS.md`](./EVAL_GATE_STATUS.md); it needs writing up and one diagram.
- **Carousel versions** of `eval-audit-checklist` and `eval-two-trees`. Documents are the
  strongest LinkedIn format by a wide margin and both diagrams split naturally — the checklist
  into one question per slide, the two trees into a five-beat reveal.

### What the LinkedIn posts are for

Each one is standalone value **and** carries the Substack link in the post body — not the
first comment (see *The link question — reversed*). The ask is always the same and always
last: the promise, not "subscribe."

> *I write up one measurement from a real multi-agent system every week, with the query that
> produced it. [link]*

**Source material for L4 (not yet annotated):** the 2026-09-13 LangGraph
smoke — 1600 s, HITL, retry amplification after a successful write (last-12
AI relevance scorer, then `retry_development`), empty Home, starved journal.
Handoff and the debug loop we already describe:
[`docs/eval-runs/2026-09-13-langgraph-smoke/README.md`](../eval-runs/2026-09-13-langgraph-smoke/README.md).
Do not put FM ids in the annotation TUI; do not cite a pass rate from n=1.

---

## L1 — The question nobody's dashboard answers (LinkedIn, Tue wk 1)

**Art:** `eval-industry-gap.png`

> 89% of teams say they have observability for their AI agents. 62% have detailed
> step-level tracing. 52% run offline evals.
>
> There is no survey question for how many traces a human on the team has actually read.
>
> I think that is the number that decides whether any of the others mean anything, and I
> think almost nobody knows theirs. So I went and got mine.
>
> I run a multi-agent testbed — nine agent roles across three orchestration frameworks,
> about 13,000 lines of eval infrastructure on top: trace store, sampling strategies, an
> annotation tool, judge alignment with bootstrap confidence intervals, a $0 gate on every
> pull request. Every stage built, typed, unit-tested. Observability box fully ticked.
>
> Traces a human had read: zero. For two months.
>
> The cause was not laziness and it was not missing instrumentation. The harness had been
> logging the whole time — into a directory the corpus builder never opened. One default
> argument, two trees, no test between them. 210 run records across three backends and 69
> days, sitting unread one level over.
>
> Which means my failure taxonomy — seventeen categories, each bound to a deterministic
> check — came from an essay I wrote from memory rather than from anything I observed. The
> checks were well-engineered detectors for failures nobody had confirmed the system had.
>
> Here is the part I think generalizes. Every percentage in those surveys measures whether
> you installed the thing. None of them measures whether anyone looked at what it produced.
> Installing observability is procurement. Reading traces is the work, and it is the step
> that quietly gets skipped, because it is the only one you cannot build your way through.
>
> Root cause, the queries, and the fix in the write-up Thursday.

*Notes: the survey source goes inline (LangChain, State of Agent Engineering, n = 1,340) —
the numbers are load-bearing and an uncited stat invites the wrong argument. Close with the
Substack promise and the link **in the post body**; personal profiles do not pay the link
penalty and burying it in a comment only costs clicks. No hashtags. The personal material
sits in the middle, between two paragraphs about everyone else — do not move it to the top.
Target ~1,500 characters; short paragraphs, one idea each. Budget 30 minutes after posting
to reply to every comment.*

---

## L2 — Two trees, one reader (LinkedIn, Thu wk 1) — CAROUSEL

**Format: carousel, 6 slides.** Built from `eval-two-trees` as a reveal rather than a single
frame: the diagram gives away the answer at a glance, which is exactly what you do not want
before slide 4.

| Slide | Content |
| --- | --- |
| 1 | **My eval corpus had 50 traces and zero spans.** The cause was not what I expected. |
| 2 | `workspace/<run_id>/` — src/, tests/, and no telemetry. 440 directories, 221 of them empty. This is where my corpus builder was looking. |
| 3 | `output/runs/<run_id>/` — 211 dated run dirs. 210 run.json. 141 state.json with real cost and tokens. 60 cost logs. 8 receipts. **Three backends. 69 days.** |
| 4 | `evals/cli.py:547` — `backfill.add_argument("--workspace-root", default="./workspace")` |
| 5 | One default argument. Two trees. No test between them. Nothing fails loudly when a writer and a reader disagree about where data lives — the corpus just comes back thin. |
| 6 | **Does the thing that writes your traces agree with the thing that reads them?** Ten minutes to check. Full write-up + the promise + link. |

> Post body (carousels still need one, ~600–900 characters):
>
> My eval harness had been logging for two months. The corpus builder was reading the other
> directory.
>
> Not a missing-instrumentation problem. The records existed — 210 of them, three backends,
> a 69-day span — sitting one level over from where anything looked for them.
>
> One default argument, two trees, and no test between them.
>
> This is the failure mode I now check for first, in any system where something writes
> traces and something else reads them. It does not announce itself. Nothing errors. The
> corpus simply comes back thinner than the system that produced it, and every statistic
> above it inherits that quietly.
>
> Slides walk through how I found it, and the ten-minute version you can run on your own.
>
> I write up one measurement from a real multi-agent system every week, with the query that
> produced it. [link]

---

## S1 — The Starved Harness (Substack, Thu wk 1)

[`docs/posts/the-starved-harness.md`](../posts/the-starved-harness.md).

**Art order:** `eval-self-review-cadence.png` as the hero — four audits and what each
caught, so the piece opens on method rather than on a miss. `eval-two-trees.png` at the
root-cause section. `eval-infra-vs-evidence.png` where the loop is described.

**The Act I / Act III frame is in place.** The essay opens on 15 February — the rainy
Sunday, the dropped prompts, the lesson filed — runs through the seven months of applying
it, and lands on the one place it was never applied. The standfirst is now the thesis
("the instrument is the last thing anyone audits") rather than a confession.

Use the July 23 rhyme **here and only here**. Credit Husain and Shankar by name in the
opening; the piece works because it applies someone else's method honestly.

---

## L3 — Five questions before you trust a green check (LinkedIn, Tue wk 2) — CAROUSEL

**Format: carousel.** This is the strongest LinkedIn format and this post is built to be
saved, which is the heaviest engagement signal there is. Seven slides: a cover, one per
question, and a closing slide carrying the promise and link. `eval-audit-checklist.png` is
the source — each row becomes a slide.

| Slide | Content |
| --- | --- |
| 1 | **Five questions before you trust a green check.** Each has a cheap answer and an expensive one. The cheap answer is usually wrong. |
| 2 | **00 — Does the thing that writes your traces agree with the thing that reads them?** Two directories, one writer, one reader, no test between them. Nothing fails loudly when they diverge. |
| 3 | **01 — How many real traces, and how diverse?** Group by every dimension you have. If one value dominates a column, your n is a fiction. |
| 4 | **02 — How many has a human actually read?** Not scored. Read, with notes. The number no dashboard reports and no survey asks for. |
| 5 | **03 — Where did your failure categories come from?** If you cannot point from a category to the traces that produced it, you are testing your imagination. |
| 6 | **04 — What does a green run actually assert?** Say it in one sentence. "My check code behaves as written" is real and useful. It is not a quality claim. |
| 7 | **I failed all five on a system I was proud of.** Full write-up + promise + link. |

> Post body (~700 characters — the slides are the content, do not repeat them here):
>
> I built about 13,000 lines of eval infrastructure before I thought to ask what it was
> actually measuring. Then I wrote down the questions I should have asked in July, and ran
> them against my own system.
>
> I failed all five.
>
> The one that got me was question zero, which I would not have put on the list a month ago:
> does the thing that writes your traces agree with the thing that reads them? Mine had not,
> for two months, and nothing had errored.
>
> Slides have all five. Ten minutes to run against your own.
>
> The uncomfortable part underneath them: building measurement infrastructure is the most
> comfortable way to avoid doing measurement. The people who teach this spend 60–80% of
> development time on error analysis and evaluation. I had spent close to 100% of mine on
> evaluation infrastructure and 0% on error analysis.
>
> I write up one measurement from a real multi-agent system every week, with the query that
> produced it. [link]

*Notes: the slides carry the five questions — **the post body must not repeat them**. Cite
the 60–80% figure inline (Husain, AI Evals FAQ). No hashtags. This is the save-optimised
post of the set; budget 30 minutes after posting to reply to every comment.*

---

## S2 / L4 — FIXTURE-ONLY (Substack Thu wk 2, LinkedIn Thu wk 2)

**This is the term-planting piece.** Everything else in the series is a finding; this one is
a piece of vocabulary the field does not have and could use. Treat it as the most important
post here, and give the Substack version the room to be definitive — this is the page you
want people citing in a year.

**Art:** a new diagram is needed — three stacked bars or three labelled panels for
`FIXTURE-ONLY` / `CORPUS` / `LIVE`, each with what a pass rate on it does and does not
license you to say. House style, 1200 wide.

### LinkedIn version (L4)

> Your eval suite is green. What exactly did it pass against?
>
> I could not find standard vocabulary for this, so I have started using three words, and
> every rate I publish now carries one of them.
>
> FIXTURE-ONLY. Measured against synthetic test cases you wrote yourself. A green run proves
> your check code behaves the way you wrote it. That is a real and useful thing to know. It
> says nothing whatsoever about whether your system works.
>
> CORPUS. Measured against real traces from real runs. This is a claim about your system, on
> that sample, with that n.
>
> LIVE. Measured against a run you just executed. A claim about your system now.
>
> Most eval suites I have looked at are FIXTURE-ONLY, and their owners do not know it. Mine
> was, for two months, while I described it to people as evidence the system worked. The
> suite was not lying. I had written the disclosure myself, in a README, under a heading I
> titled "honest." Then the numbers travelled and the label stayed home.
>
> So the rule I hold myself to now: every rate renders its kind and its n, emitted by the
> reporting code rather than remembered by me. Prose cannot opt out of it.
>
> That one constraint would have caught the entire episode three months earlier than I did.
>
> I write up one measurement from a real multi-agent system every week, with the query that
> produced it. [link]

### Substack version (S2)

Written: [`docs/posts/fixture-only.md`](../posts/fixture-only.md) — ~1,600 words.

Structure: the moment the implication outran the claim → the three definitions →
why a CI badge is honest but read dishonestly → moving the label from prose into the
reporting code → what the honesty costs, stamped → the four questions to ask of other
people's claims → the rule.

Two things in it were deliberate and should survive editing:

- **The `n=1` limit is stated inside the essay**, where the quotable line lives: *"that
  is currently a guess rather than a finding — I have surveyed exactly one suite, and it
  was mine. Someone should go and count."* That sentence costs nothing, closes off the
  obvious attack, and sets up the survey issue.
- **The current state is published with its stamps** — `FIXTURE-ONLY`, `--warn-only`,
  `n: 0`, `eligible_to_gate: false`. Less impressive than "we have a $0 eval gate in CI"
  and much harder to argue with.

Art: [`eval-corpus-kinds.svg`](../images/eval-corpus-kinds.svg), embedded after the
opening.
---

## L5 — Self-reported telemetry (LinkedIn, Tue wk 3)

**Art:** [`eval-telemetry-writers.png`](../images/publication/eval-telemetry-writers.png) — the prompt line, then all three signals with who writes each and how many files exist.

*Was an X thread in the previous plan. As a LinkedIn post it loses the code blocks and gains
the argument — which is the better trade, since the idea is the point and the SQL was only
ever proof.*

> I had a failure mode in my taxonomy for an agent that grades its own work.
>
> I did not have one for an agent that *reports* its own work.
>
> The second turns out to be worse, and it took me two months to notice.
>
> A self-graded verdict is visibly wrong. You read it, you disagree with it, you fix the
> prompt. It announces itself.
>
> Self-reported telemetry does not announce anything. It produces a dataset that looks
> clean, and nothing downstream has any way to know it is thin. Every statistic built on top
> inherits the gap silently.
>
> Here is what that looked like in my own system.
>
> The file that records phase transitions — the trajectory every interesting check in my
> harness reasons over — had exactly one writer in code, added last week. Otherwise it was
> requested. A numbered bullet in an agent prompt: "write phase transition entries to
> workspace/logs/phases.jsonl."
>
> Across 440 runs, zero of those files exist.
>
> The precise version matters, because the sweeping version would be false. Most of my
> telemetry is written by code. The audit log has a writer. The cost log has two, and sixty
> of those files exist on disk. Phase records were the one signal I left to an instruction —
> and they happened to be the one every trajectory check depends on.
>
> That is the shape of the problem. Not "we forgot to log." One signal, delegated to
> something that had no obligation to produce it, holding up everything measured above it.
>
> Worth asking of your own system this week: which of your signals are produced by code you
> own, and which are asked for in a prompt?
>
> I write up one measurement from a real multi-agent system every week, with the query that
> produced it. [link]

---

## S3 / L6 — What thirty traces found (wk 3) — GATED

**Art:** built from the real frequency table. Reuse the house style; a horizontal bar of
axial categories by count, with `n` and the corpus stamp visible.

> Three weeks ago I posted that my eval system had never seen real data. I pointed it at the
> right directory, instrumented the runs, and read thirty traces by hand.
>
> [What the thirty traces actually showed — the categories, their counts, which of the
> seventeen imagined failure modes survived contact, and which ones I had never observed.]
>
> [How many of the 17 were confirmed / unobserved / refined. The new categories that had no
> FM at all.]
>
> Every figure here carries its n and its corpus kind, because that was the whole point.

**Gate:** do not draft this until `evals/annotations/` holds ≥30 records with
`unaided: true`. Fill the brackets from the real frequency table, and keep the
`NON-REPRESENTATIVE` stamp on it if the corpus still carries one.

L1 makes a promise. This is the post that keeps it. If the annotation pass slips, week 3
slips with it — it does not get written from expectations.

---

## Content strength — what the authority actually rests on

Audited 2026-09-13. The question is not "is there enough copy" (there nearly is) but
"does it hold up to a hostile reader."

### What is genuinely strong

| | |
| --- | --- |
| **Every figure is checkable** | 211 run directories, 1.97 seconds, 0 of 17, 440 runs — each is a query result or a file count against code in a public repo. Almost nobody in this conversation publishes numbers a stranger can verify. This is the core credential and it should never be diluted with an unverifiable one. |
| **Borrowed authority is borrowed correctly** | The method is Husain and Shankar's, named as theirs. Applying someone's method honestly and reporting what it found is a stronger position than claiming to have invented one. |
| **Seven months of self-audit is a record, not a claim** | Four documented passes, each catching what the last could not. That is evidence of a practice. |
| **`FIXTURE-ONLY` is a real contribution** | Vocabulary the field lacks, immediately usable, naming a confusion everyone has. |

### Where a hostile reader gets traction

1. **It is n=1.** Every finding comes from one person's one system. The unflattering
   summary — *"he found a bug in his own side project"* — is available to anyone who
   wants it, and nothing in the current series closes it off.
2. **The industry framing is borrowed, not measured.** The 89% / 62% / 52% figures are
   LangChain's. The claim that *"most eval suites are FIXTURE-ONLY and their owners do
   not know it"* is the most quotable line in the series and is currently an assertion.
   It is probably true. It is not evidenced.
3. **The one post that would produce original data does not exist.** S3 / L6 is the only
   piece that yields something nobody else has — a real failure-frequency table from a
   multi-agent system, with `n` and intervals. Everything else is analysis of a mistake.
4. **One issue is not a publication.** The promise says weekly. Substack's
   recommendations network — the largest growth lever on the platform — needs a track
   record before other writers reciprocate.
5. **The best asset in the repo is unused.** [`failure-taxonomy.md`](../posts/failure-taxonomy.md)
   is ~2,500 words on seventeen ways multi-agent builds break, attributed by layer
   (model / framework / harness / provider). That is the most original thing here, and
   this campaign only mentions it as *the thing that was not derived from traces*.

### The two acts that would change the position

**Do the annotation pass.** An afternoon of unglamorous reading converts the series from
"I found a measurement bug" into "here is what a multi-agent system actually fails at,
measured." It unblocks week 3 and it is the highest-authority act available at any price.

**Survey other people's eval suites.** Clone ten public agent repos, classify each suite
by corpus kind, publish the counts. That converts `FIXTURE-ONLY` from a coinage into a
finding, removes the n=1 exposure in one move, and is the kind of piece that gets cited
rather than liked. It is also the natural Substack issue 4.

### Honest bottom line

**Weeks 1–2 are ready.** S2 is written; four LinkedIn posts and two Substack issues, all
evidenced. **Week 3 is not**, and depends on work that has not started.
**After week 3 there is nothing**, though the taxonomy essay is three issues of unused
material sitting in the repo.

Enough to start well. Not yet enough to sustain a position.

## Pre-flight — what is still missing

Audited 2026-09-13. Copy is drafted for every ungated piece. These are the gaps.

### Blocked on Rick

| | |
| --- | --- |
| **Substack URL** | 4 posts end on `[link]`. Nothing can ship until that resolves to a real publication URL. If the Substack does not exist yet, creating it and setting the promise in the About page is task zero. |
| **The promise, confirmed** | Proposed: *one measurement from a real multi-agent system every week, with the query that produced it.* It appears as the sign-off in every LinkedIn post and should be the publication's tagline. Confirm or replace before L1 ships, because changing it later breaks the consistency that makes it work. |
| **Repo link** | No post currently links `github.com/RickZee/ai-team`. Decide whether the repo is public-facing for this series. If yes it belongs in S1 and in the L2 carousel's last slide; if no, remove the "reproducible from the repository" claims from the art, which currently promise it. |
| **Annotation pass** | S3 / L6 are gated on `evals/annotations/` holding ≥30 records with `unaided: true`. Currently 0. Week 3 does not exist until this is done. |

### Assets still to build

| Asset | For | Status |
| --- | --- | --- |
| [`eval-corpus-kinds`](../images/publication/eval-corpus-kinds.png) | S2 / L4 | **built** |
| [`carousels/l2-two-trees.pdf`](../images/publication/carousels/l2-two-trees.pdf) | L2 | **built** — 6 square slides, upload as a document post |
| [`carousels/l3-five-questions.pdf`](../images/publication/carousels/l3-five-questions.pdf) | L3 | **built** — 7 square slides, upload as a document post |
| [`eval-telemetry-writers`](../images/publication/eval-telemetry-writers.png) | L5 | **built** — replaces the planned crop; shows all three signals and who writes each |
| Frequency-table diagram | S3 / L6 | **cannot be built** — depends on the annotation pass |

All seven standalone diagrams are SVG + 2× PNG, C2PA stripped. Carousels ship as **PDF** —
that is what LinkedIn document posts accept; PNG slides are not a document post.

**Carousels are generated from a template, not hand-drawn**, by a small toolkit kept outside
this repo (`art-build`). To re-cut a deck, edit the slide copy there and rebuild — the PDFs
here are output. Contact sheets (`carousels/*-sheet.png`) let a whole deck be reviewed in one
look without opening the PDF.

### Copy status

| Piece | Copy | Length |
| --- | --- | --- |
| L1 | full draft | 1,738 chars — in band |
| L2 | carousel brief + body | 879 chars — correct for a carousel |
| S1 | [the essay](../posts/the-starved-harness.md) | ~2,500 words, sign-off in place |
| L3 | carousel brief + body | ~900 chars — correct for a carousel |
| S2 / L4 | **both written** — L4 in this doc, S2 at [`posts/fixture-only.md`](../posts/fixture-only.md) | ~1,600 words |
| L5 | full draft | 1,665 chars — in band |
| S3 / L6 | skeleton with bracketed placeholders | gated |

### Standing rules, applied per post

- **No hashtags.** 3–5 slightly reduce reach, 6+ clearly do.
- **Link in the post body**, never the first comment — personal profiles do not pay the link
  penalty and burying it only costs clicks.
- **Every LinkedIn post ends on the promise + link.** Same wording every time.
- **30 minutes after posting** goes to replying to comments. That is distribution, not manners.
- **Every rate carries its corpus kind and its `n`.** No exceptions, including in slide text.

## Art

Method-forward set: each piece is about a diagnostic other people can use, with this repo's
numbers as the worked example rather than the subject. Two tiers, following the repo's
existing convention (see [`docs/images/README.md`](../images/README.md)).

**Embedded in the essay — SVG in `docs/images/`, PNG export in `publication/`.** Same
pattern as `substack-harness-layers`.

| Diagram | Used in | What it shows |
| --- | --- | --- |
| [`eval-self-review-cadence`](../images/eval-self-review-cadence.svg) | S1 hero | Four self-audits across seven months and what each one caught |
| [`eval-two-trees`](../images/eval-two-trees.svg) | S1, and the L2 carousel | The writer/reader split, drawn so anyone can check for it in their own system |
| [`eval-infra-vs-evidence`](../images/eval-infra-vs-evidence.svg) | S1 | Seven stages all ship; the one input that makes them count cannot be built |

**Social cards — `publication/` and nowhere else.** Never embedded in a repo doc; they exist
to be uploaded.

| Card | Used in | What it shows |
| --- | --- | --- |
| [`eval-industry-gap.png`](../images/publication/eval-industry-gap.png) | L1 | Four survey percentages, and the question nobody asks |
| [`eval-audit-checklist.png`](../images/publication/eval-audit-checklist.png) | L3 carousel source | The five questions, as an instrument |
| [`eval-corpus-kinds.png`](../images/publication/eval-corpus-kinds.png) | S2 / L4 | `FIXTURE-ONLY` / `CORPUS` / `LIVE` — what each licenses you to claim |
| [`eval-telemetry-writers.png`](../images/publication/eval-telemetry-writers.png) | L5 | Three signals, and which one was left to a prompt |

**Carousels (PDF, square, LinkedIn document posts):**

| Deck | Used in | Slides |
| --- | --- | --- |
| [`l2-two-trees.pdf`](../images/publication/carousels/l2-two-trees.pdf) | L2 | 6 — the audit, the two trees, the default argument, why it hid, the question |
| [`l3-five-questions.pdf`](../images/publication/carousels/l3-five-questions.pdf) | L3 | 7 — cover, five questions, closer |

Upload the **PNG** in every case — LinkedIn and X both strip or refuse SVG. PNGs render at
2× (2400px wide) so they stay sharp on retina timelines. House style matches the existing
Substack assets — `#faf9f5` ground, `#1d9e75` accent, `#1a1a2e` ink.

**Retired, and why:** `eval-three-zeros`, `eval-seven-months`, `eval-built-vs-fed`. All three
had the same defect — their subject was the failure rather than the capability. Three red
zeros and a timeline of mistakes make a stranger conclude *this person's eval system didn't
work*, not *this person audits eval systems*.

## Assets

| Asset | Where |
| --- | --- |
| S1 essay | [`docs/posts/the-starved-harness.md`](../posts/the-starved-harness.md) |
| S2 essay | [`docs/posts/fixture-only.md`](../posts/fixture-only.md) |
| Showcase page | [`docs/showcase/starved-harness.html`](../showcase/starved-harness.html) |
| Raw audit (journal) | [`docs/journal/2026-09-13-eval-methodology-audit.md`](../journal/2026-09-13-eval-methodology-audit.md) |
| Seven-month narrative | [`docs/journal/journey.md`](../journal/journey.md) — Feb 15 and Sep 13 entries are the bookends |
| Remediation spec | [`.kiro/specs/eval-methodology-alignment/`](../../.kiro/specs/eval-methodology-alignment/) |
| Method sources | Husain & Shankar on Lenny's Podcast; Husain, *AI Evals FAQ* |
| First live case (unlabeled) | [`docs/eval-runs/2026-09-13-langgraph-smoke/`](../eval-runs/2026-09-13-langgraph-smoke/) |
| Industry figures | LangChain, *State of Agent Engineering* (n = 1,340) |

Credit the source material by name in the anchor essay and in L3. The post works
because it applies someone else's method honestly, not because it invents one.
