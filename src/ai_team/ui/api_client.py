"""
HTTP client for the AI-Team web dashboard API.

Shared by the Textual TUI (and other non-browser clients) so run lifecycle,
artifacts, and catalog endpoints stay aligned with ``ui.web.server``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_API_BASE = os.environ.get("AI_TEAM_WEB_URL", "http://127.0.0.1:8421")


class DashboardApiClient:
    """Thin REST wrapper around ``/api/*`` endpoints."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        root = (base_url or DEFAULT_API_BASE).rstrip("/")
        self.base_url = root
        self.api_root = f"{root}/api"
        self._client = httpx.Client(base_url=self.api_root, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> DashboardApiClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path, **kwargs)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def is_available(self) -> bool:
        try:
            data = self.health()
            return data.get("status") == "ok"
        except Exception as exc:
            logger.debug("dashboard_api_unavailable", error=str(exc))
            return False

    def backends(self) -> list[dict[str, Any]]:
        return self._request("GET", "/backends")["backends"]

    def profiles(self) -> dict[str, Any]:
        return self._request("GET", "/profiles")

    def estimate(self, complexity: str = "medium") -> dict[str, Any]:
        return self._request("POST", "/estimate", json={"complexity": complexity})

    def list_runs(self) -> list[dict[str, Any]]:
        return self._request("GET", "/runs")["runs"]

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/runs/{run_id}")

    def start_demo(self) -> dict[str, Any]:
        return self._request("POST", "/demo")

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return self._request("POST", f"/runs/{run_id}/cancel")

    def delete_run(self, run_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/runs/{run_id}")

    def resume_run(self, run_id: str, feedback: str) -> dict[str, Any]:
        return self._request("POST", f"/runs/{run_id}/resume", json={"feedback": feedback})

    def registry_runs(self) -> list[dict[str, Any]]:
        return self._request("GET", "/registry/runs")["runs"]

    def project_tree(self, project_id: str, root: str = "workspace") -> list[dict[str, Any]]:
        return self._request("GET", f"/projects/{project_id}/tree", params={"root": root})["tree"]

    def project_file(self, project_id: str, path: str, root: str = "workspace") -> dict[str, Any]:
        return self._request(
            "GET",
            f"/projects/{project_id}/file",
            params={"path": path, "root": root},
        )

    def project_tests(self, project_id: str) -> dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}/tests")

    def project_architecture(self, project_id: str) -> dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}/architecture")

    @property
    def ws_base(self) -> str:
        if self.base_url.startswith("https://"):
            return "wss://" + self.base_url.removeprefix("https://")
        return "ws://" + self.base_url.removeprefix("http://")
