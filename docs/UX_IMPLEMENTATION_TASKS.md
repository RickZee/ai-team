# UX Implementation Task List (for Claude Code)

Implementation backlog derived from [UX_REVIEW.md](UX_REVIEW.md). Each task is
self-contained: scope, files to touch, implementation notes, and **acceptance
criteria** that must all pass before the task is "done."

**Conventions (from `CLAUDE.md` and the repo):**
- Frontend: React + TypeScript under `src/ai_team/ui/web/frontend/src`. Tests are
  vitest/RTL in `__tests__` dirs; use existing `data-testid` patterns.
- Backend: FastAPI in `src/ai_team/ui/web/server.py`; in-memory `RunState`
  (`runs`/`monitors` dicts). New endpoints need pytest coverage (happy + adversarial).
- Run `npm run lint`, `npm run test`, and `poetry run pytest` green before done.
- One task → one PR where practical. Respect dependency order below.

**Definition of Done (applies to every task):**
- [ ] Code + tests added; `npm run test` and (if backend touched) `poetry run pytest` pass.
- [ ] `npm run lint` / ruff / mypy clean for touched files.
- [ ] No new console errors; no `print()` in library code (use structlog server-side).
- [ ] `data-testid`s added for new interactive elements.
- [ ] Relevant docs updated (`docs/WEB_DASHBOARD.md`, this file's checkbox).

**Dependency order:** T1 → T2 → (T3–T14 mostly parallel). T3 depends on T1's cancel
endpoint pattern. T9 depends on T2 (catalog).

---

## P0 — Trust & control

### T1 — Stop/cancel a running run
**Why:** No way to abort an in-flight (possibly paid, possibly long) run — top trust gap.
**Files:** `server.py` (new endpoint + `RunState`), `Dashboard.tsx`, `hooks/useApi.ts`,
`components/PhasePipeline.tsx` or the sticky header in `Dashboard.tsx`, new
`__tests__`.
**Backend notes:** runs are fired as background tasks and tracked in `RunState`.
True mid-phase cancel may not be possible, so implement **cooperative cancel**:
add `POST /api/runs/{run_id}/cancel` that sets a `cancel_requested` flag and marks
status `cancelling` → `cancelled` (extend `finish_run` / add `cancel_run`). Background
loops/steps should check the flag at phase boundaries and stop. The demo simulation
(`_run_demo_async`) must honor it between `step()` calls.
**Frontend notes:** add a **Stop run** button in the sticky header, visible only when
`isLive`. Confirm via existing `ConfirmModal`. Optimistically show "Cancelling…".

**Acceptance criteria:**
- [ ] `POST /api/runs/{id}/cancel` returns 200 for a running run; 404 for unknown id;
      400 if the run is already terminal.
- [ ] After cancel, `GET /api/runs/{id}` reports `cancelling` then a terminal
      `cancelled` status; the WebSocket pushes the status change.
- [ ] The demo simulation stops within one `step()` of a cancel request (no further
      file/agent events emitted).
- [ ] A **Stop run** button appears on the live Dashboard, opens a confirm, and is
      hidden once the run is terminal.
- [ ] `cancelled` runs render a distinct status chip (not styled as `error`).
- [ ] Backend test covers cancel-running, cancel-unknown (404), cancel-terminal (400).
- [ ] Frontend test asserts the button shows only when live and triggers the API call.

### T2 — Estimate vs. actual cost on the Run summary
**Why:** Cost is estimated and shown live but never reconciled — the highest-value trust add.
**Files:** `components/RunSummaryCard.tsx`, `Run.tsx`/`Dashboard.tsx` to carry the
estimate forward, `types.ts`, `__tests__`.
**Notes:** persist the last `estimate.total_usd` for a run (store on the run entry when
starting, or pass through the WebSocket `start` payload). Summary shows **Estimated $X**
vs **Actual $Y** with a delta and a +/- color.

**Acceptance criteria:**
- [ ] When an estimate was produced before the run, the summary card shows estimated,
      actual, and the difference.
- [ ] When no estimate exists (e.g. demo, or estimate skipped), the card shows actual
      only with an "estimate not run" note — no NaN/`$undefined`.
- [ ] Demo runs (no real cost) never show a misleading delta.
- [ ] Test covers both with-estimate and without-estimate rendering.

### T3 — Recover from a failed run (retry / edit-and-rerun)
**Why:** `status === "error"` is a dead-end.
**Files:** `Dashboard.tsx`, `Run.tsx`, `components/RunSummaryCard.tsx`/error blocks,
routing/state to prefill Run, `__tests__`.
**Notes:** On error (and on `cancelled`), offer **Retry** (same backend/profile/brief)
and **Edit & rerun** (navigate to `/run` with fields prefilled from the failed run).
Carry brief/profile/backend via route state or a small store.

**Acceptance criteria:**
- [ ] A failed run shows a **Retry** action that starts a new run with identical config.
- [ ] **Edit & rerun** navigates to `/run` with backend, profile, complexity, and
      description prefilled from the failed run.
- [ ] The original failed run remains in history (retry creates a new run id).
- [ ] Test asserts prefill values match the source run.

---

## P1 — Legibility of agent activity

### T4 — Agent handoff timeline
**Why:** Multi-agent flow is the headline feature but reads as a flat process list.
**Files:** new `components/AgentTimeline.tsx`, `Dashboard.tsx`, types, `__tests__`.
**Notes:** render a horizontal swimlane keyed to phases (intake→planning→development→
testing→deployment) showing each agent's start/finish and the current owner. Derive
from existing `monitor.agents` + `monitor.log` (or extend monitor events). Keep the
existing `AgentTable` available (toggle or below the timeline).

**Acceptance criteria:**
- [ ] Timeline shows, per agent, phase, start, finish (or "active"), and current owner.
- [ ] Retries are visibly marked on the timeline (see T7 interplay).
- [ ] Works from current monitor data without backend changes, OR backend change is
      additive and covered by a test.
- [ ] Renders sensibly with 1 agent and with all 9; no overflow breakage at 1440px.
- [ ] Test feeds a sample monitor and asserts agent rows + active state.

### T5 — Activity log filtering (level + text)
**Why:** Log has no filtering; noise hurts both ops and screenshots.
**Files:** `components/ActivityLog.tsx`, `Dashboard.tsx`, `__tests__`.
**Notes:** add level filters (info/warn/error) and a text filter input. Default to
hiding debug-level lines. Preserve the existing `aria-live` region.

**Acceptance criteria:**
- [ ] Level toggles filter visible entries; text filter does case-insensitive substring.
- [ ] Filters reset cleanly between selected runs.
- [ ] `aria-live="polite"` preserved on the live region.
- [ ] Test asserts filtering by level and by text.

### T6 — Prominent "awaiting human" indicator on Dashboard
**Why:** A paused (HITL) run can be missed on a busy dashboard.
**Files:** `Dashboard.tsx`, `components/AlertBanner.tsx` (reuse), optional
`document.title` update, `__tests__`.
**Notes:** when the active run is `awaiting_human`, pin a high-contrast banner at the
top and update the browser tab title (e.g. "⏸ Action needed — AI-Team"). Restore the
title when resolved.

**Acceptance criteria:**
- [ ] A top banner appears whenever the selected run is `awaiting_human`.
- [ ] `document.title` reflects the paused state and is restored after resume/cancel.
- [ ] Banner does not appear for running/terminal runs.
- [ ] Test covers the awaiting_human → resolved transition.

### T7 — Surface retries and guardrail warns as positive signals
**Why:** Self-correction builds trust; today it's buried in the log.
**Files:** `AgentTimeline.tsx` (T4) and/or `Dashboard.tsx`, `MetricsCard.tsx`,
`__tests__`.
**Notes:** annotate retries on the timeline/metrics ("self-corrected") and show
guardrail warn count distinctly from fail. The demo's
`test_create_item_validation` retry is the canonical example to render well.

**Acceptance criteria:**
- [ ] Retry count is shown with a "self-corrected" affordance, not styled as an error.
- [ ] Guardrail warns are visually distinct from fails.
- [ ] Test asserts a retry event renders the positive treatment.

---

## P1 — Onboarding & clarity

### T8 — Relabel and disambiguate the "Demo" button
**Why:** "Demo" is read as "run my brief"; it actually plays a fixed sim with no files.
**Files:** `Dashboard.tsx`, `Run.tsx`, `CommandPalette.tsx`, sidebar run rendering,
`__tests__`.
**Notes:** relabel to **"Play sample run (free · no files)"** with a one-line helper.
Visually separate from primary Run. Tag the resulting run as "Sample" in the sidebar so
it's never confused with a real run.

**Acceptance criteria:**
- [ ] Button label and helper text updated on all three surfaces (Dashboard, Run, palette).
- [ ] Sample/demo runs show a "Sample" tag in the run sidebar/list.
- [ ] Existing demo behavior (zero cost, no files) is unchanged.
- [ ] Test asserts the new label and the sample tag.

### T9 — Onboarding empty state ("How it works")
**Why:** First-run empty state doesn't explain the product, cost, or backend choice.
**Files:** `Dashboard.tsx` empty state, optional new `components/HowItWorks.tsx`,
`__tests__`. **Depends on T2/T8 copy and T2 backend catalog from T9-backend? (no — uses
existing `/api/backends`).**
**Notes:** 3 steps (Describe → Watch agents build → Browse artifacts) + the sample-run
CTA + a one-line backend/key explainer.

**Acceptance criteria:**
- [ ] Empty Dashboard shows the 3-step explainer and both CTAs (sample run, go to Run).
- [ ] Explains that real runs may cost money and which key each backend needs.
- [ ] Disappears once a run is selected/active.
- [ ] Test asserts the explainer renders only in the empty state.

### T10 — Show backend prerequisites in the selector
**Why:** Users can pick a backend whose key/runtime they don't have and fail at runtime.
**Files:** `Run.tsx`, `Compare.tsx`, `hooks/useCatalog.ts`, possibly `/api/backends`
in `server.py`, `__tests__`.
**Notes:** show the required key inline (e.g. "needs ANTHROPIC_API_KEY"). If the server
can report configured/unconfigured backends, disable or warn on unconfigured ones.

**Acceptance criteria:**
- [ ] Each backend option displays its required key/runtime hint.
- [ ] If the catalog reports a backend as unconfigured, it is disabled or clearly warned.
- [ ] Falls back gracefully when the catalog endpoint doesn't provide config status.
- [ ] Test asserts the hint renders and (if applicable) the disabled state.

---

## P2 — Interaction & polish

### T11 — Command palette: keyboard nav + wire estimate + group headers
**Why:** Palette needs a mouse to run a command; the Estimate command is never wired.
**Files:** `CommandPalette.tsx`, `App.tsx` (pass `onEstimate` or remove the command),
`__tests__`.
**Notes:** add ↑/↓ to move selection, Enter to run, highlight the active item, wrap at
ends. Render each group header once (not per item). Either pass a working `onEstimate`
from `AppShell`/Run or remove the dead command.

**Acceptance criteria:**
- [ ] ↑/↓ change the highlighted command; Enter runs it; Esc closes.
- [ ] The "Estimate cost" command either works end-to-end or is removed (no dead command).
- [ ] Group headers appear once per group.
- [ ] Focus returns to the previously focused element on close.
- [ ] Test covers arrow navigation + Enter activation.

### T12 — Run-history sidebar: filter, search, grouping
**Why:** Lists all runs with no controls; becomes a junk wall.
**Files:** `Dashboard.tsx` sidebar, possibly a new `components/RunList.tsx`, `__tests__`.
**Notes:** add a status filter + text search, group by day, mark sample runs (T8), and a
hide/clear affordance for old runs.

**Acceptance criteria:**
- [ ] Status filter and search narrow the list; clearing restores it.
- [ ] Runs are grouped by day with headers.
- [ ] Performs acceptably with 100+ runs (no full-list re-render jank).
- [ ] Test covers filter + search behavior.

### T13 — Brief input affordances (auto-grow + full-brief view)
**Why:** 3-row textarea is cramped for the real multi-sentence briefs.
**Files:** `Run.tsx`, `Compare.tsx`, sidebar/meta card, `__tests__`.
**Notes:** auto-grow or make the description textarea resizable; let users expand the
full brief from the run list (hover/click), not just the active run's meta card.

**Acceptance criteria:**
- [ ] Description field grows with content (or is resizable) up to a sensible max.
- [ ] Full brief is viewable from the run list, not only the active run.
- [ ] Test asserts the expand affordance reveals the full text.

### T14 — Compare summary: direction glyphs + auto verdict; plus a11y pass
**Why:** "Best" highlight isn't self-explanatory; status relies on color; focus mgmt gaps.
**Files:** `Compare.tsx` summary table, `utils/compareSummary.ts`, status chips across
pages, modals, `__tests__`.
**Notes:** add ▲/▼ or "(lower is better)" per metric row and a one-line auto verdict
("LangGraph: lowest cost; Claude Agent SDK: most tests passed"). Pair every status with
text/icon (not color alone), ensure visible focus rings, trap focus in modals and
restore on close, verify contrast on the heavy `dim` grey text.

**Acceptance criteria:**
- [ ] Each summary row shows its preferred direction; a verdict line summarizes winners.
- [ ] All status indicators convey meaning without relying on color alone.
- [ ] Modals (ConfirmModal, CommandPalette) trap focus and restore it on close.
- [ ] Axe (or equivalent) reports no new critical a11y violations on the four pages.
- [ ] Test covers the verdict line and the direction glyphs.

---

## Suggested sequencing

1. **Sprint 1 (trust):** T1, T2, T3.
2. **Sprint 2 (legibility):** T4, T5, T6, T7.
3. **Sprint 3 (onboarding):** T8, T9, T10.
4. **Sprint 4 (polish/a11y):** T11, T12, T13, T14.

Hand this file to Claude Code task-by-task; each task's acceptance criteria are written
to be directly testable.
