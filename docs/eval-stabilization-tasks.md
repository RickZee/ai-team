# Eval & Backend Stabilization — Task List

Created 2026-06-25. Source: 14 consecutive "fix" commits chasing the same eval
run to green. Symptom was whack-a-mole; this doc captures the **root architectural
problems** and a prioritized plan to stop the bleeding.

## Diagnosis — why we kept getting stuck

The smoke-test eval (`add(a,b)` + one test) failed ~10 times across two days.
Each failure had a *different surface symptom* but three structural causes:

1. **No isolation between "did the backend work" and "can we observe it".**
   Most failures were in result transport / display / judge plumbing, not in the
   backends producing wrong code. We spent days fixing the harness, not the system.

2. **Crewai's console event-listener is fundamentally hostile to subprocess use.**
   `EventListener` is a singleton that hardwires `ConsoleFormatter(verbose=True)`
   (`.venv/.../crewai/events/event_listener.py:129`). `update_method_status`
   (`console_formatter.py:492`) has **no verbose gate** and recurses
   `update_method_status → print → update_method_status` until `RecursionError`
   when `rich.Live` can't render in a non-TTY. Our `verbose=False` plumbing
   (commit f8ffd7c) never touched this path. **This is THE crewai blocker.**

3. **Result serialization crosses a process boundary with live framework objects.**
   `flow.state.model_dump()` embeds LangChain message objects with circular refs.
   Pickling for `multiprocessing.Queue` → RecursionError, or json.dumps spins at
   96% CPU. We patched this 3 times (4be3ee3, 0df8fb1, bdd366d) and it *still*
   recurs because the RecursionError now fires inside crewai's listener before
   our sanitizer runs.

## Task list

### P0 — Kill the crewai recursion at the source (unblocks crewai entirely)

- [ ] **T1. Neutralize crewai's ConsoleFormatter in backend mode.**
  At `crewai_backend/backend.py` import (or top of `run()`), grab the
  `EventListener` singleton and disable its live console:
  ```python
  from crewai.events.event_listener import EventListener
  el = EventListener()
  el.formatter.verbose = False
  el.formatter._is_streaming = True   # makes print() early-return on Tree args
  # or: el.formatter.console = Console(quiet=True, file=open(os.devnull, "w"))
  ```
  Verify `update_method_status` no longer recurses (it calls `self.print(tree)`;
  with `_is_streaming=True`, `print` returns immediately on Tree args — breaks the cycle).
  *Acceptance:* crewai smoke-test completes < 400s with zero RecursionError in log.

- [ ] **T2. Add a regression guard.** Unit test that imports the crewai backend,
  asserts `EventListener().formatter` is in non-live mode. Catches a crewai
  upgrade re-enabling it.

### P0 — Stop result objects crossing the process boundary

- [ ] **T3. Backends return a flat, JSON-safe `dict` — never a live framework object.**
  Make each backend's `ProjectResult.raw` a plain dict of scalars + lists + the
  workspace path. Build it explicitly from known fields; do **not** dump
  `flow.state` / LangGraph state wholesale. This removes the entire class of
  serialization bugs (4be3ee3, 0df8fb1, bdd366d become unnecessary).
  *Acceptance:* `json.dumps(result.raw)` succeeds with default recursionlimit,
  no `default=str`, no try/except.

- [ ] **T4. Delete the defensive sanitizer scaffolding** once T3 lands:
  recursionlimit fiddling in `test_backend_comparison.py` and
  `crewai_backend/backend.py`. Keep one allowlist as the single source of truth
  for what a backend result may contain.

### P1 — Make the harness observable & fast

- [ ] **T5. Run pytest in the workspace ONCE; cache the result.**
  Currently `run_pytest_in_workspace` is called 2-3× per backend (one per test
  method) and the backend itself already ran pytest. Smoke-test runs pytest
  ~4× total. Make it a `@pytest.fixture(scope="module")` that runs once, returns
  `{ok, pass_rate, output}`. Cuts wall time and removes the import-mismatch
  flakiness surface.

- [ ] **T6. Normalize generated workspace layout across backends.**
  SDK writes `ws/src/calc.py` + `ws/tests/test_calc.py`; crewai/langgraph write
  flat. This forced `--import-mode=importlib` (15b2099) and broke file-existence
  checks. Define one expected layout in the scenario; have the eval normalize or
  the backends conform. *Acceptance:* same assertion code works for all 3 backends.

- [ ] **T7. Single timeout source of truth.** Today: scenario `timeout_seconds`,
  `max(x*1.5, 600)` in test_backend_comparison, AND `pytest --timeout=600` in
  run_evals — three layers that disagree (crewai needs ~430s, kept getting killed
  at 600 "timeout" while actually succeeding). Pick one budget per backend in the
  scenario file; derive the rest. *Acceptance:* a backend that finishes in 430s is
  never reported as a 600s timeout.

### P1 — Make the LLM judge deterministic & cheap

- [ ] **T8. Judge gets structured evidence, not scraped files.**
  Pass the backend's *reported* `test_results` + file list as the evidence object
  (started in 4fde53a). Don't re-derive "pytest exits 0" by re-running pytest and
  re-reading prose. *Acceptance:* "pytest exits 0" criterion scores from
  structured data, not a second pytest invocation.

- [ ] **T9. Make judge optional and clearly separated from pass/fail.**
  Backend *correctness* (files exist, tests pass) must be judge-independent.
  Judge scores (goal_alignment, criteria) are *quality signal*, reported but not
  gating the "did it work" verdict. Right now a flaky empty judge response
  (2d6dace) can fail an otherwise-correct run.

### P2 — Address the real backend-quality findings (not harness bugs)

- [ ] **T10. langgraph: deepseek tool non-compliance.**
  deepseek-v3 narrates "I will use file_writer" then emits markdown instead of
  calling the tool. The `_extract_and_write_code_blocks` fallback only catches
  fenced blocks. Options: (a) switch the langgraph dev/qa roles to a
  tool-reliable model, (b) harden the fallback parser, (c) add a "files written?"
  gate that forces a retry with an explicit tool-only instruction. This is a
  genuine capability gap, ~50% nondeterministic pass rate.

- [ ] **T11. SDK cost.** Claude Agent SDK costs $0.30–0.40 for the smoke task
  (30-40× crewai/langgraph) due to full agent scaffolding. Document as expected;
  consider a cheaper model or a "trivial task" fast path. Budget already raised
  to $0.50 (15b2099) so it doesn't fail the run, but the *signal* matters.

### P2 — Reduce the flow surface

- [ ] **T12. Audit the 26 `@listen/@start/@router` methods in main_flow.py (1286 lines).**
  The post-completion phases (self-improvement crew, scorecard, lesson extraction)
  add ~60s + extra LLM calls + were where crewai hung. Make post-run analysis
  **opt-in** (off by default in eval/CI mode) so a smoke test doesn't trigger a
  manager self-improvement report.

## Suggested order

1. T1 (crewai recursion) — biggest unblock, smallest change
2. T3 (flat result dicts) — removes whole bug class
3. T7 (one timeout) + T5 (one pytest run) — stops false timeouts & flakiness
4. T9/T8 (judge separation) — stops flaky judge failing correct runs
5. T12 (opt-in post-run) — speeds smoke runs
6. T10/T11 — actual backend quality work, no longer masked by harness noise

## Principle going forward

> The eval harness must fail **only** when a backend produces wrong output —
> never because of how we transport, display, or judge that output.

Every one of the 14 fix-commits violated this. T1–T9 restore it.
