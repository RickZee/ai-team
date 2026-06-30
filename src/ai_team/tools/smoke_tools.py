"""Runtime smoke test: boot a generated app and probe its HTTP endpoints.

The unit-test phase exercises route handlers with an in-process test client, so
it can pass while the *running* app is broken (e.g. a logging-config mismatch
that 500s every real request, or a packaging error that stops the server from
booting at all). This module closes that gap: it actually starts the generated
service and makes real HTTP calls, so "tests pass" cannot be confused with
"the app works".

Backend-agnostic — it inspects the per-run workspace on disk (Dockerfile /
docker-compose.yml / a Flask app module), not any backend's in-memory state, so
every orchestration backend reuses the same gate via the same
``docs/smoke_results.json`` contract.

Security (per project rules): subprocess calls use argument lists with
``shell=False``; no ``shell=True``, no string interpolation into a shell.
"""

from __future__ import annotations

import contextlib
import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# Bounded probe budgets so a hung app can never wedge the pipeline.
_BOOT_TIMEOUT_S = 45.0
_PROBE_TIMEOUT_S = 5.0
_POLL_INTERVAL_S = 1.0
_DEFAULT_HEALTH_PATHS = ("/health", "/healthz", "/api/health", "/")


class ProbeResult(BaseModel):
    """One HTTP probe against the running app."""

    method: str = Field(..., description="HTTP method.")
    path: str = Field(..., description="Request path probed.")
    status: int | None = Field(None, description="HTTP status code, or None if unreachable.")
    ok: bool = Field(False, description="True for a 2xx response.")
    detail: str = Field("", description="Short body excerpt or error string.")


class SmokeResult(BaseModel):
    """Structured result of a runtime smoke test."""

    ran: bool = Field(False, description="Whether a server was started and probed.")
    success: bool = Field(False, description="True if the app booted and all probes were 2xx.")
    entrypoint: str = Field("", description="Detected launch mode (compose, module, none).")
    base_url: str = Field("", description="Base URL probed, if any.")
    probes: list[ProbeResult] = Field(default_factory=list, description="Individual probe results.")
    message: str = Field("", description="Human-readable summary / first failure detail.")
    logs: str = Field("", description="Captured server/boot logs (truncated) for diagnosis.")


def _free_port() -> int:
    """Reserve an ephemeral local port for the booted server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _detect_flask_app_target(workspace: Path) -> str | None:
    """Find a ``module:attr`` Flask entrypoint under ``src`` (best-effort)."""
    src = workspace / "src"
    if not src.is_dir():
        return None
    # Prefer a module that exposes a module-level ``app`` (Flask convention).
    for py in sorted(src.rglob("app.py")):
        text = py.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^\s*app\s*=\s*(Flask\(|create_app\()", text, re.MULTILINE):
            module = ".".join(py.relative_to(src).with_suffix("").parts)
            return f"{module}:app"
    # Fall back to a factory function.
    for py in sorted(src.rglob("*.py")):
        text = py.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"^\s*def\s+create_app\s*\(", text, re.MULTILINE):
            module = ".".join(py.relative_to(src).with_suffix("").parts)
            return f"{module}:create_app()"
    return None


def _probe(base_url: str, method: str, path: str, *, body: dict | None = None) -> ProbeResult:
    """Make one HTTP request and capture status + a short body excerpt."""
    url = base_url.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310 - localhost only
    try:
        with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT_S) as resp:  # noqa: S310
            status = int(resp.status)
            excerpt = resp.read(512).decode("utf-8", errors="replace")
            return ProbeResult(
                method=method, path=path, status=status, ok=200 <= status < 300, detail=excerpt
            )
    except urllib.error.HTTPError as e:
        excerpt = ""
        with contextlib.suppress(Exception):
            excerpt = e.read(512).decode("utf-8", errors="replace")
        return ProbeResult(
            method=method, path=path, status=int(e.code), ok=False, detail=excerpt or str(e)
        )
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return ProbeResult(method=method, path=path, status=None, ok=False, detail=str(e))


def _wait_for_boot(base_url: str, health_paths: tuple[str, ...], deadline: float) -> ProbeResult:
    """Poll health endpoints until one answers (any status) or the deadline passes."""
    last = ProbeResult(method="GET", path=health_paths[0], status=None, ok=False, detail="no boot")
    while time.monotonic() < deadline:
        for path in health_paths:
            res = _probe(base_url, "GET", path)
            if res.status is not None:
                return res
            last = res
        time.sleep(_POLL_INTERVAL_S)
    return last


def _expected_probes(workspace: Path) -> list[tuple[str, str, dict | None]]:
    """Derive probes from the acceptance contract; default to a health GET.

    Reads ``expected_output.json`` (``endpoints`` / ``smoke`` hints) when the
    demo provides one; otherwise probes ``/health``.
    """
    default: list[tuple[str, str, dict | None]] = [("GET", "/health", None)]
    contract = workspace / "expected_output.json"
    if not contract.is_file():
        return default
    try:
        spec = json.loads(contract.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    smoke = spec.get("smoke") if isinstance(spec, dict) else None
    probes: list[tuple[str, str, dict | None]] = []
    if isinstance(smoke, list):
        for item in smoke:
            if not isinstance(item, dict):
                continue
            method = str(item.get("method") or "GET").upper()
            path = str(item.get("path") or "").strip()
            body = item.get("body") if isinstance(item.get("body"), dict) else None
            if path:
                probes.append((method, path, body))
    return probes or default


def run_app_smoke(workspace_dir: str | Path, *, write_results: bool = True) -> SmokeResult:
    """Boot the generated app from ``workspace_dir`` and probe it over HTTP.

    Launch strategy, in priority order:
      1. ``docker-compose.yml`` -> ``docker compose up -d`` (mapped to a free
         host port when the compose file publishes a port).
      2. A Flask ``module:app`` entrypoint under ``src`` -> run with the
         workspace's Python via the stdlib server.

    The server is always torn down. When ``write_results`` is set, the outcome
    is written to ``docs/smoke_results.json`` so guardrails and the agent loop
    can read a stable contract.
    """
    workspace = Path(workspace_dir).resolve()
    if not workspace.is_dir():
        return SmokeResult(message=f"Workspace not found: {workspace}")

    compose = next(
        (workspace / n for n in ("docker-compose.yml", "docker-compose.yaml") if (workspace / n).is_file()),
        None,
    )
    if compose is not None:
        result = _smoke_compose(workspace, compose)
    else:
        result = _smoke_flask_module(workspace)

    if write_results:
        out = workspace / "docs" / "smoke_results.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result.model_dump(), indent=2), encoding="utf-8")
    return result


def _smoke_flask_module(workspace: Path) -> SmokeResult:
    """Boot a Flask app module with the stdlib server and probe it."""
    target = _detect_flask_app_target(workspace)
    if target is None:
        return SmokeResult(
            entrypoint="none",
            message="No bootable entrypoint found (no docker-compose.yml, no Flask app under src/)",
        )

    module = target.split(":", 1)[0]
    factory = target.endswith("()")
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    # `flask --app <target> run` resolves both `module:app` and `module:create_app()`.
    cmd = ["python", "-m", "flask", "--app", target.rstrip("()"), "run", "--port", str(port)]
    if factory:
        cmd = ["python", "-m", "flask", "--app", module, "run", "--port", str(port)]

    env_src = str(workspace / "src")
    proc = subprocess.Popen(  # noqa: S603 - arg list, shell=False
        cmd,
        cwd=str(workspace),
        env={"PYTHONPATH": env_src, "PATH": _safe_path(), "FLASK_RUN_HOST": "127.0.0.1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return _probe_and_teardown(workspace, proc, base_url, entrypoint="module")


def _smoke_compose(workspace: Path, compose: Path) -> SmokeResult:
    """Boot the stack with docker compose and probe the published port."""
    if not _has_docker():
        return SmokeResult(
            entrypoint="compose",
            message="docker-compose.yml present but Docker is unavailable; skipping runtime smoke",
        )
    published = _compose_published_port(compose)
    if published is None:
        return SmokeResult(
            entrypoint="compose",
            message="Could not determine a published port from docker-compose.yml",
        )
    base_url = f"http://127.0.0.1:{published}"
    up = subprocess.run(  # noqa: S603
        ["docker", "compose", "up", "-d", "--build"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if up.returncode != 0:
        _compose_down(workspace)
        return SmokeResult(
            entrypoint="compose",
            base_url=base_url,
            message="docker compose up failed",
            logs=(up.stdout + "\n" + up.stderr)[-4000:],
        )
    try:
        return _probe_running(workspace, base_url, entrypoint="compose")
    finally:
        _compose_down(workspace)


def _probe_and_teardown(
    workspace: Path, proc: subprocess.Popen, base_url: str, *, entrypoint: str
) -> SmokeResult:
    """Probe a process-backed server, then terminate it."""
    try:
        return _probe_running(workspace, base_url, entrypoint=entrypoint, proc=proc)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _probe_running(
    workspace: Path,
    base_url: str,
    *,
    entrypoint: str,
    proc: subprocess.Popen | None = None,
) -> SmokeResult:
    """Wait for boot, run the expected probes, and assemble the result."""
    deadline = time.monotonic() + _BOOT_TIMEOUT_S
    boot = _wait_for_boot(base_url, _DEFAULT_HEALTH_PATHS, deadline)
    logs = _drain_logs(proc)
    if boot.status is None:
        return SmokeResult(
            ran=True,
            success=False,
            entrypoint=entrypoint,
            base_url=base_url,
            message=f"Server never became reachable at {base_url}: {boot.detail}",
            logs=logs,
        )

    probes = [_probe(base_url, m, p, body=b) for (m, p, b) in _expected_probes(workspace)]
    failed = [p for p in probes if not p.ok]
    success = not failed
    if failed:
        first = failed[0]
        message = (
            f"{first.method} {first.path} -> "
            f"{first.status if first.status is not None else 'unreachable'}: "
            f"{first.detail[:200]}"
        )
    else:
        message = f"App booted and {len(probes)} probe(s) returned 2xx"
    return SmokeResult(
        ran=True,
        success=success,
        entrypoint=entrypoint,
        base_url=base_url,
        probes=probes,
        message=message,
        logs=logs,
    )


def _drain_logs(proc: subprocess.Popen | None) -> str:
    """Best-effort non-blocking capture of a process's buffered output."""
    if proc is None or proc.stdout is None:
        return ""
    # Only read what is already buffered without blocking on a live server.
    import select

    chunks: list[str] = []
    try:
        while True:
            ready, _, _ = select.select([proc.stdout], [], [], 0)
            if not ready:
                break
            line = proc.stdout.readline()
            if not line:
                break
            chunks.append(line)
            if sum(len(c) for c in chunks) > 4000:
                break
    except (OSError, ValueError):
        pass
    return "".join(chunks)[-4000:]


def _has_docker() -> bool:
    try:
        proc = subprocess.run(  # noqa: S603
            ["docker", "info"], capture_output=True, text=True, timeout=15, check=False
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _compose_published_port(compose: Path) -> int | None:
    """Parse the first published host port from a compose file (safe_load)."""
    try:
        import yaml

        data = yaml.safe_load(compose.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - malformed compose is a smoke failure, not a crash
        return None
    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, dict):
        return None
    for svc in services.values():
        if not isinstance(svc, dict):
            continue
        for mapping in svc.get("ports") or []:
            host = _host_port(mapping)
            if host is not None:
                return host
    return None


def _host_port(mapping: Any) -> int | None:
    """Extract the host port from a compose ``ports`` entry (``"8000:8000"``)."""
    if isinstance(mapping, int):
        return mapping
    if isinstance(mapping, dict):
        published = mapping.get("published")
        return int(published) if published is not None else None
    if isinstance(mapping, str):
        # Form: "[host_ip:]host:container" — take the host part.
        parts = mapping.split(":")
        if len(parts) >= 2:
            with_host = parts[-2]
            return int(with_host) if with_host.isdigit() else None
        if parts and parts[0].isdigit():
            return int(parts[0])
    return None


def _compose_down(workspace: Path) -> None:
    subprocess.run(  # noqa: S603
        ["docker", "compose", "down", "-v"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _safe_path() -> str:
    """Minimal PATH so the booted server still finds python/flask."""
    import os

    return os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
