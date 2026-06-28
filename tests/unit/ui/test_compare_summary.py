"""Tests for compare summary helpers."""

from __future__ import annotations

from ai_team.ui.compare_summary import build_compare_verdict, parse_elapsed_seconds


def test_parse_elapsed_seconds() -> None:
    assert parse_elapsed_seconds("2m 30s") == 150


def test_build_compare_verdict() -> None:
    rows = [
        {"key": "a", "label": "CrewAI", "cost_usd": 0.2, "tests_passed": 3, "failed": False},
        {"key": "b", "label": "LangGraph", "cost_usd": 0.1, "tests_passed": 5, "failed": False},
    ]
    verdict = build_compare_verdict(
        rows,
        [
            ("cost", "min", lambda r: float(r["cost_usd"])),
            ("tests passed", "max", lambda r: float(r["tests_passed"])),
        ],
    )
    assert "LangGraph: lowest cost" in verdict
    assert "LangGraph: highest tests passed" in verdict
