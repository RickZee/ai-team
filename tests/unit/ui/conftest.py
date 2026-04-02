"""Fixtures for web UI tests."""

from __future__ import annotations

import pytest
from ai_team.ui.web import server as web_server
from fastapi.testclient import TestClient


@pytest.fixture
def web_client() -> TestClient:
    """Sync ``TestClient`` for the dashboard FastAPI app."""
    return TestClient(web_server.app)
