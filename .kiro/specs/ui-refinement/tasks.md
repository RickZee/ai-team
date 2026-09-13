# Implementation Plan — UI Refinement

**Spec ID:** `ui-refinement`
**Requirements:** [`requirements.md`](./requirements.md) · **Design:** [`design.md`](./design.md)

---

## How to execute this plan

- Work **one task at a time, in order**. Do not batch phases.
- All paths are relative to `src/ai_team/ui/web/frontend` unless stated otherwise.
- Every task lists a **Definition of done**. Do not mark it complete until each bullet is
  literally true.
- **Gate after every task:** `npm run lint && npm run build && npm test`.
- **Gate after every phase** that changes markup: `uv run pytest tests/e2e/web -m web_e2e`
  from the repo root.
- **Never rename or remove a `data-testid`.** Adding is fine (R21.1).
- One commit per phase, each green on its own, so any phase can be reverted alone (R21.6).
- Phase 9's drift test will fail until Phases 1–6 are done. That is expected — do not
  write it early and do not weaken it to make it pass.

Cursor prompt shape:

```
Read .kiro/specs/ui-refinement/requirements.md and design.md for context.
Implement task 2.3 from .kiro/specs/ui-refinement/tasks.md.
Do not start any other task. Do not rename any data-testid.
Stop when its Definition of done is satisfied and
`npm run lint && npm run build && npm test` passes in src/ai_team/ui/web/frontend.
```

---

## Phase 0 — Baseline

- [ ] **0.1 Capture the before state**
  - Record, in `.kiro/specs/ui-refinement/BASELINE.md`: `wc -l src/App.css src/index.css`,
    the count of raw spacing declarations, distinct `font-size` values, distinct
    `border-radius` values, and `npm test` pass count.
  - Screenshot (manually, checked into nothing — attach to the PR) Home, Run, Compare with
    three live columns, RunDetail on each of its four tabs, and Artifacts.
  - **Definition of done:** `BASELINE.md` exists with the six counts; all screenshots taken.
  - _2026-09-13: numeric counts are in `BASELINE.md`. Visuals were shot after `ee821f6`
    (finished UI), so they do not satisfy this task. Before-shots can still be taken from
    `87600d2` (parent of `ee821f6`); see `BASELINE.md`._
  - _Requirements: R21.2_

- [x] **0.2 Freeze the test-id surface**
  - Generate `.kiro/specs/ui-refinement/TESTIDS.txt`: every `data-testid` literal in `src/`,
    sorted and deduplicated.
  - **Definition of done:** file exists; a `grep -c` count is recorded in `BASELINE.md`.
    This file is the diff target for R21.1 at the end of every later phase.
  - _Requirements: R21.1_

---

## Phase 1 — Deletion (no visual change)

Nothing in this phase should alter a single rendered pixel. If something moves, a class
was not dead — restore it and investigate.

- [x] **1.1 Remove the Dashboard-era rules**
  - For each class in R6.1, `grep -rn "<class>" src/ ../../../../../tests/` first. Delete
    only on zero hits outside `App.css`.
  - Delete the `@media (max-width: 1100px)` block (App.css:931) once its contents are gone.
  - **Definition of done:** every class listed in R6.1 is absent from `App.css`; the app
    renders identically on all five routes; `npm test` green.
  - _Requirements: R6.1, R6.2_

- [x] **1.2 Resolve duplicate selectors**
  - `.btn-sm`, `.hitl-payload`, `.run-list-item`, `.run-list-item-wrap`,
    `.summary-table th/td`, `.artifacts-controls select`: keep the **winning** (later)
    declaration, delete the earlier, merge any non-conflicting properties into the survivor.
  - **Definition of done:** no selector text appears twice in `App.css`; the computed styles
    for a run-list card, a `.btn-sm`, and a summary-table cell are unchanged (verify in
    devtools before/after).
  - _Requirements: R6.3_

- [x] **1.3 Merge the duplicate media blocks**
  - Fold `@media (max-width: 900px)` at App.css:1493 into the one at :978, preserving
    declaration order so the cascade result is identical.
  - **Definition of done:** exactly one `@media (max-width: 900px)` block; narrow-width
    rendering unchanged at 375px, 768px, 899px.
  - _Requirements: R5.5_

- [x] **1.4 Delete the unused sprite and reconcile orphan classes**
  - Delete `public/icons.svg` (referenced by nothing).
  - Produce the orphan list in both directions (CSS-defined-unused, TSX-used-undefined) and
    record it in `BASELINE.md`. Resolve the *undefined* half now by either styling or
    removing: `.muted` (→ `.text-muted`, R3.7), `.panel-nested`, `.empty-state-icon`,
    `.compact`, `.how-it-works-cost`.
  - Structural hooks that stay (test/query targets only) get listed in `design.md` §9's
    allowlist rather than styled.
  - **Definition of done:** `public/icons.svg` gone; no `className` literal in `src/`
    resolves to nothing except those named in the allowlist.
  - _Requirements: R6.4, R16.5, R3.7_

- [x] **1.5 Phase gate**
  - **Definition of done:** `npm run lint && npm run build && npm test` green;
    `uv run pytest tests/e2e/web -m web_e2e` green; `data-testid` diff vs `TESTIDS.txt`
    empty; `wc -l src/App.css` recorded — expect roughly −250 to −350 lines.
  - _Requirements: R21.2, R21.3_

---

## Phase 2 — Tokens

- [x] **2.1 Create the token file**
  - Create `src/styles/tokens.css` with the full block from design §2.2 and §2.3
    (spacing, radius, type, layout, icon, surfaces, foreground, borders, intents,
    categorical, tints) plus `color-scheme: dark`.
  - Create `src/styles/reset.css` (the current `*` reset) and `src/styles/base.css`
    (html/body/heading/link/`:focus-visible`).
  - Import order in `main.tsx`: `tokens.css`, `reset.css`, `base.css`, then `App.css`.
    Delete `src/index.css`.
  - **Definition of done:** app builds and renders; `src/index.css` gone; no visual change
    yet beyond native control theming (which is expected, R15.1).
  - _Requirements: R1.1, R2.1, R2.2, R2.5, R3.1, R15.1_

- [x] **2.2 Migrate spacing and radius**
  - Replace every raw length in `padding`/`margin`/`gap`/`inset`/`border-radius` in
    `App.css` using the mapping table in design §2.2. Keep `0`, `auto`, `100%`,
    percentages, 1–2px borders, and `vh` scroll caps.
  - Do **not** add a token to avoid a rounding decision (R1.5).
  - **Definition of done:** zero raw lengths remain in those properties; the app is visually
    equivalent within ±2px; `npm test` green.
  - _Requirements: R1.2, R1.3, R1.4, R1.6_

- [x] **2.3 Migrate type**
  - Replace every `font-size` with a `--text-*` token per design §2.2; set
    `html { font-size: 100% }` and `body { font-size: var(--text-base) }`; replace inline
    font stacks with `--font-sans`/`--font-mono`; reduce `font-weight: 700` to `600`.
  - Add the single `h1, h2, h3, h4` sizing block in `base.css`; remove per-component
    heading size overrides.
  - **Definition of done:** no raw `font-size` outside `tokens.css`; no `font-weight: 700`;
    text at browser zoom 150% still lays out without clipping.
  - _Requirements: R2.1, R2.2, R2.3, R2.4, R2.5, R2.6_

- [ ] **2.4 Phase gate**
  - **Definition of done:** all gates green; screenshots retaken and compared against 0.1 —
    differences are sub-pixel spacing only, no layout breakage.
  - _2026-09-13: unchecked. Reconstructing 0.1 from `87600d2` still cannot produce this
    gate — it required a Phase-2-only tree photographed before colour/IA/nav landed._
  - _Requirements: R21.2, R21.3_

---

## Phase 3 — Colour and intent

This is the phase a reviewer will notice. Keep it to one commit.

- [x] **3.1 Introduce role tokens and migrate rules**
  - Point every colour declaration in `App.css` at a role or intent token. Alpha tints move
    to `--tint-*`.
  - **Definition of done:** no hex, `rgb()`, or `rgba()` literal remains in `App.css`;
    `--cyan/--green/--red/--yellow/--blue/--magenta/--orange` are deleted from the sheet.
  - _Requirements: R3.1, R3.6, R3.8_

- [x] **3.2 Retire the hue utility classes**
  - Replace `.cyan`/`.green`/`.red`/`.yellow`/`.blue` and `.dim`/`.text-dim`/`.muted` at
    every call site with `.text-accent`/`.text-success`/`.text-danger`/`.text-warning`/
    `.text-muted`.
  - **Definition of done:** the old class names appear nowhere in `src/`; every replaced
    element keeps its previous colour except where R3.2 intends a change.
  - _Requirements: R3.6, R3.7_

- [x] **3.3 Rebuild the button variants**
  - Implement `.btn` base plus `.btn-primary` (accent fill), `.btn-secondary`,
    `.btn-danger`, `.btn-ghost`, `.btn-link`, and the single `.btn-sm`.
  - Collapse the duplicated `a.btn-*` blocks into `:where(a, button)` selectors.
  - Replace `opacity: 0.9` hovers with explicit hover colours; replace `transition: all`
    with an explicit property list.
  - **Definition of done:** every button in the app renders with a visible
    `--border-default` edge; primary buttons are accent-filled; no `transition: all`
    remains; `npm test` green.
  - _Requirements: R3.2, R3.3, R3.4, R13.4, R14.1_

- [x] **3.4 Danger tone for destructive confirms**
  - Add `tone?: "default" | "danger"` to `ConfirmModal`; render `.btn-danger` when
    `tone="danger"`. Pass it from the Delete-run confirm (`pages/Home.tsx`) and the
    Stop-run confirm (`pages/RunDetail.tsx`).
  - **Definition of done:** both destructive confirms show a red confirm button;
    `data-testid="confirm-modal-ok"` unchanged; the Compare preflight modal stays default.
  - _Requirements: R3.5_

- [x] **3.5 Status → intent map**
  - Add `src/utils/statusIntent.ts` per design §3.3 and use it in `RunList`,
    `RunStatStrip`, `CompareColumn`, and `RunSummaryCard`. Collapse `.badge*`,
    `.status-chip`, `.run-list-sample-tag`, `.run-list-comparison-chip`, and
    `.agent-timeline-phase` onto `.chip` + `.chip-<intent>`.
  - **Definition of done:** one `chip-${intent}` dynamic pattern replaces eleven
    `status-*` classes; every status renders the same colour it did before; unit tests
    asserting on status classes updated in this task with the reason in the commit body.
  - _Requirements: R3.1, R21.4_

- [x] **3.6 Contrast check script**
  - Add `scripts/check-contrast.mjs`: parse `tokens.css`, assert text pairs ≥ 4.5:1 and
    boundary pairs ≥ 3:1, exit non-zero with the failing pair named.
  - Wire it into `npm test` (as a vitest case) or as a `pretest` script.
  - **Definition of done:** script passes on the current tokens; deliberately breaking
    `--border-default` to `#484f58` makes it fail with a clear message.
  - _Requirements: R14.1, R14.5_

- [ ] **3.7 Phase gate**
  - **Definition of done:** all gates green; screenshots retaken; the only intended visual
    deltas are: primary buttons blue, destructive confirms red, all control borders
    lighter.
  - _2026-09-13: unchecked. After-state shots show cyan primary and a red Stop-run confirm,
    mixed with later a11y/Compare/nav changes. A 3.7-only diff would need a Phase-3 tree
    photographed before Phases 4–8._
  - _Requirements: R21.2, R21.3_

---

## Phase 4 — Accessibility

- [x] **4.1 Headings and skip link**
  - Add exactly one `<h1>` per route (Home, Run, Compare, RunDetail, Artifacts); demote or
    promote existing headings to the map in design §8.1.
  - Add a `.visually-hidden` utility and a "Skip to content" link as the first focusable
    element, targeting `<main id="main">`.
  - **Definition of done:** each page has exactly one `h1`; no level is skipped; the skip
    link is reachable by Tab from a cold load and moves focus into main.
  - _Requirements: R8.1, R8.2, R8.3, R8.4, R8.5, R12.5_

- [x] **4.2 Form labels**
  - Give every control in `RunConfigForm` (4) and `Artifacts` (2) a `useId()`-derived `id`
    and matching `htmlFor`; wire `.form-helper`, `.backend-key-hint`, and
    `.estimate-helper` via `aria-describedby`; forward `id`/`aria-describedby` through
    `AutoGrowTextarea`.
  - **Definition of done:** clicking each label focuses its control; `htmlFor` count is 6+;
    `RunConfigForm` rendered twice on one page produces no duplicate ids.
  - _Requirements: R9.1, R9.2, R9.3, R9.5, R9.6_

- [x] **4.3 Tab pattern**
  - Implement design §4.1 in `pages/RunDetail.tsx`: `aria-controls`, `role="tabpanel"`,
    `aria-labelledby`, roving `tabIndex`, and Arrow/Home/End handling. Preserve the hash
    sync exactly.
  - In `pages/Artifacts.tsx` and `components/CodeViewer.tsx`, remove tab semantics in
    favour of plain buttons with `aria-pressed`.
  - **Definition of done:** arrow keys move between the four run tabs and wrap; `#activity`
    deep-links still select Activity; `Dashboard.*`/`Run*` unit tests green unchanged.
  - _Requirements: R10.1, R10.2, R10.3, R10.4, R10.5_

- [x] **4.4 Dialog pattern**
  - Extend `useFocusTrap(open, ref, onClose)` with Escape, overlay-click dismissal, and
    background-scroll lock. Remove `CommandPalette`'s local Escape branch. Switch
    `ConfirmModal` to `useId()` and add `aria-describedby` and the R3.5 `tone` prop
    plumbing if not already done in 3.4.
  - **Definition of done:** Escape closes both the command palette and every confirm modal;
    clicking the overlay closes; clicking inside does not; focus returns to the invoker;
    the page behind does not scroll while open.
  - _Requirements: R11.1, R11.2, R11.3, R11.4, R11.5, R11.6_

- [x] **4.5 Live regions**
  - `AlertBanner`: `role="alert"` for error, `role="status"` otherwise. Add the HITL
    banner to the `alert` path.
  - Remove `aria-live`/`aria-relevant` from the `.activity-log` container and the
    `ariaLive` prop from `ActivityLog`; add a `.visually-hidden` `role="status"` element in
    the run view that announces status and phase transitions only.
  - **Definition of done:** appending 200 log lines produces no live-region announcements;
    a phase change produces exactly one; `ActivityLog` call sites updated.
  - _Requirements: R12.1, R12.2, R12.3, R12.4_

- [x] **4.6 Focus, scroll regions, and motion**
  - Add `tabIndex={0}` + an accessible name to every scroll container in R13.1.
  - Add the `prefers-reduced-motion` guard; verify `:focus-visible` against `--bg-raised`.
  - Give icon-only controls a 24×24 minimum target via padding.
  - Convert the `role="button"` div in `CodeViewer` to a real `<button>` (or record why
    not in design §6.3).
  - **Definition of done:** every scroll region is reachable and scrollable by keyboard;
    the spinner does not animate under reduced motion; no icon button is smaller than 24px.
  - _Requirements: R13.1, R13.2, R13.3, R13.5, R13.6, R13.7_

- [x] **4.7 Native control polish**
  - Re-evaluate `::-webkit-scrollbar` now that `color-scheme: dark` is set; keep and
    document, or delete. Normalize `input[type="search"]` across its three uses; set
    `accent-color`.
  - **Definition of done:** `<select>` popups, autofill, and scrollbars render dark in
    Chrome and Safari; the decision on the scrollbar override is recorded in design §9.
  - _Requirements: R15.2, R15.3, R15.4, R6.6_

- [x] **4.8 Phase gate**
  - **Definition of done:** all gates green; a full keyboard-only pass of Home → new run →
    run detail (all four tabs) → stop-run confirm reaches and operates every control.
  - _Requirements: R21.2, R21.3_

---

## Phase 5 — Surfaces and layout

- [x] **5.1 De-nest panels**
  - Apply design §3.2: `Home` stops wrapping `RunList`; `CompareColumn`'s inner panels
    become `.panel-section`; `RunDetail`'s Tests tab stops wrapping `TestResultsPanel`.
  - Define `.panel-section` (background + radius + padding, no border).
  - **Definition of done:** no `.panel` renders inside another `.panel` anywhere in the
    app (verify by a DOM query in devtools on all five routes).
  - _Requirements: R4.1, R4.2, R4.3, R4.4_

- [x] **5.2 Single gutter and content container**
  - Move the horizontal inset to one `.content` wrapper inside `<main>`; remove
    `padding-left/right` from `.page-shell`, `.home-page`, `.compare-page`,
    `.run-detail-page`. Apply `--content-max-width` with `margin-inline: auto`.
  - Cap prose blocks at `--measure`.
  - **Definition of done:** gutter is 24px, not 48px; content stops at 96rem on a wide
    display; no horizontal body scrollbar at 320px, 768px, 1280px, 2560px.
  - _Requirements: R5.1, R5.2, R5.3_

- [x] **5.3 Empty and loading states**
  - Delete `.empty-state`; convert its nine direct users (`TestResultsPanel` ×2,
    `ArchitecturePanel` ×2, `CodeViewer` ×2, `ActivityLog`, `RunArtifactsPanel`,
    `Artifacts`) to `EmptyState`/`LoadingState` — four of them are loading states and
    become `LoadingState`; drop `className="empty-state"` from the eleven `EmptyState`
    call sites, keeping only `panel` on the two in `Artifacts`; remove every
    non-machine-text italic.
  - **Definition of done:** one empty-state implementation remains; no italic body text;
    `EmptyState.test.tsx` and `RunList.test.tsx` green.
  - _Requirements: R7.1, R7.2, R7.3, R7.4_

- [x] **5.4 Breakpoint consolidation**
  - Delete `--bp-*` tokens; express the three documented breakpoints (design §5) as
    literals; ensure at most one `@media` block per breakpoint.
  - **Definition of done:** three media blocks total; layout verified at 375, 640, 1024,
    1440, 2560px.
  - _Requirements: R5.4, R5.5_

- [x] **5.5 Phase gate**
  - _Requirements: R21.2, R21.3_

---

## Phase 6 — Icons and truncation

- [x] **6.1 Emoji → lucide**
  - Replace every decorative emoji per design §7 with a lucide icon carrying
    `aria-hidden="true"`; add `--icon-sm`/`--icon-md` sizing; icons inherit `currentColor`.
  - **Definition of done:** no emoji literal remains in `src/**/*.tsx` except where task
    6.2 converts it to text; icons are visually consistent with the existing
    `FileTreeViewer`/`CodeViewer` icons.
  - _Requirements: R16.1, R16.2, R16.4_

- [x] **6.2 Meaningful glyphs → text**
  - `RunStatStrip`, `CompareColumn`, `GuardrailsPanel`: replace `✓`/`✗`/`⚠` composites
    with readable text (`12 passed · 1 failed`), keeping the existing `data-testid`s.
  - **Definition of done:** a screen reader reads the stat strip as a sentence;
    `RunStatStrip.test.tsx` updated in this task if it asserted on glyphs.
  - _Requirements: R16.3, R21.4_

- [x] **6.3 Command palette affordance**
  - Convert the `⌘K` span to a `<button>` that opens the palette; detect platform once at
    module scope to render `⌘K` or `Ctrl K`; accessible name "Open command palette".
  - **Definition of done:** clicking it opens the palette; it is keyboard-reachable; a
    non-Mac user agent renders `Ctrl K`.
  - _Requirements: R16.6_

- [x] **6.4 CSS truncation**
  - Replace display-only `slice()` calls (`RunDetail` title, `Compare` form summary,
    `CommandPalette` labels) with CSS ellipsis/line-clamp; add the standard `line-clamp`
    beside every `-webkit-line-clamp`; remove `cursor: help` and the tooltip-only `title`
    attributes listed in design §7.
  - **Definition of done:** a 300-character description truncates cleanly at every width
    and is fully readable on the run detail page; no `title` attribute is the sole access
    path to content.
  - _Requirements: R17.1, R17.2, R17.3, R17.4, R17.5_

- [x] **6.5 Phase gate**
  - _Requirements: R21.2, R21.3_

---

## Phase 7 — Compare information architecture *(highest risk)*

- [x] **7.1 Metric tiering**
  - Add `tier: "primary" | "secondary"` to `metricRows`; render the five primary rows, then
    a `<details>`-driven disclosure, then the secondary rows (hidden, **not unmounted**).
  - Persist the open state in `sessionStorage`.
  - **Definition of done:** five rows visible by default; all eleven `data-testid`
    `direction-*` targets still queryable; `Compare.test.tsx` green with at most the
    disclosure opened in the test setup.
  - _Requirements: R18.1, R18.2, R21.1_

- [x] **7.2 Best-cell marking**
  - Add a non-colour marker with an accessible name to `.summary-best`.
  - **Definition of done:** the winning cell is identifiable in greyscale;
    `compareSummary.test.ts` unchanged (the util is untouched).
  - _Requirements: R14.4, R18.4_

- [x] **7.3 Narrow-width representation**
  - Below 1024px: summary table first and expanded, each backend column collapsed into a
    `<details>` titled with backend name + status chip. Above: explicit
    `grid-template-columns: repeat(3, minmax(0, 1fr))`, no `overflow-x` fallback.
  - **Definition of done:** at 800px the page leads with the summary table and no column
    is lost; at 1280px the three columns render side by side; `Compare.layout.test.tsx`
    and `Compare.reattach.test.tsx` green.
  - _Requirements: R18.3, R18.5, R18.6_

- [x] **7.4 Phase gate**
  - **Definition of done:** all gates green, including a live three-backend sample compare
    (`Play sample runs`) driven end to end at 1280px and 800px.
  - _Requirements: R21.2, R21.3_

---

## Phase 8 — Navigation and charts

- [x] **8.1 Nav shape**
  - Remove the conditional "Run" nav item; add `aria-current="page"` and a non-colour
    active indicator; give the brand an accessible name independent of its icon; document
    `/artifacts` as intentionally unlinked.
  - **Definition of done:** nav has the same items on every route; `nav-home` and
    `nav-compare` test ids unchanged; the now-unused `nav-open-run` test id is removed from
    markup **and** from any test that referenced it, with the reason in the commit body.
  - _Requirements: R19.1, R19.2, R19.3, R19.4, R19.5, R21.4_

- [x] **8.2 Chart theming**
  - Theme the Recharts axes, grid, bars, and tooltip from tokens; move tick font size to
    the scale; add an accessible summary for the chart; replace the permanently disabled
    "Re-run (CLI)" button with static text.
  - **Definition of done:** the tooltip is dark and bordered; no inline colour or font-size
    literal remains in `TestResultsPanel`; no disabled-forever control remains.
  - _Requirements: R20.1, R20.2, R20.3, R20.4, R20.5_

- [x] **8.3 Phase gate**
  - _Requirements: R21.2, R21.3_

---

## Phase 9 — Guards

- [x] **9.1 Drift test**
  - Write `src/__tests__/styles.drift.test.ts` per design §9: raw spacing, raw type, raw
    colour, duplicate selectors, orphan classes in both directions, line budget.
  - Failure messages name file, line, and the offending value plus the token to use.
  - The dynamic-class allowlist is a single commented array.
  - **Definition of done:** the test passes on the migrated codebase; reintroducing
    `padding: 0.35rem` anywhere in `App.css` fails it with a message naming the line.
  - _Requirements: R22.1, R22.2, R22.3, R22.4, R22.5, R22.6, R22.8, R22.9_

- [x] **9.2 A11y invariant tests**
  - Add the three assertions from design §4.4 (one `h1` per page; every `<label>` resolves;
    every `role="tab"` resolves to a `role="tabpanel"`) across Home, Run, Compare,
    RunDetail.
  - **Definition of done:** tests pass; removing an `htmlFor` or an `aria-controls` makes
    one fail.
  - _Requirements: R22.7_

- [x] **9.3 Close out**
  - Update `BASELINE.md` with the after-state counts; confirm the `data-testid` diff vs
    `TESTIDS.txt` contains only additions plus the one documented removal from 8.1.
  - Record the resolved answers to design §12's open decisions in that section.
  - **Definition of done:** `App.css` ≤ 1,600 lines; zero raw values; zero orphans; all
    gates green; §12 has no unanswered row.
  - _Requirements: R6.5, R21.1, R22.9_

---

## Minimum defensible slice

If the whole plan is too long: **Phases 1, 3.3–3.4, and 4.** Deleting the dead sheet,
giving buttons a visible edge and destructive confirms a red one, and fixing the six
accessibility defects is the part a user or an auditor would actually notice. Phase 2
(tokens) without Phase 9 (guards) is worth doing but will decay; Phase 9 without Phase 2
cannot pass.

If even that is too long: **task 1.1 and task 4.2.** A stylesheet that no longer lies
about what it styles, and form labels that work.
