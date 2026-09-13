# Design — UI Refinement

**Spec ID:** `ui-refinement`
**Requirements:** [`requirements.md`](./requirements.md)
**Tasks:** [`tasks.md`](./tasks.md)

---

## 1. Overview

### 1.1 The central move

The UI does not need a design system. It has one — it just isn't load-bearing. Tokens are
declared in `index.css` and referenced by 29 of 237 spacing declarations; a content
max-width is declared and referenced by none. Everything else is a literal chosen at the
moment a component was written.

So this spec does not introduce a system. It **makes the existing one the only way to
express a value**, and then puts a test in front of the door:

```
  BEFORE                                   AFTER
  ──────                                   ─────
  index.css   6 tokens, 3 unused           styles/tokens.css   the only literals in the app
      │                                         │
      ▼                                         ▼
  App.css     2,160 lines                   App.css     ≤ 1,600 lines, tokens only
   ├─ 208 raw lengths                        ├─ 0 raw lengths        ─┐
   ├─ 14 font sizes                          ├─ 5 type steps          ├─ asserted by
   ├─ 7 radii                                ├─ 3 radii               │  styles.drift.test.ts
   ├─ 6 duplicate selectors                  ├─ 0 duplicates          │
   └─ ~25 classes styling nothing            └─ 0 orphans            ─┘
```

The three-line version of every decision below: **one source for values, one meaning per
colour, one border level per region.**

### 1.2 Design principles

1. **Tokens are the vocabulary, not a suggestion.** A value that cannot be expressed in
   tokens is a signal that the component is wrong, not that the scale is too coarse (R1.5).
2. **Colour carries meaning, never decoration.** After R3 there is no `--green`; there is
   `--intent-success`. A developer reaching for green to make a button prominent will find
   only `--intent-accent`, which is the correct answer.
3. **One border level per region.** Nested 1px borders with doubled padding are the single
   largest contributor to the "busy" reading of the current UI (R4).
4. **Half-ARIA is a defect, not a partial credit.** `role="tablist"` without keyboard
   support tells a screen-reader user to expect arrow keys that do nothing. Either complete
   the pattern or drop the role (R10.5).
5. **Nothing is enforced by prose.** Every constraint this spec states gets a test (R22),
   because a convention that lives in a spec is a convention that expires with the next
   contributor.
6. **Cosmetic refactors are the easiest place to break behaviour.** Hence frozen test ids,
   per-phase commits, and e2e green at every phase boundary (R21).
7. **Delete first, then restyle.** Every hour spent tokenizing a rule that styles a deleted
   page is an hour wasted — which is why Phase 1 is deletion and Phase 2 is tokens.

### 1.3 What this deliberately does not change

No Python. No `server.py`, no REST or WebSocket contract, no `types/index.ts` shape, no
hook signature, no polling interval, no run semantics. `tests/e2e/web` is not edited —
it is the control that proves the refactor was cosmetic.

---

## 2. Token architecture

### 2.1 File layout

```
src/
  styles/
    tokens.css        ← the ONLY file containing literals
    reset.css         ← box-sizing, margin/padding zeroing, media defaults
    base.css          ← html/body/headings/links/focus-visible
  App.css             ← component rules, tokens only
  main.tsx            ← imports tokens.css, reset.css, base.css, then App.css
```

`index.css` is deleted; its three unused breakpoint tokens go with it (R5.4). If `App.css`
cannot reach the 1,600-line budget by deletion alone, it splits into
`styles/components/*.css` imported from `App.css` — layout, forms, run, compare,
artifacts — but splitting is a last resort, not the goal.

### 2.2 The scales

```css
:root {
  color-scheme: dark;                        /* R15.1 */

  /* Spacing — 4px base */
  --space-0: 0;        --space-1: 0.25rem;   --space-2: 0.5rem;
  --space-3: 0.75rem;  --space-4: 1rem;      --space-5: 1.5rem;
  --space-6: 2rem;     --space-7: 3rem;

  /* Radius */
  --radius-sm: 4px;    --radius-md: 6px;     --radius-lg: 8px;
  --radius-full: 9999px;

  /* Type */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Fira Code", Menlo, Consolas, monospace;
  --text-xs:   0.6875rem;   /* 11px — uppercase labels, chips. Never running text. */
  --text-sm:   0.8125rem;   /* 13px — secondary, meta, log */
  --text-base: 0.875rem;    /* 14px — body */
  --text-md:   1rem;        /* 16px — panel/section titles */
  --text-lg:   1.25rem;     /* 20px — page titles */
  --leading-tight: 1.25; --leading-normal: 1.5; --leading-relaxed: 1.6;

  /* Layout */
  --content-max-width: 96rem;
  --measure: 68ch;
  --icon-sm: 14px; --icon-md: 16px;
}
```

**Mapping from today's values** (apply mechanically; accept the ±1–2px shifts, R1.6):

| Old | New | | Old | New |
| --- | --- | --- | --- | --- |
| `0.1rem`, `0.15rem`, `0.2rem` | `--space-1` | | `0.65rem`, `0.7rem`, `0.75rem` | `--text-xs` |
| `0.25rem`, `0.3rem`, `0.35rem` | `--space-1` | | `0.78rem`, `0.8rem`, `0.85rem` | `--text-sm` |
| `0.4rem`, `0.45rem`, `0.5rem`, `0.6rem` | `--space-2` | | `0.9rem`, `14px` | `--text-base` |
| `0.75rem` | `--space-3` | | `1rem`, `1.1rem` | `--text-md` |
| `1rem`, `1.25rem` | `--space-4` | | `1.2rem`, `1.25rem`, `1.4rem` | `--text-lg` |
| `1.5rem` | `--space-5` | | | |
| `2rem` | `--space-6` | | `2px`, `3px`, `4px` radius | `--radius-sm` |

Two judgement calls worth stating: `0.35rem` (the most common raw value, 30+ uses) rounds
**down** to `--space-1`, which tightens several strips by 1px; `1.25rem` rounds **up** to
`--space-4` in padding contexts and to `--text-lg` in type contexts.

### 2.3 Colour

```css
:root {
  /* Surfaces */
  --bg-canvas:  #0d1117;   --bg-surface: #161b22;   --bg-raised: #21262d;

  /* Foreground */
  --fg-default: #e6edf3;   /* 16.0:1 on canvas */
  --fg-muted:   #8b949e;   /*  6.2:1 on canvas, 4.95:1 on raised */

  /* Borders */
  --border-subtle:  #30363d;  /* dividers ONLY — 1.55:1, non-essential by definition */
  --border-default: #6e7681;  /* every interactive edge — 4.12 / 3.77 / 3.31:1 */

  /* Intent */
  --intent-accent:  #58a6ff;  /* primary actions, links, focus   7.49:1 on canvas */
  --intent-success: #3fb950;  /* pass, complete                  7.45:1 */
  --intent-danger:  #f85149;  /* fail, error, destructive        5.65:1 */
  --intent-warning: #d29922;  /* warn, awaiting, cancelling      7.50:1 */
  --intent-special: #bc8cff;  /* comparison grouping             7.51:1 */

  /* Categorical (backend identity only — NOT status, NOT action) */
  --cat-1: #f0883e;  /* CrewAI    */
  --cat-2: #58a6ff;  /* LangGraph */
  --cat-3: #bc8cff;  /* Claude Agent SDK */

  /* Tints — the only place rgba() is permitted (R22.4) */
  --tint-accent:  rgba(88, 166, 255, 0.15);
  --tint-success: rgba(63, 185, 80, 0.15);
  --tint-danger:  rgba(248, 81, 73, 0.12);
  --tint-warning: rgba(210, 153, 34, 0.15);
  --tint-special: rgba(188, 140, 255, 0.15);
}
```

All contrast figures are measured, not estimated. The important one is `--border-default`:
`#484f58`, the intuitive next step up from `#30363d`, only reaches **2.28:1** on canvas and
**1.84:1** on raised — still failing. `#6e7681` is the first value in this family that
clears 3:1 against all three surfaces.

`--cat-2` deliberately equals `--intent-accent` today. That collision is why R3.8 exists:
after this spec, LangGraph's blue is `--cat-2` and a primary button's blue is
`--intent-accent`, and the two can diverge without a search-and-replace.

### 2.4 What replaces the hue utilities

| Removed | Replacement |
| --- | --- |
| `.cyan` | `.text-accent` |
| `.green` | `.text-success` |
| `.red` | `.text-danger` |
| `.yellow` | `.text-warning` |
| `.blue` | `.text-accent` |
| `.dim`, `.text-dim`, `.muted` | `.text-muted` |

---

## 3. Component primitives

### 3.1 Buttons

Five variants, one size modifier. Every one gets `--border-default` as its edge.

| Variant | Fill | Foreground | Border | Use |
| --- | --- | --- | --- | --- |
| `.btn-primary` | `--intent-accent` | `--bg-canvas` (7.49:1) | accent | the one main action per view |
| `.btn-secondary` | `--bg-raised` | `--fg-default` | `--border-default` | everything else |
| `.btn-danger` | `--intent-danger` | `--bg-canvas` (5.65:1) | danger | destructive confirm only |
| `.btn-ghost` | transparent | `--fg-muted` | transparent | icon buttons, toolbar |
| `.btn-link` | none | `--intent-accent` | none | inline text action |

`.btn-sm` is the only size modifier and is defined **once** (R6.3). `.btn-warning` is
dead on arrival — zero call sites — and goes out with Phase 1's deletions.

Anchors styled as buttons (`a.btn-primary`, `a.btn-secondary`) currently duplicate the
entire declaration block. They collapse to a shared `.btn` base with
`:where(a, button).btn-*`, eliminating ~40 lines.

**Hover states** move from `opacity: 0.9` (which dims the text along with the fill) to an
explicit hover colour per variant.

### 3.2 Surfaces

```
.panel            bg-surface · 1px border-subtle · radius-lg · space-4   ← exactly one level
  .panel-header   text-xs · uppercase · fg-muted                          ← no border
  .panel-section  bg-raised · radius-md · space-3 · NO BORDER             ← inner grouping
```

The nesting audit (R4.3) resolves three cases:

| Location | Today | After |
| --- | --- | --- |
| `Home` → `RunList` | `.panel` wrapper + list chrome inside | `RunList` owns the panel; wrapper removed |
| `CompareColumn` → log/guardrails | `.panel` inside a column inside a grid | `.panel-section` |
| `RunDetail` Tests tab | `.panel` wrapper around `TestResultsPanel` | wrapper removed; panel lives in the component |

### 3.3 Chips and badges

`.chip` + `.chip-sm`/`.chip-md` already exist and are sound. The duplicate concepts
(`.badge`, `.status-chip`, `.run-list-sample-tag`, `.run-list-comparison-chip`,
`.agent-timeline-phase`) collapse onto `.chip` with intent modifiers
(`.chip-success`, `.chip-danger`, `.chip-warning`, `.chip-accent`, `.chip-neutral`),
and the status → intent mapping lives in **one** exported map:

```ts
// src/utils/statusIntent.ts
export const STATUS_INTENT = {
  running: "accent", complete: "success", complete_approved: "success",
  error: "danger", cancelled: "warning", cancelling: "warning",
  awaiting_human: "special", pending: "neutral", idle: "neutral",
} as const;
```

This is also what lets R22.5's dynamic-class allowlist be short and honest: one
`chip-${intent}` pattern instead of eleven `status-*` classes.

---

## 4. Accessibility patterns

### 4.1 Tabs (R10)

```tsx
const TABS = [["overview","Overview"],["activity","Activity"],
              ["artifacts","Artifacts"],["tests","Tests"]] as const;

<div role="tablist" aria-label="Run sections" onKeyDown={onTabKeyDown}>
  {TABS.map(([id, label]) => (
    <button key={id} role="tab" id={`tab-${id}`} aria-controls={`panel-${id}`}
            aria-selected={tab === id} tabIndex={tab === id ? 0 : -1}
            data-testid={`run-tab-${id}`} onClick={() => selectTab(id)}>
      {label}
    </button>
  ))}
</div>

<div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}
     tabIndex={0} data-testid={`run-tab-panel-${tab}`}>…</div>
```

`onTabKeyDown` handles `ArrowLeft`/`ArrowRight` (wrapping), `Home`, `End`, moving focus and
selection together. The hash sync in `selectTab`/`hashchange` is untouched.

`Artifacts` tabs and `CodeViewer` file tabs: **drop the tab semantics.** They are a
filter and an editor-style file switcher respectively; plain buttons with
`aria-pressed` is the honest markup and avoids three roving-tabindex implementations.

### 4.2 Dialog (R11)

`useFocusTrap(open, ref, onClose)` gains Escape handling, background-scroll locking, and
overlay-click dismissal via a `data-overlay` check. `CommandPalette` drops its local
Escape branch and passes `close`. `ConfirmModal` switches to `useId()` for
`aria-labelledby`/`aria-describedby` and gains the `tone` prop from R3.5.

### 4.3 Live regions (R12)

The current `aria-live="polite"` on the scrolling log announces every appended line — a
screen reader reading a build log in real time. Replace with:

```tsx
<p className="visually-hidden" role="status">
  {`${runStatus}. Phase ${monitor.phase}.`}
</p>
```

rendered once per run view and updated only when status or phase changes. The log itself
becomes a plain focusable scroll region (R13.1) with `aria-label="Activity log"`.

### 4.4 The invariants worth testing (R22.7)

Three assertions catch most regressions without a new dependency:

1. each page renders exactly one `<h1>`;
2. every `<label>` in the tree resolves to a form control (via `htmlFor` or nesting);
3. every `role="tab"` has an `aria-controls` that resolves to a `role="tabpanel"`.

---

## 5. Layout model

```
body
└── .app
    ├── nav.nav                     full-bleed, bg-surface, border-bottom
    └── main#main.main              padding-block: space-5
        └── .content                max-width: var(--content-max-width)
                                    margin-inline: auto
                                    padding-inline: space-5
            └── page                NO horizontal padding of its own (R5.1)
```

Breakpoints, stated once and used literally (R5.4):

| Name | Value | Effect |
| --- | --- | --- |
| narrow | `≤ 640px` | single column everywhere; nav wraps; strips wrap |
| medium | `≤ 1024px` | Compare shows the summary table as primary (R18.3); form grids single-column |
| wide | `> 1024px` | three Compare columns; two-column form grids |

`--bp-*` custom properties are deleted: they cannot be used in a media query condition, so
their presence implies a capability the file does not have.

---

## 6. Compare redesign (R18)

### 6.1 Metric tiering

```
PRIMARY   (always visible)          SECONDARY (inside <details>)
──────────────────────────          ───────────────────────────
Cost (USD)          ↓ lower          Phase                 —
Elapsed             ↓ lower          Tokens (est.)         ↑ higher
Tests passed        ↑ higher         Tasks completed       ↑ higher
Tests failed        ↓ lower          Tasks failed          ↓ lower
Files generated     ↑ higher         Guardrails passed     ↑ higher
                                     Guardrails failed     ↓ lower
                                     Retries               ↓ lower
   5 rows                               7 rows   = all 12 of metricRows
```

`metricRows` in `pages/Compare.tsx` gains a `tier: "primary" | "secondary"` field. The
table renders primary rows, then a `<tr>` containing the disclosure, then secondary rows
when open. Every existing `data-testid` stays on its row (R21.1); tests that assert on a
secondary row either open the disclosure or rely on the DOM presence — the rows are
**hidden, not unmounted**, which keeps `data-testid="direction-*"` queryable.

### 6.2 Narrow-width behaviour

Below `1024px`, three 320px-minimum columns stack — at which point the page is three
sequential run monitors, not a comparison. The summary table (already `min-width: 36rem`
with a sticky first column) is the better narrow representation, so:

- `≤ 1024px`: summary table first and expanded; each backend column collapsed into a
  `<details>` titled with the backend name and its status chip.
- `> 1024px`: current three-column layout, with an explicit `grid-template-columns:
  repeat(3, minmax(0, 1fr))` rather than `auto-fit` + `overflow-x` (R18.5).

### 6.3 Best-cell marking

`.summary-best` keeps its `--tint-success` background and adds a `▲`/`▼` marker with
`aria-label="best"`, so the winner survives greyscale, colour-blindness, and a
screenshot pasted into a doc (R14.4).

---

## 7. Italic, tooltip, and emoji inventory

**Italic** survives in exactly one place after R7.2: `.summary-failed-reason`, where the
text is a machine-produced error string. Everything else (`.empty-state`,
`.empty-state-title`'s `font-style: normal` override, which only exists to undo the
inherited italic) is removed.

**`title=` attributes** are kept only where they duplicate visible text for a truncated
element AND a non-hover path exists. Removed from: summary table cells (`cursor: help`
goes with them, R17.4), `.log-line` (the full message is in the expanded log), and
`.run-detail-title` (the full description is on the page).

**Emoji → lucide** (R16.2):

| Emoji | Where | Replacement |
| --- | --- | --- |
| `🤖` | `App.tsx` brand | `Bot` |
| `⚖` | `RunList` chip/toggle, `RunDetail` chip, `Compare` form summary | `Scale` |
| `✕` | `RunList` delete | `X` |
| `×` | `AlertBanner` dismiss | `X` |
| `▾` `▸` | `RunList` comparison toggle | `ChevronDown` / `ChevronRight` |
| `✓` `✗` `⚠` | `RunStatStrip`, `CompareColumn`, `GuardrailsPanel` | text form: `12 passed · 1 failed` |

The `✓`/`✗` case matters most: `"3✓ / 1✗ tests"` is announced as "3 check mark 1 ballot X
tests" or, on some platforms, as nothing at all.

---

## 8. Structure and navigation

### 8.1 Heading map (R8.3)

| Level | Use |
| --- | --- |
| `h1` | page title, one per route, `--text-lg` |
| `h2` | major region within a page (Compare summary, a run tab's main panel) |
| `h3` | panel title (`.panel-header`, `--text-xs` uppercase) |
| `h4` | subsection inside a panel |

Today's 21 `h3` + 11 `h4` mostly land correctly once an `h1` exists above them; the audit
is mechanical.

### 8.2 Nav (R19)

```
[icon] AI-Team        Home   Compare                    [⌘K / Ctrl K]
```

Fixed shape. No contextual "Run" item. Active item carries `aria-current="page"`, a weight
change, and a 2px bottom rule — not colour alone.

### 8.3 `/artifacts`

Stays a redirect target with **no** nav entry: artifacts are per-run and reached from a
run's Artifacts tab. `ArtifactsRedirect` keeps its behaviour; the route is documented in
`App.tsx` as intentionally unlinked.

---

## 9. Enforcement (R22)

`src/__tests__/styles.drift.test.ts` reads `src/App.css` plus `src/styles/*.css` and every
`src/**/*.tsx`, then asserts:

```ts
describe("stylesheet drift", () => {
  it("contains no raw spacing or radius values outside tokens.css", …)
  it("contains no raw font-size values outside tokens.css", …)
  it("contains no colour literals outside tokens.css", …)
  it("defines no selector twice in one file", …)
  it("has no CSS class that no component renders", …)
  it("has no rendered className that no CSS defines", …)
  it("keeps App.css under the line budget", …)
});
```

Two implementation notes that decide whether this test is useful or hated:

1. **Failure messages must name the offender**: `App.css:412  padding: 0.35rem  → use
   var(--space-1)`. A drift test whose output is `expected 3 to be 0` gets `.skip`-ed
   within a month.
2. **The dynamic-class allowlist is documentation.** Classes built at runtime
   (`chip-${intent}`, `log-${level}`, `phase-${state}`) live in one commented array in the
   test file. Adding a dynamic class means adding it there — which is exactly the review
   friction that keeps the pattern from spreading.

**Structural allowlist** (query/layout hooks with no visual rule of their own; task 1.4).
Keep in sync with `STRUCTURAL_ALLOWLIST` in `styles.drift.test.ts`:

`run-config-form`, `run-detail-header`, `tests-panel`, `activity-log-wrap`,
`home-empty`, `home-run-list`, `home-page`, `run-detail-page`, `run-detail-meta`,
`run-tab-overview`, `run-tab-activity`, `run-summary-demo-note`, `panel-inner`,
`run-list-panel`, `run-list-day-group`, `coverage-chart`, `test-failures`,
`command-palette-overlay`, `arch-panel`, `form-grid-backend`, `download-hint`,
`pytest-raw`, `adr-block`, `code-view-modes`, `btn`, `active`, `done`, `compact`.

**Scrollbar (task 4.7 / R15.3, R6.6).** `color-scheme: dark` is set on `:root`. A thin
`::-webkit-scrollbar` overlay is **kept** in `styles/responsive.css` so the gutter matches
`--bg-canvas` on overlay scrollbars; documented next to the rules in `App.css`.

Deliberately **not** enforced: rule-count limits, selector nesting depth, property order,
and anything a formatter would argue about.

---

## 10. Migration order and risk

| Phase | Risk | Why |
| --- | --- | --- |
| 1 Deletion | **Low** | Nothing rendered changes; verified by search before each removal |
| 2 Tokens | **Medium** | Every rule touched; ±1–2px shifts across the app are expected and accepted |
| 3 Colour | **Medium** | Visible: every primary button turns blue. Reversible in one token. |
| 4 A11y | **Low** | Additive attributes; tab keyboard handling is the only new logic |
| 5 Surfaces/layout | **Medium** | Panel de-nesting changes spacing in three places |
| 6 Icons | **Low** | Mechanical, but touches many files — keep it its own commit |
| 7 Compare IA | **High** | Real markup change in the most test-covered page |
| 8 Nav IA | **Low** | One conditional removed |
| 9 Guards | **Low** | Test-only, but will fail loudly until Phases 1–6 are complete |

**Order rationale.** Deletion first so no effort is spent tokenizing dead rules. Tokens
before colour so the colour swap is a token edit rather than 60 rule edits. A11y before
the IA work so the tab and dialog patterns are already correct when Compare's markup
moves. Guards last, because a drift test that cannot pass yet is a broken build.

Phases 7 and 8 are the only ones a reviewer could reasonably reject on taste; they are
last and independently revertable (R21.6).

---

## 11. Testing strategy

| Layer | What it covers | Command |
| --- | --- | --- |
| Type/lint | no unused imports, no `any` regressions | `npm run lint` |
| Build | TS project references still compile | `npm run build` |
| Unit (110 cases / 28 files) | component behaviour, unchanged by this spec except where R21.4 applies | `npm test` |
| Drift (new) | token discipline, orphans, duplicates, budget | `npm test` |
| A11y invariants (new) | one `h1`, labels resolve, tabs resolve | `npm test` |
| Contrast (new) | token pairs meet 4.5:1 / 3:1 | `node scripts/check-contrast.mjs` |
| E2E (Playwright, unchanged) | the app still works | `uv run pytest tests/e2e/web -m web_e2e` |

The e2e suite is the control for this entire spec: it selects by `data-testid` and
asserts on behaviour, so if it stays green while every rule in the stylesheet changes,
the refactor was genuinely cosmetic.

---

## 12. Open decisions

| # | Decision | Resolved |
| --- | --- | --- |
| 12.1 | Adopt `vitest-axe` (one dev dependency) for smoke a11y coverage? | **No** — three targeted invariants in `a11y.invariants.test.tsx` (§4.4) |
| 12.2 | Split `App.css` into `styles/components/*.css`? | **Yes** — deletion + tokens still exceeded 1,600 lines. Split to `styles/{run,compare,artifacts,responsive}.css` imported from `App.css` (602 lines) |
| 12.3 | Keep `.crewai/.langgraph/.claude-title` hues, or make backend colour positional? | **Keep the hues** as `--cat-1/2/3` |
| 12.4 | Compare secondary metrics: hidden rows vs unmounted rows? | **Hidden** — `hidden` attribute, not unmounted (R18.2) |
| 12.5 | Does the nav need a visible link to Artifacts? | **No** — `/artifacts` stays an unlinked redirect (§8.3) |
| 12.6 | `--content-max-width` at `96rem` | **Locked at `96rem`** |

Decisions already closed by the requirements, recorded here so they are not reopened
mid-implementation: primary accent becomes cyan with a dedicated danger intent (R3);
dark-only, no theme toggle (constraints); `data-testid` values frozen (R21.1); no new
runtime dependency (constraints).
