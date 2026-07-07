# UI/UX Improvement Plan — Phase 3: Information Architecture & Visual Coherence

Follows [Phase 1](UI_UX_IMPROVEMENT_PLAN.md) (correctness) and
[Phase 2](UI_UX_IMPROVEMENT_PLAN_PHASE2.md) (responsive layout), both implemented.
Phase 3 addresses what remains after those: the UI still **feels underdeveloped** —
not because features are missing, but because the same information appears in
multiple places with different values, panels contradict each other, screens are
organized around internal code structure rather than user workflows, and visual
alignment is inconsistent enough to read as unfinished.

All findings below verified live on 2026-07-06 (post-Phase-2 build, 1566px viewport,
with three active runs and several terminal runs in the sidebar).

## Who uses this UI (design against these, not against the component list)

The project is a **framework comparison platform** (README: "same team, three
orchestration backends, measured side by side") plus an autonomous-team demo. Three
workflows cover everything:

1. **Launch** — describe a project, pick backend(s), start, know it started.
2. **Monitor** — watch one or more live runs; intervene on HITL; trust the numbers.
3. **Review** — after completion: did it pass, what did it cost, what did it build,
   how do backends compare.

Today these are smeared across 4 nav tabs (Dashboard, Run, Compare, Artifacts) whose
boundaries reflect code modules, not the three workflows. Every Phase-3 task moves a
screen closer to one of those workflows.

Frontend root: `src/ai_team/ui/web/frontend/`.

---

## IA-1 Restructure navigation around workflows: 3 destinations, not 4 tabs

**Problem (observed live).** Reviewing a completed comparison requires: Compare tab →
per-column "Dashboard" button (leaves Compare) → Dashboard shows that run → back to
Compare (state may reattach or reset) → "Artifacts" button → Artifacts page with its
own separate run selector that defaults to some other run. The user re-selects the
same run in three different UIs. Meanwhile "Dashboard" is both the run-history
browser AND the run-detail view, overloading one route with two jobs.

**Fix.** Reorganize into three destinations:

- **Home** (`/`) — run browser: the run list (current sidebar, promoted to the main
  surface at this route), plus a prominent "New run" launcher entry point. No live
  monitor here; clicking a run navigates to it.
- **Run detail** (`/runs/:id`) — ONE page per run with internal tabs:
  **Overview** (stat strip, phase pipeline, summary card when terminal) ·
  **Activity** (log + agents + guardrails) · **Artifacts** (file tree + preview,
  today's Artifacts page scoped to this run) · **Tests** (test results panel).
  The Artifacts nav tab disappears; its page component is reused inside run detail.
  Comparison runs get a "part of comparison" chip linking to the comparison view.
- **Compare** (`/compare`) — launcher + live columns as today, but each column's
  footer links to `/runs/:id` (one place), not separate Dashboard/Artifacts buttons.

Keep old routes as redirects (`/artifacts?project=X` → `/runs/X#artifacts`).

**Acceptance criteria.**
- [x] Nav has exactly three entries: Home, Compare, and (contextually) the open run.
- [x] Reviewing a completed run — status, cost, files, tests — happens without
      leaving `/runs/:id`.
- [x] Artifacts browser no longer has its own run selector; it inherits run context.
- [x] `/artifacts?project=X` and old deep links redirect correctly (tests).
- [x] Run list is reachable in ≤1 click from anywhere (Home).

**Files.** `App.tsx` (routes), new `src/pages/RunDetail.tsx` (absorbs Dashboard's
detail half + Artifacts + Tests as tabs), `Dashboard.tsx` (becomes Home / run
browser), `Compare.tsx` (column footer links), redirect shims.

---

## IA-2 One fact, one place: kill every duplicated data display

**Problem (observed live).** On a single active-run screen, **elapsed and cost render
twice** (stat strip: "8m 32s · $0.0335"; Metrics panel: "Elapsed 8m 32s / Cost (USD)
$0.0335") and **the phase renders three times** (phase pipeline in sticky header,
"Development" text in the stat strip, highlighted "DEVELOPMENT" chip row inside
Agent Timeline). When these drift — and Phase-1/data-fix history shows they do —
the user cannot tell which one to trust. Duplication isn't reassuring; it's how the
"misaligned information" feeling is produced.

**Fix.**
- Stat strip is the **only** place for: status, phase (text), elapsed, cost, test
  pass/fail. Remove those five rows from `MetricsCard` — it keeps only the long
  tail (tasks, files, retries, guardrail counts, tokens).
- Agent Timeline drops its own phase-chip row (the sticky pipeline is 40px above
  it); it shows only agent lanes/activity. If there are no agent entries, show one
  `EmptyState` line, not a chip row + placeholder.
- Rename "AI-Team Dashboard" brand to "AI-Team" — "Dashboard" is also a nav tab
  label; brand + tab currently read as a duplicated word pair in the header.

**Acceptance criteria.**
- [x] grep-level audit documented in the PR: each of status/phase/elapsed/cost/tests
      renders from exactly one component on any given screen.
- [x] MetricsCard no longer contains elapsed or cost rows.
- [x] Agent Timeline contains no phase chips.
- [x] Existing tests updated; no test asserts the same value in two panels.

**Files.** `MetricsCard.tsx`, `AgentTimeline.tsx`, `RunStatStrip.tsx`,
`Dashboard.tsx`/`RunDetail.tsx`, `App.tsx` (brand).

---

## IA-3 Compare columns must never show two states at once

**Problem (observed live).** A reattached finished comparison renders each column
with body text **"Not started"** AND a footer reading **"Complete" + Dashboard +
Artifacts buttons** — simultaneously, in the same column. Two different state
sources (live socket state vs. reattach seed) each render their own fragment.
This is the single most credibility-damaging screen in the app: it visibly
contradicts itself.

**Fix.**
- Each column renders from **one** derived state object (the existing
  `getColumnState()` output), through one component with explicit variants:
  `idle | starting | live | awaiting_human | terminal(status)`. No fragment of the
  column may read a different source than the rest.
- Terminal variant: compact result card (status chip, elapsed, cost, tests, files —
  the per-column mini-summary) + one "Open run" link. Never the "Not started" or
  "Waiting for agents…" placeholders.
- Idle variant (genuinely not started): placeholder only, no footer.
- Delete the dead vertical whitespace between the column title and first content
  block (currently ~80px of nothing before "Not started").

**Acceptance criteria.**
- [x] Component test: terminal reattach seed → column shows result card, and
      querying "Not started"/"Waiting for agents" returns nothing.
- [x] Component test: idle column → no footer buttons rendered.
- [x] Visual: no column state combination can render contradictory status texts
      (enumerate variants in a single switch; exhaustive TS check).
- [x] Column title-to-content gap ≤ 16px.

**Files.** `CompareColumn.tsx` (single-variant render), `Compare.tsx` (pass one
state object), tests.

---

## V-1 Activity Log is unreadable: fix the layout, then the content

**Problem (observed live).** The log renders three columns (time / agent / message)
where the message column is squeezed to ~12 characters, so every entry wraps into a
vertical strip: `retry_de` / `→ phase` / `developm…`. A horizontal scrollbar sits at
the bottom of the panel. The one panel that tells the user *what is happening right
now* is the least readable thing on the screen.

**Fix.**
- Single-line entries: `13:25 · langgraph · testing → development (retry)` — time
  compact (no seconds unless expanded), agent as a small colored tag, message takes
  all remaining width with `text-overflow: ellipsis` + full text on hover/click.
- No fixed column widths; flexbox with message as `flex: 1; min-width: 0`.
- Translate raw internal messages at the display layer: `retry_development → phase
  development` renders as `retry → development`; `__interrupt__: (Interrupt(value=…`
  renders as `⏸ paused for human review`. Keep raw text in a tooltip/expanded view.
  (Mapping table, not free-form rewriting — new unknown messages pass through.)
- Auto-follow: newest entry visible while live, pause auto-scroll when the user
  scrolls up (standard log-tail behavior), "jump to latest" affordance.

**Acceptance criteria.**
- [x] No entry wraps below 1280px panel widths; no horizontal scrollbar in the log.
- [x] Interrupt and retry messages render human-readable; raw payload reachable.
- [x] Auto-scroll pauses on user scroll-up and resumes via "jump to latest".
- [x] Component test with 50 long entries: DOM height stable, entries single-line.

**Files.** `ActivityLog.tsx`, message-mapping util (new, unit-tested), `App.css`.

---

## V-2 Run-list cards: fix overlap, truncation, and density

**Problem (observed live).** Delete buttons float **on top of** card content,
clipped mid-word ("Dele"); titles truncate at ~25 chars ("Write calc.py with
add/subtract/multiply…") wasting the card's second line; every card spends a full
line on the date ("Jul 6, 2026, 01:17 PM") under a day-group header that already
says "TODAY"; identical descriptions produce six visually identical cards
distinguishable only by a tiny backend label.

**Fix.**
- Delete becomes a hover/focus-revealed icon button in the card's top-right corner,
  inside the card bounds, `aria-label` preserved. Never overlaps text.
- Card layout: line 1 = time only ("13:17") + status chip + backend tag, right-
  aligned delete icon on hover; line 2 = description, 2-line clamp
  (`-webkit-line-clamp: 2`), full text in `title`.
- Drop the redundant full date inside day groups (header already scopes the day).
- Comparison members: group visually — one comparison card that expands to its 3
  runs, or a shared left-border accent + "⚖ comparison" chip — so six near-identical
  cards stop reading as noise.

**Acceptance criteria.**
- [x] No absolutely-positioned element overlaps card text at any width ≥ 1024px.
- [x] Delete reachable by keyboard (focus reveals it), `aria-label` intact,
      existing `delete-run-{id}` test-ids preserved.
- [x] Cards inside a day group show time-of-day only.
- [x] Runs sharing a `comparison_id` are visually grouped or accented.
- [x] 300-run fixture: sidebar scroll remains smooth (respect Phase-2 cap).

**Files.** `RunList.tsx`, `App.css`.

---

## V-3 Empty panels must not occupy prime layout space

**Problem (observed live).** The Guardrails panel occupies a full grid column to say
"Guardrails hidden — click Show or wait for a failure"; the Agent Timeline spends a
tall panel on "Waiting for agents…"; a full-width **"Hide runs"** button bar spans
the entire viewport above the dashboard (the single widest element on the page is a
sidebar toggle). Empty chrome is why the UI reads "overcrowded yet empty".

**Fix.**
- Guardrails: render as a **status line** inside the stat strip area ("Guardrails:
  none yet" / "✓ 4 · ✗ 1") until there is at least one event; only then mount the
  panel. Remove the Show/Hide toggle entirely — presence of data decides.
- Agent Timeline: don't mount the panel until `agents` is non-empty; a one-line
  "No agent activity reported by this backend" note sits in the Activity tab
  header area instead. (CrewAI/LangGraph currently never populate agents — see
  [DATA_INTEGRITY_FIXES.md](DATA_INTEGRITY_FIXES.md); until that lands, this panel
  is empty 100% of the time for 2 of 3 backends.)
- Sidebar toggle: replace the full-width "Hide runs" bar with a chevron icon on the
  sidebar edge (standard drawer pattern, already half-implemented in Phase 2 R-3).
- General rule (add to the doc header of `App.css`): a panel earns grid space only
  when it has content; empty states are lines, not boxes.

**Acceptance criteria.**
- [x] Zero-event terminal or live run: no Guardrails box in the grid; status line
      present.
- [x] Backend reporting no agents: no Agent Timeline panel mounted.
- [x] Sidebar toggle is an edge chevron ≤ 40px wide; full-width bar removed.
- [x] With all panels empty (fresh demo run), the run detail page still looks
      composed: stat strip + pipeline + log, no empty boxes.

**Files.** `Dashboard.tsx`/`RunDetail.tsx`, `GuardrailsPanel.tsx`,
`AgentTimeline.tsx`, `App.css`.

---

## V-4 Dead deep links: error state, not infinite spinner

**Problem (observed live).** `/runs/<id>` for a run the server no longer tracks
shows "Loading run…" forever. No timeout, no error, no way out. (Hit today with a
morning run id after the server restarted.)

**Fix.** If `GET /api/runs/{id}` 404s or the run is absent from the list after
first load: render an `EmptyState` — "Run not found. It may have been deleted or
the server restarted." + "Back to runs" action. If the run exists on disk
(registry) but not in memory, say that instead and show the disk data (Phase 1
P0-2 machinery).

**Acceptance criteria.**
- [x] Unknown run id → error state within one fetch round-trip (no spinner > 3s).
- [x] Error state has a working "Back to runs" action.
- [x] Component test for the 404 path.

**Files.** `Dashboard.tsx`/`RunDetail.tsx`, `useApi.ts` (surface 404 distinctly).

---

## V-5 Alignment and rhythm pass: make it look designed

**Problem (observed live).** Panel headers mix ALL-CAPS ("AGENT TIMELINE", "METRICS")
with Title Case buttons ("Show table", "Expand full log"); buttons inside headers
have three different sizes; the stat strip, panel grid, and sticky header each use
different horizontal padding so left edges don't align vertically down the page;
chip styles differ between run list (small caps chips) and stat strip (larger
chips); link-styled buttons ("Play sample run") sit baseline-misaligned next to
filled buttons.

**Fix.**
- Define in `index.css` and apply everywhere: one panel-header style (size, weight,
  case, letter-spacing), one in-header button size (`btn-sm`), one chip component
  (size variants sm/md only), one baseline alignment rule for mixed
  button/link rows (`align-items: center`, consistent `line-height`).
- Align all top-level containers (sticky header content, stat strip, panel grid,
  page header) to the same left/right content edges — one `--content-inset` token.
- Buttons: exactly three variants exist after this pass (primary / secondary /
  quiet-link) with one size scale; delete any ad-hoc `style=` or per-page button
  CSS.

**Acceptance criteria.**
- [x] Screenshot the run-detail page: every panel's left edge, the stat strip, and
      the sticky header content share one vertical line (attach to PR).
- [x] One `<Chip>` (or one `.chip` class family) renders every status/backend/tag
      chip in the app; grep shows no remaining ad-hoc chip CSS.
- [x] All panel headers use the shared header class; no inline-styled buttons.

**Files.** `index.css`, `App.css`, sweep across components (mechanical).

---

## V-6 Compare launcher: collapse after launch

**Problem (observed live).** The launch form (profile, complexity, description,
three buttons, two helper lines) permanently occupies the top ~45% of the Compare
viewport — even mid-comparison and after completion, when the user's attention is
entirely on the columns. Results start below the fold at 1440×800.

**Fix.** After launch (or reattach), collapse the form to a one-line summary bar:
"⚖ smoke · Simple · 'Write a single Python module calc.py…' — Edit & rerun". Expand
on click. New-visit default: expanded. The columns become the page's first content
block during and after a comparison.

**Acceptance criteria.**
- [x] During a live comparison at 1440×800, all three column headers and their stat
      blocks are visible without scrolling.
- [x] Collapsed bar shows profile, complexity, truncated description; expands on
      click with state preserved.
- [x] Reattach (reload mid-run) lands in collapsed state.

**Files.** `Compare.tsx`, `RunConfigForm.tsx` (collapsible wrapper), `App.css`.

---

## Suggested order

1. **IA-3** (contradictory Compare columns) — worst credibility bug, small scope.
2. **V-1** (activity log readability) — highest-frequency surface, small scope.
3. **V-2** + **V-4** (run cards, dead links) — small, independent.
4. **IA-2** (dedup pass) — before IA-1 so the merged pages don't inherit duplicates.
5. **IA-1** (navigation restructure) — the big one; do after the components it
   rearranges are individually sane.
6. **V-3**, **V-6**, **V-5** — polish passes on the restructured layout.

## Out of scope for Phase 3

Data correctness (blank metrics, cost wiring, SDK registry) — tracked in
[DATA_INTEGRITY_FIXES.md](DATA_INTEGRITY_FIXES.md). Phase 3 tasks must not paper
over missing data with fake displays; where data is absent because of those bugs,
show honest empty states (V-3) until the fixes land.
