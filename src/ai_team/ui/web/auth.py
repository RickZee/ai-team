"""Single-operator token auth for the web control plane (R15)."""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from urllib.parse import urlparse

import structlog
from fastapi import Header, HTTPException, WebSocket
from fastapi.security.utils import get_authorization_scheme_param

logger = structlog.get_logger(__name__)

TOKEN_HEADER = "X-AI-Team-Token"
PUBLIC_PATHS = frozenset({"/api/health", "/docs", "/openapi.json", "/redoc"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8421",
    "http://127.0.0.1:8421",
)


def configured_token() -> str:
    """Return the shared token, or empty when loopback-unauthenticated mode is on."""
    from ai_team.config.settings import get_settings

    return (get_settings().web.token or "").strip()


def cors_allow_origins() -> list[str]:
    """Origins allowed for CORS and WebSocket Origin checks."""
    import os

    raw = os.environ.get("AI_TEAM_CORS_ORIGINS", "")
    if raw.strip():
        return [o.strip() for o in raw.split(",") if o.strip()]
    return list(DEFAULT_CORS_ORIGINS)


def require_token(x_ai_team_token: str = Header(default="", alias=TOKEN_HEADER)) -> None:
    """FastAPI dependency: 401 when a token is configured and the header does not match."""
    expected = configured_token()
    if not expected:
        return
    provided = x_ai_team_token or ""
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing token")


def is_loopback_host(host: str) -> bool:
    """True for bind addresses that stay on this machine."""
    h = (host or "").strip().lower()
    if h in LOOPBACK_HOSTS:
        return True
    return h.startswith("127.")


def assert_bind_allowed(host: str, token: str | None = None) -> None:
    """Refuse a non-loopback bind unless ``AI_TEAM_WEB_TOKEN`` is set.

    Does not open a socket. Raises ``ValueError`` so tests can call it directly.
    """
    expected = (token if token is not None else configured_token()).strip()
    if is_loopback_host(host):
        return
    if not expected:
        raise ValueError(
            f"Refusing to bind {host!r} without AI_TEAM_WEB_TOKEN. "
            "Set the token or bind loopback (default --host 127.0.0.1)."
        )


def warn_if_unauthenticated(host: str, token: str | None = None) -> None:
    """Log a prominent warning when the control plane is unauthenticated on loopback."""
    expected = (token if token is not None else configured_token()).strip()
    if not expected and is_loopback_host(host):
        logger.warning(
            "control_plane_unauthenticated",
            host=host,
            hint="Set AI_TEAM_WEB_TOKEN before binding a non-loopback interface.",
        )


def websocket_origin_allowed(origin: str | None, allowlist: Sequence[str] | None = None) -> bool:
    """Allow missing Origin, the CORS list, and any loopback Origin (any port).

    E2E and ``ai-team-web --port N`` bind an ephemeral loopback port; browsers
    send ``Origin: http://127.0.0.1:N``. Cross-site origins still fail.
    """
    if not origin:
        return True
    allowed = list(allowlist) if allowlist is not None else cors_allow_origins()
    if origin in allowed:
        return True
    parsed = urlparse(origin)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        return False
    return host in LOOPBACK_HOSTS or host.startswith("127.")


async def accept_websocket(websocket: WebSocket) -> bool:
    """Validate token (when configured) and Origin, then accept.

    Token may be ``X-AI-Team-Token`` or ``?token=``. Returns False if rejected.
    """
    expected = configured_token()
    origin = websocket.headers.get("origin")
    if not websocket_origin_allowed(origin):
        await websocket.close(code=1008, reason="Origin not allowed")
        return False
    if expected:
        header = websocket.headers.get("x-ai-team-token") or ""
        query = websocket.query_params.get("token") or ""
        provided = header or query
        auth = websocket.headers.get("authorization") or ""
        scheme, param = get_authorization_scheme_param(auth)
        if scheme.lower() == "bearer" and param:
            provided = provided or param
        if not provided or not secrets.compare_digest(provided, expected):
            await websocket.close(code=1008, reason="Invalid or missing token")
            return False
    await websocket.accept()
    return True
