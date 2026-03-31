"""Load project description from a demo directory (shared by run_demo and compare_backends)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_project_description(demo_dir: Path) -> str:
    """
    Load project description from ``project_description.txt`` or ``input.json``.

    Raises:
        FileNotFoundError: If neither file exists or paths are invalid.
        ValueError: If JSON has no usable description fields.
    """
    desc_file = demo_dir / "project_description.txt"
    if desc_file.is_file():
        return desc_file.read_text(encoding="utf-8").strip()

    input_file = demo_dir / "input.json"
    if not input_file.is_file():
        raise FileNotFoundError(
            f"Demo has neither project_description.txt nor input.json: {demo_dir}"
        )
    data: dict[str, Any] = json.loads(input_file.read_text(encoding="utf-8"))
    desc = data.get("description")
    if isinstance(desc, str) and desc.strip():
        return desc.strip()
    parts: list[str] = []
    if data.get("project_name"):
        parts.append(str(data["project_name"]))
    if data.get("description"):
        parts.append(str(data["description"]))
    if data.get("stack"):
        stack = data["stack"]
        parts.append(f"Stack: {', '.join(stack) if isinstance(stack, list) else stack}")
    if not parts:
        raise ValueError(f"input.json has no description or project_name: {input_file}")
    return " — ".join(parts)
