"""Fixtures for web dashboard E2E tests (demo/mock paths — no LLM spend)."""

from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FRONTEND_DIR = _REPO_ROOT / "src" / "ai_team" / "ui" / "web" / "frontend"
_FRONTEND_DIST = _FRONTEND_DIR / "dist"
_SERVER_STARTED = False


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(base_url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/api/health", timeout=2.0)
            if r.status_code == 200 and r.json().get("status") == "ok":
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Web server did not become healthy at {base_url}") from last_error


def ensure_frontend_built() -> Path:
    """Build the React app if ``dist/`` is missing (required for browser E2E)."""
    if _FRONTEND_DIST.exists() and (_FRONTEND_DIST / "index.html").exists():
        return _FRONTEND_DIST
    if os.environ.get("AI_TEAM_SKIP_FRONTEND_BUILD") == "1":
        pytest.skip("Frontend dist missing and AI_TEAM_SKIP_FRONTEND_BUILD=1")
    node_modules = _FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        subprocess.run(
            ["npm", "ci"],
            cwd=_FRONTEND_DIR,
            check=True,
            timeout=300,
        )
    subprocess.run(
        ["npm", "run", "build"],
        cwd=_FRONTEND_DIR,
        check=True,
        timeout=300,
    )
    if not (_FRONTEND_DIST / "index.html").exists():
        raise RuntimeError(f"Frontend build did not produce {_FRONTEND_DIST / 'index.html'}")
    return _FRONTEND_DIST


def _mount_frontend_if_needed() -> None:
    global _SERVER_STARTED
    from ai_team.ui.web.server import register_frontend

    if _SERVER_STARTED:
        return
    from ai_team.ui.web import server as web_server

    register_frontend(web_server.app, _FRONTEND_DIST)
    _SERVER_STARTED = True


@pytest.fixture(scope="module")
def web_server_url() -> Generator[str, None, None]:
    """Live Uvicorn server for HTTP/WebSocket E2E (module-scoped)."""
    _mount_frontend_if_needed()
    port = _free_port()
    from ai_team.ui.web import server as web_server

    config = uvicorn.Config(
        web_server.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base)
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=10.0)


@pytest.fixture
def web_http_client(web_server_url: str) -> httpx.Client:
    """HTTP client against the live web server."""
    return httpx.Client(base_url=web_server_url, timeout=30.0)


@pytest.fixture
def web_client() -> TestClient:
    """In-process FastAPI client (fast; used for mocked WebSocket runs)."""
    from ai_team.ui.web import server as web_server

    return TestClient(web_server.app)


@pytest.fixture(scope="session")
def browser_base_url() -> Generator[str, None, None]:
    """Base URL with built frontend for Playwright (session-scoped)."""
    ensure_frontend_built()
    _mount_frontend_if_needed()
    port = _free_port()
    from ai_team.ui.web import server as web_server

    config = uvicorn.Config(
        web_server.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base)
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=10.0)


@pytest.fixture(scope="session")
def playwright_browser_type_launch_args() -> dict[str, object]:
    """Headless Chromium for CI-friendly browser E2E."""
    return {"headless": True}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "web_e2e: Web dashboard E2E (demo/mock; no LLM cost).",
    )
    config.addinivalue_line(
        "markers",
        "browser_e2e: Playwright browser E2E (requires built frontend).",
    )
