# UI/UX Improvement Plan — 2026-07-06

Findings from a live review of the web UI (Vite dev @5173 → FastAPI @8421, three
completed disk runs present). Each task is self-contained for implementation:
problem, evidence, fix sketch, acceptance criteria, files.

Frontend root: `src/ai_team/ui/web/frontend/`. Server: `src/ai_team/ui/web/server.py`.
Run existing tests with `npm --prefix src/ai_team/ui/web/frontend run test`; add new
component tests alongside in `src/__tests__/` or `src/pages/__tests__/`.

Priorities: **P0** = broken behavior a user will hit; **P1** = misleading state or
missing feedback; **P2** = polish.

**Status (2026-07-06):** Implemented in this pass unless noted partial.

---

## P0-1 Dashboard never loads runs in a hidden/background tab

**Problem.** `Dashboard.tsx` polls via `tick()` which returns early when
`document.hidden`. The guard also swallows the *initial* fetch, so a tab opened in
the background (or any automation context) renders "No runs yet" indefinitely; after
focusing, the user still waits up to `POLL_IDLE_MS` (8s) for the next interval.

**Evidence.** Live: API `GET /api/runs` returns 3 runs (200), sidebar stuck on
"No runs yet"; `document.visibilityState === "hidden"` confirmed in page context.

**Fix.**
- Always run `pollRuns()` once on mount, regardless of visibility.
- Add a `visibilitychange` listener: when the document becomes visible, poll
  immediately (don't wait for the next interval tick).
- Keep the hidden-guard for *recurring* ticks (it's a sensible battery/API saver).

**Acceptance criteria.**
- [x] With the tab hidden at mount time, the run list is populated as soon as the
      component mounts (verify: mock `document.hidden = true`, assert `getRuns`
      called once and state set).
- [x] On `visibilitychange` → visible, a poll fires within 100ms (mock timers).
- [x] Recurring interval still skips ticks while hidden.
- [x] Existing Dashboard tests pass.

**Files.** `src/pages/Dashboard.tsx`, test in `src/pages/__tests__/`.

---

## P0-2 Deep link to a completed run renders it as a live run

**Problem.** `/runs/<id>` derives `isTerminal`/`isLive` from `activeRun`, which comes
from the *runs list* state. If the list hasn't loaded (see P0-1, or the run aged out
of `/api/runs`), `activeRun` is `undefined`, both flags are false, and a **completed**
run renders the live layout: "Waiting for agents…", "Waiting for agent activity…",
no `RunSummaryCard`, no `ArtifactPreview`, no run-meta header (id/status/description).

**Evidence.** Live: navigated directly to
`/runs/2026-07-03_210313_write-a-single-python-module_01` (status `complete`,
4 tasks, 2 files, 5 tests passed) — rendered as a waiting/live view.

**Fix.** `GET /api/runs/{run_id}` already returns `status`, `backend`, `profile`,
`description`. Store that response (not just `.monitor`) and use it as the fallback
source for status/meta when the runs-list entry is missing. Derive
`isTerminal`/`isLive` from `activeRun?.status ?? runDetail?.status`.

**Acceptance criteria.**
- [x] Direct navigation to `/runs/<terminal-run-id>` with an empty runs list shows:
      status chip, description, `RunSummaryCard`, `ArtifactPreview` — and does NOT
      show "Waiting for agents…".
- [x] Live runs deep-linked the same way still connect to the monitor WebSocket.
- [x] Component test covers the "detail loaded, list empty" path.

**Files.** `src/pages/Dashboard.tsx`, `src/hooks/useApi.ts` (getRun return already
sufficient), tests.

---

## P0-3 Elapsed timer keeps counting on finished runs

**Problem.** Completed runs show a ticking elapsed time computed from `started_at`
with no cap at completion. A run finished Jul 3 displayed **"60h 56m"** (and rising)
on Jul 6. Was flagged in the 2026-07-04 handoff (open item 4); still live. Misleading
everywhere elapsed renders: Dashboard metrics, Compare columns, summary table.

**Evidence.** Live screenshots on both Dashboard (`60h 56m`) and Compare (`60h 57m`)
for terminal runs; `docs/images/` has the earlier "28h 30m" receipt.

**Fix.** Server-side in the monitor/state serialization: when the run has a
`finished_at` (or terminal status), compute elapsed as `finished_at - started_at`,
frozen. Client-side: never locally tick elapsed for a run whose status is terminal.

**Acceptance criteria.**
- [x] `GET /api/runs/{id}` for a terminal run returns an elapsed value equal to
      (finished_at − started_at), stable across repeated calls.
- [x] Compare columns and Dashboard metrics show the frozen value for terminal runs.
- [x] Unit test: terminal run state → elapsed does not change between two
      serializations 2s apart.

**Files.** `src/ai_team/monitor.py` (`Metrics.end_time`), `src/ai_team/ui/web/server.py`,
frontend displays server-provided `elapsed` only.

---

## P0-4 Compare silently reattaches to a days-old finished comparison and shows it as active

**Problem.** `Compare.tsx` restores `ai-team-compare-active` from localStorage on
every mount, with no expiry and no cleanup when all runs are terminal. Three days
after the last comparison, opening the Compare tab shows the old columns looking
*live*: ticking elapsed (P0-3), CrewAI column "Waiting for agents to join the run…",
Claude column agent badge "● ACTIVE". There is no visible control to dismiss the
stale comparison.

**Evidence.** Live: Compare tab on 2026-07-06 rendered the 2026-07-03 comparison in
this state without any user action.

**Fix.**
- After reattach resolves, if **all** restored runs are terminal, render them in a
  clearly-labelled "Last comparison (finished <relative time>)" state — no
  waiting/active affordances — or clear the stored id entirely and show results
  read-only.
- Add a "Clear" / "New comparison" button whenever a reattached comparison is shown.
- Fix the agent-status source so a terminal run can never render "ACTIVE" badges
  (derive agent badges from run status, not the last streamed agent snapshot).
- "Waiting for agents to join the run…" must only render for non-terminal statuses.

**Acceptance criteria.**
- [x] Reattached fully-terminal comparison renders with a "finished" banner/label,
      zero active/waiting indicators, and a working "Clear" button that empties
      localStorage and resets the page.
- [x] Reattached in-flight comparison still live-reconnects (existing behavior).
- [x] Component test: seed localStorage + mock `GET /comparisons/{id}` returning all
      `complete` → assert no "Waiting for agents" text, no ACTIVE badge, Clear works.

**Files.** `src/pages/Compare.tsx`, `src/components/CompareColumn.tsx`, tests.

---

## P0-5 Artifacts default root hides existing files ("No files yet for this run")

**Problem.** The Artifacts page defaults to root `workspace`. For the reviewed
completed runs, `GET /api/projects/{id}/tree?root=workspace` returns `tree: []` while
`?root=bundle` contains the artifacts (manifest, phase outputs). The user sees
"No files yet for this run" — copy that implies the run is still pending — for runs
that generated files.

**Evidence.** Live curl of both roots for
`2026-07-03_210313_write-a-single-python-module_01`; UI screenshot showing empty
state with Root=Workspace.

**Fix.**
- On run selection, if the selected root's tree is empty and the other root is
  non-empty, auto-switch to the non-empty root (and note it in the UI).
- Empty-state copy must be status-aware: terminal run → "No files in the workspace
  for this run — try the Bundle root" (or the auto-switch makes this moot);
  running → keep "No files yet".

**Acceptance criteria.**
- [x] Selecting a completed run whose workspace is empty but bundle is non-empty
      lands on the bundle tree without manual root switching.
- [x] Both-empty terminal run shows copy that does not imply "yet"/pending.
- [x] Test covers the auto-switch and the copy branch.

**Files.** `src/pages/Artifacts.tsx`, tests.

---

## P0-6 Terminal runs lose activity log, agent timeline, and guardrail events

**Problem.** For disk-loaded terminal runs the monitor has metrics (tasks/files/tests)
but empty `log`, `agents`, and `guardrail_events` — panels render "Waiting for agent
activity…" and "No guardrail checks yet" on runs that demonstrably had activity and
guardrail traffic. The persisted monitor snapshot is partial.

**Evidence.** Live: completed run with 4 tasks / 2 files / 5 tests shows empty
Activity Log, empty Agent Timeline, "No guardrail checks yet".

**Fix.** Persist the full monitor state (log entries, agent snapshots, guardrail
events) into the run bundle at finalize time (extends `ResultsBundle.finalize()`
from the Jul 4 session), and load it back in `GET /api/runs/{id}`. Cap the log at a
sane size (e.g. last 500 entries) to bound bundle growth.

**Acceptance criteria.**
- [x] After a run completes, bundle `state.json` stores `monitor_snapshot` (log,
      agents, guardrail_events capped at 500).
- [x] `GET /api/runs/{id}` loads snapshot from bundle when in-memory monitor is gone.
- [x] Dashboard for a terminal run renders log/guardrail panels (terminal copy when empty).
- [x] Server integration test: finalize → read back → fields populated.

**Files.** `src/ai_team/ui/web/server.py`, `src/ai_team/core/results/writer.py`,
`Dashboard.tsx`, tests both sides.

---

## P1-1 HITL "Approve" looks one-click but only pre-fills the textarea

**Problem.** In `HumanReviewPanel.tsx`, Approve/Request changes/Reject buttons only
set textarea text; nothing is sent until "Submit & Resume". No indicator that the
response is still unsent. Users click Approve, believe the run resumed, and wait on
a paused run. (Handoff 2026-07-04 problem #13 / open item 2.)

**Fix.** Either (a) make the three preset buttons submit immediately, with the
textarea reserved for custom guidance, or (b) keep two-step but add an explicit
"draft — not sent" chip next to the filled textarea and change button copy to
"Use template". Option (a) recommended; keep a confirm only for Reject.

**Acceptance criteria.**
- [x] Clicking Approve sends `POST /runs/{id}/resume` with the approval text and
      shows the submitting state without further clicks (if option a).
- [x] Custom text path unchanged: type → "Submit & Resume".
- [x] Component test for preset-click → POST fired exactly once.

**Files.** `src/components/HumanReviewPanel.tsx`, tests.

---

## P1-2 HITL panel lingers after resume until page reload

**Problem.** After a successful resume the panel stays visible until a reload
(handoff open item 3). `onResumed` triggers a poll, but the panel's render condition
(`runStatus === "awaiting_human" || live.hitlPayload`) keeps it up because
`hitlPayload` isn't cleared on resume.

**Fix.** Clear the HITL payload in the WebSocket hook state when a resume succeeds
(optimistically) and when a `run_resumed`/status-change event arrives. Render
condition should require `awaiting_human` status, using payload only as supplement.

**Acceptance criteria.**
- [x] Successful submit hides the panel within one poll cycle without reload.
- [x] Panel reappears if the run pauses again later (new payload).
- [x] Test: simulate resume success → panel unmounts.

**Files.** `src/hooks/useWebSocket.ts`, `src/pages/Dashboard.tsx`,
`src/components/HumanReviewPanel.tsx`, tests.

---

## P1-3 Compare grid overflows the viewport; third column clipped

> **Superseded by Phase 2 R-2** ([UI_UX_IMPROVEMENT_PLAN_PHASE2.md](UI_UX_IMPROVEMENT_PLAN_PHASE2.md))
> — implement the full responsive treatment there instead of this spot fix.

**Problem.** At 1400px wide, the 3-column compare grid overflows horizontally — the
Claude Agent SDK column is cut off mid-table with no scroll affordance visible.

**Fix.** Make `.compare-grid-3` responsive: `minmax(0, 1fr)` columns with
`overflow-x: auto` on the grid container as a fallback; stack to 1–2 columns below
~1200px. Ensure inner tables use `table-layout: fixed` or wrap.

**Acceptance criteria.**
- [x] At 1280px and 1440px, all three columns fully visible or horizontally
      scrollable with a visible scrollbar; no clipped content.
- [x] At 900px, columns stack vertically and remain readable.

**Files.** `src/App.css` (compare grid rules), `CompareColumn.tsx`.

---

## P1-4 Page title is the Vite scaffold default ("frontend")

**Problem.** `index.html` still has `<title>frontend</title>`. Only Dashboard sets a
title at runtime; other routes can surface "frontend" in the tab bar and history.

**Fix.** Set `<title>AI-Team Dashboard</title>` in `index.html`; add per-route
titles ("Run — AI-Team", "Compare — AI-Team", "Artifacts — AI-Team") via a small
`useDocumentTitle` hook. Keep the existing "⏸ Action needed" override.

**Acceptance criteria.**
- [x] Every route shows a meaningful tab title; no route shows "frontend".
- [x] HITL override still wins while `awaiting_human`.

**Files.** `index.html`, `src/hooks/useDocumentTitle.ts`, the four pages.

---

## P1-5 Artifacts run-selector rows are cluttered and duplicated

**Problem.** Selector rows render like
`2026-07-… · No assignment · crewai · disk · Jul 4, 2026, 10:46 AM · disk · artifacts`
— truncated id first, "disk" twice, trailing source tokens meaningless to users.

**Fix.** Row format: `<date> · <backend> · <description-or-run-id>` with the id in a
`title` tooltip. Show source ("disk"/"live") at most once, as a small tag, if at all.

**Acceptance criteria.**
- [x] No duplicated tokens in any option row.
- [x] Description shown when present; run id only as fallback/tooltip.
- [x] Selector remains keyboard-navigable.

**Files.** `src/hooks/useUnifiedRuns.ts`, `src/pages/Artifacts.tsx`.

---

## P2-1 Run form feedback gaps

**Problems.**
- Disabled "Run" gives no reason (empty description) — no tooltip or helper.
- "Estimate Cost" uses only `complexity`; description and backend are ignored, which
  reads as if the estimate reflects the entered project. Mislabeled precision.
- "Complexity" has no explanation of what it affects (estimate only? agent behavior?).

**Fixes.**
- Helper text under Run when disabled: "Enter a project description to run."
- Rename estimate button/label to "Estimate cost by complexity" or include a note
  "Estimate is based on complexity tier and team profile, not your description."
- One-line helper under Complexity stating what it drives.

**Acceptance criteria.**
- [x] Empty description → visible inline reason; button still disabled.
- [x] Estimate panel/button copy states its actual inputs.
- [x] Complexity helper text present on Run and Compare pages.

**Files.** `src/components/RunConfigForm.tsx`, `src/pages/Run.tsx`, `src/pages/Compare.tsx`.

---

## P2-2 Nav brand crowds the active tab pill

**Problem.** "AI-Team Dashboard" brand text sits ~4px from the active "Dashboard"
pill; reads as one merged element at a glance.

**Fix.** Add margin/gap between `.nav-brand` and `.nav-links` (e.g. `gap: 24px`).

**Acceptance criteria.**
- [x] Visible separation at 1280–1600px widths; no wrap regression at 1024px.

**Files.** `src/App.css`.

---

## P2-3 Run list scalability

**Problem.** Sidebar renders every run; with hundreds of disk runs this bloats DOM
and scans. Search/filter exist but the full list still mounts.

**Fix.** Cap initial render per day-group (e.g. 20) with "Show all (N)" expander, or
virtualize. Cheap option first.

**Acceptance criteria.**
- [x] 500-run fixture renders < 100 run items initially and remains scroll-smooth.
- [x] Search still matches runs beyond the initial cap.

**Files.** `src/components/RunList.tsx`, test with a large fixture.

---

## Suggested order

1. P0-1 + P0-2 together (same file, same state model).
2. P0-3 (server elapsed freeze) — unblocks honest Compare/summary numbers.
3. P0-4 (stale compare reattach) — depends on P0-3 for frozen elapsed display.
4. P0-5, P0-6.
5. P1-1 + P1-2 (HITL pair).
6. P1-3, P1-4, P1-5, then P2s.
