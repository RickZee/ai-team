"""Essay punchline must match a count computed from failure_modes.yaml (R11.5)."""

from __future__ import annotations

from pathlib import Path

import yaml

_ESSAY = Path(__file__).resolve().parents[3] / "docs/posts/failure-taxonomy.md"
_TAXONOMY = Path(__file__).resolve().parents[3] / "evals/taxonomy/failure_modes.yaml"


def test_model_layer_ratio_matches_yaml() -> None:
    data = yaml.safe_load(_TAXONOMY.read_text(encoding="utf-8"))
    modes = data["failure_modes"]
    total = len(modes)
    model = sum(1 for m in modes if m.get("layer") == "model")
    essay = _ESSAY.read_text(encoding="utf-8")
    words = (
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
    )
    spoken_n = words[model - 1]
    spoken_total = words[total - 1]
    assert f"{spoken_n} of the {spoken_total}" in essay
    assert model == 4
    assert total == 17
