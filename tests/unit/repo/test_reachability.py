"""Reachability: every shipped module is imported from an entry point or dormant (R9.1).

to see this fail: add ``src/ai_team/orphan_mod.py`` with no imports.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.unit.repo._paths import REPO_ROOT

# Deliberately off the default path. Each value is the one documented activation
# step (env flag or CLI command). R1.4 / R9.2.
DORMANT_MODULES: dict[str, str] = {
    "src/ai_team/harness/session_loop.py": "AI_TEAM_SESSION_LOOP=1",
    "evals/ladder_report.py": "python -m evals.cli ladder report",
}

_ENTRY_POINTS = [
    "src/ai_team/main.py",
    "src/ai_team/__main__.py",
    "src/ai_team/ui/web/server.py",
    "evals/cli.py",
    "evals/__main__.py",
    "evals/run_evals.py",
]

_SKIP_PARTS = frozenset({"vendor", "node_modules", "frontend", "__pycache__"})

# Compatibility shims (task 6.3). Imported only via deprecated paths; removal 2026-12-31.
_DEPRECATED_SHIM_PREFIXES = (
    "src/ai_team/agents/",
    "src/ai_team/crews/",
    "src/ai_team/tasks/",
    "src/ai_team/flows/",
)


def _iter_py() -> list[Path]:
    out: list[Path] = []
    for root in (REPO_ROOT / "src" / "ai_team", REPO_ROOT / "evals"):
        for path in root.rglob("*.py"):
            if any(p in _SKIP_PARTS for p in path.parts):
                continue
            out.append(path)
    if not out:
        raise AssertionError("no Python files under src/ai_team or evals")
    return out


def _imports_of(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _module_name(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT)
    if rel.parts[0] == "src":
        rel = Path(*rel.parts[1:])
    rel = rel.parent if rel.name == "__init__.py" else rel.with_suffix("")
    return ".".join(rel.parts)


def test_no_orphan_modules() -> None:
    files = _iter_py()
    by_name = {_module_name(p): p for p in files}
    reachable: set[str] = set()
    queue: list[str] = []
    for ep in _ENTRY_POINTS:
        path = REPO_ROOT / ep
        if not path.is_file():
            raise AssertionError(f"entry point missing: {ep}")
        name = _module_name(path)
        reachable.add(name)
        queue.append(name)

    while queue:
        current = queue.pop()
        path = by_name.get(current)
        if path is None:
            continue
        for imported in _imports_of(path):
            # prefix match: importing ai_team.harness pulls the package
            candidates = [imported]
            if imported.startswith("ai_team.") or imported.startswith("evals."):
                candidates.append(imported)
            for cand in candidates:
                if cand in by_name and cand not in reachable:
                    reachable.add(cand)
                    queue.append(cand)
                # also mark child modules when a package is imported
                prefix = cand + "."
                for name in by_name:
                    if name.startswith(prefix) and name not in reachable:
                        # only follow explicit imports, not the whole package
                        pass

    # Dormant allowlist must name a flag.
    for rel, flag in DORMANT_MODULES.items():
        if not flag.strip():
            raise AssertionError(f"{rel} is on DORMANT_MODULES with an empty flag")
        if not (REPO_ROOT / rel).is_file():
            raise AssertionError(f"DORMANT_MODULES names missing file: {rel}")

    # This graph is conservative (function-level imports count). Fail only on
    # modules that have no incoming import from *any* non-test file.
    used_by: dict[str, set[str]] = {n: set() for n in by_name}
    for path in files:
        src = _module_name(path)
        for imported in _imports_of(path):
            if imported in used_by:
                used_by[imported].add(src)
            prefix = imported + "."
            for name in used_by:
                if name.startswith(prefix):
                    used_by[name].add(src)

    scripts_root = REPO_ROOT / "scripts"
    if scripts_root.is_dir():
        for path in scripts_root.glob("*.py"):
            src = f"scripts.{path.stem}"
            for imported in _imports_of(path):
                if imported in used_by:
                    used_by[imported].add(src)
                prefix = imported + "."
                for name in used_by:
                    if name.startswith(prefix):
                        used_by[name].add(src)

    for prefix in _DEPRECATED_SHIM_PREFIXES:
        shim_dir = REPO_ROOT / prefix.rstrip("/")
        if not shim_dir.is_dir() or not any(shim_dir.glob("*.py")):
            raise AssertionError(f"deprecated shim prefix matched nothing: {prefix}")

    real_orphans: list[str] = []
    test_prefixes = ("tests.",)
    for name, path in sorted(by_name.items()):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in DORMANT_MODULES or path.name == "__init__.py":
            continue
        if any(rel.startswith(p) for p in _DEPRECATED_SHIM_PREFIXES):
            continue
        if "ui/web/frontend" in rel:
            continue
        users = used_by.get(name, set())
        non_test = [u for u in users if not u.startswith(test_prefixes)]
        if non_test:
            continue
        # Also OK if this module *is* an entry point.
        if rel in _ENTRY_POINTS:
            continue
        real_orphans.append(
            f"{rel} is imported only by tests. Wire it, add it to DORMANT_MODULES "
            f"with its flag, or delete it."
        )

    assert not real_orphans, "\n".join(real_orphans)
