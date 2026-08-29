"""Task-typed model routing. Config table, not agent prose."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import structlog
import yaml
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

TaskType = Literal[
    "classify",
    "format",
    "mechanical_check",
    "plan",
    "judge",
    "generate",
]

DETERMINISTIC_SENTINEL = "deterministic"

_CONFIG_NAME = "task_routes.yaml"


class Route(BaseModel):
    """Resolved model route."""

    task_type: TaskType
    env: str
    model_id: str
    deterministic: bool = False
    same_model: bool = False
    unwired: bool = False


def _routes_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / _CONFIG_NAME


def load_task_routes(path: Path | None = None) -> dict[str, Any]:
    """Load ``task_routes.yaml``. Empty dict if missing."""
    p = path or _routes_path()
    if not p.is_file():
        logger.warning("task_routes_missing", path=str(p))
        return {"version": "1", "routes": {}}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {"version": "1", "routes": {}}
    return data


def resolve_route(
    task_type: TaskType | str,
    env: str,
    *,
    profile_overrides: dict[str, str] | None = None,
    same_model: bool = False,
    same_model_id: str | None = None,
    routes: dict[str, Any] | None = None,
) -> Route:
    """Map ``(task_type, env)`` to a model id.

    Missing types fall back to ``generate`` with ``unwired=True``.
    ``mechanical_check`` may resolve to the ``deterministic`` sentinel (no LLM).
    Same-model profiles override every non-deterministic type to one id.
    """
    table = routes if routes is not None else load_task_routes()
    env_table = (table.get("routes") or {}).get(env) or (table.get("routes") or {}).get("dev") or {}
    raw = env_table.get(task_type)
    unwired = False
    if raw is None:
        raw = env_table.get("generate")
        unwired = task_type != "generate"
        if unwired:
            logger.warning("task_route_unwired", task_type=task_type, env=env)
    model_id = str(raw or "deterministic")
    if profile_overrides and task_type in profile_overrides:
        model_id = profile_overrides[task_type]
    deterministic = model_id == DETERMINISTIC_SENTINEL or task_type == "mechanical_check"
    if deterministic and model_id != DETERMINISTIC_SENTINEL and task_type == "mechanical_check":
        model_id = DETERMINISTIC_SENTINEL
        deterministic = True
    if same_model and same_model_id and not deterministic:
        model_id = same_model_id
    return Route(
        task_type=task_type,  # type: ignore[arg-type]
        env=env,
        model_id=model_id,
        deterministic=deterministic,
        same_model=same_model and not deterministic,
        unwired=unwired,
    )
