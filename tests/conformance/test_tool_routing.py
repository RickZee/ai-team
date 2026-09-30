"""Every tool call on the thin slice went through ToolBus.invoke."""

from __future__ import annotations

import pytest

from tests.conformance.conftest import BACKENDS, audit_rows

pytestmark = pytest.mark.parametrize("thin_run", BACKENDS, indirect=True)


def test_tool_calls_are_audited(thin_run) -> None:
    rows = audit_rows(thin_run)
    uses = [row for row in rows if row.get("type") == "tool_use"]
    names = [row.get("tool") for row in uses]
    assert names.count("write_file") == 2
    assert "commit_write" in names
    assert len(uses) == len([row for row in rows if row.get("type") == "tool_result"])
