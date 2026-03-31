"""Results bundle writer.

Creates a stable, org-grade output structure under ``output/runs/<project_id>/`` and
an isolated per-run workspace under ``workspace/<project_id>/``.

Registry files at the output root:

- ``index.json`` — list of runs with metadata from each ``run.json``
- ``latest`` — text file containing the most recently touched run id
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import structlog
from ai_team.config.settings import get_settings
from ai_team.core.results.models import GeneratedFileEntry, RunMetadata, Scorecard

logger = structlog.get_logger(__name__)

RUNS_SUBDIR = "runs"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


class ResultsBundle:
    """Create and write run artifacts in a canonical structure."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        s = get_settings()
        root = Path(s.project.output_dir).resolve()
        self._registry_root = root
        self._base_output = root / RUNS_SUBDIR / project_id
        self._base_workspace = Path(s.project.workspace_dir).resolve() / project_id

    @property
    def output_dir(self) -> Path:
        return self._base_output

    @property
    def workspace_dir(self) -> Path:
        return self._base_workspace

    def _update_registry(self) -> None:
        """Write ``output/index.json`` and ``output/latest`` from ``output/runs/*``."""
        root = self._registry_root
        runs_dir = root / RUNS_SUBDIR
        runs_dir.mkdir(parents=True, exist_ok=True)
        run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
        if not run_dirs:
            payload = {"version": 1, "updated_at": _utcnow().isoformat(), "runs": []}
            (root / "index.json").write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8"
            )
            return

        def sort_key(p: Path) -> float:
            best = p.stat().st_mtime
            for name in ("state.json", "run.json", "events.jsonl"):
                f = p / name
                if f.exists():
                    best = max(best, f.stat().st_mtime)
            return best

        run_dirs.sort(key=sort_key, reverse=True)
        entries: list[dict[str, Any]] = []
        for d in run_dirs:
            run_json = d / "run.json"
            row: dict[str, Any] = {
                "run_id": d.name,
                "output_dir": str(d.resolve()),
            }
            if run_json.exists():
                try:
                    data = json.loads(run_json.read_text(encoding="utf-8"))
                    row["started_at"] = data.get("started_at")
                    row["completed_at"] = data.get("completed_at")
                    row["backend"] = data.get("backend")
                    row["team_profile"] = data.get("team_profile")
                except (json.JSONDecodeError, OSError):
                    pass
            entries.append(row)
        payload = {"version": 1, "updated_at": _utcnow().isoformat(), "runs": entries}
        (root / "index.json").write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        (root / "latest").write_text(run_dirs[0].name + "\n", encoding="utf-8")

    def init_dirs(self) -> None:
        (self._base_output / "artifacts" / "intake").mkdir(parents=True, exist_ok=True)
        (self._base_output / "artifacts" / "planning").mkdir(parents=True, exist_ok=True)
        (self._base_output / "artifacts" / "development").mkdir(parents=True, exist_ok=True)
        (self._base_output / "artifacts" / "testing").mkdir(parents=True, exist_ok=True)
        (self._base_output / "artifacts" / "deployment").mkdir(parents=True, exist_ok=True)
        (self._base_output / "reports").mkdir(parents=True, exist_ok=True)
        (self._base_output / "logs").mkdir(parents=True, exist_ok=True)
        self._base_workspace.mkdir(parents=True, exist_ok=True)
        (self._base_workspace / "src").mkdir(parents=True, exist_ok=True)
        (self._base_workspace / "tests").mkdir(parents=True, exist_ok=True)

    # ---- canonical files -------------------------------------------------

    def write_run(self, meta: RunMetadata) -> Path:
        self.init_dirs()
        path = self._base_output / "run.json"
        path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        self._update_registry()
        return path

    def write_state(self, state: dict[str, Any]) -> Path:
        self.init_dirs()
        path = self._base_output / "state.json"
        path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        self._update_registry()
        return path

    def append_event(self, event: dict[str, Any]) -> Path:
        self.init_dirs()
        path = self._base_output / "events.jsonl"
        line = json.dumps(event, default=str)
        path.write_text("", encoding="utf-8") if not path.exists() else None
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return path

    def write_scorecard(self, scorecard: Scorecard) -> Path:
        self.init_dirs()
        path = self._base_output / "reports" / "scorecard.json"
        path.write_text(scorecard.model_dump_json(indent=2), encoding="utf-8")
        return path

    def write_summary(self, markdown: str) -> Path:
        self.init_dirs()
        path = self._base_output / "reports" / "summary.md"
        path.write_text(markdown.strip() + "\n", encoding="utf-8")
        return path

    # ---- artifacts -------------------------------------------------------

    def write_artifact_text(self, phase: str, name: str, content: str) -> Path:
        self.init_dirs()
        out = self._base_output / "artifacts" / phase / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        return out

    def write_artifact_json(self, phase: str, name: str, obj: Any) -> Path:
        self.init_dirs()
        out = self._base_output / "artifacts" / phase / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        return out

    # ---- generated files -------------------------------------------------

    def record_generated_file(
        self,
        *,
        rel_path: str,
        phase: str,
        agent_role: str,
    ) -> GeneratedFileEntry:
        self.init_dirs()
        abs_path = (self._base_workspace / rel_path).resolve()
        try:
            data = _read_bytes(abs_path)
        except FileNotFoundError:
            data = b""
        entry = GeneratedFileEntry(
            path=rel_path.replace(os.sep, "/"),
            sha256=_sha256_bytes(data),
            bytes=len(data),
            phase=phase,
            agent_role=agent_role,
            timestamp=_utcnow(),
        )
        return entry

    def write_code_manifest(self, entries: list[GeneratedFileEntry]) -> Path:
        self.init_dirs()
        out = self._base_output / "artifacts" / "development" / "code_manifest.json"
        payload = [e.model_dump(mode="json") for e in entries]
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return out

    # ---- utilities -------------------------------------------------------

    def default_run_metadata(
        self,
        *,
        backend: str,
        team_profile: str,
        env: str | None,
        argv: list[str] | None = None,
        models: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
        started_at: datetime | None = None,
    ) -> RunMetadata:
        get_settings()
        return RunMetadata(
            project_id=self.project_id,
            backend=backend,
            team_profile=team_profile,
            env=env,
            started_at=started_at or _utcnow(),
            workspace_dir=str(self.workspace_dir),
            output_dir=str(self.output_dir),
            argv=list(argv or []),
            models=dict(models or {}),
            extra=dict(extra or {}),
        )


def scorecard_from_langgraph_state(
    run_id: str,
    state: dict[str, Any],
    *,
    backend: str = "langgraph",
) -> Scorecard:
    """Build a summary scorecard from a LangGraph graph state dict."""
    phase = str(state.get("current_phase") or "")
    if phase == "complete":
        sc_status: Literal["complete", "error", "partial"] = "complete"
    elif phase == "error":
        sc_status = "error"
    else:
        sc_status = "partial"
    errors = state.get("errors") or []
    if not isinstance(errors, list):
        errors = []
    guardrails: list[dict[str, Any]] = []
    for e in errors:
        if not isinstance(e, dict):
            continue
        g = e.get("guardrail")
        if isinstance(g, dict):
            guardrails.append(g)
        elif e.get("type") == "GuardrailError" or (
            "guardrail" in str(e.get("message", "")).lower()
        ):
            guardrails.append(e)
    tr = state.get("test_results") or {}
    lint_ok: bool | None = None
    tests_ok: bool | None = None
    if isinstance(tr, dict):
        lint = tr.get("lint")
        tests = tr.get("tests")
        if isinstance(lint, dict) and "ok" in lint:
            lint_ok = bool(lint.get("ok"))
        if isinstance(tests, dict) and "ok" in tests:
            tests_ok = bool(tests.get("ok"))
    meta = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
    team = meta.get("team_profile") if isinstance(meta, dict) else None
    kpis: dict[str, Any] = {}
    if isinstance(tr, dict) and tr.get("passed") is not None:
        kpis["tests_passed_field"] = tr.get("passed")
    rid = run_id
    artifact_paths = {
        "state_json": f"{RUNS_SUBDIR}/{rid}/state.json",
        "run_json": f"{RUNS_SUBDIR}/{rid}/run.json",
        "events_jsonl": f"{RUNS_SUBDIR}/{rid}/events.jsonl",
        "scorecard_json": f"{RUNS_SUBDIR}/{rid}/reports/scorecard.json",
    }
    if isinstance(tr, dict) and tr:
        artifact_paths["test_results_json"] = f"{RUNS_SUBDIR}/{rid}/artifacts/testing/test_results.json"
        if (tr.get("lint") or {}).get("output"):
            artifact_paths["ruff_txt"] = f"{RUNS_SUBDIR}/{rid}/artifacts/testing/ruff.txt"
        if (tr.get("tests") or {}).get("output"):
            artifact_paths["pytest_txt"] = f"{RUNS_SUBDIR}/{rid}/artifacts/testing/pytest.txt"
    return Scorecard(
        status=sc_status,
        run_id=rid,
        current_phase=phase or None,
        backend=backend,
        team_profile=team if isinstance(team, str) else None,
        error_count=len(errors),
        test_passed=tests_ok,
        lint_ok=lint_ok,
        guardrails=guardrails,
        kpis=kpis,
        artifact_paths=artifact_paths,
    )


def scorecard_from_project_state(
    run_id: str,
    state: Any,
    *,
    status: Literal["complete", "error", "partial"],
    backend: str = "crewai",
    duration_seconds: float | None = None,
) -> Scorecard:
    """Build a summary scorecard from CrewAI ``ProjectState`` (duck-typed; no flows import)."""
    tr = getattr(state, "test_results", None)
    test_passed = getattr(tr, "success", None) if tr is not None else None
    meta = getattr(state, "metadata", None) or {}
    team = str(meta.get("team_profile") or "full") if isinstance(meta, dict) else "full"
    generated = getattr(state, "generated_files", None) or []
    errors = getattr(state, "errors", None) or []
    phase = getattr(state, "current_phase", None)
    phase_val = phase.value if phase is not None and hasattr(phase, "value") else str(phase or "")
    kpis: dict[str, Any] = {"files_generated": len(generated)}
    if duration_seconds is not None:
        kpis["duration_seconds"] = duration_seconds
    if tr is not None:
        kpis["tests_total"] = getattr(tr, "total", 0)
        kpis["tests_passed_count"] = getattr(tr, "passed", 0)
    rid = run_id
    return Scorecard(
        status=status,
        run_id=rid,
        current_phase=phase_val or None,
        backend=backend,
        team_profile=team,
        error_count=len(errors),
        test_passed=test_passed if isinstance(test_passed, bool) else None,
        artifact_paths={
            "state_json": f"{RUNS_SUBDIR}/{rid}/state.json",
            "run_json": f"{RUNS_SUBDIR}/{rid}/run.json",
            "scorecard_json": f"{RUNS_SUBDIR}/{rid}/reports/scorecard.json",
        },
        kpis=kpis,
    )
