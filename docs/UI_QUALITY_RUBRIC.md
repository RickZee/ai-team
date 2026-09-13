# UI quality rubric (advisory)

This document is a calibration aid for humans looking at generated UIs. **No gate
reads it.** Criterion wording steers output toward convergence — treat scores as
conversation, not as a pass/fail instrument, until this rubric clears the
eval-harness alignment bar (`docs/EVAL_METHODOLOGY.md`).

## Criteria

| Criterion | 1 — weak | 2 — adequate | 3 — strong | 4 — excellent |
| --- | --- | --- | --- | --- |
| Design quality | Default system fonts, no hierarchy, colliding contrast | Readable, one typeface, basic spacing | Clear hierarchy, consistent density, intentional color | Distinct visual system that still feels native to the product |
| Originality | Clone of a tutorial screenshot | Familiar pattern, no distinctive choices | A few memorable decisions (type, layout, empty states) | Recognizably *this* product without being gimmicky |
| Craft | Misaligned controls, overflow, broken focus | Mostly aligned; a few rough edges | Tight spacing, hover/focus, no overflow at the stated viewport | Pixel-consistent across the recorded viewport; details hold up zoomed |
| Functionality | Primary action missing or dead | Happy path works; errors ignored | Happy path + empty/error states | Every acceptance step is operable without a console or page error |

## Calibration notes

- Score the **recorded viewport** (default 1280×720), not a resized window.
- Functionality here is *visual operability*, not a substitute for
  `run_ui_smoke` / `CHK-runtime-smoke-present`. Those stay deterministic.
- Do not average the four scores into a gate. A 4/4 on craft with a dead
  primary button is still a failed smoke.

## Why this stays advisory

Wording a rubric is itself a style prior. Until we can show that scores agree
with a held-out human set *and* that the rubric does not collapse generated UIs
onto one look, it does not belong in Tier A.
