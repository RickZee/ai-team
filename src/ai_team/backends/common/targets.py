"""Where a backend's agents run: this process, a local container, or the cloud.

``container`` and ``cloud`` are thin clients. The pipeline itself always runs
with ``target=local`` inside the container.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Any

from ai_team.backends.common.thin_slice import run_scripted
from ai_team.core.backend import ThreadedBackend
from ai_team.core.result import ProjectResult
from ai_team.core.team_profile import TeamProfile


class ExecutionTarget(StrEnum):
    """Where the agents execute."""

    LOCAL = "local"
    CONTAINER = "container"
    CLOUD = "cloud"


class UnsupportedTargetError(ValueError):
    """The target is unknown, or this backend does not support it."""


class RemoteRunClient(ABC):
    """Start a remote run, poll it, and copy artifacts back."""

    @abstractmethod
    def start(self, description: str, profile_name: str) -> str:
        """Start a run. Return its id. Must not spend before the id exists."""

    @abstractmethod
    def status(self, run_id: str) -> str:
        """Return a status string such as ``complete`` or ``running``."""

    @abstractmethod
    def fetch_artifacts(self, run_id: str, dest: Path) -> None:
        """Copy the remote workspace into ``dest``."""


class FakeRemoteClient(RemoteRunClient):
    """In-process stand-in. The pipeline runs locally; fetch copies nothing new."""

    def __init__(self, *, profile: TeamProfile, options: dict[str, Any], backend_name: str) -> None:
        self._profile = profile
        self._options = options
        self._backend_name = backend_name
        self.last_result: ProjectResult | None = None

    def start(self, description: str, profile_name: str) -> str:
        _ = profile_name
        self.last_result = run_scripted(
            self._backend_name,
            description,
            self._profile,
            self._options,
        )
        raw = self.last_result.raw if self.last_result else {}
        return str(raw.get("run_id") or "")

    def status(self, run_id: str) -> str:
        raw = self.last_result.raw if self.last_result else {}
        if raw.get("run_id") == run_id:
            return "complete"
        return "unknown"

    def fetch_artifacts(self, run_id: str, dest: Path) -> None:
        _ = run_id
        dest.mkdir(parents=True, exist_ok=True)
        raw = self.last_result.raw if self.last_result else {}
        src = Path(str(raw.get("workspace_dir") or dest))
        if src.resolve() == dest.resolve():
            return
        for path in src.rglob("*"):
            if not path.is_file():
                continue
            target = dest / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


class FakeRemoteBackend(ThreadedBackend):
    """Conformance double for a container or cloud target."""

    name: str = "fake-remote"

    def run(
        self,
        description: str,
        profile: TeamProfile,
        env: str | None = None,
        **kwargs: Any,
    ) -> ProjectResult:
        _ = env
        target = str(kwargs.get("target") or ExecutionTarget.LOCAL.value)
        client = kwargs.get("remote_client")
        if not isinstance(client, RemoteRunClient):
            client = FakeRemoteClient(profile=profile, options=dict(kwargs), backend_name=self.name)
        if target in {ExecutionTarget.CONTAINER.value, ExecutionTarget.CLOUD.value}:
            run_id = client.start(description, profile.name)
            if client.status(run_id) != "complete":
                return ProjectResult(
                    backend_name=self.name,
                    success=False,
                    error=f"remote status for {run_id} was not complete",
                    team_profile=profile.name,
                )
            dest = Path(str(kwargs.get("workspace_dir") or "."))
            client.fetch_artifacts(run_id, dest)
            if isinstance(client, FakeRemoteClient) and client.last_result is not None:
                return client.last_result
        return run_scripted(self.name, description, profile, kwargs)
