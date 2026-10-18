"""The spec register in .kiro/specs/README.md is generated, valid and current."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    """Import scripts/spec_index.py, which is not an installed module."""
    spec = importlib.util.spec_from_file_location(
        "spec_index", REPO_ROOT / "scripts" / "spec_index.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up while building
    spec.loader.exec_module(module)
    return module


spec_index = _load()


def _write_spec(
    root: Path, name: str, created: str, status: str, deps: str = "", tasks: str = ""
) -> None:
    folder = root / name
    folder.mkdir()
    lines = [f"# Requirements: {name}", "", f"**Spec ID:** `{name}`", f"**Status:** {status}"]
    lines.append(f"**Created:** {created}")
    if deps:
        lines.append(f"**Depends on:** {deps}")
    lines += ["", "---", "", "## R1"]
    (folder / "requirements.md").write_text("\n".join(lines) + "\n")
    if tasks:
        (folder / "tasks.md").write_text(tasks)


def test_every_spec_folder_is_in_the_register_and_current() -> None:
    specs = spec_index.load_specs()
    folders = {p.name for p in spec_index.SPECS_DIR.iterdir() if (p / "requirements.md").exists()}
    assert {s.spec_id for s in specs} == folders
    readme = spec_index.README.read_text()
    block = spec_index.render(specs)
    assert spec_index.updated_readme(readme, block) == readme, (
        "Spec register is stale: run `uv run python scripts/spec_index.py --write`"
    )


def test_every_spec_header_is_valid() -> None:
    assert spec_index.problems(spec_index.load_specs()) == []


def test_status_vocabulary_is_enforced(tmp_path: Path) -> None:
    _write_spec(tmp_path, "alpha", "2026-01-01", "Draft for implementation")
    _write_spec(tmp_path, "beta", "2026-01-02", "Shipped")
    _write_spec(tmp_path, "gamma", "2026-01-03", "Done", tasks="- [ ] **1.1 x**\n")
    issues = spec_index.problems(spec_index.load_specs(tmp_path))
    # "Draft for implementation" starts with "Draft", so it is allowed; the other two are not.
    assert len(issues) == 2
    assert any("beta" in i and "Status must start" in i for i in issues)
    assert any("gamma" in i and "no task is checked" in i for i in issues)


def test_tasks_and_multiline_depends_are_read(tmp_path: Path) -> None:
    _write_spec(tmp_path, "base", "2026-01-01", "Done", tasks="- [x] **1.1**\n- [x] **1.2**\n")
    _write_spec(
        tmp_path,
        "child",
        "2026-01-01",
        "In progress",
        deps="[`../base/`](../base/) Phases 0–3, and\nfrom [`../missing/`](../missing/) task 2",
        tasks="- [x] **1.1**\n- [ ] **1.2**\n  - [ ] nested items are not tasks\n",
    )
    specs = {s.spec_id: s for s in spec_index.load_specs(tmp_path)}
    assert (specs["base"].done, specs["base"].total) == (2, 2)
    assert (specs["child"].done, specs["child"].total) == (1, 2)
    assert specs["child"].depends_on == ("base",)  # unknown folders are dropped


def test_same_day_dependencies_list_first(tmp_path: Path) -> None:
    _write_spec(tmp_path, "aaa-consumer", "2026-02-01", "Draft", deps="[x](../zzz-foundation/)")
    _write_spec(tmp_path, "zzz-foundation", "2026-02-01", "Draft")
    _write_spec(tmp_path, "early", "2026-01-15", "Done", tasks="- [x] **1**\n")
    order = [s.spec_id for s in spec_index.load_specs(tmp_path)]
    assert order == ["early", "zzz-foundation", "aaa-consumer"]


def test_updated_readme_requires_markers() -> None:
    with pytest.raises(ValueError):
        spec_index.updated_readme("# no markers here\n", "block")


def test_readme_table_has_no_task_counts() -> None:
    """Ticking a task box must not make the README stale."""
    specs = spec_index.load_specs()
    assert "Tasks done" not in spec_index.render(specs)
    assert "Tasks done" in spec_index.render(specs, with_tasks=True)
