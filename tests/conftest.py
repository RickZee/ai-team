"""Session-wide guards that apply to every test in the suite.

These exist because of defects found on 2026-09-12 that no amount of line coverage
would have caught: a unit test rewrote a committed golden record on every run
(`test_r16_unit_gaps.py` monkeypatched `VALIDATION_LOG` but not `ALIGNMENT_DIR`), and a
second test's assertion depended on the repo's `workspace/` directory being empty.

The rule both violate is the same one: **a test may not modify tracked files.** Ground
truth under `evals/golden/`, the replay corpus under `evals/fixtures/traces/`, and the
taxonomy are inputs to the $0 Tier A gate. A test that edits them corrupts the thing the
gate measures, and it does so silently — the suite still passes.

A third class is process-global state. ``reset_bus(empty=True)`` and
``reload_settings()`` leak into later tests under a shuffled run — file-tool
tests then fail with ``Unknown tool: read_file``. The per-test teardown below
puts the bus catalog and the settings cache back.

A fourth, found on 2026-09-17: the suite read whatever API keys happened to be in the
developer's shell. With ``OPENROUTER_API_KEY=`` still set from week 1's $0 dry run, four
``test_run_demo.py`` tests failed on the new key preflight; with a *real* key exported, the
same tests ran against live settings. Either way the suite was testing a different program
than CI does. ``_isolate_api_keys`` below pins both variables to a fixed fake value, so a
test that cares about key handling sets its own (``monkeypatch.setenv`` wins) and every other
test sees the same thing on every machine.

A fifth, same day: tests that build a ``ResultsBundle`` wrote real run
directories into the repo's own ``output/runs/``. That folder is the corpus the eval
harness and the course's week 6 audit read, so a learner who ran ``pytest tests/unit``
before the audit ingested 14 runs instead of the 5 they had made — a corpus nobody
curated, which is exactly what week 3 warns about. ``_isolate_run_output`` below points
the whole suite at a temp directory and fails the session if anything lands in the real
one anyway.

A sixth, 2026-09-21: nested pytest (qa tools, harness gates) inherited the parent
``--cov`` ``COVERAGE_FILE`` and wrote statement coverage next to branch data.
``coverage combine`` then raised ``DataError`` after 1693 passing tests, so
``pre_push_check.sh`` failed closed. ``pytest_configure`` below strips inherited
coverage env from child processes.

A seventh, 2026-09-30: report and lessons tests opened ``MemorySettings.sqlite_path``,
whose default is the developer's real long-term store (``./data/memory.db``). On a
fresh checkout that silently created the database; on a sandboxed mount it raised
``disk I/O error``. ``_isolate_memory_store`` points the suite at a temp database.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Trees a test must never write to. Paths are repo-relative.
IMMUTABLE_TREES = (
    "evals/golden",
    "evals/fixtures/traces",
    "evals/taxonomy",
)


def pytest_configure(config: pytest.Config) -> None:
    """Keep nested pytest from writing into the parent ``--cov`` data file.

    Installed again from a session fixture so it wins over pytest-cov's own
    Popen wrapper (that plugin configures after conftest).
    """
    _install_popen_coverage_scrub()


@pytest.fixture(scope="session", autouse=True)
def _scrub_nested_coverage_env() -> None:
    _install_popen_coverage_scrub()


def _install_popen_coverage_scrub() -> None:
    """Strip inherited coverage env from child processes.

    ``ci_unit_test.sh --cov`` sets ``COVERAGE_FILE`` and pytest-cov sets
    ``COVERAGE_PROCESS_START``. Child pytest then writes *statement* coverage
    into the parent's *branch* file; combine fails. Spawn sites that set their
    own ``COVERAGE_FILE`` (via ``coverage_subprocess_env``) keep it.
    """
    current = subprocess.Popen
    if getattr(current, "_ai_team_cov_scrub", False):
        return

    class _Popen(current):  # type: ignore[valid-type,misc]
        _ai_team_cov_scrub = True

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            env = kwargs.get("env")
            env = os.environ.copy() if env is None else dict(env)
            parent_file = os.environ.get("COVERAGE_FILE")
            for key in (
                "COVERAGE_PROCESS_START",
                "COV_CORE_SOURCE",
                "COV_CORE_CONFIG",
                "COV_CORE_DATAFILE",
                "COV_CORE_BRANCH",
                "COV_CORE_CONTEXT",
            ):
                env.pop(key, None)
            if parent_file and env.get("COVERAGE_FILE") == parent_file:
                env.pop("COVERAGE_FILE", None)
            kwargs["env"] = env
            super().__init__(*args, **kwargs)

    _Popen._ai_team_cov_scrub = True  # type: ignore[attr-defined]
    subprocess.Popen = _Popen  # type: ignore[misc]


def _snapshot(root: Path) -> dict[str, str]:
    """Map repo-relative path -> sha256 for every file under the immutable trees."""
    digests: dict[str, str] = {}
    for rel in IMMUTABLE_TREES:
        tree = root / rel
        if not tree.exists():
            continue
        for path in sorted(tree.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            digests[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


@pytest.fixture(scope="session", autouse=True)
def _tracked_inputs_stay_immutable() -> Iterator[None]:
    before = _snapshot(REPO_ROOT)
    yield
    after = _snapshot(REPO_ROOT)

    modified = sorted(p for p in before.keys() & after.keys() if before[p] != after[p])
    removed = sorted(before.keys() - after.keys())
    added = sorted(after.keys() - before.keys())

    problems: list[str] = []
    if modified:
        problems.append(f"modified: {modified}")
    if removed:
        problems.append(f"removed: {removed}")
    if added:
        problems.append(f"created: {added}")

    assert not problems, (
        "the test suite wrote to tracked ground-truth files — "
        + "; ".join(problems)
        + ". Redirect the write to tmp_path (monkeypatch the module's directory constant, "
        "e.g. evals.alignment.ALIGNMENT_DIR and VALIDATION_LOG) rather than relaxing this guard."
    )


@pytest.fixture(scope="session", autouse=True)
def _isolate_api_keys() -> Iterator[None]:
    """Pin API-key variables so the suite does not inherit the developer's shell."""
    pinned = {
        "OPENROUTER_API_KEY": "test-key-not-a-real-credential",
        "ANTHROPIC_API_KEY": "test-key-not-a-real-credential",
    }
    previous = {k: os.environ.get(k) for k in pinned}
    os.environ.update(pinned)
    try:
        yield
    finally:
        for k, v in previous.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture(scope="session", autouse=True)
def _isolate_memory_store(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Keep the suite out of the developer's long-term memory database."""
    previous = os.environ.get("MEMORY_SQLITE_PATH")
    os.environ["MEMORY_SQLITE_PATH"] = str(tmp_path_factory.mktemp("memory") / "memory.db")
    from ai_team.config.settings import reload_settings

    reload_settings()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("MEMORY_SQLITE_PATH", None)
        else:
            os.environ["MEMORY_SQLITE_PATH"] = previous
        reload_settings()


@pytest.fixture(scope="session", autouse=True)
def _isolate_run_output(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Send every run artifact the suite produces to a temp dir, not the repo's corpus.

    ``PROJECT_OUTPUT_DIR`` is read through ``ProjectSettings``, and the per-test
    ``reload_settings()`` teardown re-reads the environment, so setting it once here holds
    for the whole session. A test that needs its own output root still monkeypatches it.
    """
    real_runs = REPO_ROOT / "output" / "runs"
    before = {p.name for p in real_runs.iterdir()} if real_runs.is_dir() else set()

    previous = os.environ.get("PROJECT_OUTPUT_DIR")
    os.environ["PROJECT_OUTPUT_DIR"] = str(tmp_path_factory.mktemp("run-output"))
    from ai_team.config.settings import reload_settings

    reload_settings()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PROJECT_OUTPUT_DIR", None)
        else:
            os.environ["PROJECT_OUTPUT_DIR"] = previous
        reload_settings()

    after = {p.name for p in real_runs.iterdir()} if real_runs.is_dir() else set()
    leaked = sorted(after - before)
    assert not leaked, (
        "the test suite wrote run directories into the repo's output/runs: "
        f"{leaked}. That folder is the eval corpus and the week 6 audit reads it. "
        "Point the write at tmp_path instead of relaxing this guard."
    )


@pytest.fixture(autouse=True)
def _reset_process_singletons() -> Iterator[None]:
    """Restore ToolBus and Settings after every test.

    Teardown runs after monkeypatch restores the environment, so
    ``reload_settings()`` re-reads the real env rather than a leftover tmp_path.
    """
    yield
    from ai_team.config.settings import reload_settings
    from ai_team.tools.bus import reset_bus

    reset_bus()
    reload_settings()
