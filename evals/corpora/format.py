"""Labeled guardrail corpus record format (R6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

Label = Literal["violation", "benign"]
Source = Literal["observed", "synthetic"]


class GuardrailCase(BaseModel):
    """One labeled case for scoring a guardrail as a classifier.

    ``input`` is the exact kwargs/payload the guardrail function receives.
    ``label`` is the human ground truth: ``violation`` means the guardrail should
    fire (``fail``); ``benign`` means it must not.
    """

    case_id: str = Field(..., description="Stable id within the corpus file.")
    input: dict[str, Any] = Field(
        ...,
        description="Exact payload passed to the guardrail invoke callable.",
    )
    label: Label = Field(..., description="Human label: violation or benign.")
    source: Source = Field(
        ...,
        description="observed = mined from a real run; synthetic = hand-authored.",
    )
    origin_trace_id: str | None = Field(
        default=None,
        description="Trace id when source=observed; otherwise None.",
    )


def load_corpus(path: Path) -> list[GuardrailCase]:
    """Load a JSONL guardrail corpus; skip blank lines."""
    cases: list[GuardrailCase] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            cases.append(GuardrailCase.model_validate(json.loads(text)))
        except (json.JSONDecodeError, ValueError) as exc:
            msg = f"{path}:{line_no}: invalid GuardrailCase: {exc}"
            raise ValueError(msg) from exc
    return cases


def append_cases(path: Path, cases: list[GuardrailCase]) -> None:
    """Append cases to a JSONL corpus file (create parent dirs as needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for case in cases:
            fh.write(case.model_dump_json() + "\n")
