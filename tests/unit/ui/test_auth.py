"""Auth, bind defaults, and route-coverage for the control plane (R15, R24).

to see the route-coverage test fail: remove ``dependencies=_AUTH`` from any
non-public route in ``server.py``.
"""

from __future__ import annotations

import pytest
from ai_team.config.settings import reload_settings
from ai_team.ui.web.auth import (
    PUBLIC_PATHS,
    TOKEN_HEADER,
    assert_bind_allowed,
    require_token,
    websocket_origin_allowed,
)
from ai_team.ui.web.server import app, build_web_parser
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient


def _reload_token(monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    if token:
        monkeypatch.setenv("AI_TEAM_WEB_TOKEN", token)
    else:
        monkeypatch.delenv("AI_TEAM_WEB_TOKEN", raising=False)
    reload_settings()


def test_health_is_public_without_token(web_client: TestClient) -> None:
    r = web_client.get("/api/health")
    assert r.status_code == 200


def test_mutating_route_401_without_header(
    web_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reload_token(monkeypatch, "secret-token")
    r = web_client.post("/api/demo")
    assert r.status_code == 401


def test_mutating_route_200_with_header(
    web_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reload_token(monkeypatch, "secret-token")
    r = web_client.post("/api/demo", headers={TOKEN_HEADER: "secret-token"})
    assert r.status_code == 200
    assert "run_id" in r.json()


def test_no_token_configured_allows_loopback(
    web_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reload_token(monkeypatch, "")
    r = web_client.post("/api/demo")
    assert r.status_code == 200


def test_default_host_is_loopback() -> None:
    parser = build_web_parser()
    args = parser.parse_args([])
    assert args.host == "127.0.0.1"


def test_bind_guard_refuses_non_loopback_without_token() -> None:
    with pytest.raises(ValueError, match="AI_TEAM_WEB_TOKEN"):
        assert_bind_allowed("0.0.0.0", token="")


def test_bind_guard_allows_loopback_without_token() -> None:
    assert_bind_allowed("127.0.0.1", token="")


def test_bind_guard_allows_non_loopback_with_token() -> None:
    assert_bind_allowed("0.0.0.0", token="set")


def test_disallowed_origin_rejected() -> None:
    assert websocket_origin_allowed("https://evil.example", ["http://localhost:5173"]) is False
    assert websocket_origin_allowed(None, ["http://localhost:5173"]) is True
    assert websocket_origin_allowed("http://localhost:5173", ["http://localhost:5173"]) is True
    # E2E / random --port: loopback Origin is allowed even when not on the CORS list.
    assert websocket_origin_allowed("http://127.0.0.1:59999", ["http://localhost:5173"]) is True
    assert websocket_origin_allowed("http://localhost:59999") is True


def test_websocket_handshake_rejects_disallowed_origin(web_client: TestClient) -> None:
    """CORS middleware never sees a WS upgrade — Origin is checked at handshake."""
    from starlette.websockets import WebSocketDisconnect

    with (
        pytest.raises(WebSocketDisconnect) as exc,
        web_client.websocket_connect(
            "/ws/monitor/no-such-run",
            headers={"Origin": "https://evil.example"},
        ),
    ):
        pass
    assert exc.value.code == 1008


def test_route_coverage_every_route_authed_or_public() -> None:
    """Enumerate ``app.routes`` — the test that catches the twenty-fifth route."""
    public_exact = set(PUBLIC_PATHS)
    missing: list[str] = []
    scanned = 0
    for route in app.routes:
        if isinstance(route, APIWebSocketRoute):
            scanned += 1
            # Handshake is accept_websocket, not Depends — treat path as authed by contract.
            assert route.path.startswith("/ws/")
            continue
        if not isinstance(route, APIRoute):
            continue
        scanned += 1
        path = route.path
        if path in public_exact or path == "/{spa_path:path}":
            continue
        if path.startswith("/assets"):
            continue
        names = []
        for dep in route.dependant.dependencies:
            call = getattr(dep, "call", None)
            names.append(getattr(call, "__name__", "") if call else "")
        if "require_token" not in names:
            missing.append(f"{sorted(route.methods)} {path}")
    if scanned == 0:
        raise AssertionError("route scan matched zero routes — path glob broken")
    assert not missing, (
        "Unauthenticated routes (add dependencies=_AUTH or list in PUBLIC_PATHS):\n"
        + "\n".join(missing)
    )


def test_require_token_dependency_callable() -> None:
    require_token("")  # no token configured in default test env
    assert TOKEN_HEADER == "X-AI-Team-Token"
