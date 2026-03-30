"""Tests for demo directory description loading."""

from __future__ import annotations

import json
from pathlib import Path

from ai_team.utils.demo_input import load_project_description


def test_load_from_project_description_txt(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    (d / "project_description.txt").write_text("  Hello world project  ", encoding="utf-8")
    assert load_project_description(d) == "Hello world project"


def test_load_from_input_json_description_field(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    (d / "input.json").write_text(
        json.dumps({"description": "Build a Flask API", "project_name": "x"}),
        encoding="utf-8",
    )
    assert load_project_description(d) == "Build a Flask API"
