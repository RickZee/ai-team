"""Register built-in file/code/git/test tools on a :class:`ToolBus`.

Handlers call module-private implementations. Public ``@tool`` wrappers go
through the bus (task 3.1).
"""

from __future__ import annotations

from typing import Any

from ai_team.tools.bus import ToolBus, ToolSpec
from ai_team.tools.kinds import ToolObservation, ToolRequest
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Arg schemas
# ---------------------------------------------------------------------------


class PathArgs(BaseModel):
    path: str = Field(..., description="Path relative to the workspace.")


class WriteArgs(BaseModel):
    path: str
    content: str


class DeleteArgs(BaseModel):
    path: str
    confirm: bool = False


class ShellArgs(BaseModel):
    command: str
    timeout: int = 10


class PythonArgs(BaseModel):
    code: str
    timeout: int = 10


class CommitWriteArgs(BaseModel):
    draft_id: str = Field(..., description="Id returned by a drafted write.")


class GitPathArgs(BaseModel):
    path: str


class GitAddArgs(BaseModel):
    path: str
    files: list[str]


class GitCommitArgs(BaseModel):
    path: str
    message: str


class EmptyToolArgs(BaseModel):
    """No arguments."""


def _obs(
    *,
    ok: bool,
    code: str,
    summary: str,
    tool: str,
    kind: str,
    risk_class: str,
    artifact_refs: list[str] | None = None,
    detail: dict[str, Any] | None = None,
) -> ToolObservation:
    return ToolObservation(
        ok=ok,
        code=code,  # type: ignore[arg-type]
        summary=summary[:2000],
        artifact_refs=artifact_refs or [],
        tool=tool,
        kind=kind,  # type: ignore[arg-type]
        risk_class=risk_class,  # type: ignore[arg-type]
        duration_ms=0,
        detail=detail or {},
    )


def _handle_read_file(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.file_tools import _read_file_impl

    _ = request
    text = _read_file_impl(str(args["path"]))
    summary = text if len(text) <= 2000 else text[:1999] + "…"
    detail: dict[str, Any] = {"content": text, "full_chars": len(text)}
    refs: list[str] = [str(args["path"])] if len(text) > 2000 else []
    return _obs(
        ok=True,
        code="ok",
        summary=summary,
        tool="read_file",
        kind="read",
        risk_class="low",
        artifact_refs=refs,
        detail=detail,
    )


def _handle_write_file(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.file_tools import _write_file_impl

    _ = request
    _write_file_impl(str(args["path"]), str(args["content"]))
    return _obs(
        ok=True,
        code="ok",
        summary=f"Wrote {args['path']}",
        tool="write_file",
        kind="write",
        risk_class="write",
        artifact_refs=[str(args["path"])],
    )


def _handle_list_directory(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.file_tools import _list_directory_impl

    _ = request
    names = _list_directory_impl(str(args["path"]))
    text = "\n".join(names) if names else "(empty)"
    return _obs(
        ok=True,
        code="ok",
        summary=text[:2000],
        tool="list_directory",
        kind="read",
        risk_class="low",
    )


def _handle_create_directory(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.file_tools import _create_directory_impl

    _ = request
    _create_directory_impl(str(args["path"]))
    return _obs(
        ok=True,
        code="ok",
        summary=f"Created directory {args['path']}",
        tool="create_directory",
        kind="write",
        risk_class="write",
        artifact_refs=[str(args["path"])],
    )


def _handle_delete_file(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.file_tools import _delete_file_impl

    _ = request
    _delete_file_impl(str(args["path"]), confirm=bool(args.get("confirm", False)))
    return _obs(
        ok=True,
        code="ok",
        summary=f"Deleted {args['path']}",
        tool="delete_file",
        kind="irreversible",
        risk_class="irreversible",
        artifact_refs=[str(args["path"])],
    )


def _handle_execute_shell(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.code_tools import _execute_shell_impl

    _ = request
    result = _execute_shell_impl(str(args["command"]), timeout=int(args.get("timeout") or 10))
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    summary = combined.strip() or f"exit {result.return_code}"
    if len(summary) > 2000:
        summary = summary[:1999] + "…"
    ok = result.return_code == 0 and not result.timed_out
    return _obs(
        ok=ok,
        code="ok" if ok else "error",
        summary=summary,
        tool="execute_shell",
        kind="irreversible",
        risk_class="irreversible",
        detail={
            "return_code": result.return_code,
            "timed_out": result.timed_out,
            "duration_seconds": result.duration_seconds,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
    )


def _handle_execute_python(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.code_tools import _execute_python_impl

    _ = request
    result = _execute_python_impl(str(args["code"]), timeout=int(args.get("timeout") or 10))
    combined = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    summary = combined.strip() or f"exit {result.return_code}"
    if len(summary) > 2000:
        summary = summary[:1999] + "…"
    ok = result.return_code == 0 and not result.timed_out
    return _obs(
        ok=ok,
        code="ok" if ok else "error",
        summary=summary,
        tool="execute_python",
        kind="write",
        risk_class="write",
        detail={
            "return_code": result.return_code,
            "timed_out": result.timed_out,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": result.duration_seconds,
        },
    )


def _handle_commit_write(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.config.settings import get_workspace_dir
    from ai_team.tools.draft import commit_draft

    _ = request
    workspace = __import__("pathlib").Path(get_workspace_dir())
    try:
        path = commit_draft(workspace, str(args["draft_id"]))
    except FileNotFoundError as exc:
        return _obs(
            ok=False,
            code="not_found",
            summary=str(exc),
            tool="commit_write",
            kind="write",
            risk_class="write",
        )
    except ValueError as exc:
        return _obs(
            ok=False,
            code="validation_failed",
            summary=str(exc),
            tool="commit_write",
            kind="write",
            risk_class="write",
        )
    return _obs(
        ok=True,
        code="ok",
        summary=f"Committed draft to {path}",
        tool="commit_write",
        kind="write",
        risk_class="write",
        artifact_refs=[path],
    )


def _handle_git_status(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.git_tools import git_status

    _ = request
    status = git_status(str(args["path"]))
    summary = (
        f"{status.branch} staged={len(status.staged_files)} unstaged={len(status.unstaged_files)}"
    )
    return _obs(
        ok=True,
        code="ok",
        summary=summary,
        tool="git_status",
        kind="read",
        risk_class="low",
        detail=status.model_dump(),
    )


def _handle_git_commit(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.git_tools import git_commit

    _ = request
    sha = git_commit(str(args["path"]), str(args["message"]))
    return _obs(
        ok=True,
        code="ok",
        summary=f"Committed {sha}",
        tool="git_commit",
        kind="write",
        risk_class="write",
        detail={"sha": sha},
    )


def _handle_git_add(args: dict[str, Any], request: ToolRequest) -> ToolObservation:
    from ai_team.tools.git_tools import git_add

    _ = request
    git_add(str(args["path"]), list(args["files"]))
    return _obs(
        ok=True,
        code="ok",
        summary=f"Staged {len(args['files'])} path(s)",
        tool="git_add",
        kind="write",
        risk_class="write",
    )


def register_builtin_tools(bus: ToolBus) -> None:
    """Register file, code, git, and commit_write tools on *bus*."""
    specs = [
        ToolSpec(
            name="read_file",
            kind="read",
            risk_class="low",
            args_schema=PathArgs,
            handler=_handle_read_file,
        ),
        ToolSpec(
            name="write_file",
            kind="write",
            risk_class="write",
            args_schema=WriteArgs,
            handler=_handle_write_file,
        ),
        ToolSpec(
            name="list_directory",
            kind="read",
            risk_class="low",
            args_schema=PathArgs,
            handler=_handle_list_directory,
        ),
        ToolSpec(
            name="create_directory",
            kind="write",
            risk_class="write",
            args_schema=PathArgs,
            handler=_handle_create_directory,
        ),
        ToolSpec(
            name="delete_file",
            kind="irreversible",
            risk_class="irreversible",
            args_schema=DeleteArgs,
            handler=_handle_delete_file,
        ),
        ToolSpec(
            name="execute_shell",
            kind="irreversible",
            risk_class="irreversible",
            args_schema=ShellArgs,
            handler=_handle_execute_shell,
        ),
        ToolSpec(
            name="execute_python",
            kind="write",
            risk_class="write",
            args_schema=PythonArgs,
            handler=_handle_execute_python,
        ),
        ToolSpec(
            name="commit_write",
            kind="write",
            risk_class="write",
            args_schema=CommitWriteArgs,
            handler=_handle_commit_write,
        ),
        ToolSpec(
            name="git_status",
            kind="read",
            risk_class="low",
            args_schema=GitPathArgs,
            handler=_handle_git_status,
        ),
        ToolSpec(
            name="git_add",
            kind="write",
            risk_class="write",
            args_schema=GitAddArgs,
            handler=_handle_git_add,
        ),
        ToolSpec(
            name="git_commit",
            kind="write",
            risk_class="write",
            args_schema=GitCommitArgs,
            handler=_handle_git_commit,
        ),
    ]
    for spec in specs:
        bus.register(spec)
