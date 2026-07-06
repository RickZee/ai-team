# UI/UX Improvement Plan — Phase 2: Usability & Responsive Layout

Follows [UI_UX_IMPROVEMENT_PLAN.md](UI_UX_IMPROVEMENT_PLAN.md) (Phase 1: correctness
bugs). Phase 2 theme: **simple UX with every needed element visible, and content
that adapts to the window size**. The Compare tab currently does not fit the
viewport at common widths — that is the anchor complaint; fix the system, not just
the symptom.

Frontend root: `src/ai_team/ui/web/frontend/`. All layout rules live in
`src/App.css` / `src/index.css` today.

Target widths (acceptance baseline for every task):

| Tier | Width | Expectation |
|---|---|---|
| Laptop | 1280px | Everything usable, no horizontal page scroll |
| Desktop | 1440–1920px | Content scales up, no dead whitespace columns |
| Narrow | 1024px | Usable; panels may stack |
| Tablet | 768px | Degrades gracefully; read-only monitoring acceptable |

---

## R-1 Layout tokens and breakpoints (foundation)

**Problem.** No shared breakpoints or spacing scale; each page hardcodes its own
grid. That is why Compare overflows while Dashboard doesn't — no common system.

**Fix.**
- Define CSS custom properties in `index.css`: spacing scale (`--space-1..6`),
  content max-width, and breakpoints as documented constants
  (`1024 / 1280 / 1440`).
- Replace per-page fixed grids with shared utility classes:
  `.grid-2`, `.grid-3` built on `repeat(auto-fit, minmax(<min>, 1fr))` with
  `minmax(0, 1fr)` semantics so children can shrink (the current overflow root
  cause: grid children default to `min-width: auto` and refuse to shrink below
  their table content).
- Every panel gets `min-width: 0` and internal `overflow-x: auto` so wide tables
  scroll inside the panel instead of blowing out the page.

**Acceptance criteria.**
- [ ] No page produces a horizontal scrollbar on `<body>` at 1024–1920px.
- [ ] Grid utilities used by Dashboard, Compare, Artifacts (grep: no page-local
      `grid-template-columns` with fixed px for content grids).
- [ ] A deliberately wide table inside any panel scrolls within the panel.

**Files.** `src/index.css`, `src/App.css`, touched pages.

---

## R-2 Compare tab fits the window (the reported bug)

**Problem.** 3 fixed columns overflow at 1400px; third column clipped with no
scroll affordance. Summary table repeats the same width bomb below.

**Fix.**
- Columns: `repeat(auto-fit, minmax(320px, 1fr))` → 3-up on wide screens, 2-up at
  ~1280px, 1-up below ~1024px, without media-query sprawl.
- Column order when stacked: keep BACKENDS order; each column keeps its own
  status header so vertical scanning works.
- Comparison Summary table: sticky first column (`position: sticky; left: 0`),
  panel-internal horizontal scroll, and a column-count-aware compact mode
  (numbers only, tooltips for detail) below 1280px.
- Metric labels never wrap mid-word; long backend titles truncate with tooltip.

**Acceptance criteria.**
- [ ] 1280px: all three columns fully visible OR 2+1 stacked — zero clipped
      content either way.
- [ ] 1024px: stacked single/double column; summary table scrolls inside its
      panel with sticky metric-name column.
- [ ] 1920px: columns widen to fill; no fourth phantom column, no giant gaps.
- [ ] Playwright/vitest DOM check at 3 widths asserting
      `document.body.scrollWidth <= window.innerWidth`.

**Files.** `src/pages/Compare.tsx`, `src/components/CompareColumn.tsx`,
`src/App.css`.

---

## R-3 Dashboard adapts: sidebar and panel grid

**Problem.** Fixed sidebar + 2-col panel grid wastes space at 1920px and cramps at
1024px. Activity Log and Guardrails compete for the same row; metrics panel is
tall-narrow with dead space.

**Fix.**
- Sidebar: collapsible (chevron toggle, state in localStorage); auto-collapsed
  below 1100px with an overlay drawer.
- Panel grid: `auto-fit` columns so 1920px gets 3-up (Timeline | Metrics | Log),
  1280px 2-up, 1024px 1-up. Guardrails panel spans full width when it has failure
  rows, stays compact when green.
- Sticky header (phase pipeline + status chips) already exists — verify it
  survives stacking without covering content (`scroll-margin-top` on panels).

**Acceptance criteria.**
- [ ] Sidebar collapse toggle works, persists across reload, auto-collapses
      below 1100px.
- [ ] No layout tier shows a panel narrower than 280px or an empty grid cell.
- [ ] Sticky header never overlaps panel headings at any tier.

**Files.** `src/pages/Dashboard.tsx`, `src/App.css`.

---

## U-1 One obvious primary action per screen

**Problem.** Empty Dashboard shows two competing buttons (sample run vs Go to Run);
Run page shows three same-weight actions (Run / Estimate Cost / Play sample); user
must already know the product to pick. "Simple UX" = one primary, rest secondary.

**Fix.**
- Visual hierarchy: exactly one `btn-primary` per screen state. Estimate and
  sample-run become quiet/secondary (text-button or outline).
- Empty Dashboard: primary = "Start a run" (routes to Run); sample run demoted to
  a link-style button beneath ("or watch a free sample").
- Run page: primary = Run. Estimate result inline near the button, not a separate
  page-level panel jump.

**Acceptance criteria.**
- [ ] Audit: each route/state renders exactly one primary-styled button.
- [ ] Existing test-ids preserved (`run-submit`, `dashboard-demo`, …).

**Files.** `src/pages/Dashboard.tsx`, `src/pages/Run.tsx`, `src/pages/Compare.tsx`,
`src/App.css`.

---

## U-2 All needed run info visible without scrolling (above the fold)

**Problem.** For an active run at 1280×800 the user should see: phase, status,
elapsed, cost, and latest activity — without scrolling. Today cost/tokens sit deep
in the Metrics panel and the latest log lines can be below the fold.

**Fix.**
- Promote a compact stat strip into the sticky header: status chip · phase ·
  elapsed · cost · tests (pass/fail). Single line, small.
- Activity Log defaults to "last 5 lines" compact mode with expand; full log on
  demand (flip today's default: currently full-log-first).
- Metrics panel keeps the long tail (retries, guardrail counts, tokens).

**Acceptance criteria.**
- [ ] 1280×800, active run: status, phase, elapsed, cost, and ≥3 latest log lines
      visible with zero scroll.
- [ ] Stat strip values match Metrics panel values (single source, no drift).
- [ ] Log expand/collapse state survives WebSocket updates (no jump-to-top).

**Files.** `src/pages/Dashboard.tsx`, `src/components/MetricsCard.tsx`,
`src/components/ActivityLog.tsx`, `src/App.css`.

---

## U-3 Shared run-config form (Run and Compare drift)

**Problem.** Run and Compare duplicate the same form (profile, complexity,
description, estimate) with drifted details — Run has backend select + key hints,
Compare lacks them; helper copy differs; future fields will fork further. Two
places to fix every P2-1 item from Phase 1.

**Fix.** Extract `<RunConfigForm>` component: fields, validation ("description
required" inline reason), estimate trigger + inline result, submit slot for
page-specific buttons. Run passes backend selector; Compare passes none.

**Acceptance criteria.**
- [ ] Both pages render the shared component; no duplicated field markup left.
- [ ] Phase-1 P2-1 helper texts appear on both pages automatically.
- [ ] Existing test-ids unchanged; both pages' tests green.

**Files.** new `src/components/RunConfigForm.tsx`, `src/pages/Run.tsx`,
`src/pages/Compare.tsx`.

---

## U-4 Empty states always say what to do next

**Problem.** Empty states are dead ends or misleading: "No runs yet" (no action),
"No matching runs" (no clear-filters shortcut), "No files yet for this run"
(Phase 1 P0-5 covers correctness; copy pattern still ad-hoc), "No guardrail checks
yet" on terminal runs.

**Fix.** One `<EmptyState icon title hint action>` component. Every empty state
gets: what happened, why (if known), one action. Examples:
- Runs sidebar: "No runs yet" + button "Start a run".
- Filtered list: "No runs match" + "Clear filters".
- Terminal run, no guardrail events: "No guardrail events recorded for this run"
  (past tense — no "yet").

**Acceptance criteria.**
- [ ] All empty states rendered via the shared component (grep for ad-hoc
      `className="dim"` empty paragraphs in pages/components → none for empty
      states).
- [ ] Every empty state has either an action button or past-tense copy for
      terminal contexts.

**Files.** new `src/components/EmptyState.tsx`, all pages/components with empty
branches.

---

## U-5 Artifacts browser layout at width

**Problem.** Fixed narrow file tree + wide preview wastes the tree at 1920px and
starves it at 1024px; header selector row (Run + Root) overflows awkwardly narrow.

**Fix.**
- Tree/preview split: draggable or `clamp(220px, 20vw, 360px)` tree column,
  `min-width: 0` preview with internal scroll.
- Header controls wrap as a flex row; selector width caps with ellipsis + tooltip
  (pairs with Phase 1 P1-5 label cleanup).

**Acceptance criteria.**
- [ ] 1024px: tree and preview both usable, header controls wrap without overlap.
- [ ] 1920px: preview does not exceed readable width (~100ch) or tree does not
      stretch beyond its clamp.

**Files.** `src/pages/Artifacts.tsx`, `src/App.css`.

---

## Suggested order

1. **R-1** foundation (tokens, grid utilities, `min-width: 0` sweep) — everything
   else builds on it.
2. **R-2** Compare fit (the reported bug) — first visible payoff.
3. **R-3** Dashboard grid + sidebar.
4. **U-3** shared form (do before U-1 so hierarchy lands once, in one component).
5. **U-1**, **U-2**, **U-4**, **U-5**.

Phase-1 dependency: R-2 supersedes Phase 1 **P1-3** (fold it in here); U-4
complements **P0-5** copy fix.
