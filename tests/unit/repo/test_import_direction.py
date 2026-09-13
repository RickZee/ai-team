"""Import-direction rule (R10.5). Track B exceptions are named, not silent.

to see this fail: add ``from ai_team.backends.crewai_backend import x`` to
``src/ai_team/core/protocol.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.unit.repo._paths import REPO_ROOT

# Known Track B debt. Remove when Phase 6 lands.
_ALLOWED: dict[str, frozenset[str]] = {
    "evals/checks/trajectory.py": frozenset(
        {"ai_team.flows.listener_introspection", "ai_team.flows.main_flow"}
    ),
    "evals/arms/solo.py": frozenset({"ai_team.backends.claude_agent_sdk_backend.workspace"}),
}

_FORBIDDEN_PREFIXES = ("ai_team.backends",)


def _imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_core_harness_evals_do_not_import_backends() -> None:
    scanned = 0
    violations: list[str] = []
    roots = [
        REPO_ROOT / "src" / "ai_team" / "core",
        REPO_ROOT / "src" / "ai_team" / "harness",
        REPO_ROOT / "src" / "ai_team" / "config",
        REPO_ROOT / "evals",
    ]
    for root in roots:
        for path in root.rglob("*.py"):
            if "vendor" in path.parts:
                continue
            scanned += 1
            rel = path.relative_to(REPO_ROOT).as_posix()
            allowed = _ALLOWED.get(rel, frozenset())
            for name in _imports(path):
                if name in allowed:
                    continue
                if name.startswith("ai_team.flows") or name.startswith("ai_team.backends"):
                    violations.append(
                        f"{rel} imports {name}; evals/core/harness/config may not import "
                        "backends (design.md §4). Move the contract into core/."
                    )
    if scanned == 0:
        raise AssertionError("import-direction scan matched zero files")
    assert not violations, "\n".join(violations)
