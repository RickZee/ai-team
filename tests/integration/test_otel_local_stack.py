"""Against the real local Docker stack: export reaches the collector file and Phoenix (otel R7.4).

Skips unless Docker works and ``AI_TEAM_DOCKER_TESTS=1``. Runs its own compose project on
spare ports with temporary folders, so it never touches ``output/`` or a stack you already have
running. Run with ``make test-otel-integration``.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from evals.trace import otel_run

pytestmark = [pytest.mark.integration, pytest.mark.slow]

REPO = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO / "docker" / "docker-compose.yml"
PROJECT = "aiteam-otel-test"


def _docker_ok() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


if os.environ.get("AI_TEAM_DOCKER_TESTS") != "1":
    pytest.skip("set AI_TEAM_DOCKER_TESTS=1 to run the Docker stack tests", allow_module_level=True)
if not _docker_ok():
    pytest.skip("Docker is not available", allow_module_level=True)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class Stack:
    env: dict[str, str]
    otel_dir: Path
    http: int
    phoenix: int
    health: int

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.http}"

    def _run(self, *args: str, timeout: int) -> subprocess.CompletedProcess[str]:
        cmd = [
            "docker",
            "compose",
            "-p",
            PROJECT,
            "-f",
            str(COMPOSE_FILE),
            "--profile",
            "observability",
            *args,
        ]
        return subprocess.run(
            cmd, check=True, env=self.env, timeout=timeout, capture_output=True, text=True
        )

    def compose(self, *args: str, timeout: int = 300) -> None:
        self._run(*args, timeout=timeout)

    def collector_logs(self) -> str:
        out = self._run("logs", "otel-collector", timeout=60)
        return out.stdout + out.stderr


def _wait(url: str, seconds: float = 120) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310 - localhost
                if resp.status < 500:
                    return
        except OSError:
            time.sleep(1)
    raise AssertionError(f"not ready after {seconds}s: {url}")


@pytest.fixture(scope="module")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Stack]:
    root = tmp_path_factory.mktemp("otel-stack")
    otel_dir, phoenix_dir = root / "otel", root / "phoenix"
    otel_dir.mkdir()
    phoenix_dir.mkdir()
    ports = {name: _free_port() for name in ("grpc", "http", "health", "aspire", "phoenix")}
    env = {
        **os.environ,
        "AI_TEAM_OTEL_DIR": str(otel_dir),
        "AI_TEAM_PHOENIX_DIR": str(phoenix_dir),
        "AI_TEAM_OTEL_GRPC_PORT": str(ports["grpc"]),
        "AI_TEAM_OTEL_HTTP_PORT": str(ports["http"]),
        "AI_TEAM_OTEL_HEALTH_PORT": str(ports["health"]),
        "AI_TEAM_ASPIRE_PORT": str(ports["aspire"]),
        "AI_TEAM_PHOENIX_PORT": str(ports["phoenix"]),
    }
    st = Stack(env, otel_dir, ports["http"], ports["phoenix"], ports["health"])
    st.compose("up", "-d", "otel-collector", "aspire-dashboard", "phoenix")
    try:
        _wait(f"http://127.0.0.1:{st.health}/")
        _wait(f"http://127.0.0.1:{st.phoenix}/")
        yield st
    finally:
        st.compose("down", "-v", timeout=120)


def _make_run(root: Path, name: str) -> Path:
    run = root / name
    (run / "logs").mkdir(parents=True)
    ts = "2026-10-18T12:00:0{}+00:00"
    (run / "run.json").write_text(
        json.dumps(
            {
                "project_id": name,
                "backend": "langgraph",
                "started_at": ts.format(0),
                "output_dir": str(run),
                "workspace_dir": str(run),
            }
        )
    )
    base = {
        "tool": "write_file",
        "tool_name": "write_file",
        "agent_role": "dev",
        "phase": "development",
        "run_id": name,
    }
    rows = [
        {**base, "type": "tool_use", "timestamp": ts.format(1)},
        {**base, "type": "tool_result", "timestamp": ts.format(2), "ok": True},
    ]
    (run / "logs" / "audit.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return run


def _phoenix_tool_spans(st: Stack, tool: str) -> list[dict]:
    query = urllib.parse.urlencode({"limit": 1000})
    url = f"http://127.0.0.1:{st.phoenix}/v1/projects/ai-team/spans/otlpv1?{query}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - localhost
            data = json.loads(resp.read())
    except OSError:
        return []
    return [s for s in data.get("data", []) if s.get("name") == f"execute_tool {tool}"]


def _until(fn, seconds: float = 30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = fn()
        if found:
            return found
        time.sleep(1)
    return fn()


def test_export_reaches_file_and_phoenix_and_survives_restart(stack: Stack, tmp_path: Path) -> None:
    run = _make_run(tmp_path, "otel-it-1")
    status = otel_run.export_run(run, endpoint=stack.endpoint)
    assert status["status"] == "posted", status

    raw = stack.otel_dir / "traces.jsonl"
    assert _until(lambda: raw.is_file() and "otel-it-1" in raw.read_text()), "not in collector file"
    assert _until(lambda: _phoenix_tool_spans(stack, "write_file")), "not in Phoenix"
    # Aspire has no query API; a rejected batch shows up as a dropped export in the collector.
    assert "Exporting failed" not in stack.collector_logs(), "an exporter (Aspire?) dropped spans"

    stack.compose("restart", "phoenix", timeout=120)
    _wait(f"http://127.0.0.1:{stack.phoenix}/")
    assert _until(lambda: _phoenix_tool_spans(stack, "write_file")), "lost after Phoenix restart"


def test_backfill_with_one_broken_run(stack: Stack, tmp_path: Path, monkeypatch) -> None:
    good = _make_run(tmp_path, "otel-it-good")
    _make_run(tmp_path, "otel-it-broken")
    real = otel_run.build_trace

    def flaky(run_dir: Path):
        if run_dir.name.endswith("broken"):
            raise ValueError("cannot build")
        return real(run_dir)

    monkeypatch.setattr(otel_run, "build_trace", flaky)
    summary = otel_run.export_all(tmp_path, endpoint=stack.endpoint)
    assert summary["exported"] == 1
    assert [f["run"] for f in summary["failed"]] == ["otel-it-broken"]
    assert json.loads((good / "logs" / "otel.export.json").read_text())["status"] == "posted"
