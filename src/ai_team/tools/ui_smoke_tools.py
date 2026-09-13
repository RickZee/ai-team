"""UI smoke: Playwright against a local app only (R13).

Mirrors ``smoke_tools.py`` — same result-file contract, same "never probe a
foreign service" rule. Off-path for UI-less scenarios (``skipped``, never ``pass``).
"""

from __future__ import annotations

import json
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

_RESULT_NAME = "ui_smoke_results.json"
_BOOT_TIMEOUT_S = 45.0
_DEFAULT_VIEWPORT = {"width": 1280, "height": 720}


class UiStepResult(BaseModel):
    """One UI action and its deterministic outcome."""

    action: str
    selector: str | None = None
    outcome: Literal["pass", "fail", "skipped"] = "skipped"
    console_errors: list[str] = Field(default_factory=list)
    page_errors: list[str] = Field(default_factory=list)
    screenshot_path: str | None = None
    duration_ms: int = 0


class UiSmokeResult(BaseModel):
    """Structured result of a UI smoke run."""

    status: Literal["pass", "fail", "skipped"] = "skipped"
    steps: list[UiStepResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_s: float = 0.0
    base_url: str | None = None
    skip_reason: str | None = None
    ran: bool = False
    success: bool = False
    kind: str = "ui"


def _is_local_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def _write_result(workspace: Path, result: UiSmokeResult) -> Path:
    dest = workspace / "docs" / _RESULT_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return dest


def run_ui_smoke(
    workspace: Path,
    *,
    scenario: dict[str, Any] | None = None,
    item_id: str = "ui",
    playwright_factory: Any | None = None,
) -> UiSmokeResult:
    """Boot (optional) and probe the scenario's local UI.

    Returns ``skipped`` when ``scenario.ui`` is absent. Refuses any non-local
    ``base_url``. Console and page errors fail the step.
    """
    started = datetime.now(UTC)
    ui = (scenario or {}).get("ui")
    if not ui:
        result = UiSmokeResult(status="skipped", skip_reason="scenario.ui is null")
        _write_result(workspace, result)
        return result

    base_url = str(ui.get("base_url") or "").strip()
    if not base_url:
        result = UiSmokeResult(status="skipped", skip_reason="ui.base_url missing")
        _write_result(workspace, result)
        return result
    if not _is_local_url(base_url):
        result = UiSmokeResult(
            status="fail",
            base_url=base_url,
            skip_reason="refused foreign service",
            steps=[
                UiStepResult(
                    action="navigate",
                    outcome="fail",
                    page_errors=["refused non-local base_url"],
                )
            ],
        )
        _write_result(workspace, result)
        logger.warning("ui_smoke_refused_foreign", base_url=base_url)
        return result

    boot = ui.get("boot_cmd")
    proc: subprocess.Popen[bytes] | None = None
    if isinstance(boot, list) and boot:
        try:
            proc = subprocess.Popen(  # noqa: S603 — argument list
                [str(x) for x in boot],
                cwd=workspace,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ready = str(ui.get("ready_path") or "/")
            _wait_ready(base_url, ready)
        except OSError as exc:
            result = UiSmokeResult(
                status="fail",
                base_url=base_url,
                skip_reason=f"boot failed: {exc}",
            )
            _write_result(workspace, result)
            return result

    steps = list(ui.get("steps") or [{"action": "navigate", "selector": None}])
    viewport = ui.get("viewport") or _DEFAULT_VIEWPORT
    step_results: list[UiStepResult] = []
    try:
        step_results = _run_playwright(
            base_url,
            steps,
            workspace=workspace,
            item_id=item_id,
            viewport=viewport,
            factory=playwright_factory,
        )
    except Exception as exc:  # noqa: BLE001 — surface as a failed step
        logger.warning("ui_smoke_playwright_failed", error=str(exc))
        step_results = [UiStepResult(action="navigate", outcome="fail", page_errors=[str(exc)])]
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    failed = any(s.outcome == "fail" for s in step_results)
    result = UiSmokeResult(
        status="fail" if failed else "pass",
        steps=step_results,
        started_at=started,
        duration_s=(datetime.now(UTC) - started).total_seconds(),
        base_url=base_url,
        ran=True,
        success=not failed,
    )
    _write_result(workspace, result)
    return result


def _wait_ready(base_url: str, ready_path: str) -> None:
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    deadline = time.monotonic() + _BOOT_TIMEOUT_S
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.2)
    del ready_path


def _run_playwright(
    base_url: str,
    steps: list[dict[str, Any]],
    *,
    workspace: Path,
    item_id: str,
    viewport: dict[str, Any],
    factory: Any | None,
) -> list[UiStepResult]:
    if factory is not None:
        produced = factory(base_url, steps, workspace, item_id, viewport)
        return list(produced)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is not installed") from exc

    out: list[UiStepResult] = []
    shot_dir = workspace / "docs" / "verification" / item_id
    shot_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={
                "width": int(viewport.get("width", 1280)),
                "height": int(viewport.get("height", 720)),
            }
        )
        console: list[str] = []
        page_errors: list[str] = []
        page.on(
            "console",
            lambda msg: console.append(f"{msg.type}: {msg.text}") if msg.type == "error" else None,
        )
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        for i, step in enumerate(steps):
            t0 = time.monotonic()
            action = str(step.get("action") or "navigate")
            selector = step.get("selector")
            try:
                if action == "navigate" or i == 0:
                    page.goto(base_url, wait_until="domcontentloaded")
                if selector and action == "click":
                    page.click(str(selector))
                shot = shot_dir / f"step-{i:02d}.png"
                page.screenshot(path=str(shot))
                errors = [c for c in console if c.startswith("error")]
                outcome: Literal["pass", "fail", "skipped"] = (
                    "fail" if errors or page_errors else "pass"
                )
                out.append(
                    UiStepResult(
                        action=action,
                        selector=str(selector) if selector else None,
                        outcome=outcome,
                        console_errors=list(console),
                        page_errors=list(page_errors),
                        screenshot_path=str(shot.relative_to(workspace)),
                        duration_ms=int((time.monotonic() - t0) * 1000),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                out.append(
                    UiStepResult(
                        action=action,
                        selector=str(selector) if selector else None,
                        outcome="fail",
                        page_errors=[str(exc)],
                        duration_ms=int((time.monotonic() - t0) * 1000),
                    )
                )
        browser.close()
    return out


def load_ui_smoke(workspace: Path) -> dict[str, Any] | None:
    """Load ``docs/ui_smoke_results.json`` if present."""
    path = workspace / "docs" / _RESULT_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
