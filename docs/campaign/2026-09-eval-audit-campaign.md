# Campaign — the eval audit (Sept–Oct 2026)

**Anchor:** [`docs/posts/the-starved-harness.md`](../posts/the-starved-harness.md)
**Showcase page:** *The Starved Harness* (published artifact — paste URL below when live)
**Claim rules:** [`EVAL_GATE_STATUS.md`](./EVAL_GATE_STATUS.md) — read before editing any post.

---

## The angle

Not "look at my eval harness." Every AI-builder feed has one of those this quarter,
and mine has no results to show because it has no data.

The angle is **the audit finding**: a correctly-built eval system that had never
seen real data, the one-line root cause, and the fact that building measurement
infrastructure is the most comfortable way to avoid doing measurement. That is a
story almost nobody posts, because it costs something to post it, which is exactly
why it will travel.

Three reasons it works for ArqiSoft specifically:

1. **It is verifiable.** Every number is a query result or a file count. Nobody in
   this space is showing their empty annotations directory.
2. **It demonstrates the service.** Federal QA and test-lead work is precisely
   "your metric does not measure what you think it measures." This is that, on my
   own system, in public.
3. **It sets up a sequel.** The follow-up post — *what thirty traces read by hand
   actually found* — is the payoff, and it only lands because this one was honest.

## What may not be said

- No pass rate, accuracy figure, or quality claim of any kind. There is no
  `CORPUS` rate in existence.
- "$0 per-PR eval gate in CI" is true and publishable. "94% of evals pass" is not,
  in any phrasing, ever, until the corpus exists.
- Do not describe the taxonomy as validated, the judges as aligned, or the gate as
  hard. All three are false and all three are checkable by anyone who clones it.
- Every rate that does appear carries its `n` and its corpus kind.

---

## Sequence

| Day | Channel | Piece | Purpose |
| --- | --- | --- | --- |
| 1 (Mon) | LinkedIn | **L1 — three zeros** | The hook. Finding first, no preamble. |
| 1 (Mon) | X | **X1 — thread, the audit** | Same finding, dev audience, code blocks. |
| 3 (Wed) | LinkedIn | **L2 — the wrong directory** | Root cause + the generalizable lesson. |
| 5 (Fri) | X | **X2 — FM-016 vs FM-018** | Single post, the sharpest technical idea. |
| 8 (Mon) | Substack | **Anchor essay** | Full piece. Everything points here. |
| 8 (Mon) | LinkedIn | **L3 — the essay + the five-question audit** | Drives to anchor + showcase. |
| 10 (Wed) | X | **X3 — thread, run this audit yourself** | Utility. Most shareable of the set. |
| ~22 | LinkedIn | **L4 — what thirty traces found** | The payoff. **Only after Phase 1 + task 4.2 actually run.** |

Do not publish L4 until the annotations exist. A promised follow-up that never
arrives undoes the credibility the first three bought.

**Source material for L4 (not yet annotated):** the 2026-09-13 LangGraph
smoke — 1600 s, HITL, retry amplification after a successful write (last-12
AI relevance scorer, then `retry_development`), empty Home, starved journal.
Handoff and the debug loop we already describe:
[`docs/eval-runs/2026-09-13-langgraph-smoke/README.md`](../eval-runs/2026-09-13-langgraph-smoke/README.md).
Do not put FM ids in the annotation TUI; do not cite a pass rate from n=1.

---

## LinkedIn

### L1 — three zeros (day 1)

> I spent three weeks building an eval system for my multi-agent platform. About
> 13,000 lines: trace store, sampling strategies, an annotation tool, judge
> alignment with bootstrap confidence intervals, a $0 eval gate on every pull
> request.
>
> Last week I audited it against the methodology it was built from. Three numbers
> came back.
>
> 0 — spans across all 50 indexed traces. The trace store was full of shells.
>
> 0 — traces ever read and annotated by a human. The annotation tool works. The
> annotations directory is empty.
>
> 0 of 17 — failure modes derived from observation. Thirteen came from an essay I
> wrote from memory in July. Four came from published references. None came from
> reading a trace.
>
> Every stage of the loop downstream of "look at your data" was built, typed,
> unit-tested — and had never seen any data.
>
> The green check in my CI proves my check code behaves the way I wrote it. It has
> never once said anything about whether the agents work. My repo said so, in a
> README, under a heading I titled "honest." I wrote the disclosure and then let
> the numbers travel without it.
>
> Root cause in the next post. The harness had been logging the whole time. It was
> writing to one directory and reading from another.

*Notes: no link in L1. The finding carries it. Reply to your own comment thread
with the repo link after the first hour.*

### L2 — the wrong directory (day 3)

> My eval harness had been logging the whole time. It was writing to one directory
> and reading from another.
>
> workspace/<run_id>/ — where the agents' generated code lands. src/, tests/,
> nothing else. That is where my corpus builder was looking.
>
> output/runs/<run_id>/ — where the harness writes its own records. 211 dated run
> directories. 210 run.json files carrying backend, completion time and final
> status. 141 with real cost and token counts. 60 cost logs. 8 signed receipts.
> Three backends. A 69-day span.
>
> evals/cli.py:547 — backfill.add_argument("--workspace-root", default="./workspace")
>
> The corpus I audited as "one backend, 1.97 seconds" could have been three
> backends over 69 days, for $0.00, on the day that line was written.
>
> There is a second half, and it is the one I had actually feared. The file that
> records phase transitions — the trajectory every interesting check reasons over —
> has one code writer, added last week, and one line in a prompt asking the model
> to write it. Zero of those files exist anywhere.
>
> Most of my telemetry is written by code. Phase records are the one signal I left
> to an instruction, and they are the one every trajectory check depends on.
>
> Two questions worth asking your own system today. Does the thing that writes your
> traces agree with the thing that reads them about where traces live? And which of
> your signals are produced by code you own, versus asked for in a prompt?

### L3 — the essay (day 8)

> Full write-up of the audit is up: *The Starved Harness*.
>
> [anchor link]
>
> The part that transfers to anyone building on LLMs is a five-question audit that
> takes about ten minutes:
>
> 0. Is the thing that writes your traces pointed at the same directory as the thing
> that reads them? I would not have put this on the list a week ago. My harness had
> been logging for two months into a tree the corpus builder never opened.
>
> 1. How many real traces are in your eval set, and how diverse are they? Group by
> every dimension you have. If one value dominates a column, your n is a fiction.
> Mine was 50 traces — one backend, one scenario, one status, all created inside a
> 1.97-second window.
>
> 2. How many has a human actually read? Not scored — read, with notes.
>
> 3. Where did your failure categories come from? If you cannot point from a
> category to the specific traces that produced it, you are testing your
> imagination.
>
> 4. What does a green run actually assert? Say it out loud in one sentence. If the
> sentence is "my check code behaves as written," that is real and useful, it is
> not a quality claim, and you should stop letting it travel as one.
>
> The uncomfortable finding underneath all of it: building measurement
> infrastructure is the most comfortable way to avoid doing measurement. The people
> who teach this say they spend 60-80% of development time on error analysis and
> evaluation. I spent close to 100% of mine on evaluation infrastructure and 0% on
> error analysis. Those are different activities. The first is engineering, which I
> enjoy. The second is reading traces for four hours, which is boring and cannot be
> handed to a model without destroying what it produces.
>
> I built the tool that makes the boring thing efficient, then did not do the
> boring thing, and the tool was good enough that its existence felt like progress.

*Notes: the showcase page is the better link for a mobile audience — swap it in if
the essay is not up yet.*

### L4 — the payoff (day ~22, gated)

> Three weeks ago I posted that my eval system had never seen real data. I
> instrumented the runs and then read thirty traces by hand.
>
> [What the thirty traces actually showed — the categories, their counts, which of
> my seventeen imagined failure modes survived contact, and which ones I had never
> observed.]
>
> [How many of the 17 were confirmed / unobserved / refined. The new categories
> that had no FM at all.]
>
> Every figure here carries its n and its corpus kind, because that was the whole
> point of the exercise.

**Gate:** do not draft this until `evals/annotations/` has ≥30 records. Fill the
brackets from the real frequency table, with the `NON-REPRESENTATIVE` stamp if the
corpus still carries one.

---

## X

### X1 — thread, the audit (day 1)

**1/**
> I built an eval harness for my multi-agent system. 11.3k lines. Trace store,
> sampling, annotation TUI, judge alignment with bootstrap CIs, $0 gate in CI.
>
> Then I audited it against the methodology it was built from.
>
> Every downstream stage was built. None had ever seen data.

**2/**
> ```
> select count(*)              -> 50
> select sum(span_count)       -> 0
> select backend, count(*)     -> [('crewai', 50)]
> select scenario_id, count(*) -> [('unknown', 50)]
> select status, count(*)      -> [('failed', 50)]
> ```
> 50 traces. 0 spans between all 50. One backend. One status. One scenario id, and
> that id is "unknown".

**3/**
> All 50 created inside a 1.97-second window on one afternoon in August.
>
> That is not a corpus. That is n=1 wearing n=50's clothes.

**4/**
> ```
> $ ls -A evals/annotations/
> $
> ```
> Zero traces open-coded by a human. The annotation tool is built, typed, tested.
> Nobody ever used it.

**5/**
> Which means my 17-mode failure taxonomy came from an essay I wrote from memory in
> July.
>
> 13 from that essay. 4 from published references. 0 from reading a trace.
>
> Every deterministic check in the harness is bound to one of those 17.

**6/**
> Then I found where the records actually were.
> ```
> $ ls output/runs | grep -c '^20'             -> 211
> $ find output/runs -name run.json | wc -l    -> 210
> $ find output/runs -name state.json | wc -l  -> 141
> ```
> Backend, status, cost, tokens, duration. Three backends. A 69-day span.

**7/**
> ```
> evals/cli.py:547
>   backfill.add_argument("--workspace-root", default="./workspace")
> ```
> workspace/ is where the agents' generated code lands.
> output/runs/ is where the harness writes its records.
>
> I was reading the first one.

**8/**
> The corpus I'd just audited as "one backend, 1.97 seconds" could have been three
> backends over 69 days. For $0.00. On the day that line was written.

**9/**
> Second half, and this one I'd actually feared: phases.jsonl — the trajectory every
> interesting check reasons over — has one code writer (added last week) and one line
> in a prompt asking the model to produce it.
>
> Zero exist. Anywhere. In 440 runs.

**10/**
> Being precise, because the general claim would be wrong: most of my telemetry IS
> written by code. audit.jsonl has a writer. costs.jsonl has two, and 60 files exist.
>
> Phase records are the one signal I left to an instruction, and the one every
> trajectory check needs.

**11/**
> So the honest version isn't "haven't done error analysis yet."
>
> It's: I pointed the measurement at the wrong directory and built two more specs on
> the empty result.

**12/**
> The fix is a spec, not a patch. Corpus reads the run-record tree. Phase telemetry
> moves into the harness. Unreadable runs stop being recorded as failed ones. Every
> failure mode records where it came from. Three refusals with no override flag.
>
> Write-up + the queries: [link]

### X2 — single post (day 5)

> I had a failure mode for an agent that grades its own work.
>
> I did not have one for an agent that *reports* its own work.
>
> The second is worse. A self-graded verdict is visibly wrong and you can argue
> with it. Self-reported telemetry produces a clean-looking dataset, and nothing
> downstream has any way to know.

### X3 — thread, run this yourself (day 10)

**1/**
> Ten-minute audit for anyone with an eval setup. Five questions. I failed all five
> on a system I was proud of.

**2/**
> 0. Is the thing that writes your traces pointed at the same directory as the thing
> that reads them?
>
> I would not have put this on the list a week ago. It is first now.

**3/**
> 1. How many real traces, and how diverse?
>
> Group by every dimension you have. If one value dominates a column, your n is
> fiction. I had 50 rows and an effective n of about 1.

**4/**
> 2. How many has a human actually read?
>
> Not scored. Read, with notes. Mine: zero.

**5/**
> 3. Where did your failure categories come from?
>
> If you can't point from a category to the specific traces that produced it,
> you're testing your imagination. 0 of my 17 traced to a trace.

**6/**
> 4. What does a green run actually assert?
>
> Say it in one sentence. If it's "my check code behaves as written" — that's real,
> it's useful, and it is not a quality claim. Stop letting it travel as one.

**7/**
> The thing underneath all of them: building measurement infrastructure is the most
> comfortable way to avoid doing measurement.
>
> Engineering the tool feels like progress. Reading traces for four hours doesn't.
> Only one of them tells you what's broken.

**8/**
> Full audit, with the queries and file counts: [link]

---

## Assets

| Asset | Where |
| --- | --- |
| Anchor essay | [`docs/posts/the-starved-harness.md`](../posts/the-starved-harness.md) |
| Showcase page | published artifact — *The Starved Harness* |
| Raw audit (journal) | [`docs/journal/2026-09-13-eval-methodology-audit.md`](../journal/2026-09-13-eval-methodology-audit.md) |
| Remediation spec | [`.kiro/specs/eval-methodology-alignment/`](../../.kiro/specs/eval-methodology-alignment/) |
| Method sources | Husain & Shankar on Lenny's Podcast; Husain, *AI Evals FAQ* |
| First live case (unlabeled) | [`docs/eval-runs/2026-09-13-langgraph-smoke/`](../eval-runs/2026-09-13-langgraph-smoke/) |

Credit the source material by name in the anchor essay and in L3. The post works
because it applies someone else's method honestly, not because it invents one.
