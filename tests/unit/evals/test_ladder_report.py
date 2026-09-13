"""Ladder report stamps, refusals, and Markdown-from-JSON identity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.ladder_report import (
    STAMP_DERIVED,
    STAMP_MIXED,
    STAMP_NEVER,
    STAMP_STALE,
    STAMP_UNDERPOWERED,
    ClaimRefusalError,
    markdown_from_ladder_json,
    render_ladder,
)

pytestmark = pytest.mark.eval_unit

_GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "ladder"


def _trace(arm: str, *, model: str = "m1", n_extra: int = 0, **kwargs: object) -> dict:
    base = {
        "arm_id": arm,
        "model_id": model,
        "cost": {"usd": 1.0},
        "wall_clock_s": 10.0,
        "smoke_pass": 1.0,
        "accepted_change": 1.0,
        "demotion": 0.0,
        "qa_false_negative": 0.0,
        "source_ref": "local",
        "divergences": [
            {
                "field": "max_features",
                "expected": 200,
                "actual": 25,
                "reason": "cap",
            }
        ],
        "provenance": {"model_ids": {"*": model}},
    }
    base.update(kwargs)
    return base


def test_refuses_mixed_and_underpowered() -> None:
    with pytest.raises(ClaimRefusalError, match="mixed"):
        render_ladder([_trace("solo", model="a"), _trace("ai_team", model="b")])
    with pytest.raises(ClaimRefusalError, match="underpowered"):
        render_ladder([_trace("solo"), _trace("ai_team")])


def test_stamps_with_flags() -> None:
    traces = [_trace("solo", model="a"), _trace("ai_team", model="b")]
    doc = render_ladder(traces, allow_mixed_model=True, allow_underpowered=True)
    assert STAMP_MIXED in doc["stamps"]
    assert STAMP_UNDERPOWERED in doc["stamps"]
    md = markdown_from_ladder_json(doc)
    assert STAMP_MIXED in md
    assert STAMP_UNDERPOWERED in md
    # Markdown numbers come from JSON, not a second computation.
    assert "1.000" in md
    assert json.dumps(doc["arms"][0]["n"]) in md or str(doc["arms"][0]["n"]) in md


def test_stale_never_measured_and_suppressed_ratio() -> None:
    traces = [
        _trace(
            "ai_team_ablated:smoke_gate",
            family="ablation",
            ablation_model_id="old-model",
            ablation_measured=False,
            ablation_delta=0,
            cost_per_fm_avoided=12.0,
        )
        for _ in range(3)
    ]
    traces += [_trace("ai_team") for _ in range(3)]
    doc = render_ladder(traces, default_model="new-model")
    stale_row = next(a for a in doc["arms"] if a["arm_id"].startswith("ai_team_ablated"))
    assert stale_row["staleness"] == STAMP_STALE
    assert stale_row["cost_per_fm_avoided"] is None
    never = render_ladder(
        [
            _trace(
                "ai_team_ablated:lessons_loop",
                family="ablation",
                ablation_measured=False,
                ablation_delta=0,
            )
            for _ in range(3)
        ]
        + [_trace("ai_team") for _ in range(3)],
        default_model="new-model",
    )
    never_row = next(a for a in never["arms"] if "lessons" in a["arm_id"])
    assert never_row["staleness"] == STAMP_NEVER
    assert "ai_team_ablated:lessons_loop" in never["no_measured_effect"]
    md = markdown_from_ladder_json(never)
    assert "components with no measured effect" in md
    # n=3 suppresses the ratio even when present
    assert STAMP_DERIVED not in md


def test_golden_three_fixture_traces() -> None:
    traces = [
        _trace("solo", cost={"usd": 1.0}, wall_clock_s=10.0),
        _trace(
            "reference",
            cost={"usd": 4.0},
            wall_clock_s=40.0,
            smoke_pass=0.0,
            accepted_change=0.0,
            source_ref="vendor:3313e97",
        ),
        _trace("ai_team", cost={"usd": 2.0}, wall_clock_s=20.0, divergences=[]),
    ]
    doc = render_ladder(traces, allow_underpowered=True)
    golden = json.loads((_GOLDEN / "golden.json").read_text(encoding="utf-8"))
    assert doc["stamps"] == golden["stamps"]
    assert [a["arm_id"] for a in doc["arms"]] == [a["arm_id"] for a in golden["arms"]]
    ref = next(a for a in doc["arms"] if a["arm_id"] == "reference")
    assert any(
        d.get("actual") == 25 and d.get("field") == "max_features" for d in ref["divergences"]
    )
    md = markdown_from_ladder_json(doc)
    assert "4.000" in md
    assert "max_features" in md
    # Markdown is a projection of this JSON, not a second computation.
    assert str(doc["arms"][0]["n"]) in md


def test_markdown_reads_json_not_recompute() -> None:
    doc = {
        "stamps": [STAMP_UNDERPOWERED],
        "arms": [
            {
                "arm_id": "reference",
                "n": 3,
                "cost_usd_mean": 4.25,
                "wall_clock_s_mean": 99.0,
                "smoke_pass_rate": 0.5,
                "accepted_change_rate": 0.0,
                "demotion_rate": 0.1,
                "qa_false_negative_rate": 0.2,
                "source_ref": "vendor:3313e97",
                "divergences": [
                    {"field": "max_features", "expected": 200, "actual": 25, "reason": "cap"}
                ],
            }
        ],
        "no_measured_effect": [],
    }
    md = markdown_from_ladder_json(doc)
    assert "4.250" in md
    assert "max_features" in md
    assert "25" in md
    assert "full scenario contract" in md
    assert STAMP_UNDERPOWERED in md
