"""Fixtures for web UI tests."""

from __future__ import annotations

import pytest
from ai_team.core.run_store import RunStore
from ai_team.ui.web import server as web_server
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolated_run_store(monkeypatch: pytest.MonkeyPatch):
    """Route every RunStore construction to an in-memory DB during tests.

    Without this, every test that calls state.create_run(...) or constructs
    its own RunState() (several do, not just through web_client) would write
    real rows into whatever data/memory.db the test process's settings
    resolve to, since RunState now persists run lifecycle events via
    RunStore. Patches the factory (_build_run_store), not just the shared
    module-level `state`, so tests that build a fresh RunState() are covered
    too.
    """
    monkeypatch.setattr(web_server, "_build_run_store", lambda: RunStore(":memory:"))
    original = web_server.state.store
    web_server.state.store = RunStore(":memory:")
    yield
    web_server.state.store = original


@pytest.fixture
def web_client() -> TestClient:
    """Sync ``TestClient`` for the dashboard FastAPI app."""
    return TestClient(web_server.app)
