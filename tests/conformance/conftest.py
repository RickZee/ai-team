"""Conformance fixtures. Offline, deterministic, draft-then-commit on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ai_team.backends.registry import get_backend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import load_team_profile
from tests.conformance.fake_models import load_thin_slice

BACKENDS = ("crewai", "langgraph", "claude-agent-sdk", "fake-remote")


def run_thin_slice(
    backend_name: str,
    tmp_path: Path,
    **overrides: Any,
) -> ProjectResult:
    """Inject the shared script and run one backend."""
    script = load_thin_slice()
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    options: dict[str, Any] = {
        "conformance_script": script,
        "workspace_dir": workspace,
        "output_dir": output,
        "thread_id": f"conf-{backend_name}",
        "model_tier": "local",
    }
    options.update(overrides)
    target = "container" if backend_name == "fake-remote" else "local"
    options.setdefault("target", target)
    backend = get_backend(backend_name, target=target)
    profile = load_team_profile("prototype")
    return backend.run(str(script["description"]), profile, **options)


def audit_rows(result: ProjectResult) -> list[dict[str, Any]]:
    """Audit rows written into the run workspace."""
    path = Path(str(result.raw["workspace_dir"])) / "logs" / "audit.jsonl"
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


@pytest.fixture
def thin_run(request: pytest.FixtureRequest, tmp_path: Path) -> ProjectResult:
    """One happy-path thin slice for the parametrized backend."""
    name = str(request.param)
    return run_thin_slice(name, tmp_path)
