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


def _port_in_use(port: int) -> bool:
    """True if something is already listening on ``port`` (localhost)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


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


def _probe(
    base_url: str, method: str, path: str, *, body: dict | None = None
) -> tuple[ProbeResult, str]:
    """Make one HTTP request; return the result and the raw response body.

    The raw body (separate from the truncated ``detail`` excerpt) lets a probe
    sequence capture a field — e.g. the id a ``POST`` returned — for use in a
    later probe's path or body.
    """
    url = base_url.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310 - localhost only
    try:
        with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT_S) as resp:  # noqa: S310
            status = int(resp.status)
            raw = resp.read(2048).decode("utf-8", errors="replace")
            res = ProbeResult(
                method=method, path=path, status=status, ok=200 <= status < 300, detail=raw[:512]
            )
            return res, raw
    except urllib.error.HTTPError as e:
        raw = ""
        with contextlib.suppress(Exception):
            raw = e.read(2048).decode("utf-8", errors="replace")
        res = ProbeResult(
            method=method, path=path, status=int(e.code), ok=False, detail=(raw or str(e))[:512]
        )
        return res, raw
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return ProbeResult(method=method, path=path, status=None, ok=False, detail=str(e)), ""


def _interpolate(value: Any, variables: dict[str, str]) -> Any:
    """Substitute ``{name}`` tokens in a string (or recursively in a dict)."""
    if isinstance(value, str):
        for k, v in variables.items():
            value = value.replace("{" + k + "}", v)
        return value
    if isinstance(value, dict):
        return {k: _interpolate(v, variables) for k, v in value.items()}
    return value


def _run_probe_sequence(base_url: str, specs: list[dict[str, Any]]) -> list[ProbeResult]:
    """Run probes in order, threading captured variables between them.

    Each spec is ``{method, path, body?, save?}``. ``save`` maps a variable name
    to a key in the JSON response, e.g. ``{"id": "id"}`` captures the created
    resource id so a later ``DELETE /todos/{id}`` can reference it. ``{name}``
    tokens in ``path`` and ``body`` are interpolated from captured variables.
    """
    variables: dict[str, str] = {}
    results: list[ProbeResult] = []
    for spec in specs:
        method = str(spec.get("method") or "GET").upper()
        path = str(_interpolate(spec.get("path") or "", variables))
        raw_body = spec.get("body")
        body = _interpolate(raw_body, variables) if isinstance(raw_body, dict) else None
        res, raw = _probe(base_url, method, path, body=body)
        results.append(res)
        save = spec.get("save")
        if isinstance(save, dict) and raw:
            with contextlib.suppress(ValueError, TypeError):
                payload = json.loads(raw)
                for var, key in save.items():
                    if isinstance(payload, dict) and key in payload:
                        variables[str(var)] = str(payload[key])
    return results


def _wait_for_boot(base_url: str, health_paths: tuple[str, ...], deadline: float) -> ProbeResult:
    """Poll health endpoints until one answers (any status) or the deadline passes."""
    last = ProbeResult(method="GET", path=health_paths[0], status=None, ok=False, detail="no boot")
    while time.monotonic() < deadline:
        for path in health_paths:
            res, _ = _probe(base_url, "GET", path)
            if res.status is not None:
                return res
            last = res
        time.sleep(_POLL_INTERVAL_S)
    return last


def _expected_probes(workspace: Path) -> list[dict[str, Any]]:
    """Derive an ordered probe sequence from the acceptance contract.

    Reads a ``smoke`` list from ``expected_output.json`` when the demo provides
    one; otherwise probes ``GET /health``. Each entry is
    ``{method, path, body?, save?}`` — ``save`` captures a JSON response field
    into a variable (e.g. ``{"id": "id"}``) and ``{var}`` tokens in later
    ``path``/``body`` are interpolated, so a contract can drive a full CRUD
    round-trip (create → read → update → delete) against the running app.
    """
    default: list[dict[str, Any]] = [{"method": "GET", "path": "/health"}]
    contract = workspace / "expected_output.json"
    if not contract.is_file():
        return default
    try:
        spec = json.loads(contract.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    smoke = spec.get("smoke") if isinstance(spec, dict) else None
    probes: list[dict[str, Any]] = []
    if isinstance(smoke, list):
        for item in smoke:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if not path:
                continue
            entry: dict[str, Any] = {
                "method": str(item.get("method") or "GET").upper(),
                "path": path,
            }
            if isinstance(item.get("body"), dict):
                entry["body"] = item["body"]
            if isinstance(item.get("save"), dict):
                entry["save"] = item["save"]
            probes.append(entry)
    return probes or default


def run_app_smoke(workspace_dir: str | Path, *, write_results: bool = True) -> SmokeResult:
    """Boot the generated app from ``workspace_dir`` and probe it over HTTP.

    Launch strategy, in priority order:
      1. ``docker-compose.yml`` -> ``docker compose up -d`` on the host port the
         compose file publishes. If that port is already bound by something
         else, the smoke is skipped rather than risk probing a foreign service.
      2. A Flask ``module:app`` entrypoint under ``src`` -> run on a free
         ephemeral port with the workspace's Python via the stdlib server.

    The server is always torn down. When ``write_results`` is set, the outcome
    is written to ``docs/smoke_results.json`` so guardrails and the agent loop
    can read a stable contract.
    """
    workspace = Path(workspace_dir).resolve()
    if not workspace.is_dir():
        return SmokeResult(message=f"Workspace not found: {workspace}")

    compose = next(
        (
            workspace / n
            for n in ("docker-compose.yml", "docker-compose.yaml")
            if (workspace / n).is_file()
        ),
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


def load_or_run_smoke(workspace_dir: str | Path, *, max_age_s: float = 600.0) -> SmokeResult:
    """Reuse a recent ``docs/smoke_results.json`` if present, else boot the app.

    Booting the app (especially ``docker compose up --build``) is expensive, so
    every consumer in a single run — the QA agent (via the MCP tool), the SDK
    recovery loop, the LangGraph smoke node, and the shared post-run gate —
    shares one result rather than re-booting. The file is trusted only when it
    is at most ``max_age_s`` old, so a stale result from a previous run does not
    mask the current one.
    """
    workspace = Path(workspace_dir).resolve()
    cached = workspace / "docs" / "smoke_results.json"
    try:
        if cached.is_file() and (time.time() - cached.stat().st_mtime) <= max_age_s:
            data = json.loads(cached.read_text(encoding="utf-8"))
            return SmokeResult.model_validate(data)
    except (OSError, ValueError):
        pass  # unreadable / malformed cache -> fall through and boot
    return run_app_smoke(workspace)


def _smoke_flask_module(workspace: Path) -> SmokeResult:
    """Boot a Flask app module with the stdlib server and probe it."""
    target = _detect_flask_app_target(workspace)
    if target is None:
        return SmokeResult(
            entrypoint="none",
            message="No bootable entrypoint found (no docker-compose.yml, no Flask app under src/)",
        )

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    # `flask --app <spec> run` resolves both `module:app` and a `module:create_app()`
    # factory; strip the call parens flask doesn't expect on the CLI.
    app_spec = target.rstrip("()")
    cmd = ["python", "-m", "flask", "--app", app_spec, "run", "--port", str(port)]

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
    if _port_in_use(published):
        # Something already listens on the publish port. Probing it would test a
        # foreign service (false pass/fail); skip rather than report a bogus result.
        return SmokeResult(
            entrypoint="compose",
            message=(
                f"Host port {published} is already in use; skipping compose smoke "
                "to avoid probing an unrelated service"
            ),
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

    probes = _run_probe_sequence(base_url, _expected_probes(workspace))
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
    """Best-effort non-blocking capture of a live process's buffered output.

    Reads directly from the pipe fd with ``os.read`` after ``select`` reports it
    readable, so a server that wrote a partial (newline-less) line and is still
    running cannot block us — unlike ``readline()``, which waits for a full line.
    """
    if proc is None or proc.stdout is None:
        return ""
    import os
    import select

    fd = proc.stdout.fileno()
    chunks: list[bytes] = []
    total = 0
    try:
        while total < 4000:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            data = os.read(fd, 4096)  # returns what's buffered, no newline wait
            if not data:  # EOF (process exited and pipe drained)
                break
            chunks.append(data)
            total += len(data)
    except (OSError, ValueError):
        pass
    return b"".join(chunks).decode("utf-8", errors="replace")[-4000:]


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
