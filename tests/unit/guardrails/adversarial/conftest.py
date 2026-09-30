"""Pytest fixtures for guardrail tests: TaskOutput-like mocks and realistic AI output samples."""

from __future__ import annotations

from typing import Any

import pytest


class TaskOutputMock:
    """Mock for CrewAI TaskOutput: has .raw attribute used by guardrail adapters."""

    def __init__(self, raw: str) -> None:
        self.raw = raw

    def __repr__(self) -> str:
        return f"TaskOutputMock(len(raw)={len(self.raw)})"


@pytest.fixture
def task_output_factory() -> Any:
    """Return a callable that builds TaskOutputMock(raw=text)."""

    def _make(raw: str) -> TaskOutputMock:
        return TaskOutputMock(raw=raw)

    return _make
