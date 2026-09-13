"""README project-structure tree matches ``src/ai_team/`` packages (R5.2).

to see this fail: add ``src/ai_team/newpkg/__init__.py`` without updating README.md.
"""

from __future__ import annotations

from tests.unit.repo._paths import REPO_ROOT

_SKIP = frozenset({"__pycache__", "frontend"})


def test_readme_structure_lists_top_level_packages() -> None:
    pkg_root = REPO_ROOT / "src" / "ai_team"
    packages = sorted(
        p.name
        for p in pkg_root.iterdir()
        if p.is_dir()
        and p.name not in _SKIP
        and not p.name.startswith(".")
        and ((p / "__init__.py").is_file() or any(p.glob("*.py")))
    )
    if not packages:
        raise AssertionError("src/ai_team contained zero packages — walker broken")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    missing = [name for name in packages if f"{name}/" not in readme and f"{name}" not in readme]
    # knowledge/ is markdown, still a top-level dir
    assert not missing, (
        "README structure omits: " + ", ".join(missing) + ". Update the Project structure tree."
    )
