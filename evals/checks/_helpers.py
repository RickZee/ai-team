"""Shared helpers for check implementations."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from evals.trace.models import Trace

_SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"
_WRITE_TOOLS = frozenset(
    {
        "file_writer",
        "write_file",
        "Write",
        "write",
        "create_file",
        "save_file",
    }
)
_FENCED_CODE = re.compile(r"```[\w+-]*\n[\s\S]+?```")
_MODULE_NOT_FOUND = re.compile(r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]")


def scenario_config(trace: Trace) -> dict[str, Any]:
    """Resolve scenario knobs from ``raw_result`` override or scenarios JSON."""
    override = trace.raw_result.get("scenario")
    if isinstance(override, dict):
        return override
    path = _SCENARIOS_DIR / f"{trace.scenario_id}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def is_write_tool(payload: dict[str, Any]) -> bool:
    """True when a tool_use payload looks like a file-writing tool."""
    name = str(payload.get("tool") or payload.get("name") or payload.get("tool_name") or "")
    return name in _WRITE_TOOLS or "write" in name.lower() or "file_writer" in name.lower()


def has_fenced_code(text: str) -> bool:
    """True when *text* contains a markdown fenced code block."""
    return bool(_FENCED_CODE.search(text or ""))


def no_audit_log(trace: Trace) -> bool:
    """True when the builder recorded that tool-level audit is unavailable."""
    joined = " ".join(trace.warnings)
    return "no audit log" in joined and "tool-level checks skipped" in joined


def parse_requirements_packages(text: str) -> set[str]:
    """Extract top-level distribution names from a requirements.txt body."""
    pkgs: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # strip extras/version markers: flask[async]==2.0 -> flask
        name = re.split(r"[<=>!~\[]", line, maxsplit=1)[0].strip()
        if name:
            pkgs.add(name.lower().replace("_", "-"))
    return pkgs


def module_not_found_names(text: str) -> list[str]:
    """Extract package names from ModuleNotFoundError messages."""
    return [m.group(1) for m in _MODULE_NOT_FOUND.finditer(text or "")]


def normalize_pkg(name: str) -> str:
    """Normalize an import/distribution name for fuzzy matching."""
    return name.lower().replace("_", "-").split(".")[0]
