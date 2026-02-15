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
from typing import List, Optional

import structlog

from ai_team.config.settings import get_settings

logger = structlog.get_logger(__name__)

# Default max directory nesting under allowed roots
MAX_DIRECTORY_DEPTH = 20


def _get_allowed_roots() -> List[Path]:
    """Return resolved absolute paths for workspace and output directories."""
    settings = get_settings()
    return [
        Path(settings.project.workspace_dir).resolve(),
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
    settings = get_settings()
    if Path(path).is_absolute():
        p = Path(path)
    else:
        base = Path(settings.project.workspace_dir).resolve()
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
        raise ValueError(
            f"Path not under allowed directories (workspace/output): {path_str}"
        )

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


def _audit_log(operation: str, path: str, success: bool, detail: Optional[str] = None) -> None:
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


def _scan_dangerous_patterns(content: str) -> Optional[str]:
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
        raise ValueError(
            f"File size {size_kb:.1f} KB exceeds limit {max_kb} KB: {path}"
        )


# -----------------------------------------------------------------------------
# Raw functions (for testing and direct use)
# -----------------------------------------------------------------------------


def read_file(path: str) -> str:
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


def write_file(path: str, content: str) -> bool:
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
    resolved = _resolve_and_validate_path(
        path, allow_new_file=True
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


def list_directory(path: str) -> List[str]:
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


def create_directory(path: str) -> bool:
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


def delete_file(path: str, confirm: bool = False) -> bool:
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


# -----------------------------------------------------------------------------
# CrewAI @tool-decorated versions (for agent use)
# -----------------------------------------------------------------------------

try:
    from crewai.tools import tool

    @tool("Read file contents")
    def read_file_tool(path: str) -> str:
        """Read a file and return its contents. Use a path relative to the workspace or output directory. Path traversal (e.g. ..) is not allowed."""
        return read_file(path)

    @tool("Write content to file")
    def write_file_tool(path: str, content: str) -> str:
        """Write content to a file. Path must be under workspace or output directory. Content is scanned for dangerous patterns (eval, exec, subprocess, etc.). Returns 'OK' on success."""
        write_file(path, content)
        return "OK"

    @tool("List directory contents")
    def list_directory_tool(path: str) -> str:
        """List files and directories in the given path. Path must be under workspace or output. Returns a newline-separated list of entry names."""
        names = list_directory(path)
        return "\n".join(names) if names else "(empty)"

    @tool("Create directory")
    def create_directory_tool(path: str) -> str:
        """Create a directory (and parent directories if needed). Path must be under workspace or output. Nesting depth is limited."""
        create_directory(path)
        return "OK"

    @tool("Delete file")
    def delete_file_tool(path: str, confirm: bool = True) -> str:
        """Delete a file. Only files can be deleted (not directories). Set confirm=True to perform the deletion. Path must be under workspace or output."""
        delete_file(path, confirm=confirm)
        return "OK"

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
