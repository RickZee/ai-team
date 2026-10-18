"""The local trace stack is pinned, fans out to every viewer and stays on localhost (otel R5)."""

from __future__ import annotations

from typing import Any

import yaml

from tests.unit.repo._paths import REPO_ROOT

_COMPOSE = REPO_ROOT / "docker" / "docker-compose.yml"
_COLLECTOR = REPO_ROOT / "docker" / "otel-collector.yaml"


def _services() -> dict[str, Any]:
    return yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))["services"]


def _observability() -> dict[str, Any]:
    return {k: v for k, v in _services().items() if "observability" in (v.get("profiles") or [])}


def test_observability_profile_has_collector_aspire_and_phoenix() -> None:
    assert set(_observability()) == {"otel-collector", "aspire-dashboard", "phoenix"}


def test_images_are_pinned() -> None:
    for name, svc in _observability().items():
        image = svc["image"]
        tag = image.rsplit(":", 1)[-1] if ":" in image else ""
        assert tag and tag != "latest", f"{name} image must be pinned: {image}"


def test_every_published_port_is_localhost_only() -> None:
    for name, svc in _observability().items():
        for port in svc.get("ports") or []:
            assert str(port).startswith("127.0.0.1:"), f"{name} publishes {port} beyond localhost"


def test_phoenix_keeps_its_data() -> None:
    phoenix = _observability()["phoenix"]
    assert phoenix["environment"]["PHOENIX_WORKING_DIR"] == "/mnt/data"
    assert any(str(v).endswith(":/mnt/data") for v in phoenix["volumes"])


def test_collector_pipeline_fans_out_with_processors_and_health() -> None:
    cfg = yaml.safe_load(_COLLECTOR.read_text(encoding="utf-8"))
    traces = cfg["service"]["pipelines"]["traces"]
    assert traces["processors"] == ["memory_limiter", "batch"]
    assert set(traces["exporters"]) == {"otlphttp/aspire", "otlphttp/phoenix", "file"}
    assert "health_check" in cfg["service"]["extensions"]
    assert cfg["exporters"]["otlphttp/phoenix"]["endpoint"] == "http://phoenix:6006"


def test_native_backends_are_tagged() -> None:
    services = _services()
    for name in ("strands", "agent-framework"):
        attrs = services[name]["environment"]["OTEL_RESOURCE_ATTRIBUTES"]
        assert f"ai_team.backend={name}" in attrs
        assert "ai_team.source=framework" in attrs
        assert "openinference.project.name=ai-team" in attrs
