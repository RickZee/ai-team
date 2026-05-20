"""Tests for demo directory description and team profile loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ai_team.utils.demo_input import (
    DemoInput,
    load_demo_input,
    load_project_description,
    resolve_team_profile,
)


def test_load_from_project_description_txt(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    (d / "project_description.txt").write_text("  Hello world project  ", encoding="utf-8")
    assert load_project_description(d) == "Hello world project"
    assert load_demo_input(d) == DemoInput(description="Hello world project")


def test_load_from_input_json_description_field(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    (d / "input.json").write_text(
        json.dumps({"description": "Build a Flask API", "project_name": "x"}),
        encoding="utf-8",
    )
    assert load_project_description(d) == "Build a Flask API"


def test_load_team_profile_from_input_json(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    (d / "input.json").write_text(
        json.dumps({"description": "Smoke", "team_profile": "prototype"}),
        encoding="utf-8",
    )
    demo = load_demo_input(d)
    assert demo.team_profile == "prototype"
    assert resolve_team_profile(d) == "prototype"


def test_cli_team_overrides_input_json(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    (d / "input.json").write_text(
        json.dumps({"description": "x", "team_profile": "prototype"}),
        encoding="utf-8",
    )
    assert resolve_team_profile(d, cli_team="backend-api") == "backend-api"


def test_resolve_unknown_profile_raises(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir()
    (d / "input.json").write_text(json.dumps({"description": "x"}), encoding="utf-8")
    with pytest.raises(KeyError, match="Unknown team profile"):
        resolve_team_profile(d, cli_team="nonexistent_profile_xyz")
