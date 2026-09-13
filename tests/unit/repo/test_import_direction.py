"""Import-direction rule (design.md §4 / R10.5).

to see this fail: add ``from ai_team.backends.crewai_backend import x`` to
``src/ai_team/core/protocol.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.unit.repo._paths import REPO_ROOT

_SRC = REPO_ROOT / "src" / "ai_team"

# R10.5 + design.md §4 "may never import backends".
_NO_BACKENDS = (
    "core",
    "config",
    "harness",
    "tools",
    "guardrails",
    "memory",
)

# design.md §4: these packages also must not import ui.
_NO_UI = ("core", "config", "harness", "tools", "guardrails", "memory")

_BACKEND_SUBTREES = (
    "ai_team.backends.crewai_backend",
    "ai_team.backends.langgraph_backend",
    "ai_team.backends.claude_agent_sdk_backend",
)

_RULE = "evals/core/harness/config may not import backends (design.md §4). Move the contract into core/."


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


def _iter_py(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "vendor" not in p.parts]


def _hits(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def test_core_harness_evals_do_not_import_backends() -> None:
    scanned = 0
    violations: list[str] = []

    for pkg in _NO_BACKENDS:
        root = _SRC / pkg
        if not root.is_dir():
            raise AssertionError(f"import-direction package missing: {pkg}")
        for path in _iter_py(root):
            scanned += 1
            rel = path.relative_to(REPO_ROOT).as_posix()
            for name in _imports(path):
                if _hits(name, "ai_team.backends"):
                    violations.append(f"{rel} imports {name}; {_RULE}")
                if pkg in _NO_UI and _hits(name, "ai_team.ui"):
                    violations.append(
                        f"{rel} imports {name}; {pkg} may not import ui (design.md §4)"
                    )

    evals_root = REPO_ROOT / "evals"
    if not evals_root.is_dir():
        raise AssertionError("evals/ missing — import-direction walker broken")
    for path in _iter_py(evals_root):
        scanned += 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        for name in _imports(path):
            if _hits(name, "ai_team.backends"):
                violations.append(f"{rel} imports {name}; {_RULE}")

    backends_root = _SRC / "backends"
    for path in _iter_py(backends_root):
        scanned += 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        owner = next(
            (t for t in _BACKEND_SUBTREES if f"/{t.rsplit('.', 1)[-1]}/" in f"/{rel}/"), None
        )
        if owner is None:
            continue
        for name in _imports(path):
            for other in _BACKEND_SUBTREES:
                if other == owner:
                    continue
                if _hits(name, other):
                    violations.append(
                        f"{rel} imports {name}; backends may import only their own subtree "
                        "(design.md §4)"
                    )

    if scanned == 0:
        raise AssertionError("import-direction scan matched zero files")
    assert not violations, "\n".join(violations)
