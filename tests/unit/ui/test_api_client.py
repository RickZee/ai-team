"""Tests for ``DashboardApiClient``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_team.ui.api_client import DashboardApiClient


class TestDashboardApiClient:
    def test_is_available_true(self) -> None:
        client = DashboardApiClient("http://test")
        with patch.object(client, "health", return_value={"status": "ok"}):
            assert client.is_available() is True
        client.close()

    def test_is_available_false_on_error(self) -> None:
        client = DashboardApiClient("http://test")
        with patch.object(client, "health", side_effect=OSError("down")):
            assert client.is_available() is False
        client.close()

    def test_ws_base_http_to_ws(self) -> None:
        client = DashboardApiClient("http://127.0.0.1:8421")
        assert client.ws_base == "ws://127.0.0.1:8421"
        client.close()

    def test_delete_run_calls_delete(self) -> None:
        client = DashboardApiClient("http://test")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"run_id": "abc", "deleted": True}
        with patch.object(client._client, "request", return_value=mock_response) as req:
            result = client.delete_run("abc")
        assert result["deleted"] is True
        req.assert_called_once()
        assert req.call_args[0][0] == "DELETE"
        client.close()
