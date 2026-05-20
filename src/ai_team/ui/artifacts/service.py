"""
Artifact browser service: registry, file trees, safe reads, panel loaders, ZIP export.
"""

from __future__ import annotations

import contextlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Literal

import structlog
from ai_team.config.settings import get_settings
from ai_team.core.results.writer import RUNS_SUBDIR
from ai_team.models.architecture import ArchitectureDocument
from ai_team.models.outputs import TestResult
from ai_team.tools.file_tools import read_file
from ai_team.ui.artifacts.models import (
    ArchitecturePanelData,
    ArtifactFileContent,
    ArtifactTreeNode,
    FileCoverageItem,
    RegistryRun,
    TestFailureItem,
    TestsPanelData,
)

logger = structlog.get_logger(__name__)

ArtifactRoot = Literal["workspace", "bundle"]

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".ai_team_snapshots",
        "node_modules",
    }
)

_SENSITIVE_SUBSTR = (".env", "credentials", "secrets", "id_rsa", ".pem")

_TEXT_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".html",
        ".css",
        ".scss",
        ".json",
        ".yaml",
        ".yml",
        ".md",
        ".txt",
        ".toml",
        ".ini",
        ".cfg",
        ".sh",
        ".sql",
        ".xml",
        ".csv",
        ".dockerfile",
    }
)

_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".sql": "sql",
    ".toml": "toml",
    ".xml": "xml",
}


def _output_root() -> Path:
    return Path(get_settings().project.output_dir).resolve()


def _workspace_root() -> Path:
    return Path(get_settings().project.workspace_dir).resolve()


def resolve_project_paths(project_id: str) -> tuple[Path, Path]:
    """Return (workspace_dir, bundle_dir) for a project id."""
    if ".." in project_id or "/" in project_id or "\\" in project_id:
        raise ValueError("Invalid project_id")
    ws = _workspace_root() / project_id
    bundle = _output_root() / RUNS_SUBDIR / project_id
    return ws, bundle


def _tree_root(project_id: str, root: ArtifactRoot) -> Path:
    ws, bundle = resolve_project_paths(project_id)
    if root == "workspace":
        return ws
    return bundle


def _is_sensitive(rel_path: str) -> bool:
    lower = rel_path.lower().replace("\\", "/")
    return any(s in lower for s in _SENSITIVE_SUBSTR)


def _list_relative_files(base: Path, *, max_files: int = 500) -> list[tuple[str, int]]:
    """Return sorted (relative_path, size_bytes) for files under base."""
    if not base.is_dir():
        return []
    out: list[tuple[str, int]] = []
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(base).parts
        if any(part in _SKIP_DIR_NAMES for part in rel_parts):
            continue
        rel = str(p.relative_to(base)).replace("\\", "/")
        if _is_sensitive(rel):
            continue
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        out.append((rel, size))
        if len(out) >= max_files:
            break
    return sorted(out, key=lambda x: x[0])


def _nested_dict_add(tree: dict[str, Any], rel_path: str, size: int) -> None:
    parts = rel_path.split("/")
    node = tree
    for i, part in enumerate(parts):
        if part not in node:
            node[part] = {"__size__": size} if i == len(parts) - 1 else {}
        elif i == len(parts) - 1:
            node[part]["__size__"] = size
        if i < len(parts) - 1:
            node = node[part]


def _nested_dict_to_nodes(prefix: str, tree: dict[str, Any]) -> list[ArtifactTreeNode]:
    nodes: list[ArtifactTreeNode] = []
    for name in sorted(tree.keys(), key=str.lower):
        entry = tree[name]
        rel = f"{prefix}/{name}" if prefix else name
        if "__size__" in entry and len(entry) == 1:
            nodes.append(
                ArtifactTreeNode(
                    name=name,
                    path=rel,
                    type="file",
                    size=int(entry["__size__"]),
                    children=[],
                )
            )
        elif isinstance(entry, dict):
            child_tree = {k: v for k, v in entry.items() if k != "__size__"}
            children = _nested_dict_to_nodes(rel, child_tree)
            size_val = entry.get("__size__")
            nodes.append(
                ArtifactTreeNode(
                    name=name,
                    path=rel,
                    type="dir",
                    size=int(size_val) if size_val is not None else None,
                    children=children,
                )
            )
    return sorted(nodes, key=lambda n: (n.type == "file", n.name.lower()))


def build_tree(project_id: str, root: ArtifactRoot) -> list[ArtifactTreeNode]:
    """Build nested file tree for workspace or bundle root."""
    base = _tree_root(project_id, root)
    nested: dict[str, Any] = {}
    for rel, size in _list_relative_files(base):
        _nested_dict_add(nested, rel, size)
    return _nested_dict_to_nodes("", nested)


def _abs_path_for_rel(project_id: str, root: ArtifactRoot, rel_path: str) -> Path:
    if ".." in rel_path or rel_path.startswith("/"):
        raise ValueError("Invalid path")
    if _is_sensitive(rel_path):
        raise ValueError("Sensitive path not allowed")
    base = _tree_root(project_id, root)
    return (base / rel_path).resolve()


def _guess_language(path: str) -> str | None:
    suffix = Path(path).suffix.lower()
    if suffix == ".dockerfile" or path.lower().endswith("dockerfile"):
        return "dockerfile"
    return _LANG_MAP.get(suffix)


def _is_probably_text(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in _TEXT_EXTENSIONS or path.name.lower() in ("dockerfile", "makefile"):
        return True
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return False
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def read_artifact_file(
    project_id: str,
    root: ArtifactRoot,
    rel_path: str,
) -> ArtifactFileContent:
    """Read a file under project workspace or bundle with validation."""
    resolved = _abs_path_for_rel(project_id, root, rel_path)
    if not resolved.is_file():
        raise ValueError(f"Not a file: {rel_path}")
    size_bytes = resolved.stat().st_size
    language = _guess_language(rel_path)

    if not _is_probably_text(resolved):
        logger.info("artifact_read_binary", project_id=project_id, path=rel_path)
        return ArtifactFileContent(
            path=rel_path,
            root=root,
            content=None,
            language=language,
            size_bytes=size_bytes,
            is_binary=True,
        )

    try:
        text = read_file(str(resolved))
    except ValueError as e:
        raise ValueError(str(e)) from e

    truncated = False
    max_chars = 512_000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... truncated ...]"
        truncated = True

    return ArtifactFileContent(
        path=rel_path,
        root=root,
        content=text,
        language=language,
        size_bytes=size_bytes,
        is_binary=False,
        truncated=truncated,
    )


def load_registry(extra_runs: list[dict[str, Any]] | None = None) -> list[RegistryRun]:
    """Load disk registry and merge optional in-memory web runs."""
    index_path = _output_root() / "index.json"
    runs: dict[str, RegistryRun] = {}
    if index_path.is_file():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            for row in data.get("runs") or []:
                if not isinstance(row, dict):
                    continue
                rid = str(row.get("run_id") or "")
                if not rid:
                    continue
                runs[rid] = RegistryRun(
                    run_id=rid,
                    output_dir=row.get("output_dir"),
                    started_at=_iso_str(row.get("started_at")),
                    completed_at=_iso_str(row.get("completed_at")),
                    backend=row.get("backend"),
                    team_profile=row.get("team_profile"),
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("artifact_registry_read_failed", error=str(e))

    for row in extra_runs or []:
        rid = str(row.get("run_id") or row.get("thread_id") or "")
        if not rid:
            continue
        existing = runs.get(rid)
        runs[rid] = RegistryRun(
            run_id=rid,
            output_dir=existing.output_dir if existing else None,
            started_at=row.get("started_at") or (existing.started_at if existing else None),
            completed_at=row.get("finished_at") or (existing.completed_at if existing else None),
            backend=row.get("backend") or (existing.backend if existing else None),
            team_profile=row.get("profile") or (existing.team_profile if existing else None),
            status=row.get("status"),
            description=row.get("description"),
        )

    return sorted(
        runs.values(),
        key=lambda r: r.started_at or "",
        reverse=True,
    )


def _iso_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _read_json_path(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _normalize_tests_from_dict(data: dict[str, Any], source: str) -> TestsPanelData:
    """Map heterogeneous test_results shapes to TestsPanelData."""
    failures: list[TestFailureItem] = []
    for item in data.get("failures") or []:
        if isinstance(item, dict):
            failures.append(
                TestFailureItem(
                    test_name=str(item.get("test_name") or item.get("name") or "unknown"),
                    error=str(item.get("error") or item.get("message") or ""),
                    traceback=str(item.get("traceback") or ""),
                )
            )

    per_file: list[FileCoverageItem] = []
    cov = data.get("coverage_report") or data.get("coverage") or {}
    if isinstance(cov, dict):
        for entry in cov.get("per_file") or cov.get("files") or []:
            if isinstance(entry, dict):
                per_file.append(
                    FileCoverageItem(
                        path=str(entry.get("path") or entry.get("file") or ""),
                        line_coverage=float(entry.get("line_coverage") or entry.get("lines") or 0),
                        branch_coverage=float(
                            entry.get("branch_coverage") or entry.get("branches") or 0
                        ),
                    )
                )
        line_cov = float(
            cov.get("line_coverage") or cov.get("lines") or data.get("coverage_line") or 0
        )
        branch_cov = float(
            cov.get("branch_coverage") or cov.get("branches") or data.get("coverage_branch") or 0
        )
    else:
        line_cov = float(data.get("coverage_line") or 0)
        branch_cov = float(data.get("coverage_branch") or 0)

    tests_raw = data.get("tests")
    tests_block: dict[str, Any] = tests_raw if isinstance(tests_raw, dict) else {}
    passed = int(data.get("passed") or tests_block.get("passed") or 0)
    failed = int(data.get("failed") or tests_block.get("failed") or 0)
    errors = int(data.get("errors") or tests_block.get("errors") or 0)
    skipped = int(data.get("skipped") or tests_block.get("skipped") or 0)
    total = int(
        data.get("total") or tests_block.get("total") or (passed + failed + errors + skipped)
    )

    return TestsPanelData(
        total=total,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        coverage_line=line_cov,
        coverage_branch=branch_cov,
        duration_seconds=float(data.get("duration_seconds") or data.get("duration") or 0),
        failures=failures,
        per_file_coverage=per_file,
        source=source,
    )


def load_tests_panel(project_id: str) -> TestsPanelData:
    """Load test results from bundle, workspace, or state.json."""
    ws, bundle = resolve_project_paths(project_id)
    candidates: list[tuple[Path, str]] = [
        (bundle / "artifacts" / "testing" / "test_results.json", "bundle:test_results.json"),
        (ws / "docs" / "test_results.json", "workspace:docs/test_results.json"),
        (bundle / "state.json", "bundle:state.json"),
    ]
    for path, source in candidates:
        raw = _read_json_path(path)
        if raw is None:
            continue
        if source.endswith("state.json") and isinstance(raw, dict):
            tr = raw.get("test_results")
            if isinstance(tr, dict):
                return _normalize_tests_from_dict(tr, source)
            continue
        if isinstance(raw, dict):
            try:
                model = TestResult.model_validate(raw)
                return _normalize_tests_from_dict(model.model_dump(), source)
            except Exception:
                return _normalize_tests_from_dict(raw, source)

    pytest_txt = bundle / "artifacts" / "testing" / "pytest.txt"
    raw_pytest = None
    if pytest_txt.is_file():
        with contextlib.suppress(OSError):
            raw_pytest = pytest_txt.read_text(encoding="utf-8", errors="replace")[:8000]

    return TestsPanelData(raw_pytest=raw_pytest, source="empty")


def load_architecture_panel(project_id: str) -> ArchitecturePanelData:
    """Load architecture from JSON artifacts or markdown fallback."""
    ws, bundle = resolve_project_paths(project_id)
    json_candidates: list[tuple[Path, str]] = [
        (bundle / "artifacts" / "planning" / "architecture.json", "bundle:architecture.json"),
        (ws / "docs" / "architecture.json", "workspace:docs/architecture.json"),
    ]
    for path, source in json_candidates:
        raw = _read_json_path(path)
        if not isinstance(raw, dict):
            continue
        nested = raw.get("architecture")
        arch_raw: dict[str, Any] = nested if isinstance(nested, dict) else raw
        try:
            doc = ArchitectureDocument.model_validate(arch_raw)
            return ArchitecturePanelData(
                system_overview=doc.system_overview,
                ascii_diagram=doc.ascii_diagram,
                components=[c.model_dump() for c in doc.components],
                technology_stack=[t.model_dump() for t in doc.technology_stack],
                interface_contracts=[i.model_dump() for i in doc.interface_contracts],
                data_model_outline=doc.data_model_outline,
                deployment_topology=doc.deployment_topology,
                adrs=[a.model_dump() for a in doc.adrs],
                source=source,
            )
        except Exception:
            return ArchitecturePanelData(
                system_overview=str(arch_raw.get("system_overview") or ""),
                ascii_diagram=str(arch_raw.get("ascii_diagram") or ""),
                components=list(arch_raw.get("components") or []),
                technology_stack=list(arch_raw.get("technology_stack") or []),
                source=source,
            )

    md_candidates = [
        (ws / "docs" / "architecture.md", "workspace:docs/architecture.md"),
        (bundle / "artifacts" / "planning" / "architecture.md", "bundle:architecture.md"),
    ]
    for path, source in md_candidates:
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            return ArchitecturePanelData(markdown_fallback=text, source=source)

    state_path = bundle / "state.json"
    raw = _read_json_path(state_path)
    if isinstance(raw, dict):
        arch = raw.get("architecture")
        if isinstance(arch, dict):
            return ArchitecturePanelData(
                system_overview=str(arch.get("system_overview") or arch.get("overview") or ""),
                ascii_diagram=str(arch.get("ascii_diagram") or ""),
                components=list(arch.get("components") or []),
                technology_stack=list(arch.get("technology_stack") or []),
                source="bundle:state.json",
            )
        if isinstance(arch, str) and arch.strip():
            return ArchitecturePanelData(
                markdown_fallback=arch, source="bundle:state.json:architecture"
            )

    return ArchitecturePanelData(source="empty")


def workspace_zip_bytes(project_id: str) -> bytes:
    """Zip workspace directory for download."""
    ws, _ = resolve_project_paths(project_id)
    if not ws.is_dir():
        raise ValueError(f"Workspace not found for project: {project_id}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, _ in _list_relative_files(ws, max_files=2000):
            abs_path = ws / rel
            if abs_path.is_file():
                zf.write(abs_path, arcname=f"{project_id}/{rel}")
    logger.info("artifact_zip_created", project_id=project_id)
    return buf.getvalue()
