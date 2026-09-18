"""
Every check module must be imported by ``ensure_checks_loaded()``.

Week 5 step 4 of the course tells the learner to write ``evals/checks/mine.py`` and then
says: *"The test suite enforces each of these, so if you skip one, pytest tells you which."*
On 2026-09-17 a tester wrote the module, skipped the one-line registry import, and the whole
suite stayed green (404 passed). The check existed on disk, was never imported, never
registered, and therefore never ran — the quietest possible failure, and the one the rest of
the wiring table cannot catch, because every other guard only looks at checks the registry
already knows about.

A module that *defines* a check and that nothing imports is a check that silently does not
run. The guard finds those by looking for the ``@check(`` decorator in the source rather than
by keeping a list of filenames, so a new check module is covered the moment it is written —
including the learner's ``mine.py`` — while helpers that happen to live in the same folder
(``validation.py`` validates checks; it declares none) need no allowlist.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKS_DIR = REPO_ROOT / "evals" / "checks"


def _check_modules() -> list[str]:
    """Modules under evals/checks/ that declare at least one check."""
    return sorted(
        p.stem
        for p in CHECKS_DIR.glob("*.py")
        if p.stem != "registry" and "@check(" in p.read_text(encoding="utf-8")
    )


def test_every_check_module_is_imported_by_ensure_checks_loaded() -> None:
    from evals.checks.registry import ensure_checks_loaded

    ensure_checks_loaded()

    missing = [m for m in _check_modules() if f"evals.checks.{m}" not in sys.modules]
    assert not missing, (
        "these modules are in evals/checks/ but ensure_checks_loaded() never imports them, "
        f"so the checks in them never run: {missing}. "
        "Add `import evals.checks.<name>  # noqa: F401` inside ensure_checks_loaded() "
        "in evals/checks/registry.py."
    )


def test_every_check_module_registers_at_least_one_check() -> None:
    """A module that imports cleanly but registers nothing is the same failure, later."""
    from evals.checks.registry import all_checks, ensure_checks_loaded

    ensure_checks_loaded()
    registered_modules = {
        type(c).__module__ if not hasattr(c, "_fn") else c._fn.__module__  # type: ignore[attr-defined]
        for c in all_checks()
    }
    silent = [
        m
        for m in _check_modules()
        if f"evals.checks.{m}" in sys.modules and f"evals.checks.{m}" not in registered_modules
    ]
    assert not silent, (
        f"these check modules are imported but register no check: {silent}. "
        "Did you forget the @check(...) decorator, or is the id already taken?"
    )


def test_the_guard_itself_sees_the_real_check_modules() -> None:
    """An empty glob would make both tests above vacuous."""
    modules = _check_modules()
    assert len(modules) >= 10, f"only found {modules}; the walker is wrong, not the repo"
    assert "spend" in modules and "guardrails" in modules
    # validation.py lives here but declares no check — it must not be demanded.
    assert "validation" not in modules
