# Spec: `ui-refinement`

Kiro-style three-document spec for making the web UI clean, simple, and tasteful —
by making its existing design system the only way to express a value, deleting the
stylesheet that styles nothing, and fixing six accessibility defects. Read in order:

1. **[`requirements.md`](./requirements.md)** — 22 requirements with EARS acceptance
   criteria, constraints, non-goals, and a file-level traceability table.
2. **[`design.md`](./design.md)** — token architecture with measured contrast figures,
   component primitives, accessibility patterns, the Compare redesign, enforcement
   strategy (§9), migration risk (§10), and six open decisions (§12).
3. **[`tasks.md`](./tasks.md)** — 10 phases, 38 tasks, each with a definition of done and
   requirement traceability.

Scope is `src/ai_team/ui/web/frontend` only. No Python, no API contract, no run semantics.

## The one-line version

The UI already has a design system; it is applied to about an eighth of the stylesheet.
This spec makes the tokens load-bearing, deletes the ~15% of `App.css` that styles a page
that no longer exists, fixes the accessibility defects a keyboard or screen-reader user
actually hits, and adds a test that fails the build on the next raw `0.35rem`.

## What the audit found

| | Today |
| --- | --- |
| `App.css` | 2,160 lines |
| Spacing | **29** tokenized declarations vs **208** raw, across 15 distinct values |
| Type | **14** distinct `font-size` values, no scale; `body { font-size: 14px }` in px |
| Radius | **7** distinct values |
| Duplicate selectors | **6** (`.btn-sm` resolves to the second of two disagreeing blocks) |
| Dead rules | an entire Dashboard-era block — `.dashboard-layout`, `.run-sidebar`, `.sidebar-drawer-open`, `.grid-2/3`, … — plus the media query that exists only for it |
| `--content-max-width` | declared, referenced **zero** times; gutter applied twice |
| `<h1>` | **none in the application** |
| `htmlFor` | **zero occurrences**; 6 unassociated `<label>` elements |
| Tabs | `role="tablist"` with no `aria-controls`, no `tabpanel`, no keyboard support |
| Control borders | **1.25–1.55:1** — below WCAG 1.4.11's 3:1 floor |
| `color-scheme` | unset, so native `<select>` popups render light in a dark app |
| Icons | `lucide-react` **and** emoji **and** an unreferenced `public/icons.svg`, at once |

Text contrast, by contrast, is fine everywhere (4.9:1–16:1). The palette is not the
problem; the way it is applied is.

## The two decisions this spec locks in

**Cyan becomes the primary action colour.** Green (`#3fb950`) is currently both "primary
button" and "pass/complete" — and it is also the colour of the confirm button on
*"Delete run?"*. After R3, primary is `--intent-accent` (cyan, already the nav/link/focus
colour, 7.49:1 on canvas), green is reserved for success, and a new `.btn-danger` handles
destructive confirms. One token edit reverts it if it reads wrong.

**Nothing is enforced by prose.** R22 adds `styles.drift.test.ts`, which fails on a raw
length, a raw font-size, a colour literal outside `tokens.css`, a duplicate selector, an
orphan class in either direction, or a stylesheet over budget — with a message naming the
file, line, and the token to use instead.

## Constraints baked in

| | |
| --- | --- |
| Scope | `src/ai_team/ui/web/frontend` only — no Python, no API, no new page |
| Dependencies | no new runtime dependency; `lucide-react` (already present) is the icon system; at most one optional dev dependency (§12.1) |
| Test ids | **frozen** — adding allowed, renaming or removing is not (R21.1) |
| Theme | dark only; R15 declares the scheme, it does not add a second one |
| Budget | `App.css` ≤ 1,600 lines, asserted by test |
| Gate | `npm run lint && npm run build && npm test` after every task; `pytest tests/e2e/web -m web_e2e` after every phase that touches markup |
| Reversibility | one commit per phase, each green on its own |
| Out of scope | light theme, CSS framework migration, new features, visual-regression snapshots |

## Why the phase order is what it is

```
1 delete  →  2 tokens  →  3 colour  →  4 a11y  →  5 surfaces  →  6 icons  →  7 compare  →  8 nav  →  9 guards
  dead CSS   scales      intent      defects     de-nesting    lucide      IA           IA       enforcement
```

Deletion first, so no effort is spent tokenizing rules for a page that was removed. Tokens
before colour, so the accent swap is a one-token edit rather than sixty rule edits.
Accessibility before the IA work, so the tab and dialog patterns are already correct when
Compare's markup moves. Guards last, because a drift test that cannot pass yet is a broken
build.

Phases 7 and 8 are the only ones a reviewer could reject on taste. They are last, and
independently revertable.

## Executing this with Cursor

Point the agent at one task at a time:

```
Read .kiro/specs/ui-refinement/requirements.md and design.md for context.
Implement task 2.3 from .kiro/specs/ui-refinement/tasks.md.
Do not start any other task. Do not rename any data-testid.
Stop when its Definition of done is satisfied and
`npm run lint && npm run build && npm test` passes in src/ai_team/ui/web/frontend.
```

Phase 1 should not change a single rendered pixel — if something moves, a class was not
dead. Phase 3 is the one visible change (primary buttons turn blue). Phase 7 is the only
markup change in a heavily tested page; run the Playwright suite before and after it.

## Minimum defensible slice

**Phases 1, 3.3–3.4, and 4.** A stylesheet that no longer lies about what it styles,
buttons with a visible edge, destructive confirms in red, and the six accessibility
defects fixed — the part a user or an auditor would actually notice.

If even that is too long: **task 1.1 and task 4.2**. Delete the dead sheet, and make the
form labels work.
