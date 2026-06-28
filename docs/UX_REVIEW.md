# AI-Team Web UI — UX Review & Recommendations

**Reviewer role:** Lead UX + AI product SME
**Scope:** The FastAPI + React observability console — Dashboard, Run, Compare,
Artifacts, global nav, and command palette.
**Method:** Source review of `src/ai_team/ui/web/frontend/src` (pages + components).
A live screenshot pass is recommended as a follow-up to confirm rendered states.
**Date:** 2026-06-28

---

## Executive summary

The console is in good shape: four clear modes, a sensible operational/analytical
split, a calm-by-default live dashboard (collapsible guardrails, sticky phase header),
a cost pre-flight on Compare, and a command palette. The design system is coherent
(one GitHub-dark theme across pages).

The biggest opportunities are not visual polish — they're **trust, legibility of
agent activity, and reducing dead-ends**. For an *agentic* product, the UI's core job
is to make an autonomous, sometimes-slow, sometimes-failing process feel legible and
controllable. A few specific gaps work against that today.

**Top 5, in priority order:**

1. **No way to stop or cancel a running run** from the UI — the single biggest trust gap.
2. **First-run / empty states under-explain** what's about to happen and what it costs.
3. **Agent activity is a flat table** — hard to see *why* the system is doing something.
4. **The "Demo" button is ambiguous** and easily mistaken for running your real brief.
5. **Command palette is keyboard-incomplete** (no arrow-key selection; estimate command never wired).

---

## What's working well (keep these)

- **Mode separation** maps to real intent: Dashboard = monitor, Run = launch,
  Compare = analyze, Artifacts = drill down. Clear and conventional.
- **Calm live view:** guardrails collapse during a live run and auto-expand on a
  failure (`Dashboard.tsx` `showGuardrails` effect). This is exactly the right
  progressive-disclosure instinct.
- **Sticky phase header** keeps orientation as the log scrolls.
- **Cost honesty:** Compare's pre-flight modal (`ConfirmModal`) and the per-backend
  estimate (`runMultiplier={3}`) set expectations before spending. The budget-exceeded
  warning on Run is a good nudge.
- **Adaptive polling** (`POLL_ACTIVE_MS` vs `POLL_IDLE_MS`, pauses when
  `document.hidden`) is a thoughtful performance + cost detail.
- **Empty/edge states exist** for demo-has-no-files and no-files-yet in Artifacts —
  better than a blank panel.

---

## Prioritized findings

### P0 — Trust & control

**1. No cancel/stop control for an in-flight run.**
`Dashboard.tsx` renders live state but offers no way to abort. Runs can be long and
cost money; a user who pasted the wrong brief or chose the wrong backend has no exit
except waiting or killing the server.
*Recommendation:* add a **Stop run** action in the sticky header (with confirm) wired
to a `POST /api/runs/{id}/cancel`. If the backend can't truly cancel mid-phase,
surface "Cancel requested — will stop after current phase" so the state is honest.

**2. Cost is shown but never reconciled.**
Run shows an *estimate*; the live header shows `cost_usd` when reported; the summary
shows a final number. There's no moment that says "estimated $X, actual $Y."
*Recommendation:* on the Run summary card, show **estimated vs actual** side by side.
This is the single most trust-building thing you can add for a paid agentic tool.

**3. Error states are terminal dead-ends.**
On `status === "error"`, Run shows `errorMessage ?? "Run failed"` and Dashboard shows
an alert, but there's no **"Retry"** or **"Open in Run with this brief prefilled."**
*Recommendation:* every failure should offer one obvious next action (retry same
config, or edit-and-rerun). Carry the brief/profile/backend forward.

### P1 — Legibility of agent activity

**4. Agent activity is a flat table; intent is invisible.**
`AgentTable` + `ActivityLog` tell you *what* each agent is doing but not *why* or *how
the handoff flows*. For a multi-agent system this is the headline feature and it reads
like a process list.
*Recommendation:* add a lightweight **agent timeline / handoff view** — who started,
who they handed to, current owner — even a simple horizontal swimlane keyed to phases.
This is the differentiator a multi-backend agent platform should show off.

**5. The Activity Log has no filtering or severity affordance.**
`ActivityLog` renders entries with an `ariaLive` region (good for a11y) but the
Dashboard only offers Collapse/Expand. WEB_DASHBOARD.md mentions "log filters" as a
power-user feature, but the page exposes none.
*Recommendation:* add level filters (info/warn/error) and a text filter; default to
hiding debug noise. This also directly improves screenshot cleanliness.

**6. "Awaiting human" is reachable but not attention-grabbing enough.**
HITL is handled (`HumanReviewPanel`, `awaiting_human` status), but on a busy dashboard
a paused run can be missed. Compare shows a banner; the single Dashboard relies on the
panel appearing inline.
*Recommendation:* when a run is `awaiting_human`, pin a high-contrast banner at the top
of the Dashboard (and title-bar/tab indicator), since the user is now the bottleneck.

**15. Artifacts are anonymous — there's no per-agent provenance.**
The Artifacts browser shows the final file tree (`workspace`/`bundle`) as one
undifferentiated blob. For a product whose whole pitch is a *team* of specialized
agents, the UI never answers the obvious question: *which agent produced what?* The
Architect's requirements/architecture docs, the Developers' source, QA's tests, and
DevOps' Dockerfile/CI all land in the same tree with no attribution. This buries the
single most compelling proof that the multi-agent system actually divided the work.
*Current state:* `monitor.on_file_generated(path)` records only a path — no producing
agent. But the workspace layout already encodes authorship implicitly (`CLAUDE.md`):
`docs/` (Product Owner + Architect), `src/` (Developers), `tests/` (QA),
Dockerfile/CI (DevOps), and `logs/phases.jsonl` + `audit.jsonl` (who acted, when).
*Recommendation:* add a **"By agent" grouping** to the Artifacts tab so files cluster
under their producing role with each agent's icon and a one-line summary of its
contribution. Ship it now with a folder/phase→role **heuristic**, then follow up by
threading true attribution through `on_file_generated` + the monitor/logs across all
three backends. This turns a flat file dump into a visible hand-off story.

### P1 — Onboarding & clarity

**7. The "Demo" button is ambiguous and overloaded.**
It appears on Dashboard, Run, and the command palette, and always plays the same fixed
"Flask REST API" simulation (mock model names, no files written). Users naturally read
"Demo" as "run my brief as a trial." Artifacts then correctly explains demo runs have
no files — but only *after* the confusion.
*Recommendation:* relabel to **"Play sample run (free, no files)"** with a one-line
helper, and visually separate it from the primary **Run** action. Consider a small
"Sample" tag on the resulting run in the sidebar so it's never mistaken for a real run.

**8. First-run empty state under-sells and under-explains.**
The Dashboard empty state ("No Active Run… Launch a zero-cost demo or start a real
run") is functional but doesn't explain what the product *does*, what a run costs, or
which backend to pick.
*Recommendation:* turn the empty state into a 3-step "How it works" (Describe → Watch
agents build → Browse artifacts) with the sample-run CTA. This is also the best place
to disambiguate the three backends/keys.

**9. Backend choice carries hidden prerequisites.**
The Run dropdown lists CrewAI / LangGraph / Claude Agent SDK with a "(streaming)" hint,
but not the key each requires. A user with only `OPENROUTER_API_KEY` can pick Claude
Agent SDK and fail at runtime.
*Recommendation:* show the required key/runtime inline (e.g. a small "needs
ANTHROPIC_API_KEY" note), and ideally gate/disable options the server reports as
unconfigured via the catalog endpoint.

### P2 — Interaction & polish

**10. Command palette is keyboard-incomplete.**
`CommandPalette` filters by typed text and requires a **mouse click** to run a
command — there's no ↑/↓ selection or Enter-to-run, which is the whole point of a
palette. Also, it's mounted in `AppShell` without `onEstimate`, so the "Estimate cost"
command is **never available**.
*Recommendation:* add arrow-key navigation + Enter, highlight the active item, and wire
`onEstimate` (or drop that command). Group headers currently repeat per item; render
them once per group.

**11. Run-history sidebar will not scale.**
The sidebar lists *all* runs with no search, grouping, or status filter. After a few
sessions it becomes the junk wall called out in the screenshot guide.
*Recommendation:* add a status filter + search, group by day, and visually mark
sample/demo runs. Consider a "clear/hide" affordance for old runs.

**12. Long briefs are cramped.**
Run/Compare use a 3-row textarea for the project description; the real briefs in these
demos are multi-sentence. Sidebar truncates to 40 chars and relies on `title` tooltips.
*Recommendation:* auto-grow the textarea (or make it resizable) and show the full brief
on the active run's meta card (it's already there for the active run — good — extend
the affordance to hover/expand in the list).

**13. Compare summary is dense and unlabeled for direction.**
The summary table highlights the best cell per metric (`summary-best`) — nice — but a
reader doesn't know *why* a cell is "best" (lower cost vs higher tests). The
`prefer: min/max` intent lives only in code.
*Recommendation:* add a small ▲/▼ glyph or "(lower is better)" caption per row so the
highlight is self-explanatory in a screenshot.

**14. Accessibility is partway there.**
Good: `aria-live` on the log, `role="dialog"`/`aria-modal` on the palette, labeled
nav. Gaps: status is conveyed largely by color (`status-chip status-*`); the phase
pipeline likely relies on color/position; focus management isn't obviously restored
when modals close.
*Recommendation:* pair color with text/icon on every status, ensure visible focus
rings, trap focus in modals and restore on close, and verify contrast for the dim/grey
text used heavily across panels.

---

## AI-product-specific recommendations

These go beyond generic UX and lean into what an *agentic* console should do:

- **Make the "why" first-class.** Users trust autonomous systems when they can see
  reasoning/decisions. Surface each agent's current goal and key decisions (architecture
  choices, why a retry happened) — not just "running."
- **Treat retries and guardrail warns as features, not noise.** A visible "self-corrected
  here" moment (the demo's `test_create_item_validation` retry is a perfect example)
  builds confidence. Annotate retries on the timeline rather than burying them in the log.
- **Always show the budget contract.** Estimate → live spend → final, with a visible
  ceiling. Agentic tools live or die on cost predictability.
- **Give every dead-end a next step.** Failed run → retry; empty artifacts → start a real
  run (already done — extend everywhere); HITL → clear, single decision.
- **Comparison is your moat — narrate the verdict.** Compare highlights best-per-metric;
  add a one-line auto-summary ("LangGraph: lowest cost; Claude Agent SDK: most tests
  passed") so the table tells a story at a glance.
- **Show the division of labor.** Per-agent artifact provenance (finding 15) is the
  clearest evidence that a *team* — not one model — did the work. Pair the live agent
  timeline (finding 4) with a "By agent" artifact grouping so the story is consistent
  from "who's working" to "what they produced."

---

## Suggested roadmap

| Phase | Items | Outcome |
|-------|-------|---------|
| **Now (P0)** | 1 Stop/cancel · 2 Estimate-vs-actual · 3 Retry from failure | Users feel in control of cost and runs |
| **Next (P1)** | 4 Agent timeline · 5 Log filters · 6 HITL banner · 15 Per-agent artifacts (heuristic) · 7 Demo relabel · 8 Onboarding empty state · 9 Backend prereqs | The agentic story is legible; fewer wrong turns |
| **Later** | 15b True file attribution (backend) | Provenance is accurate, not heuristic |
| **Polish (P2)** | 10 Palette keyboard · 11 Sidebar scale · 12 Brief affordances · 13 Compare direction glyphs · 14 A11y pass | A console that scales and screenshots clean |

---

## Notes for a live follow-up pass

A source review can't confirm rendered spacing, contrast, motion, or real data density.
When the app is running (`ai-team-web` + `npm run dev`), capture: Dashboard live + summary,
Run with an estimate, Compare with the 3-column grid + summary, Artifacts files/tests/
architecture, and the command palette — then re-check findings 13–14 against pixels.
See [../demos/SCREENSHOTS.md](../demos/SCREENSHOTS.md) for the clean-capture procedure.
