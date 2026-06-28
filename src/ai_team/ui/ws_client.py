"""
WebSocket helpers for the AI-Team dashboard API.

Used by the Textual TUI to stream runs and monitor snapshots the same way
as the React dashboard.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import websockets


async def iter_monitor_messages(ws_base: str, run_id: str) -> AsyncIterator[dict[str, Any]]:
    """Yield monitor WebSocket messages until terminal or error."""
    url = f"{ws_base.rstrip('/')}/ws/monitor/{run_id}"
    async with websockets.connect(url) as ws:
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            yield msg
            if msg.get("type") in ("complete", "error"):
                break


async def run_via_websocket(
    ws_base: str,
    payload: dict[str, Any],
    on_message: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Start a run on ``/ws/run`` and return the last terminal message."""
    url = f"{ws_base.rstrip('/')}/ws/run"
    last: dict[str, Any] = {}
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps(payload))
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            last = msg
            if on_message:
                on_message(msg)
            if msg.get("type") in ("complete", "error", "hitl_required"):
                break
    return last


def run_monitor_sync(
    ws_base: str,
    run_id: str,
    on_message: Callable[[dict[str, Any]], None],
) -> None:
    """Blocking wrapper for monitor WebSocket iteration (TUI worker threads)."""

    async def _run() -> None:
        async for msg in iter_monitor_messages(ws_base, run_id):
            on_message(msg)

    asyncio.run(_run())


def run_start_sync(
    ws_base: str,
    payload: dict[str, Any],
    on_message: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """Blocking wrapper to start a run via WebSocket."""

    def _cb(msg: dict[str, Any]) -> None:
        on_message(msg)

    return asyncio.run(run_via_websocket(ws_base, payload, on_message=_cb))
