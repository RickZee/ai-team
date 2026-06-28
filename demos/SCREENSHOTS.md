# Screenshot Capture Guide

How to capture clean, reproducible, **junk-free** screenshots of each demo scenario
for the README, docs, blog posts, and releases.

The goal: a stranger looking at the screenshot sees the product working — not your
API keys, not 40 old test runs in the sidebar, not a `$0.0003` cost noise string, not
a half-broken layout. Every image should be intentional.

---

## Golden rules

1. **Start from a clean state.** Empty run history, fresh browser profile, no
   leftover error banners.
2. **Screenshot the real path, not the Demo button.** The **Demo** button always
   plays the same generic "Flask REST API" simulation with mock model names
   (`qwen3:14b`, `deepseek-r1:14b`) and writes no files. For per-scenario,
   reproducible images, run the brief from the **Run** tab (or CLI). Only use the
   Demo button when you explicitly want to show the zero-cost demo mode.
3. **Redact before you publish, not after.** Check the redaction list below on every
   frame *before* saving.
4. **One concept per screenshot.** Don't try to show launch + live + summary in one
   frame; capture the distinct stages.
5. **Consistent viewport and theme.** Same window size and the default GitHub-dark
   theme across the whole set so the gallery looks coherent.

---

## One-time clean setup

### Browser

- Use a **fresh/guest profile** (or incognito) so no extensions, bookmarks bar, or
  autofill chips appear.
- Set a **fixed window size**: **1440×900** (logical) is the house standard for this
  guide. Use the same size for every shot.
- Hide the bookmarks bar (`Cmd/Ctrl+Shift+B`).
- Zoom = 100% (`Cmd/Ctrl+0`).

### A clean run history (most important for the sidebar)

The Dashboard sidebar lists **every** run on the server. A wall of stale runs is the
#1 source of junk. Reset before a capture session:

```bash
# In-memory runs are cleared by restarting the API server:
uv run ai-team-web        # Ctrl+C the old one first — in-memory runs reset on restart

# Disk-backed runs (the registry) live under the workspace/output dirs.
# Move them aside instead of deleting, so you can restore later:
mkdir -p .archive/screenshots-backup
mv output/* .archive/screenshots-backup/ 2>/dev/null || true
```

> In-memory runs (`GET /api/runs`) are lost on server restart — that's exactly what
> you want for a clean sidebar. The disk registry persists separately, so move those
> aside as above. Restore afterward with the reverse `mv`.

Then create only the runs you intend to show. For the cleanest "live" shots, run a
single scenario so the sidebar holds exactly one row.

---

## Per-stage capture sequence (web UI)

Run a scenario from the **Run** tab, then capture in this order. Each stage maps to a
specific UI region described in [../docs/UX_REVIEW.md](../docs/UX_REVIEW.md).

| # | Stage | Page / region | What must be visible | Junk to remove |
|---|-------|---------------|----------------------|----------------|
| 1 | **Launch** | Run tab | Backend, profile, complexity, brief pasted in the textarea | Old `actionError` banner; partial text |
| 2 | **Estimate** | Run tab → Cost Estimate panel | Estimate table for the chosen complexity | A budget-exceeded warning unless that's the point |
| 3 | **Live — early** | Dashboard, sticky header | Phase pipeline at *Planning/Development*, run status chip, elapsed | Real run IDs/UUIDs if sensitive (see redaction) |
| 4 | **Live — agents** | Dashboard → Agents panel | Agent table with active/finished rows | Mock model names if you're claiming a real run |
| 5 | **Live — log** | Dashboard → Activity Log | A few meaningful log lines | Stack traces / noisy debug lines |
| 6 | **Guardrails** | Dashboard → Guardrails (click *Show*) | Pass/warn/fail checks | — (warns are fine; they show the system works) |
| 7 | **Complete** | Dashboard → Run summary card | Status complete, duration, metrics | Cost string if it's a distracting tiny number |
| 8 | **Artifacts — files** | Artifacts → Files | Generated file tree + a previewed file | Absolute filesystem paths in the preview header |
| 9 | **Artifacts — tests** | Artifacts → Tests | Passing test panel | A flaky/failed row unless intentional |
| 10 | **Artifacts — architecture** | Artifacts → Architecture | Architecture panel | — |
| 11 | **Compare** (optional) | Compare tab | 3 columns + summary table with best-value highlights | Pre-flight modal still open |
| 12 | **Running app** (bonus) | The generated app in a browser | The actual to-do UI / API response | localhost noise is fine; keep it tidy |

> **The Demo button's fixed scenario:** if you capture via the Demo button, expect a
> "Flask REST API" run, mock Ollama model names, a *"Missing deployment diagram"*
> architecture warning, and an 8-passed/1-failed test result with one retry. That's
> by design for the simulation — don't present it as a real scenario run.

---

## CLI captures (Scenario 4 and terminal-first shots)

For the AutoOptimizer loop and any terminal screenshot:

- Use a **clean terminal**: large readable font, default theme, no rainbow prompt,
  window sized ~120 cols.
- Clear scrollback (`clear`) before the command so only relevant output shows.
- Capture the **budget/experiment counters** and the **keep/revert** decisions.
- For `logs/experiments.jsonl`, pipe through a formatter for readability:
  ```bash
  tail -n 5 demos/02_todo_app/output/logs/experiments.jsonl | python -m json.tool
  ```
- **Scrub the prompt** — your shell prompt can leak `username@hostname` and the full
  home path. Use a minimal prompt for captures: `PS1='$ '`.

---

## Redaction checklist (run on EVERY frame before saving)

- [ ] **No API keys / tokens** anywhere (terminal env echoes, `.env` open in an editor,
      network tab).
- [ ] **No secrets in logs** — the pipeline has a secret-detection guardrail, but a
      pasted brief or error could still contain one.
- [ ] **No personal info** — username, hostname, home directory, email, real names in
      sample data. Use `Ada / ada@example.com` style placeholders.
- [ ] **No absolute local paths** — `/Users/<you>/...` or `C:\Users\<you>\...` in file
      preview headers or terminal. Run from the repo root and show relative paths.
- [ ] **No unrelated browser chrome** — other tabs' titles, bookmarks, extension icons,
      notifications.
- [ ] **No stale error banners** — dismiss "API unreachable", old `actionError`, or
      "human review required" banners that don't belong to this shot.
- [ ] **Sidebar is intentional** — one or a few relevant runs, not a graveyard.
- [ ] **Cost/token numbers make sense** — hide a distracting `$0.0001`, or show a real
      figure if the point is cost.

---

## Naming & storage

Save curated images under `docs/images/` using a predictable scheme so docs can
reference them stably:

```
docs/images/
  scenario-01-smoke/01-run.png
  scenario-01-smoke/02-summary.png
  scenario-02-todo/01-run.png
  scenario-02-todo/02-live.png
  scenario-02-todo/03-summary.png
  scenario-02-todo/04-artifacts-files.png
  scenario-02-todo/05-app-running.png
  scenario-03-microservices/...
  scenario-04-optimizer/01-loop.png
```

- Format: **PNG**, 2× (retina) where possible, then keep file size reasonable
  (compress > 1 MB shots).
- Filename: `NN-stage.png`, zero-padded, lowercase, hyphenated.
- Don't commit raw/unredacted originals — only the curated, checked frames.

---

## Quick repeatable workflow

```bash
# 1. Reset for a clean session
mkdir -p .archive/screenshots-backup && mv output/* .archive/screenshots-backup/ 2>/dev/null || true
# (restart ai-team-web to clear in-memory runs)

# 2. Start UI
uv run ai-team-web &                       # http://localhost:8421
cd src/ai_team/ui/web/frontend && npm run dev  # http://localhost:5173

# 3. Run ONE scenario from the Run tab, capture stages 1–10 in order.

# 4. Run the redaction checklist on each frame, save to docs/images/scenario-XX/.

# 5. Restore disk runs when done
mv .archive/screenshots-backup/* output/ 2>/dev/null || true
```
