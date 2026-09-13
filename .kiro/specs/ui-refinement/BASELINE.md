# UI refinement baseline (task 0.1 / 0.2)

Captured 2026-09-13 from `src/ai_team/ui/web/frontend`.

## Counts

| Metric | Before |
| --- | ---: |
| `src/App.css` lines | 2160 |
| `src/index.css` lines | 16 |
| Raw spacing/radius declarations (`padding`/`margin`/`gap`/`inset`/`inset-*`/`border-radius` with a numeric literal) | 249 |
| Tokenized spacing declarations | 49 |
| Distinct `font-size` values | 14 |
| Distinct `border-radius` values | 7 |
| `data-testid` literals (`TESTIDS.txt`, sorted unique including template patterns) | 99 |
| `npm test` | 112 passed, 1 failed, 3 errors (28 files). Failure: `Dashboard.cancel.test.tsx` — `getRunReceipt` is imported by `RunDetail` but missing from the `useApi` mock (pre-existing). |

## Screenshots

Phases 1–9 landed in `ee821f6` before any page was photographed. The PNGs in
`screenshots/` are therefore the **finished UI** (tokens + colour + a11y + Compare IA +
nav), not a Phase 0 baseline and not a Phase 2 or Phase 3 gate.

**0.1 before-state:** counts in the table above were taken from the pre-change tree.
Visuals were not. They can still be shot by checking out `87600d2` (parent of `ee821f6`),
running Vite, and capturing Home, `/run`, Compare with three live columns, RunDetail ×4,
and Artifacts. That would close 0.1. It would not close 2.4 or 3.7: those gates need
photos taken *between* phases, and those intermediate trees were never photographed.

**After-state (2026-09-13):** `.kiro/specs/ui-refinement/screenshots/`

| File | What it shows |
| --- | --- |
| `after-home.png` | Home with run cards; cyan `New run` |
| `after-run.png` | `/run` pipeline form |
| `after-compare-idle.png` | Compare after clicking Play sample runs |
| `after-compare-1280.png` | Three live demo columns side by side |
| `after-compare-800.png` | Narrow layout: Comparison Summary first |
| `after-rundetail-overview.png` | RunDetail Overview |
| `after-rundetail-activity.png` | RunDetail Activity |
| `after-rundetail-artifacts.png` | RunDetail Artifacts (demo empty) |
| `after-rundetail-tests.png` | RunDetail Tests (demo empty) |
| `after-stop-confirm.png` | Stop run? + red `.btn-danger` |
| `keyboard-command-palette.png` | Command palette |

`/artifacts` redirects to `/runs/:id#artifacts` (IA-1); the Artifacts tab shot covers that surface.

## Orphan classes (task 1.4)

Recorded after a static scan of `src/**/*.tsx` vs `App.css` (dynamic prefixes excluded).

### CSS-defined, unused in TSX (delete in Phase 1 unless noted)

Dashboard-era / dead: `dashboard`, `dashboard-header`, `dashboard-empty`, `dashboard-page`, `dashboard-alerts`, `dashboard-layout`, `sidebar-collapsed`, `sidebar-drawer-open`, `sidebar-toggle`, `run-sidebar`, `run-monitor`, `run-monitor-grid`, `grid-2`, `grid-3`, `panel-toolbar`, `panel-collapsed-hint`, `empty-actions`, `raw-events`, `demo-helper`, `btn-warning`, `run-list-assignment`, `run-list-date`, `run-list-meta`, `run-list-delete`, `run-meta-row`, `run-meta-date`, `run-complete-actions`.

Hue utilities (retire in 3.2): `cyan`, `green`, `red`, `yellow`, `blue`, `dim`.

Kept (dynamic or later collapse): `crewai-title`, `langgraph-title`, `claude-title`, `code-search-hit`, `empty-state-block`, `agent-timeline-phase`, `log-error`/`log-success`/`log-warn`, `gr-pass`/`gr-fail`/`gr-warn`, `status-*` chips, `summary-failed-reason`.

### TSX-used, undefined in CSS (resolve in 1.4)

| Class | Resolution |
| --- | --- |
| `muted` | → `.text-muted` (R3.7) |
| `panel-nested` | define as `.panel-section` (R4.4) |
| `empty-state-icon` | style |
| `compact` | style (`ActivityLog` density) |
| `how-it-works-cost` | style (measure-capped prose) |

Structural hooks (no visual rule; allowlisted in `design.md` §9): `run-config-form`, `run-detail-header`, `tests-panel`, `activity-log-wrap`, `home-empty`, `home-run-list`, `panel-inner`, `run-list-panel`, `run-list-day-group`, `coverage-chart`, `test-failures`, `command-palette-overlay`, `arch-panel`, `form-grid-backend`, `download-hint`, `pytest-raw`, `adr-block`, `code-view-modes`.

## After-state (task 9.3)

Captured 2026-09-13 after Phases 1–9. Gates: `npm run lint` (0 errors), `npm run build`,
`npm test` (125 passed / 30 files), `uv run pytest tests/e2e/web -m web_e2e`
(27 passed, 1 skipped).

| Metric | After |
| --- | ---: |
| `src/App.css` lines | 602 (budget 1600; remainder split to `styles/{run,compare,artifacts,responsive}.css`) |
| Raw spacing/radius outside `tokens.css` | 0 |
| Distinct `font-size` outside `tokens.css` | 0 |
| Orphan classes | 0 (enforced by `styles.drift.test.ts`; structural allowlist in design §9) |
| `data-testid` diff vs `TESTIDS.txt` | **Removed:** `nav-open-run` (task 8.1). **Added:** EmptyState/LoadingState ids (`agent-table-empty`, `artifacts-no-files`, `artifacts-select-run`, `file-tree-empty`, `file-tree-loading`, `guardrails-empty`, `hitl-banner`, `run-list-empty`, `run-list-empty-filtered`, `${testIdPrefix}-empty`, `${testIdPrefix}-starting`). |
