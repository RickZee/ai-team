"""Tests for the prose-to-file salvage fallback (G3).

When a model (notably deepseek via OpenRouter) emits code as markdown prose
instead of calling ``file_writer``, the workspace ends up empty and pytest
collects 0 items. These tests cover the regex extraction and the testing-node
salvage path that recover such output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr
from langchain_core.messages import AIMessage, HumanMessage

QA_PROSE = """Here are the two files:

### `calc.py`
```python
def add(a: float, b: float) -> float:
    return a + b
```

### `test_calc.py`
```python
from calc import add


def test_add():
    assert add(1, 2) == 3
```
"""


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the workspace helpers at an isolated tmp dir."""
    monkeypatch.setattr(sr, "_workspace_root", lambda: tmp_path)
    return tmp_path


class TestCodeBlockExtraction:
    def test_extracts_markdown_header_named_blocks(self, workspace: Path) -> None:
        written = sr._extract_and_write_code_blocks([AIMessage(content=QA_PROSE)])
        names = {w["path"] for w in written}
        assert names == {"calc.py", "test_calc.py"}
        assert (workspace / "test_calc.py").read_text().startswith("from calc import add")

    def test_ignores_non_ai_messages(self, workspace: Path) -> None:
        written = sr._extract_and_write_code_blocks([HumanMessage(content=QA_PROSE)])
        assert written == []

    def test_rejects_path_traversal(self, workspace: Path) -> None:
        evil = "### `../escape.py`\n```python\nx = 1\n```\n"
        written = sr._extract_and_write_code_blocks([AIMessage(content=evil)])
        assert written == []
        assert not (workspace.parent / "escape.py").exists()

    def test_rejects_nested_traversal(self, workspace: Path) -> None:
        evil = "### `sub/../../escape.py`\n```python\nx = 1\n```\n"
        written = sr._extract_and_write_code_blocks([AIMessage(content=evil)])
        assert written == []

    def test_rejects_absolute_path(self, workspace: Path) -> None:
        evil = "### `/etc/evil.py`\n```python\nx = 1\n```\n"
        written = sr._extract_and_write_code_blocks([AIMessage(content=evil)])
        assert written == []
        assert not Path("/etc/evil.py").exists()

    def test_dedupes_repeated_filenames(self, workspace: Path) -> None:
        dup = QA_PROSE + "\n\n### `calc.py`\n```python\ndef add(a, b):\n    return a + b\n```\n"
        written = sr._extract_and_write_code_blocks([AIMessage(content=dup)])
        assert [w["path"] for w in written].count("calc.py") == 1


class TestWorkspaceHasTests:
    def test_true_for_test_prefix(self, workspace: Path) -> None:
        (workspace / "test_foo.py").write_text("def test_x(): pass\n")
        assert sr._workspace_has_tests() is True

    def test_true_for_test_suffix(self, workspace: Path) -> None:
        (workspace / "foo_test.py").write_text("def test_x(): pass\n")
        assert sr._workspace_has_tests() is True

    def test_false_when_no_tests(self, workspace: Path) -> None:
        (workspace / "calc.py").write_text("def add(a, b): return a + b\n")
        assert sr._workspace_has_tests() is False
