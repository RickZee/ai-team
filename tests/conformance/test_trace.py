"""TraceBuilder sees an llm call, a tool use, and a tool result."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.trace.builder import TraceBuilder
from tests.conformance.conftest import BACKENDS

pytestmark = pytest.mark.parametrize("thin_run", BACKENDS, indirect=True)


def test_trace_has_llm_and_tools(thin_run) -> None:
    backend = thin_run.backend_name if thin_run.backend_name != "fake-remote" else None
    trace = TraceBuilder(backend=backend, scenario={"id": "thin-slice"}).from_workspace(
        Path(str(thin_run.raw["output_dir"]))
    )
    kinds = {span.type for span in trace.spans}
    assert "llm_call" in kinds
    assert "tool_use" in kinds
    assert "tool_result" in kinds
