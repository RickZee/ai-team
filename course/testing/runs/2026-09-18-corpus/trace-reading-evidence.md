# Thirty runs — mechanical evidence

**Provenance: assistant-generated. This is NOT the week 4 open-coding pass.**
Nothing here is written to `evals/annotations/` and nothing carries `unaided: true`, so
none of it counts toward G3. It is a sorted, counted view of what is in the thirty traces,
produced so the human reading starts from evidence instead of a blank workbench. The
*naming* — what each failure is called, which layer it belongs to — is deliberately left
undone. Every "pattern" below is a candidate to confirm or reject, not a category.

Bundle: `course/.work/bundle.json` (sample `stratified-1-114c4ff46a57`, 30 traces).
Reproduce: `python3 /tmp/read30.py` — parses each trace's spans into tool counts, repeated
write targets, idle gaps ≥60 s, result codes and QA verdicts.

## The corpus

27 of 30 traces carry tool activity (three are pre-fix cost-only traces from July / 13 Sept).

| | n | median tool calls | median wall | median idle |
| --- | --- | --- | --- | --- |
| killed (30-min watchdog) | 6 | 93 | 29 min | 12 min |
| failed | 2 | 30 | 21 min | — |
| complete | 19 | 24 | 11 min | — |

**Killed runs do roughly four times the tool work of completed ones and produce nothing.**
Whatever ends a run, it is not that the agents stop acting.

## Mechanical findings

**1. Forty-four percent of wall-clock is silence.** 10,357 s of 23,450 s sits in gaps of
≥60 s with no tool call at all. The extreme: a `failed` run with **11 tool calls and 1,261 s
of its 1,291 s idle**, and a `killed` run with 33 calls and 1,199 s idle. Two of the six
killed runs spent more time waiting than acting.

**2. The same file, over and over.** Single runs write or read `test_calc.py` 8, 13, 17, 23
and 29 times. The 29× case is a `failed` run whose dominant tool is `read_file` — it re-read
one file twenty-nine times and finished nothing.

**3. Agents invent files the brief forbids.** The brief says *"Output calc.py and
test_calc.py only."* Thirteen runs produced `test_calc_edge_cases.py` (5),
`test_calc_properties.py` (4), `test_calc_extended.py` (3), `test_calc_comprehensive.py` (1).
One killed run wrote `test_calc_properties.py` 23 times.

**4. Writes that go nowhere.** Across the corpus: 28 `validation_failed` and 14 `gated`
results. The worst killed run logged 122 `drafted` writes against 22 commits — it staged
five times more than the harness ever saved.

**5. The QA verdict ledger cannot say yes.**

```
verdicts across 17 runs:  {'reject': 135}
reasons:                  [('not verified at finalize', 135)]
accepts:                  0
```

Not "mostly rejects". **Zero accepts, corpus-wide**, including runs that completed with
passing tests. A completed run from 18 Sept has 8 acceptance criteria and 0 marked passing.

The mechanism is in `src/ai_team/harness/qa_verdicts.py:108`:
`emit_verdicts_from_acceptance` reads `ACCEPTANCE.json` and emits `accept` if `item.passes`
else `reject` with "not verified at finalize". And `passes` transitions false→true through
exactly one path — `acceptance_mark_passing`, exposed as an MCP tool **only on the Claude
Agent SDK backend** (`backends/claude_agent_sdk_backend/tools/mcp_server.py:242`). A
LangGraph or CrewAI agent has no way to mark an item verified. So the ledger stays empty,
and at finalize every criterion becomes a rejection.

This is a defect, not a reading. It is the third verification surface in this repo that can
structurally produce only one answer:

| | could only say | found |
| --- | --- | --- |
| Tier A deterministic-check gate | "pass" | 2026-09-18 (R12) |
| Trace reader | "this run recorded a cost" | 2026-09-19 |
| Acceptance / QA ledger | "reject" | 2026-09-21, here |

## Candidate patterns — yours to name or throw out

Written as observations, not categories, because the categories are the part you do.

- **Runs die busy, not stuck.** Killed runs average 93 tool calls. Something keeps them
  working past the point of usefulness rather than halting.
- **Re-reading substitutes for progress.** In the worst runs, `read_file` overtakes
  `write_file` as the dominant tool. Is re-reading a symptom of lost state, or of a model
  with nothing else to do?
- **The brief's scope is not enforced anywhere.** "Only these two files" is in the prompt and
  in nothing else. Thirteen runs exceeded it and no gate objected.
- **Draft/commit asymmetry.** Staging is cheap and frequent; commits are rare and phase-gated.
  Does the agent know how little of its work is landing?
- **Silence is unattributed.** 44% idle, and no span says why. There is no `phase_start` in
  this corpus at all, so a gap could be model latency, a retry, or a guardrail deliberating —
  the telemetry cannot distinguish them.

## What is still yours

Open the six killed runs first — they are the densest, 67–331 spans. For each: what were the
agents trying to do when it went sideways, what actually happened in your words, and which
layer you think it is (model / framework / harness / provider). Disagree with everything
above where it deserves it; the value of the pass is that the names are yours.

Thirty of those, written into the workbench, is G3.
