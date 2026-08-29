"""
Secure file operation tools for agent use.

Provides read_file, write_file, list_directory, create_directory, and delete_file
with path traversal prevention, directory whitelist, content scanning, size limits,
optional PII scanning, and audit logging. Both @tool-decorated (agent) and raw
function versions (for testing) are provided.
"""

import getpass
import re
from pathlib import Path

import structlog
from ai_team.config.settings import get_settings, get_workspace_dir

logger = structlog.get_logger(__name__)

# Default max directory nesting under allowed roots
MAX_DIRECTORY_DEPTH = 20


def _get_allowed_roots() -> list[Path]:
    """Return resolved absolute paths for workspace and output directories."""
    settings = get_settings()
    return [
        Path(get_workspace_dir()).resolve(),
        Path(settings.project.output_dir).resolve(),
    ]


def _resolve_and_validate_path(
    path: str,
    *,
    must_exist: bool = False,
    allow_new_file: bool = False,
    allow_new_dir: bool = False,
) -> Path:
    """
    Resolve path and ensure it is under allowed roots. Prevents path traversal and symlink escape.

    Raises:
        ValueError: If path attempts traversal, escapes whitelist, or fails existence check.
    """
    if ".." in path:
        raise ValueError("Path traversal (..) is not allowed")
    if Path(path).is_absolute():
        p = Path(path)
    else:
        base = Path(get_workspace_dir()).resolve()
        p = (base / path).resolve()

    try:
        resolved = p.resolve()
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Invalid or inaccessible path: {e}") from e

    # Reject if path contains .. components that escape
    path_str = str(resolved)
    allowed_roots = _get_allowed_roots()

    under_any = False
    for root in allowed_roots:
        try:
            root_resolved = root.resolve()
            if path_str == str(root_resolved) or path_str.startswith(str(root_resolved) + "/"):
                under_any = True
                break
        except (OSError, RuntimeError):
            continue
    if not under_any:
        raise ValueError(f"Path not under allowed directories (workspace/output): {path_str}")

    if must_exist and not resolved.exists():
        raise ValueError(f"Path does not exist: {resolved}")
    if allow_new_file and resolved.exists() and not resolved.is_file():
        raise ValueError(f"Path exists and is not a file: {resolved}")
    if allow_new_dir and resolved.exists() and not resolved.is_dir():
        raise ValueError(f"Path exists and is not a directory: {resolved}")

    return resolved


def _check_nesting_limit(resolved: Path) -> None:
    """Ensure directory depth under allowed roots is within limit."""
    allowed_roots = _get_allowed_roots()
    for root in allowed_roots:
        try:
            root_resolved = root.resolve()
            if str(resolved).startswith(str(root_resolved) + "/") or resolved == root_resolved:
                depth = len(resolved.relative_to(root_resolved).parts)
                if depth > MAX_DIRECTORY_DEPTH:
                    raise ValueError(
                        f"Directory nesting exceeds limit of {MAX_DIRECTORY_DEPTH}: {resolved}"
                    )
                return
        except ValueError:
            continue
    raise ValueError(f"Path not under allowed roots: {resolved}")


def _audit_log(operation: str, path: str, success: bool, detail: str | None = None) -> None:
    """Emit audit log for file operations."""
    user = getpass.getuser()
    logger.info(
        "file_audit",
        operation=operation,
        path=path,
        user=user,
        success=success,
        detail=detail,
    )


def _scan_dangerous_patterns(content: str) -> str | None:
    """Scan content for dangerous patterns. Returns first match or None."""
    settings = get_settings()
    for pattern in settings.guardrails.dangerous_patterns:
        if pattern in content:
            return pattern
    return None


def _scan_pii_warn(content: str) -> None:
    """If PII patterns are configured, log a warning when detected."""
    settings = get_settings()
    for pattern in settings.guardrails.pii_patterns:
        if re.search(pattern, content):
            logger.warning("pii_detected_in_content", pattern=pattern)
            return


def _check_file_size(path: Path, max_kb: int) -> None:
    """Raise ValueError if file size exceeds max_kb."""
    size_kb = path.stat().st_size / 1024
    if size_kb > max_kb:
        raise ValueError(f"File size {size_kb:.1f} KB exceeds limit {max_kb} KB: {path}")


# -----------------------------------------------------------------------------
# Raw functions (for testing and direct use)
# -----------------------------------------------------------------------------


def _read_file_impl(path: str) -> str:
    """
    Read file with path traversal prevention and size limit.

    Args:
        path: Path relative to workspace or absolute under workspace/output.

    Returns:
        File contents as string.

    Raises:
        ValueError: If path is invalid, outside whitelist, or file too large.
    """
    settings = get_settings()
    max_kb = settings.guardrails.max_file_size_kb
    resolved = _resolve_and_validate_path(path, must_exist=True)
    if not resolved.is_file():
        _audit_log("read_file", str(resolved), False, "not a file")
        raise ValueError(f"Not a file: {resolved}")
    _check_file_size(resolved, max_kb)
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        _audit_log("read_file", str(resolved), False, str(e))
        raise
    _scan_pii_warn(text)
    _audit_log("read_file", str(resolved), True)
    return text


def normalize_pytest_path(path: str) -> str:
    """Relocate root-level ``test_*.py`` files into ``tests/`` for pytest discovery."""
    if ".." in path:
        return path
    p = Path(path)
    if p.suffix == ".py" and p.name.startswith("test_") and len(p.parts) == 1:
        return str(Path("tests") / p.name)
    return path


def _write_file_impl(path: str, content: str) -> bool:
    """
    Write file with directory whitelist and dangerous-pattern scanning.

    Args:
        path: Path relative to workspace/output or absolute under allowed roots.
        content: Content to write.

    Returns:
        True if write succeeded.

    Raises:
        ValueError: If path invalid or content contains dangerous patterns.
    """
    dangerous = _scan_dangerous_patterns(content)
    if dangerous:
        raise ValueError(f"Content contains dangerous pattern: {dangerous}")
    _scan_pii_warn(content)
    path = normalize_pytest_path(path)
    resolved = _resolve_and_validate_path(path, allow_new_file=True)
    # Prevent accidental creation of pytest-collected scratch files at workspace root.
    # Root-level files named "test_*.py" will be collected by pytest and can break runs.
    ws_root = Path(get_workspace_dir()).resolve()
    try:
        rel = resolved.relative_to(ws_root)
    except ValueError:
        rel = None
    if (
        rel is not None
        and resolved.suffix == ".py"
        and resolved.name.startswith("test_")
        and len(rel.parts) == 1
    ):
        raise ValueError(
            "Refusing to write root-level pytest file. Put tests under tests/ (e.g. tests/test_*.py)."
        )
    if resolved.exists() and resolved.is_dir():
        _audit_log("write_file", str(resolved), False, "path is a directory")
        raise ValueError(f"Path is a directory: {resolved}")
    _check_nesting_limit(resolved.parent)
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
    except Exception as e:
        _audit_log("write_file", str(resolved), False, str(e))
        raise
    _audit_log("write_file", str(resolved), True)
    return True


def _list_directory_impl(path: str) -> list[str]:
    """
    List directory contents with restricted scope (under workspace/output only).

    Args:
        path: Directory path relative to workspace or absolute under allowed roots.

    Returns:
        List of entry names (files and directories) in the directory.

    Raises:
        ValueError: If path invalid or not a directory.
    """
    resolved = _resolve_and_validate_path(path, must_exist=True)
    if not resolved.is_dir():
        _audit_log("list_directory", str(resolved), False, "not a directory")
        raise ValueError(f"Not a directory: {resolved}")
    try:
        names = sorted(p.name for p in resolved.iterdir())
    except Exception as e:
        _audit_log("list_directory", str(resolved), False, str(e))
        raise
    _audit_log("list_directory", str(resolved), True)
    return names


def _create_directory_impl(path: str) -> bool:
    """
    Create directory with nesting limits.

    Args:
        path: Directory path relative to workspace/output or absolute under allowed roots.

    Returns:
        True if directory was created or already exists.

    Raises:
        ValueError: If path invalid or nesting limit exceeded.
    """
    resolved = _resolve_and_validate_path(path, allow_new_dir=True)
    if resolved.exists():
        if resolved.is_dir():
            _audit_log("create_directory", str(resolved), True, "already exists")
            return True
        _audit_log("create_directory", str(resolved), False, "path is a file")
        raise ValueError(f"Path exists and is a file: {resolved}")
    _check_nesting_limit(resolved)
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _audit_log("create_directory", str(resolved), False, str(e))
        raise
    _audit_log("create_directory", str(resolved), True)
    return True


def _delete_file_impl(path: str, confirm: bool = False) -> bool:
    """
    Delete a file with confirmation and audit log.

    Args:
        path: File path relative to workspace/output or absolute under allowed roots.
        confirm: Must be True to perform delete (safety check for agent use).

    Returns:
        True if file was deleted.

    Raises:
        ValueError: If path invalid, not a file, or confirm is False.
    """
    if not confirm:
        raise ValueError("delete_file requires confirm=True to perform deletion")
    resolved = _resolve_and_validate_path(path, must_exist=True)
    if not resolved.is_file():
        _audit_log("delete_file", str(resolved), False, "not a file")
        raise ValueError(f"Not a file (cannot delete directory): {resolved}")
    try:
        resolved.unlink()
    except Exception as e:
        _audit_log("delete_file", str(resolved), False, str(e))
        raise
    _audit_log("delete_file", str(resolved), True)
    return True


def _invoke(tool: str, args: dict[str, object]) -> object:
    from ai_team.tools.bus import get_bus
    from ai_team.tools.kinds import ToolRequest

    return get_bus().invoke(ToolRequest(tool=tool, args=args))


def read_file(path: str) -> str:
    """Read a file via the ToolBus. Returns full content (not truncated summary)."""
    from ai_team.tools.kinds import ToolObservation

    obs = _invoke("read_file", {"path": path})
    assert isinstance(obs, ToolObservation)
    if not obs.ok:
        raise ValueError(obs.summary)
    content = obs.detail.get("content")
    return str(content) if content is not None else obs.summary


def write_file(path: str, content: str) -> bool:
    """Write a file via the ToolBus (draft-then-commit unless disabled)."""
    from ai_team.tools.kinds import ToolObservation

    obs = _invoke("write_file", {"path": path, "content": content})
    assert isinstance(obs, ToolObservation)
    if not obs.ok:
        raise ValueError(obs.summary)
    return True


def list_directory(path: str) -> list[str]:
    """List a directory via the ToolBus."""
    from ai_team.tools.kinds import ToolObservation

    obs = _invoke("list_directory", {"path": path})
    assert isinstance(obs, ToolObservation)
    if not obs.ok:
        raise ValueError(obs.summary)
    names = [line for line in obs.summary.split("\n") if line and line != "(empty)"]
    return names


def create_directory(path: str) -> bool:
    """Create a directory via the ToolBus."""
    from ai_team.tools.kinds import ToolObservation

    obs = _invoke("create_directory", {"path": path})
    assert isinstance(obs, ToolObservation)
    if not obs.ok:
        raise ValueError(obs.summary)
    return True


def delete_file(path: str, confirm: bool = False) -> bool:
    """Delete a file via the ToolBus. Irreversible: gated without policy."""
    from ai_team.tools.kinds import ToolObservation

    obs = _invoke("delete_file", {"path": path, "confirm": confirm})
    assert isinstance(obs, ToolObservation)
    if not obs.ok:
        raise ValueError(obs.summary)
    return True


# -----------------------------------------------------------------------------
# CrewAI @tool-decorated versions (for agent use)
# -----------------------------------------------------------------------------


try:
    from crewai.tools import tool

    @tool("Read file contents")
    def read_file_tool(path: str) -> str:
        """Read a file and return its contents. Use a path relative to the workspace or output directory. Path traversal (e.g. ..) is not allowed."""
        from ai_team.tools.bus import observation_to_agent_text
        from ai_team.tools.kinds import ToolObservation

        obs = _invoke("read_file", {"path": path})
        assert isinstance(obs, ToolObservation)
        return observation_to_agent_text(obs)

    @tool("Write content to file")
    def write_file_tool(path: str, content: str) -> str:
        """Write content to a file. Path must be under workspace or output directory. Content is scanned for dangerous patterns (eval, exec, subprocess, etc.). Returns 'OK' on success."""
        from ai_team.tools.bus import observation_to_agent_text
        from ai_team.tools.kinds import ToolObservation

        obs = _invoke("write_file", {"path": path, "content": content})
        assert isinstance(obs, ToolObservation)
        return observation_to_agent_text(obs)

    @tool("List directory contents")
    def list_directory_tool(path: str) -> str:
        """List files and directories in the given path. Path must be under workspace or output. Returns a newline-separated list of entry names."""
        from ai_team.tools.bus import observation_to_agent_text
        from ai_team.tools.kinds import ToolObservation

        obs = _invoke("list_directory", {"path": path})
        assert isinstance(obs, ToolObservation)
        return observation_to_agent_text(obs)

    @tool("Create directory")
    def create_directory_tool(path: str) -> str:
        """Create a directory (and parent directories if needed). Path must be under workspace or output. Nesting depth is limited."""
        from ai_team.tools.bus import observation_to_agent_text
        from ai_team.tools.kinds import ToolObservation

        obs = _invoke("create_directory", {"path": path})
        assert isinstance(obs, ToolObservation)
        return observation_to_agent_text(obs)

    @tool("Delete file")
    def delete_file_tool(path: str, confirm: bool = True) -> str:
        """Delete a file. Only files can be deleted (not directories). Irreversible: gated unless policy allows. Path must be under workspace or output."""
        from ai_team.tools.bus import observation_to_agent_text
        from ai_team.tools.kinds import ToolObservation

        obs = _invoke("delete_file", {"path": path, "confirm": confirm})
        assert isinstance(obs, ToolObservation)
        return observation_to_agent_text(obs)

    def get_file_tools():
        """Return list of CrewAI file tools for use with agents."""
        return [
            read_file_tool,
            write_file_tool,
            list_directory_tool,
            create_directory_tool,
            delete_file_tool,
        ]

except ImportError:
    # CrewAI not installed (e.g. in minimal test env)
    read_file_tool = None
    write_file_tool = None
    list_directory_tool = None
    create_directory_tool = None
    delete_file_tool = None

    def get_file_tools():
        return []
