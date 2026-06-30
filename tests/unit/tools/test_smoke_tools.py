"""Unit tests for the runtime smoke runner (boots a generated app, probes HTTP).

Covers the gap that motivated the tool: an app whose unit tests pass but whose
*running* server is broken. The "broken" fixture mirrors the real failure —
route handlers that work under a test client but 500 once a real request hits a
misconfigured logging chain.
"""

from __future__ import annotations

import importlib.util
import json

import pytest
from ai_team.tools.smoke_tools import (
    SmokeResult,
    _compose_published_port,
    _host_port,
    run_app_smoke,
)

_HAS_FLASK = importlib.util.find_spec("flask") is not None
_flask_required = pytest.mark.skipif(not _HAS_FLASK, reason="flask not installed")


def _make_app(workspace, body: str) -> None:
    src = workspace / "src" / "todo"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "app.py").write_text(body)


_HEALTHY_APP = """
from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})
"""

# Mirrors the real bug: a request hook that explodes on every live request, so
# the test client may pass but the running server returns 500.
_BROKEN_APP = """
from flask import Flask, jsonify

app = Flask(__name__)


@app.before_request
def _boom():
    raise RuntimeError("logger misconfigured")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})
"""


class TestHostPortParsing:
    def test_string_host_container(self) -> None:
        assert _host_port("8000:8000") == 8000

    def test_string_with_host_ip(self) -> None:
        assert _host_port("127.0.0.1:5000:5000") == 5000

    def test_int_mapping(self) -> None:
        assert _host_port(8080) == 8080

    def test_dict_published(self) -> None:
        assert _host_port({"published": 9000, "target": 9000}) == 9000

    def test_unparseable_returns_none(self) -> None:
        assert _host_port("not-a-port") is None


class TestComposePortDetection:
    def test_reads_first_published_port(self, tmp_path) -> None:
        (tmp_path / "docker-compose.yml").write_text(
            "services:\n  web:\n    ports:\n      - '8000:8000'\n"
        )
        assert _compose_published_port(tmp_path / "docker-compose.yml") == 8000

    def test_malformed_compose_returns_none(self, tmp_path) -> None:
        (tmp_path / "docker-compose.yml").write_text("{ not: valid: yaml: ::")
        assert _compose_published_port(tmp_path / "docker-compose.yml") is None


class TestNoEntrypoint:
    def test_no_app_no_compose_is_skip_not_failure(self, tmp_path) -> None:
        (tmp_path / "src").mkdir()
        result = run_app_smoke(tmp_path)
        assert isinstance(result, SmokeResult)
        assert result.ran is False
        assert result.success is False
        assert result.entrypoint == "none"

    def test_missing_workspace(self, tmp_path) -> None:
        result = run_app_smoke(tmp_path / "nope")
        assert result.ran is False


@_flask_required
class TestRuntimeBoot:
    def test_healthy_app_passes(self, tmp_path) -> None:
        _make_app(tmp_path, _HEALTHY_APP)
        result = run_app_smoke(tmp_path)
        assert result.ran is True
        assert result.success is True, result.message
        assert any(p.path == "/health" and p.ok for p in result.probes)
        # Contract file written for the guardrail to read.
        written = json.loads((tmp_path / "docs" / "smoke_results.json").read_text())
        assert written["success"] is True

    def test_broken_app_fails_despite_importable_routes(self, tmp_path) -> None:
        # The route function is defined and importable (unit tests would pass),
        # but every real request 500s — exactly what the gate must catch.
        _make_app(tmp_path, _BROKEN_APP)
        result = run_app_smoke(tmp_path)
        assert result.ran is True
        assert result.success is False
        assert any(p.status == 500 for p in result.probes)
        written = json.loads((tmp_path / "docs" / "smoke_results.json").read_text())
        assert written["success"] is False
