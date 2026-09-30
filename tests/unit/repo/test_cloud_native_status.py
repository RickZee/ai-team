"""The cloud status table has no blank cells, and the README does not invent a green one."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TABLE = ROOT / "docs" / "CLOUD_NATIVE.md"
README = ROOT / "README.md"
_ALLOWED = {"green", "red", "not yet", "not available"}


def _rows() -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| Backend") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 7:
            raise AssertionError(f"short row: {line}")
        if any(cell == "" for cell in cells):
            raise AssertionError(f"blank cell: {line}")
        backend, target, status = cells[0], cells[1], cells[2]
        if status not in _ALLOWED:
            raise AssertionError(f"bad status {status!r} in {line}")
        rows.append((backend, target, status))
    return rows


def test_every_cell_is_filled() -> None:
    rows = _rows()
    assert len(rows) >= 15
    assert all(status in _ALLOWED for _, _, status in rows)


def test_readme_does_not_claim_a_cell_that_is_not_green() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "docs/CLOUD_NATIVE.md" in readme
    status = {(backend, target): state for backend, target, state in _rows()}
    for match in re.finditer(
        r"(crewai|langgraph|claude-agent-sdk|strands|agent-framework)\s+(local|container|cloud)\s+is\s+green",
        readme,
        flags=re.IGNORECASE,
    ):
        key = (match.group(1).lower(), match.group(2).lower())
        assert status.get(key) == "green"
