# Requirements — UI Refinement

**Spec ID:** `ui-refinement`
**Status:** Draft for implementation
**Owner:** Rick Zakharov
**Target:** `src/ai_team/ui/web/frontend` (React 19 + Vite + TypeScript)
**Created:** 2026-09-13
**Depends on:** nothing. This spec touches only the web frontend. No Python module,
no API contract, and no `data-testid` changes (R21).

---

## Introduction

The web UI has a design system. It is applied to roughly an eighth of the stylesheet.

`src/index.css` declares a spacing scale, a content max-width, and three breakpoints.
`src/App.css` — 2,160 lines — then uses `var(--space-*)` in **29** declarations and
hard-codes a length in **208** others, across 15 distinct raw values
(`0.15rem`, `0.2rem`, `0.3rem`, `0.35rem`, `0.45rem`, `0.6rem`, …). The same split shows
up in type (14 distinct `font-size` values, no scale), in radius (7 values), and in
surfaces (two competing empty-state classes, one of which renders italic body text).
`--content-max-width` is declared and never referenced, while `.main` and `.page-shell`
each apply their own 1.5rem inset, so the gutter is doubled and the measure is unbounded.

Underneath that is a layer of code that styles nothing: an entire Dashboard-era block
(`.dashboard-layout`, `.run-sidebar`, `.sidebar-collapsed`, `.sidebar-drawer-open`,
`.run-monitor-grid`, `.grid-2`, `.grid-3`, `.panel-toolbar`, `.empty-actions`,
`.raw-events`, and the `@media (max-width: 1100px)` block that exists only for it)
survives a page that no longer exists. Six selectors are defined twice with different
values — `.btn-sm` resolves to `0.35rem 0.75rem`, so the earlier `0.3rem 0.6rem` block
is a lie that a future reader will believe. `.muted` (`pages/RunDetail.tsx:337`) is used
and defined nowhere.

And underneath *that* are accessibility defects that are not stylistic:

- **No `<h1>` exists in the application.** Every page starts at `<h2>`.
- **`htmlFor` appears zero times in the codebase.** The four `<label>` elements in
  `RunConfigForm` and two in `Artifacts` are associated with nothing.
- The `RunDetail` tabs declare `role="tablist"`/`role="tab"`/`aria-selected` but have no
  `aria-controls`, no `role="tabpanel"`, and no arrow-key navigation. Partial ARIA tests
  worse than none.
- `--border` (`#30363d`) measures **1.55:1** against the page and **1.25:1** against
  input backgrounds — below the 3:1 WCAG 1.4.11 floor for control boundaries. Text
  contrast, by contrast, is fine everywhere (4.9:1–16:1); the palette is not the problem,
  the border role is.
- No `color-scheme: dark`, so native `<select>` popups, autofill, and scrollbars render
  light inside a dark application.

Finally, the UI speaks in two icon languages at once: `lucide-react` is a dependency and
is used in `CodeViewer`, `FileTreeViewer`, and `DownloadPanel`, while the nav, chips, and
stat strips use emoji (`🤖`, `⚖`, `✕`, `✓`, `✗`, `▾`, `▸`) — which render per-OS and are
announced literally ("balance scale") — and `public/icons.svg` is referenced by nothing.

### The rule this spec enforces

> A value that is not in the token set does not appear in the stylesheet, and a class
> that nothing renders does not stay in the file. Both are checked by a test, not by
> review (R22).

Every requirement below is either (a) collapsing a scattered set of values onto a named
token, (b) deleting something that renders nothing, (c) fixing a defect that a screen
reader or keyboard user hits, or (d) resolving an intent the UI states twice.

### What this spec adds

| Area | Gap today | Requirement |
| --- | --- | --- |
| Spacing | 208 raw declarations vs 29 tokenized; 15 distinct values | R1 |
| Type | 14 font sizes, no scale; `body { font-size: 14px }` in px | R2 |
| Colour intent | Green is both "primary action" and "pass"; destructive confirms are green | R3 |
| Surfaces | 54 `panel` usages, several nested → doubled borders and padding | R4 |
| Layout | `--content-max-width` unused; gutter applied twice | R5 |
| Stylesheet hygiene | ~15% of `App.css` styles nothing; 6 duplicate selectors | R6 |
| Empty states | Two competing systems; italic body text; doubled padding | R7 |
| Headings | No `<h1>` in the app | R8 |
| Form labels | Zero `htmlFor`; 6 unassociated `<label>`s | R9 |
| Tabs | Half-built ARIA, no keyboard support | R10 |
| Dialogs | No Escape, no overlay dismiss, static `id` | R11 |
| Alerts | No `role="alert"`; streaming log is `aria-live="polite"` | R12 |
| Scroll & motion | Scroll container not focusable; no reduced-motion guard | R13 |
| Non-text contrast | Control borders at 1.25–1.55:1 | R14 |
| Native controls | No `color-scheme: dark` | R15 |
| Icons | lucide + emoji + an unused SVG sprite, simultaneously | R16 |
| Truncation | JS `slice()` plus `title=` tooltips | R17 |
| Compare IA | 13 metric rows; comparison stacks vertically when narrow | R18 |
| Navigation IA | Nav item appears/disappears by route; orphan `/artifacts` | R19 |
| Charts | Recharts at library defaults inside a dark UI | R20 |
| Regression safety | 110 unit tests + Playwright e2e select on `data-testid` | R21 |
| Drift | Nothing prevents the next raw `0.35rem` | R22 |

### Design constraints (decided)

| Constraint | Decision |
| --- | --- |
| Scope | `src/ai_team/ui/web/frontend` only. No API change, no Python change, no new page. |
| Dependencies | No new runtime dependency. `lucide-react` is already present and is the icon system. At most one new **dev** dependency, and only for R22.7 (optional). |
| Test ids | `data-testid` values are **frozen**. Adding is allowed; renaming or removing is not (R21). |
| Theme | Dark only. This spec does **not** introduce a light theme; it makes the dark theme declare itself (R15). |
| Primary accent | Cyan (`#58a6ff`) becomes the primary action colour; green is reserved for success/pass; a new danger intent handles destructive confirms. **Decided — see R3.** |
| Behaviour | No change to run semantics, polling, WebSocket handling, or artifact loading. If a task needs that, it is out of scope. |
| Verification | `npm run lint && npm run build && npm test` green after every task; `pytest tests/e2e/web -m web_e2e` green at the end of each phase that touches markup. |

### Non-goals

- A light theme, a theme toggle, or `prefers-color-scheme` support. R15 declares the dark
  scheme to the browser; it does not add a second one.
- A component library, CSS-in-JS, Tailwind, or CSS Modules migration. The stylesheet stays
  a single hand-written sheet; this spec makes it obey its own tokens.
- New features, new pages, new metrics, or new API fields.
- Redesigning the Artifacts page beyond the cross-cutting requirements (R1–R17) that
  happen to touch it.
- Visual-regression snapshot infrastructure (Percy/Chromatic). R22 guards the *source*,
  not rendered pixels.

### Glossary

| Term | Definition |
| --- | --- |
| **Token** | A named CSS custom property in `src/styles/tokens.css` that is the only permitted source for a spacing, type, radius, or colour value. |
| **Raw value** | A length, colour, or font-size literal appearing outside `tokens.css`. R22 fails the build on one. |
| **Intent** | The meaning a colour carries: `accent`, `success`, `danger`, `warning`, `special`. Distinct from the surface it sits on. |
| **Surface** | A background level: `canvas` (page), `surface` (panel), `raised` (input/inset). |
| **Panel** | A bordered, padded region at exactly one nesting level (R4). |
| **Drift guard** | A vitest test that parses `App.css` and fails on a raw value, an orphan class, or a duplicate selector (R22). |
| **Orphan class** | A class defined in CSS that no `.tsx` file renders, or rendered in `.tsx` and defined in no CSS. |

---

## Requirements

### R1 — Single token source for spacing and radius

**User story:** As a developer adding a component, I want one place that answers "how much
padding," so that the answer is the same as the last person's answer.

**Acceptance criteria**

1.1 THE SYSTEM SHALL define all design tokens in a single file `src/styles/tokens.css`,
imported once from `src/main.tsx` before `App.css`, and SHALL reduce `src/index.css` to a
reset only (or delete it and fold the reset into `tokens.css`).

1.2 THE SPACING SCALE SHALL be exactly: `--space-0: 0`, `--space-1: 0.25rem`,
`--space-2: 0.5rem`, `--space-3: 0.75rem`, `--space-4: 1rem`, `--space-5: 1.5rem`,
`--space-6: 2rem`, `--space-7: 3rem`.

1.3 THE RADIUS SCALE SHALL be exactly: `--radius-sm: 4px` (chips, badges, tags),
`--radius-md: 6px` (controls, inputs, nested surfaces), `--radius-lg: 8px` (top-level
panels, modals), `--radius-full: 9999px`. The values `2px`, `3px`, and the one-off
`4px 4px 0 0` SHALL be removed.

1.4 NO `padding`, `margin`, `gap`, `inset`, `top/right/bottom/left`, or `border-radius`
declaration outside `tokens.css` SHALL contain a raw length, except: `0`, `auto`, `100%`,
percentage values, `1px`/`2px` border widths, and viewport-relative values for scroll
caps (`70vh` and similar).

1.5 WHERE a component needs a value between two steps, THE DEVELOPER SHALL choose the
nearer step rather than adding a token. New tokens require an explicit note in
`design.md` §2.

1.6 THE MIGRATION SHALL be value-preserving within one step: a `0.35rem` becomes
`--space-1` or `--space-2`, and any resulting visual change SHALL be accepted rather than
patched with a new token.

---

### R2 — Type scale

**User story:** As a reader, I want text sizes to look chosen rather than accumulated.

**Acceptance criteria**

2.1 THE TYPE SCALE SHALL be exactly five steps: `--text-xs: 0.6875rem` (uppercase
labels, chips — never running text), `--text-sm: 0.8125rem` (secondary and meta text),
`--text-base: 0.875rem` (body), `--text-md: 1rem` (panel and section titles),
`--text-lg: 1.25rem` (page titles).

2.2 THE SYSTEM SHALL define `--leading-tight: 1.25`, `--leading-normal: 1.5`,
`--leading-relaxed: 1.6`, and SHALL restrict `font-weight` to `400`, `500`, `600`. The
`700` weights SHALL be reduced to `600`.

2.3 THE SYSTEM SHALL set `html { font-size: 100% }` and express the body size as
`font-size: var(--text-base)`, replacing `body { font-size: 14px }`, so that a user's
browser font-size preference scales the interface.

2.4 NO `font-size` declaration outside `tokens.css` SHALL contain a raw value; every one
SHALL reference a `--text-*` token or `inherit`.

2.5 THE SYSTEM SHALL define `--font-sans` and `--font-mono` tokens and SHALL replace every
inline font stack (`"SF Mono", "Fira Code", monospace` appears in at least three rules).

2.6 HEADING ELEMENTS SHALL derive their size from the scale in one place (a single
`h1, h2, h3, h4` block), not from per-component overrides.

---

### R3 — Colour roles and semantic intent

**User story:** As a user about to click a green button, I want green to mean the same
thing it meant on the previous screen.

**Acceptance criteria**

3.1 THE SYSTEM SHALL express colour as **surface**, **foreground**, and **intent** roles,
and component rules SHALL reference role tokens only — never a raw hex and never a hue
token (`--cyan`, `--green`) directly:

| Role | Value | Use |
| --- | --- | --- |
| `--bg-canvas` | `#0d1117` | page |
| `--bg-surface` | `#161b22` | panels, nav, modals |
| `--bg-raised` | `#21262d` | inputs, insets, hover fills |
| `--fg-default` | `#e6edf3` | body text |
| `--fg-muted` | `#8b949e` | secondary text |
| `--border-subtle` | `#30363d` | dividers and separators **only** |
| `--border-default` | `#6e7681` | every interactive boundary (R14) |
| `--intent-accent` | `#58a6ff` | primary actions, links, focus |
| `--intent-success` | `#3fb950` | pass, complete |
| `--intent-danger` | `#f85149` | fail, error, destructive |
| `--intent-warning` | `#d29922` | warn, awaiting, cancelling |
| `--intent-special` | `#bc8cff` | comparison grouping |

3.2 `.btn-primary` SHALL use `--intent-accent` as its fill with `--bg-canvas` as its
foreground (measured 7.49:1), replacing the current green fill.

3.3 THE SYSTEM SHALL add a `.btn-danger` variant filled with `--intent-danger` and
`--bg-canvas` foreground (measured 5.65:1).

3.4 `--intent-success` SHALL NOT be used as the fill of any action button after this
spec. It remains available for status chips, badges, log lines, and the "best" cell tint.

3.5 `ConfirmModal` SHALL accept a `tone: "default" | "danger"` prop and SHALL render its
confirm button as `.btn-danger` when `tone="danger"`. THE "Delete run?" AND "Stop run?"
confirmations SHALL pass `tone="danger"`.

3.6 THE HUE ALIASES `--cyan`, `--green`, `--red`, `--yellow`, `--blue`, `--magenta`,
`--orange` SHALL be removed from the stylesheet after migration, along with the utility
classes `.cyan`, `.green`, `.red`, `.yellow`, `.blue` that name a colour rather than a
meaning. Call sites SHALL move to intent-named utilities (`.text-success`,
`.text-danger`, `.text-warning`, `.text-accent`, `.text-muted`).

3.7 `.dim` and `.text-dim` SHALL collapse into a single `.text-muted`, and the orphan
`.muted` at `pages/RunDetail.tsx:337` SHALL resolve to it.

3.8 THE BACKEND TITLE COLOURS (`.crewai-title` orange, `.langgraph-title` cyan,
`.claude-title` magenta) SHALL be retained as a categorical set but SHALL be redefined in
terms of a documented `--cat-1/2/3` categorical ramp, so that the accent hue is not doing
double duty as both "primary action" and "LangGraph".

---

### R4 — Surface and nesting rules

**User story:** As a user, I want to see one box where there is one thing, not a box
inside a box.

**Acceptance criteria**

4.1 THE SYSTEM SHALL define exactly one bordered surface primitive, `.panel`
(`--bg-surface`, `1px solid var(--border-subtle)`, `--radius-lg`, `--space-4` padding).

4.2 A `.panel` SHALL NOT contain another `.panel`. WHERE a region inside a panel needs
separation, it SHALL use `.panel-section` — background and padding, **no border, no
radius** — or a `1px solid var(--border-subtle)` rule.

4.3 THE FOLLOWING nestings SHALL be resolved: `Home` wrapping `RunList` in a `.panel`
when `RunList` renders its own chrome; `CompareColumn` rendering `.panel` children inside
a column that is itself inside `.compare-grid`; `RunDetail`'s Tests tab wrapping
`TestResultsPanel` in a `.panel`.

4.4 THE ORPHAN CLASS `.panel-nested` (used in `RunConfigForm`, defined nowhere) SHALL
either be defined as `.panel-section` per 4.2 or removed from the markup.

4.5 THE SYSTEM SHALL NOT introduce `box-shadow` for elevation. Borders and background
levels carry hierarchy in this UI; the single existing drawer shadow may remain or be
removed with the dead drawer code (R6.1).

---

### R5 — Layout container and gutters

**User story:** As a user on a wide monitor, I want a line of text to end before the edge
of the screen.

**Acceptance criteria**

5.1 THE CONTENT GUTTER SHALL be applied in exactly one place. `.main` SHALL own block
padding and the horizontal inset; `.page-shell`, `.home-page`, `.compare-page`, and
`.run-detail-page` SHALL NOT re-apply `padding-left`/`padding-right`.

5.2 THE SYSTEM SHALL apply `--content-max-width` to the content container with
`margin-inline: auto`, so content stops expanding on ultrawide displays. The token SHALL
be reduced from `120rem` to a value that produces a usable measure (design §5 specifies
`96rem`), and the Compare grid MAY opt out via an explicit `--width-wide` escape.

5.3 PROSE BLOCKS (page header descriptions, `HowItWorks`, empty-state hints) SHALL be
capped at `--measure: 68ch`.

5.4 THE BREAKPOINT TOKENS in `index.css` (`--bp-narrow`, `--bp-laptop`, `--bp-desktop`)
SHALL either be used by every media query or be deleted. Custom properties cannot appear
in a media query condition, so THE SYSTEM SHALL settle on documented literal breakpoints
in `design.md` §5 and remove the misleading tokens.

5.5 THE STYLESHEET SHALL contain at most **one** `@media` block per breakpoint. The two
separate `@media (max-width: 900px)` blocks (App.css:978 and :1493) SHALL be merged.

---

### R6 — Stylesheet hygiene

**User story:** As the next person to read this file, I want everything in it to do
something.

**Acceptance criteria**

6.1 THE SYSTEM SHALL delete every rule that styles no rendered class, including at
minimum: `.dashboard`, `.dashboard-header`, `.dashboard-empty`, `.dashboard-page`,
`.dashboard-alerts`, `.dashboard-layout`, `.sidebar-collapsed`, `.sidebar-drawer-open`,
`.sidebar-toggle`, `.run-sidebar`, `.run-monitor`, `.run-monitor-grid`, `.grid-2`,
`.grid-3`, `.panel-toolbar`, `.panel-collapsed-hint`, `.empty-actions`, `.raw-events`,
`.demo-helper`, `.btn-warning`, `a.btn-warning`, `.run-list-assignment`,
`.run-list-date`, `.run-list-meta`,
`.run-list-delete`, `.run-meta-row`, `.run-meta-date`, `.run-complete-actions`,
`.agent-row-active`, `.code-search-hit` (if unreachable), and the
`@media (max-width: 1100px)` block that targets only deleted classes.

6.2 EACH DELETION SHALL be verified by a repository-wide search for the class name in
`.tsx`, `.ts`, and `.py` (the e2e tests select by `data-testid`, but a CSS class may
appear in a Playwright selector) before removal.

6.3 THE SYSTEM SHALL resolve every duplicate selector block, keeping one definition each
for `.btn-sm`, `.hitl-payload`, `.run-list-item`, `.run-list-item-wrap`,
`.summary-table th, .summary-table td`, and `.artifacts-controls select`. WHERE the two
definitions disagree, the later (winning) value SHALL be kept and the earlier deleted.

6.4 THE SYSTEM SHALL add a definition for every class rendered but not styled that is
intended to carry style (`.empty-state-icon`, `.panel-nested`, `.muted`,
`.how-it-works-cost`, `.compact`), and SHALL remove from markup any that is not
(`.run-config-form`, `.run-detail-header`, `.tests-panel`, and similar structural hooks
may remain **only** if `design.md` §9 lists them as intentional test/query hooks).

6.5 AFTER MIGRATION `App.css` SHALL be **≤ 1,600 lines** and SHALL be split into
`src/styles/` partials imported by `App.css` (design §2.4) if it exceeds that.

6.6 THE SYSTEM SHALL remove the `::-webkit-scrollbar` block if R15's `color-scheme`
produces an acceptable native scrollbar; otherwise it SHALL be kept and documented as a
deliberate override.

---

### R7 — Empty, loading, and status text

**User story:** As a user hitting an empty panel, I want one consistent answer to "what
happened and what do I do."

**Acceptance criteria**

7.1 THE SYSTEM SHALL retain exactly one empty-state implementation: the `EmptyState`
component with `.empty-state-block`. THE CLASS `.empty-state` (italic, centred) SHALL be
deleted.

7.2 NO BODY TEXT in the application SHALL be italic. `font-style: italic` SHALL survive
only where it marks a quoted or machine-generated string, and `design.md` §7 SHALL list
every surviving instance.

7.3 THE ELEVEN `EmptyState` CALL SITES passing `className="empty-state"` — `AgentTable`,
`GuardrailsPanel`, `RunArtifactsPanel`, `RunList` ×2, `CompareColumn` ×2,
`FileTreeViewer` ×2, `Artifacts` ×2 — SHALL stop doing so, removing the doubled padding.
THE TWO `Artifacts` SITES additionally pass `"empty-state panel"`, stacking an italic
centred block inside a bordered panel; they SHALL keep only the panel.

7.4 THE NINE DIRECT USES of the deleted class — `TestResultsPanel` ×2,
`ArchitecturePanel` ×2, `CodeViewer` ×2, `ActivityLog`, `RunArtifactsPanel`, `Artifacts` —
SHALL be converted to `EmptyState` or `LoadingState`. Four of them are loading states
wearing an empty-state class; those SHALL become `LoadingState`.

7.5 `EmptyState` SHALL render its optional `icon` as a lucide icon (R16), not a string
emoji, and `.empty-state-icon` SHALL be styled or the prop removed.

---

### R8 — Document structure and headings

**User story:** As a screen-reader user, I want the page to tell me what it is.

**Acceptance criteria**

8.1 EVERY ROUTE SHALL render exactly one `<h1>`: Home ("Runs"), Run ("Run pipeline"),
Compare ("Compare backends"), RunDetail (the run description or id), Artifacts.

8.2 THE `<h1>` SHALL be styled at `--text-lg`; the visual size SHALL NOT increase merely
because the element changed.

8.3 HEADING LEVELS SHALL descend without skipping: page `<h1>` → panel `<h2>` or
`<h3>` consistently. `design.md` §8 SHALL state the chosen mapping, and it SHALL be
applied uniformly (21 `<h3>` and 11 `<h4>` exist today with no stated rule).

8.4 THE NAV SHALL be the sole `<nav aria-label="Main">`, and the brand link SHALL NOT be
a heading.

8.5 THE SYSTEM SHALL add a "Skip to content" link as the first focusable element,
targeting `<main id="main">`.

---

### R9 — Form control labelling

**User story:** As a keyboard or screen-reader user, I want to know what a select
controls, and I want clicking its label to focus it.

**Acceptance criteria**

9.1 EVERY `<label>` SHALL be associated with its control, either by `htmlFor` + `id` or
by wrapping the control. THE CODEBASE currently contains **zero** `htmlFor` attributes.

9.2 THE CONTROLS at `components/RunConfigForm.tsx:65` (Team Profile),
`:90` (Complexity), `:106` (Project Description), `:160` (Backend), and
`pages/Artifacts.tsx:178`, `:195` SHALL each receive a stable, unique `id`. WHERE a
component can render twice on one page, the id SHALL be derived from `useId()`.

9.3 HELPER TEXT (`.form-helper`, `.backend-key-hint`, `.estimate-helper`) SHALL be
associated with its control via `aria-describedby`.

9.4 EVERY CONTROL WITHOUT A VISIBLE LABEL SHALL keep an `aria-label`; the existing ones
in `RunList` and `ActivityLog` SHALL be preserved.

9.5 THE `AutoGrowTextarea` SHALL forward `id` and `aria-describedby` to its underlying
`<textarea>`.

9.6 WHERE A BUTTON is disabled to communicate a precondition, the reason SHALL be in text
(`showDisabledHint` already does this for Run/Compare) and SHALL be referenced by
`aria-describedby` rather than living only as an adjacent paragraph.

---

### R10 — Tab pattern

**User story:** As a keyboard user on a run page, I want the arrow keys to move between
Overview / Activity / Artifacts / Tests.

**Acceptance criteria**

10.1 EACH TAB in `RunDetail` SHALL carry `id`, `aria-controls` pointing at its panel, and
`aria-selected`; each panel SHALL carry `role="tabpanel"`, `aria-labelledby`, and
`tabIndex={0}`.

10.2 THE TABLIST SHALL implement roving tabindex: the selected tab has `tabIndex={0}`,
the rest `tabIndex={-1}`.

10.3 WHEN the tablist has focus, THE SYSTEM SHALL handle `ArrowLeft`, `ArrowRight`,
`Home`, and `End`, moving selection and focus together, wrapping at the ends.

10.4 THE URL HASH SYNC (`#activity`, `#artifacts`, `#tests`) SHALL be preserved exactly,
including `hashchange` handling and `replaceState` on selection.

10.5 THE SAME PATTERN SHALL be applied to the `.artifacts-tabs` in `pages/Artifacts.tsx`
and the `.code-tabs` in `CodeViewer`, or those SHALL drop their tab semantics and remain
plain buttons — whichever `design.md` §6.1 specifies, but not the current half state.

---

### R11 — Dialog pattern

**User story:** As a user who opened a confirmation by mistake, I want Escape to close it.

**Acceptance criteria**

11.1 `useFocusTrap` SHALL handle `Escape` and invoke an `onClose` callback, so that every
consumer inherits the behaviour. `CommandPalette`'s local Escape handling SHALL be
removed in favour of it, with no change to its behaviour.

11.2 `ConfirmModal` SHALL close on `Escape` and on overlay click (never on click inside
the card), and the overlay SHALL carry `aria-hidden`-safe markup — the dialog SHALL NOT
be a descendant of an `aria-hidden` node.

11.3 THE DIALOG TITLE ID SHALL be generated with `useId()` rather than the static
`id="confirm-title"`.

11.4 `ConfirmModal` SHALL reference its message via `aria-describedby`.

11.5 FOCUS SHALL return to the invoking element on close — `useFocusTrap` already does
this and SHALL be preserved under the refactor.

11.6 THE DIALOG SHALL prevent background scroll while open.

---

### R12 — Alerts and live regions

**User story:** As a screen-reader user, I want to hear that the API is unreachable, and
I do not want to hear every line of a streaming log.

**Acceptance criteria**

12.1 `AlertBanner` SHALL render `role="alert"` for the `error` variant and
`role="status"` for `warning`/`info`.

12.2 THE ACTIVITY LOG SHALL NOT announce every appended line. `aria-live` SHALL be
removed from the scrolling container; instead a visually-hidden `role="status"` region
SHALL announce **phase and status transitions only** (for example "Phase: implementation",
"Run complete").

12.3 THE `ariaLive` PROP on `ActivityLog` SHALL be removed or repurposed, and its call
sites in `RunDetail` updated.

12.4 THE HITL BANNER ("paused for human review") SHALL be announced via `role="alert"`,
since it is the one state that blocks progress.

12.5 THE SYSTEM SHALL add a `.visually-hidden` utility (clip-path technique) and SHALL
use it for the live region and the skip link (R8.5).

---

### R13 — Focus, scrollable regions, and motion

**User story:** As a keyboard user, I want to be able to scroll the log I can see.

**Acceptance criteria**

13.1 EVERY SCROLLABLE REGION that is not otherwise focusable SHALL carry `tabIndex={0}`
and an accessible name: `.activity-log`, `.guardrails-panel`, `.code-body`,
`.artifacts-tree-panel`, `.hitl-payload`, `.failure-error`, `.failure-trace`,
`.markdown-preview`, `.code-highlight-pre`.

13.2 THE `:focus-visible` OUTLINE SHALL be preserved (`2px solid var(--intent-accent)`,
`outline-offset: 2px`) and SHALL be verified to remain visible against `--bg-raised`.

13.3 THE SYSTEM SHALL wrap every animation and transition in a
`@media (prefers-reduced-motion: reduce)` guard that disables it, including
`.loading-spinner`'s `spin` keyframes and the `transition: all 0.15s` declarations.

13.4 `transition: all` SHALL be replaced with explicit property lists.

13.5 THE `CodeViewer` element carrying `role="button"` + `tabIndex={0}` SHALL become a
real `<button>` unless `design.md` §6.3 records why it cannot.

13.6 MINIMUM HIT TARGET for icon-only controls (`.run-list-delete-icon`,
`.alert-dismiss`, `.code-tab-close`) SHALL be 24×24 CSS px, met by padding rather than by
growing the glyph.

13.7 THE `.run-list-delete-icon` SHALL remain reachable without hover: its
`opacity: 0` default already lifts on `:focus-within`, which SHALL be preserved, and it
SHALL NOT be `visibility: hidden` or `display: none` at any point.

---

### R14 — Non-text contrast

**User story:** As a user, I want to see where the input field ends.

**Acceptance criteria**

14.1 EVERY INTERACTIVE BOUNDARY — input, select, textarea, button, focusable card,
tab underline — SHALL use `--border-default` (`#6e7681`), measured **4.12:1** against
`--bg-canvas`, **3.77:1** against `--bg-surface`, and **3.31:1** against `--bg-raised`,
all above the WCAG 1.4.11 3:1 floor.

14.2 `--border-subtle` (`#30363d`, 1.42–1.55:1) SHALL be used **only** for non-essential
dividers: table row rules, panel borders, separators. A divider that is the only thing
distinguishing two interactive regions is not non-essential.

14.3 STATUS CHIPS SHALL NOT rely on their 20%-alpha background alone to be perceived;
each SHALL retain its intent-coloured foreground text, which already clears 4.5:1.

14.4 THE `summary-best` HIGHLIGHT SHALL not encode "best" by background tint alone; it
SHALL add a non-colour cue (a `▲`/`▼` marker with an accessible name, or a `<strong>`),
since the existing `directionHint` explains the direction but not which cell won.

14.5 A SHORT SCRIPT (`scripts/check-contrast.mjs` or a vitest case) SHALL assert the
foreground/background pairs in `tokens.css` meet 4.5:1 for text and 3:1 for boundaries,
so a future palette edit cannot silently regress them.

---

### R15 — Native control theming

**User story:** As a user, I want the `<select>` dropdown to be dark like the rest of it.

**Acceptance criteria**

15.1 `:root` SHALL declare `color-scheme: dark`.

15.2 AFTER 15.1, THE SYSTEM SHALL re-evaluate the `::-webkit-scrollbar` override (R6.6)
and the explicit background on `input`, `select`, and `textarea`.

15.3 `input[type="search"]` SHALL have its platform decorations either kept consistently
or reset consistently across the three places it is used (`RunList`, `ActivityLog`,
`CodeViewer` search).

15.4 `accent-color: var(--intent-accent)` SHALL be set for checkboxes (the auto-scroll
toggle in `ActivityLog`).

---

### R16 — One icon system

**User story:** As a user, I want the icons to look like they came from the same place.

**Acceptance criteria**

16.1 `lucide-react` — already a dependency, already used in `CodeViewer`,
`FileTreeViewer`, and `DownloadPanel` — SHALL be the only icon source.

16.2 EVERY DECORATIVE EMOJI SHALL be replaced by a lucide icon with `aria-hidden="true"`:
`🤖` (`App.tsx` brand), `⚖` (`RunList`, `RunDetail`, `Compare` form summary), `✕`
(`RunList` delete), `▾`/`▸` (`RunList` comparison toggle), `×` (`AlertBanner` dismiss).

16.3 WHERE AN EMOJI CARRIES MEANING IN TEXT — `✓`/`✗`/`⚠` in `RunStatStrip`,
`CompareColumn`, and `GuardrailsPanel` — THE SYSTEM SHALL replace it with an icon plus a
text label, or with a plain-text form that a screen reader reads correctly
(`3 passed / 1 failed`), never a bare glyph.

16.4 ICON SIZE SHALL come from a token set (`--icon-sm: 14px`, `--icon-md: 16px`), and
icons SHALL inherit `currentColor`.

16.5 `public/icons.svg`, referenced by nothing, SHALL be deleted.

16.6 THE `⌘K` HINT in the nav SHALL become a real `<button>` that opens the command
palette, SHALL show `⌘K` on Apple platforms and `Ctrl K` elsewhere (detected once at
module scope), and SHALL carry an accessible name ("Open command palette").

---

### R17 — Truncation and overflow

**User story:** As a user on a laptop, I want a long run description to end cleanly, and
I do not want the only way to read it to be hovering with a mouse.

**Acceptance criteria**

17.1 TEXT SHALL NOT be truncated in JavaScript for display purposes. `String.slice()`
calls that shorten user-visible strings — `pages/RunDetail.tsx` (title, 80 chars),
`CompareColumn`/`Compare` form summary (48), `CommandPalette` (40) — SHALL be replaced by
CSS (`text-overflow: ellipsis` or `line-clamp`). `slice()` remains correct for
`useDocumentTitle` and for hashes.

17.2 `-webkit-line-clamp` SHALL be accompanied by the standard `line-clamp` property.

17.3 A `title` ATTRIBUTE SHALL NOT be the only way to read truncated content. WHERE the
full text matters, it SHALL be reachable by a non-hover means (the run detail page, a
disclosure, or a wrapping layout at wider widths).

17.4 `cursor: help` ON TABLE CELLS SHALL be removed; the summary table SHALL wrap or
expand rather than rely on tooltips.

17.5 EVERY HORIZONTALLY SCROLLING CONTAINER SHALL be focusable per R13.1 and SHALL NOT
cause the page body to scroll horizontally at any width ≥ 320px.

---

### R18 — Compare information architecture

**User story:** As someone reading a three-backend comparison, I want the four numbers
that matter first, and I do not want the comparison to become a vertical list.

**Acceptance criteria**

18.1 THE COMPARISON SUMMARY TABLE SHALL show five primary rows by default — **Cost
(USD)**, **Elapsed**, **Tests passed**, **Tests failed**, **Files generated** — with the
remaining seven (Phase, Tokens (est.), Tasks completed, Tasks failed, Guardrails passed,
Guardrails failed, Retries) inside a `<details>` disclosure labelled "All metrics".
Five plus seven SHALL account for all twelve rows in `metricRows`; no row is dropped.

18.2 THE DISCLOSURE STATE SHALL persist for the session only (`sessionStorage`), and the
`data-testid` attributes of every existing row SHALL be preserved (R21) — a collapsed row
SHALL still be in the DOM or the disclosure SHALL be open by default in tests.

18.3 BELOW the three-column breakpoint, THE COMPARE VIEW SHALL present the summary table
as the primary representation rather than three stacked columns, since stacked columns are
not a comparison. The columns SHALL remain reachable (a per-backend disclosure or a link
to each run).

18.4 THE EXISTING `UNDERPOWERED`/claim-discipline posture of the project SHALL be
reflected: the "best" cell highlight SHALL carry a non-colour marker (R14.4) and the
verdict line SHALL remain visually subordinate to the table, not styled as a conclusion
banner.

18.5 THE `compare-grid` SHALL NOT rely on `overflow-x: auto` to make three columns fit;
its column count SHALL be explicit per breakpoint.

18.6 NO CHANGE to comparison semantics, reattachment behaviour (`localStorage`
`ai-team-compare-active`), preflight confirmation, or the WebSocket wiring.

---

### R19 — Navigation information architecture

**User story:** As a user, I want the navigation to be the same shape on every page.

**Acceptance criteria**

19.1 THE NAV SHALL have a fixed set of items. The conditional "Run" item that appears
only when a run is open (`App.tsx:32–42`) SHALL be removed; the open run is already
reachable from Home and from the run page's own header.

19.2 WHERE a breadcrumb is needed on the run detail page, it SHALL live in the page
header (the existing "All runs" link), not in the global nav.

19.3 THE `/artifacts` ROUTE SHALL either gain a nav entry or remain a redirect target
only; `design.md` §8.3 SHALL state which, and `ArtifactsRedirect` SHALL be consistent
with it.

19.4 THE ACTIVE NAV ITEM SHALL be indicated by more than colour (weight or an underline),
and SHALL carry `aria-current="page"`.

19.5 THE BRAND SHALL link to `/` and SHALL carry an accessible name that does not depend
on the icon.

---

### R20 — Chart theming

**User story:** As a user, I want the coverage chart to belong to the page it is on.

**Acceptance criteria**

20.1 THE RECHARTS COMPONENTS in `TestResultsPanel` SHALL be themed from tokens: axis
`stroke`/`tick` at `--fg-muted`, grid at `--border-subtle`, bar fill at
`--intent-accent`, and a `contentStyle`/`itemStyle` on `<Tooltip>` using `--bg-surface`,
`--border-default`, and `--fg-default` — the default white tooltip SHALL NOT ship.

20.2 AXIS AND TICK FONT SIZES SHALL come from the type scale, not the inline
`tick={{ fontSize: 11 }}`.

20.3 COVERAGE BARS SHALL encode value by length only; WHERE a threshold colour is added,
a legend or label SHALL state the threshold.

20.4 THE PERMANENTLY DISABLED "Re-run (CLI)" BUTTON SHALL be replaced by static text
(for example `Re-run from the CLI: uv run …`), since a control that can never be
activated is not a control.

20.5 THE CHART CONTAINER SHALL have an accessible summary (a caption or
`aria-label` stating what is plotted and the overall coverage figure).

---

### R21 — Regression safety

**User story:** As the maintainer, I want to know that a cosmetic refactor did not break
the e2e suite.

**Acceptance criteria**

21.1 NO `data-testid` VALUE SHALL be renamed or removed. Adding new ones is permitted.
The Playwright suite (`tests/e2e/web`, `-m web_e2e`) and 110 vitest cases across 28 files
select on them.

21.2 AFTER EVERY TASK, `npm run lint && npm run build && npm test` SHALL pass from
`src/ai_team/ui/web/frontend`.

21.3 AFTER EVERY PHASE that changes markup, `uv run pytest tests/e2e/web -m web_e2e`
SHALL pass.

21.4 WHERE A TEST asserts on a class name, a colour, or a truncated string that this spec
changes, the test SHALL be updated in the same task as the change, with the reason stated
in the commit body — never by weakening the assertion to a substring match.

21.5 NO CHANGE to `src/ai_team/ui/web/server.py`, the REST/WebSocket contract, the
`types/index.ts` shapes, or any hook's return signature, except where a requirement here
names one explicitly (R12.3).

21.6 EACH PHASE SHALL be a separate commit (or PR) that builds and tests green on its
own, so any phase can be reverted independently.

---

### R22 — Drift guards

**User story:** As the maintainer, I want the next raw `0.35rem` to fail in CI, not in a
review comment six weeks later.

**Acceptance criteria**

22.1 THE SYSTEM SHALL add `src/__tests__/styles.drift.test.ts`, running under the existing
vitest suite, that parses the stylesheet sources and asserts:

22.2 **No raw spacing.** No `padding`, `margin`, `gap`, or `border-radius` declaration
outside `tokens.css` contains a raw length, per the R1.4 allowlist.

22.3 **No raw type.** Every `font-size` outside `tokens.css` references a `--text-*` token
or `inherit`.

22.4 **No raw colour.** No hex literal, `rgb()`, or `rgba()` outside `tokens.css`, except
`rgba(…)` alpha tints derived in a documented `--tint-*` token block.

22.5 **No orphan classes, in either direction.** Every class selector defined in CSS
appears in at least one `.tsx`; every `className` literal in `.tsx` is defined in CSS.
Dynamic patterns (`status-${status}`, `log-${level}`) SHALL be covered by an explicit,
commented allowlist in the test — the allowlist is the documentation of every dynamic
class in the app.

22.6 **No duplicate selectors.** No selector text is defined twice in the same file.

22.7 *(Optional, one dev dependency)* WHERE the team accepts `vitest-axe`, smoke a11y
assertions SHALL run against `Home`, `RunDetail`, `Compare`, and `ConfirmModal`. WHERE it
does not, targeted invariant tests SHALL assert instead: exactly one `<h1>` per page,
every `<label>` resolves to a control, every `role="tab"` has a matching `role="tabpanel"`.

22.8 THE DRIFT TEST SHALL fail with a message naming the file, line, and offending value —
a test that says only "expected 0 to be 1" will be disabled by the next person in a hurry.

22.9 THE STYLESHEET LINE BUDGET (R6.5) SHALL be asserted by the same test.

---

## Traceability summary

| Requirement | Primary files |
| --- | --- |
| R1, R2, R3 | `src/styles/tokens.css` (new), `src/App.css`, `src/index.css` |
| R4, R5, R6, R7 | `src/App.css`, `components/EmptyState.tsx`, `pages/*.tsx` |
| R8, R9 | `pages/*.tsx`, `components/RunConfigForm.tsx`, `components/AutoGrowTextarea.tsx` |
| R10 | `pages/RunDetail.tsx`, `pages/Artifacts.tsx`, `components/CodeViewer.tsx` |
| R11 | `hooks/useFocusTrap.ts`, `components/ConfirmModal.tsx`, `components/CommandPalette.tsx` |
| R12 | `components/AlertBanner.tsx`, `components/ActivityLog.tsx`, `pages/RunDetail.tsx` |
| R13 | `src/App.css`, `components/ActivityLog.tsx`, `components/GuardrailsPanel.tsx`, `components/CodeViewer.tsx` |
| R14, R15 | `src/styles/tokens.css`, `scripts/check-contrast.mjs` (new) |
| R16 | `src/App.tsx`, `components/RunList.tsx`, `components/RunStatStrip.tsx`, `public/icons.svg` (delete) |
| R17 | `pages/RunDetail.tsx`, `pages/Compare.tsx`, `components/CommandPalette.tsx`, `src/App.css` |
| R18 | `pages/Compare.tsx`, `utils/compareSummary.ts`, `src/App.css` |
| R19 | `src/App.tsx`, `pages/ArtifactsRedirect.tsx` |
| R20 | `components/TestResultsPanel.tsx` |
| R21 | all of the above; `tests/e2e/web/` unchanged |
| R22 | `src/__tests__/styles.drift.test.ts` (new) |
