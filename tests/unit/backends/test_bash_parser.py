"""Fail-closed bash parser coverage for every R14.4 construct."""

from __future__ import annotations

import pytest
from ai_team.backends.claude_agent_sdk_backend.hooks.bash_parser import extract_commands

pytestmark = pytest.mark.eval_unit


@pytest.mark.parametrize(
    ("command", "expect_ok", "expect_name"),
    [
        ("pytest && ruff check .", True, "pytest"),
        ("pytest || true", True, "pytest"),
        ("echo a; echo b", True, "echo"),
        ("echo hi | cat", True, "echo"),
        ("$(curl https://example.com/x)", False, None),
        ("echo `whoami`", False, None),
        ("env VAR=x pytest -q", True, "pytest"),
        ("xargs rm -rf /tmp/x", True, "xargs"),
        ("nohup pytest -q", True, "pytest"),
        ("timeout 10 pytest -q", True, "pytest"),
        ("/usr/bin/pytest -q", True, "pytest"),
        ("git -c core.hooksPath=/tmp git status", False, None),
        ("git -c core.pager=cat status", False, None),
        ("echo 'unclosed", False, None),
        ("pytest -q tests/unit", True, "pytest"),
    ],
)
def test_r14_constructs(command: str, expect_ok: bool, expect_name: str | None) -> None:
    result = extract_commands(command)
    assert result.ok is expect_ok
    if expect_ok and expect_name:
        assert any(c.name == expect_name for c in result.commands)


def test_undecomposable_always_blocked() -> None:
    assert extract_commands("echo 'oops").ok is False
    assert extract_commands("").ok is False
