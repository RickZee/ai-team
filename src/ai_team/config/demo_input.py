"""Load project description and team profile from a demo directory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_team.core.team_profile import load_team_profile


@dataclass(frozen=True)
class DemoInput:
    """Parsed demo fixture: description text and optional team profile."""

    description: str
    team_profile: str | None = None


def _read_input_json(demo_dir: Path) -> dict[str, Any] | None:
    input_file = demo_dir / "input.json"
    if not input_file.is_file():
        return None
    data: dict[str, Any] = json.loads(input_file.read_text(encoding="utf-8"))
    return data


def _description_from_json(data: dict[str, Any], input_file: Path) -> str:
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
        msg = f"input.json has no description or project_name: {input_file}"
        raise ValueError(msg)
    return " — ".join(parts)


def load_demo_input(demo_dir: Path) -> DemoInput:
    """
    Load description and optional ``team_profile`` from a demo directory.

    Raises:
        FileNotFoundError: If neither ``project_description.txt`` nor ``input.json`` exists.
        ValueError: If JSON has no usable description fields.
    """
    desc_file = demo_dir / "project_description.txt"
    if desc_file.is_file():
        return DemoInput(description=desc_file.read_text(encoding="utf-8").strip())

    data = _read_input_json(demo_dir)
    if data is None:
        raise FileNotFoundError(
            f"Demo has neither project_description.txt nor input.json: {demo_dir}"
        )
    input_file = demo_dir / "input.json"
    raw_team = data.get("team_profile")
    team_profile = raw_team.strip() if isinstance(raw_team, str) and raw_team.strip() else None
    return DemoInput(
        description=_description_from_json(data, input_file),
        team_profile=team_profile,
    )


def resolve_team_profile(
    demo_dir: Path,
    *,
    cli_team: str | None = None,
    default: str = "full",
) -> str:
    """
    Resolve team profile: CLI ``--team`` overrides ``input.json``, else default.

    Raises:
        KeyError: If the resolved name is not defined in ``team_profiles.yaml``.
    """
    if cli_team is not None and cli_team.strip():
        name = cli_team.strip()
    else:
        data = _read_input_json(demo_dir)
        raw = (data or {}).get("team_profile")
        name = raw.strip() if isinstance(raw, str) and raw.strip() else default
    load_team_profile(name)
    return name


def load_project_description(demo_dir: Path) -> str:
    """
    Load project description from ``project_description.txt`` or ``input.json``.

    Raises:
        FileNotFoundError: If neither file exists or paths are invalid.
        ValueError: If JSON has no usable description fields.
    """
    return load_demo_input(demo_dir).description
