"""Results bundle writer.

Creates a stable, org-grade output structure under ``output/<project_id>/`` and
an isolated per-run workspace under ``workspace/<project_id>/``.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from ai_team.config.settings import get_settings
from ai_team.core.results.models import GeneratedFileEntry, RunMetadata, Scorecard

logger = structlog.get_logger(__name__)


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
        self._base_output = Path(s.project.output_dir).resolve() / project_id
        self._base_workspace = Path(s.project.workspace_dir).resolve() / project_id

    @property
    def output_dir(self) -> Path:
        return self._base_output

    @property
    def workspace_dir(self) -> Path:
        return self._base_workspace

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
        return path

    def write_state(self, state: dict[str, Any]) -> Path:
        self.init_dirs()
        path = self._base_output / "state.json"
        path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
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
