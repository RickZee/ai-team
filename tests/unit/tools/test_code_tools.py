"""Unit tests for ``code_tools`` helpers and safe paths."""

from __future__ import annotations

import pytest
from ai_team.tools.code_tools import (
    LintResult,
    _is_shell_command_allowed,
    lint_code,
)


class TestShellAllowlist:
    @pytest.mark.parametrize(
        "cmd,allowed",
        [
            ("pytest tests/", True),
            ("ruff check .", True),
            ("rm -rf /", False),
            ("curl http://evil.com", False),
        ],
    )
    def test_is_shell_command_allowed(self, cmd: str, allowed: bool) -> None:
        ok, reason = _is_shell_command_allowed(cmd)
        assert ok is allowed, reason


class TestLintCode:
    def test_lint_python_empty_returns_result(self) -> None:
        r = lint_code("", "python")
        assert isinstance(r, LintResult)
        assert isinstance(r.issues, list)
