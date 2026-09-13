# 2026-09-13 — UI refinement suite failures

Landing `.kiro/specs/ui-refinement`. Frontend-only. Failures found while making
the gate green, and what actually fixed them.

## Vitest (pre-existing, then new)

1. **`Dashboard.cancel.test.tsx` — `getRunReceipt` missing from `useApi` mock.**
   Pre-existing at baseline (112 passed / 1 failed). `RunDetail` started calling
   `getRunReceipt`; the cancel mock did not. Fix: `getRunReceipt: vi.fn().mockResolvedValue(null)`
   on the affected page mocks.

2. **Hue class assertions.** `RunSummaryCard` test still expected `.yellow` after
   R3.2. Fix: assert `.text-warning`.

3. **`AgentTable` "Done" collision.** Status label "Done" duplicated the column
   header. Fix: `getByRole("cell", { name: "Done" })`.

4. **`Compare.test.tsx` duplicate backend names.** Narrow-width `<details>` summaries
   plus column `<h2>` meant `getByText("CrewAI")` was no longer unique. Fix:
   `getAllByText`. Testids on columns unchanged.

5. **Drift false positives.** `@import "./styles/run.css"` matched as class `css`;
   `design.md` in comments matched as `md`; `0.var(--space-*)` (bad migrator rewrite
   of `0.2rem`) matched as class `var`. Fix: strip comments before class collection;
   replace `0.var(--token)` with the mapped `--space-1`.

## Playwright

6. **`test_home_demo_via_api_deep_link` — first `h2` was "Metrics".**
   R8 made the assignment an `<h1>`, so Playwright's `get_by_role("heading", level=2)`
   resolved to the Metrics panel header. E2E is frozen. Fix: page `<h1>Run</h1>`,
   assignment `<h2 class="run-detail-title">`, panel titles demoted to `<h3>`
   (design §8.1). Suite: 27 passed, 1 skipped.

## Token migrator residue

A one-shot rem→token replace turned `0.2rem` into `0.var(--space-6)` because `2rem`
matched inside `0.2rem`. All `0.var(--*)` occurrences mapped back to `--space-1`.

## Not run

Screenshots (0.1 / 2.4 / 3.7) and a live three-backend compare (7.4) stay
human-triggered. Full keyboard-only pass (4.8) not recorded here.
