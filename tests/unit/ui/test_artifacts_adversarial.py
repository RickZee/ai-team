"""Adversarial workspace containment for artifact reads (R16).

to see these fail: drop the post-resolve ``is_relative_to`` check in
``_abs_path_for_rel``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from ai_team.ui.artifacts.service import (
    _abs_path_for_rel,
    build_tree,
    read_artifact_file,
    resolve_run_workspace_dir,
    workspace_zip_bytes,
)


@pytest.fixture
def two_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, str]:
    ws = tmp_path / "workspace"
    out = tmp_path / "output"
    ws.mkdir()
    out.mkdir()
    monkeypatch.setenv("PROJECT_WORKSPACE_DIR", str(ws))
    monkeypatch.setenv("PROJECT_OUTPUT_DIR", str(out))
    from ai_team.config.settings import reload_settings

    reload_settings()
    a, b = "run-a", "run-b"
    (ws / a).mkdir()
    (ws / b).mkdir()
    (ws / a / "ok.txt").write_text("safe\n", encoding="utf-8")
    (ws / b / "secret.txt").write_text("sibling\n", encoding="utf-8")
    return ws, a, b


def test_symlink_to_etc_passwd_rejected(two_runs: tuple[Path, str, str]) -> None:
    ws, run_a, _ = two_runs
    target = Path("/etc/passwd")
    if not target.exists():
        pytest.skip("precondition: /etc/passwd is absent on this platform")
    link = ws / run_a / "passwd.link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="escapes|Invalid"):
        _abs_path_for_rel(run_a, "workspace", "passwd.link")
    tree = build_tree(run_a, "workspace")
    names = [n.path for n in tree]
    assert "passwd.link" not in names


def test_symlink_to_sibling_run_rejected(two_runs: tuple[Path, str, str]) -> None:
    ws, run_a, run_b = two_runs
    link = ws / run_a / "other.link"
    link.symlink_to(ws / run_b / "secret.txt")
    with pytest.raises(ValueError, match="escapes"):
        _abs_path_for_rel(run_a, "workspace", "other.link")


def test_nested_symlinked_directory_skipped(two_runs: tuple[Path, str, str]) -> None:
    ws, run_a, run_b = two_runs
    nested = ws / run_a / "nested"
    nested.mkdir()
    link = nested / "out"
    link.symlink_to(ws / run_b, target_is_directory=True)
    tree = build_tree(run_a, "workspace")

    def _paths(nodes: list, acc: list[str]) -> list[str]:
        for n in nodes:
            acc.append(n.path)
            _paths(n.children, acc)
        return acc

    paths = _paths(tree, [])
    assert not any("secret.txt" in p for p in paths)


def test_absolute_project_id_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid project_id"):
        resolve_run_workspace_dir("/etc")
    with pytest.raises(ValueError, match="Invalid project_id"):
        resolve_run_workspace_dir("../etc")


def test_sensitive_name_still_blocked(two_runs: tuple[Path, str, str]) -> None:
    ws, run_a, _ = two_runs
    (ws / run_a / ".env").write_text("SECRET=1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Sensitive"):
        _abs_path_for_rel(run_a, "workspace", ".env")


def test_zip_does_not_include_escape_symlink(two_runs: tuple[Path, str, str]) -> None:
    ws, run_a, _ = two_runs
    target = Path("/etc/passwd")
    if not target.exists():
        pytest.skip("precondition: /etc/passwd is absent on this platform")
    (ws / run_a / "leak").symlink_to(target)
    blob = workspace_zip_bytes(run_a)
    assert b"root:" not in blob or os.path.basename(target) not in str(blob)
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = zf.namelist()
    assert not any("passwd" in n for n in names)


def test_in_workspace_file_still_readable(two_runs: tuple[Path, str, str]) -> None:
    _ws, run_a, _ = two_runs
    content = read_artifact_file(run_a, "workspace", "ok.txt")
    assert "safe" in (content.content or "")
