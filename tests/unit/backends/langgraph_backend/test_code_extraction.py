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


# The development supervisor's real prose shape: numbered headers with the
# filename in backticks plus trailing descriptive text. The strict header regex
# misses these, which previously left main.py unwritten (tests but no app).
DEV_SUPERVISOR_PROSE = """I'll fix the QA failures. Here are the file updates:

### 1. `main.py` (Flask Application)
```python
from flask import Flask

app = Flask(__name__)
```

### 2. Updated `tests/test_api.py`
```python
from main import app


def test_health():
    assert app is not None
```

Would you like me to proceed with saving these files?
"""


class TestCodeBlockExtraction:
    def test_extracts_markdown_header_named_blocks(self, workspace: Path) -> None:
        written = sr._extract_and_write_code_blocks([AIMessage(content=QA_PROSE)])
        names = {w["path"] for w in written}
        assert names == {"calc.py", "test_calc.py"}
        assert (workspace / "test_calc.py").read_text().startswith("from calc import add")

    def test_extracts_numbered_and_suffixed_dev_headers(self, workspace: Path) -> None:
        """'### 1. `main.py` (Flask App)' and 'Updated `tests/test_api.py`' shapes."""
        written = sr._extract_and_write_code_blocks([AIMessage(content=DEV_SUPERVISOR_PROSE)])
        names = {w["path"] for w in written}
        assert names == {"main.py", "tests/test_api.py"}
        assert (workspace / "main.py").read_text().startswith("from flask import Flask")
        assert (workspace / "tests" / "test_api.py").exists()

    def test_does_not_match_prose_mention_without_backticks(self, workspace: Path) -> None:
        """A header that names a file without backticks must not over-capture a fence."""
        prose = "### Update main.py now\n```python\nx = 1\n```\n"
        written = sr._extract_and_write_code_blocks([AIMessage(content=prose)])
        assert all(w["path"] != "main.py" for w in written)

    def test_salvages_app_module_when_other_files_already_exist(self, workspace: Path) -> None:
        """Regression: dev writes the app module as prose while test files already exist.

        The old dev-node gate (`if not generated`) skipped salvage whenever the
        workspace was non-empty, dropping main.py and causing a tests-but-no-app
        retry loop. The extractor itself must still recover main.py here.
        """
        (workspace / "tests").mkdir()
        (workspace / "tests" / "test_api.py").write_text("def test_x(): assert True\n")
        written = sr._extract_and_write_code_blocks([AIMessage(content=DEV_SUPERVISOR_PROSE)])
        assert "main.py" in {w["path"] for w in written}
        assert (workspace / "main.py").read_text().startswith("from flask import Flask")

    def test_overwrites_with_latest_prose_version(self, workspace: Path) -> None:
        """A retry's corrected prose overwrites a stale on-disk file."""
        (workspace / "main.py").write_text("# stale\n")
        prose = "### `main.py`\n```python\nfrom flask import Flask  # fixed\n```\n"
        sr._extract_and_write_code_blocks([AIMessage(content=prose)])
        assert "fixed" in (workspace / "main.py").read_text()

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
