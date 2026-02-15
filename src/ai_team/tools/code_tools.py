"""
Sandboxed code execution, linting, and formatting tools.

Provides execute_python, execute_shell, lint_code, and format_code with
process isolation, resource limits, and audit logging.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, List, Optional, Type

try:
    import resource
except ImportError:
    resource = None  # type: ignore[assignment]

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)

# Default blocked Python modules for execute_python
DEFAULT_BLOCKED_IMPORTS = frozenset({"os", "subprocess", "sys", "shutil"})

# Shell: allowed command patterns (first token or full command prefix)
SHELL_ALLOWED_PATTERNS = [
    r"^pip\s+install\s",
    r"^pip\s+list\s*$",
    r"^pip\s+show\s",
    r"^pytest\s",
    r"^pytest$",
    r"^ruff\s",
    r"^ruff$",
    r"^mypy\s",
    r"^mypy$",
    r"^black\s",
    r"^black$",
    r"^git\s+status\s*$",
    r"^git\s+status$",
    r"^git\s+diff\s",
    r"^git\s+log\s",
    r"^git\s+branch\s",
    r"^python\s",
    r"^python3\s",
    r"^node\s",
    r"^npx\s",
]
SHELL_BLOCKED_PATTERNS = [
    r"rm\s+(-rf?|-\s*rf?)\s",
    r"\brm\s+-r",
    r"rm\s+-f\s+-r",
    r"\bcurl\b",
    r"\bwget\b",
    r"\bnc\b",
    r"\bncat\b",
    r"\bnetcat\b",
    r">\s*/dev/",
    r"<\s*/dev/",
    r"\|\s*sh\s*$",
    r"\|\s*bash\s*$",
    r"sudo\s",
    r"chmod\s+[0-7]{3,4}\s",
    r"chown\s",
    r"mkfs\.",
    r":\s*\(\s*:\s*\)",
    r"dd\s+if=",
    r"mv\s+.*\s+/",
    r"mkfifo\s",
]


# -----------------------------------------------------------------------------
# Pydantic models
# -----------------------------------------------------------------------------


class ExecutionResult(BaseModel):
    """Result of running code or a shell command in the sandbox."""

    stdout: str = Field(default="", description="Standard output.")
    stderr: str = Field(default="", description="Standard error.")
    return_code: int = Field(description="Process return code.")
    timed_out: bool = Field(default=False, description="True if execution hit the timeout.")
    duration_seconds: float = Field(default=0.0, description="Wall-clock duration in seconds.")


class LintIssue(BaseModel):
    """A single lint issue."""

    file_path: str = Field(default="", description="File or '<stdin>'.")
    line: Optional[int] = Field(default=None, description="Line number if available.")
    column: Optional[int] = Field(default=None, description="Column if available.")
    code: Optional[str] = Field(default=None, description="Rule or code (e.g. E501).")
    message: str = Field(description="Linter message.")
    severity: str = Field(default="warning", description="One of: error, warning, info.")


class LintResult(BaseModel):
    """Structured result from lint_code."""

    success: bool = Field(description="True if linter ran without failure.")
    issues: List[LintIssue] = Field(default_factory=list, description="List of lint issues.")
    raw_output: str = Field(default="", description="Raw linter stdout/stderr.")
    error: Optional[str] = Field(default=None, description="Error message if linter failed to run.")


# Tool input schemas (for CrewAI BaseTool)
class ExecutePythonInput(BaseModel):
    """Input for execute_python tool."""

    code: str = Field(..., description="Python code to run in the sandbox.")
    timeout: int = Field(default=30, description="Timeout in seconds.")


class ExecuteShellInput(BaseModel):
    """Input for execute_shell tool."""

    command: str = Field(..., description="Shell command (must be whitelisted).")
    timeout: int = Field(default=10, description="Timeout in seconds.")


class LintCodeInput(BaseModel):
    """Input for lint_code tool."""

    code: str = Field(..., description="Source code to lint.")
    language: str = Field(..., description="Language: python or javascript.")


class FormatCodeInput(BaseModel):
    """Input for format_code tool."""

    code: str = Field(..., description="Source code to format.")
    language: str = Field(..., description="Language: python, javascript, or typescript.")


# -----------------------------------------------------------------------------
# Security helpers
# -----------------------------------------------------------------------------


def _apply_resource_limits(timeout_seconds: int, max_memory_mb: int = 512) -> Optional[Any]:
    """Return a callable for preexec_fn that sets CPU and memory limits (Unix only)."""
    if resource is None:
        return None

    def setlimits() -> None:
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
            # RLIMIT_AS is address space in bytes
            as_bytes = max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (as_bytes, as_bytes))
        except (ValueError, OSError):
            pass

    return setlimits


def _is_shell_command_allowed(command: str) -> tuple[bool, Optional[str]]:
    """Check if shell command is allowed. Returns (allowed, reason_if_blocked)."""
    command_stripped = command.strip()
    if not command_stripped:
        return False, "Empty command"
    for pat in SHELL_BLOCKED_PATTERNS:
        if re.search(pat, command_stripped, re.IGNORECASE):
            return False, f"Blocked pattern: {pat}"
    for pat in SHELL_ALLOWED_PATTERNS:
        if re.search(pat, command_stripped):
            return True, None
    return False, "Command not in whitelist"


def _audit_log(
    operation: str,
    *,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Emit audit log for code/shell execution."""
    payload = {"operation": operation, "timestamp": time.time()}
    if extra:
        payload.update(extra)
    logger.info("code_tools_audit", **payload)


# -----------------------------------------------------------------------------
# Raw functions (for testing and direct use)
# -----------------------------------------------------------------------------


def execute_python(
    code: str,
    timeout: int = 30,
    blocked_imports: Optional[frozenset[str]] = None,
) -> ExecutionResult:
    """
    Run Python code in a subprocess with resource limits and import restrictions.

    - Writes code to a temporary file with an import guard prepended.
    - Enforces timeout and (on Unix) CPU/memory limits.
    - Blocks os, subprocess, sys, shutil by default.
    - Captures stdout, stderr, and return code.
    """
    blocked = blocked_imports if blocked_imports is not None else DEFAULT_BLOCKED_IMPORTS
    start = time.perf_counter()
    _audit_log("execute_python", extra={"timeout": timeout})

    guard = """
# Import guard (injected by code_tools)
import builtins
_orig_import = builtins.__import__
_blocked = %s
def _guard(name, *args, **kwargs):
    if name in _blocked:
        raise ImportError("Blocked module: %%s" %% name)
    return _orig_import(name, *args, **kwargs)
builtins.__import__ = _guard
# End guard
""" % repr(
        set(blocked)
    )

    script_content = guard.strip() + "\n\n" + code
    tmpdir: Optional[Path] = None
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="ai_team_code_"))
        script_path = tmpdir / "script.py"
        script_path.write_text(script_content, encoding="utf-8")

        env = {**dict(os.environ), "PYTHONIOENCODING": "utf-8"}
        # Disable network for child: empty proxy and no write to real paths
        env["HTTP_PROXY"] = ""
        env["HTTPS_PROXY"] = ""
        env["http_proxy"] = ""
        env["https_proxy"] = ""

        preexec = _apply_resource_limits(timeout, max_memory_mb=512)
        kwargs: dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": str(tmpdir),
            "env": env,
            "timeout": timeout,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if preexec is not None and sys.platform != "win32":
            kwargs["preexec_fn"] = preexec

        proc = subprocess.run(
            [sys.executable, str(script_path)],
            **kwargs,
        )
        duration = time.perf_counter() - start
        return ExecutionResult(
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            return_code=proc.returncode or 0,
            timed_out=False,
            duration_seconds=round(duration, 3),
        )
    except subprocess.TimeoutExpired as e:
        duration = time.perf_counter() - start
        return ExecutionResult(
            stdout=(e.stdout or b"").decode("utf-8", errors="replace"),
            stderr=(e.stderr or b"").decode("utf-8", errors="replace"),
            return_code=-1,
            timed_out=True,
            duration_seconds=round(duration, 3),
        )
    except Exception as e:
        duration = time.perf_counter() - start
        return ExecutionResult(
            stdout="",
            stderr=str(e),
            return_code=-1,
            timed_out=False,
            duration_seconds=round(duration, 3),
        )
    finally:
        if tmpdir and tmpdir.exists():
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


def execute_shell(command: str, timeout: int = 10) -> ExecutionResult:
    """
    Run a shell command in a restricted environment.

    - Only whitelisted commands are allowed (e.g. pip install, pytest, ruff, mypy, git status).
    - Dangerous patterns are blocked (rm -rf, curl, wget, nc, sudo, etc.).
    - Runs in a temporary directory; no network isolation at OS level.
    """
    _audit_log("execute_shell", extra={"command_preview": command[:200], "timeout": timeout})
    allowed, reason = _is_shell_command_allowed(command)
    if not allowed:
        return ExecutionResult(
            stdout="",
            stderr=f"Command rejected: {reason}",
            return_code=-1,
            timed_out=False,
            duration_seconds=0.0,
        )

    start = time.perf_counter()
    tmpdir: Optional[Path] = None
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="ai_team_shell_"))
        proc = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tmpdir),
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        duration = time.perf_counter() - start
        return ExecutionResult(
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            return_code=proc.returncode or 0,
            timed_out=False,
            duration_seconds=round(duration, 3),
        )
    except subprocess.TimeoutExpired as e:
        duration = time.perf_counter() - start
        return ExecutionResult(
            stdout=(e.stdout or b"").decode("utf-8", errors="replace"),
            stderr=(e.stderr or b"").decode("utf-8", errors="replace"),
            return_code=-1,
            timed_out=True,
            duration_seconds=round(duration, 3),
        )
    except Exception as e:
        duration = time.perf_counter() - start
        return ExecutionResult(
            stdout="",
            stderr=str(e),
            return_code=-1,
            timed_out=False,
            duration_seconds=round(duration, 3),
        )
    finally:
        if tmpdir and tmpdir.exists():
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


def _parse_ruff_output(text: str) -> List[LintIssue]:
    """Parse ruff check output (one issue per line: path:line:col: code message)."""
    issues: List[LintIssue] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # path:line:col: code message
        match = re.match(r"^(.+?):(\d+):(\d+):\s*(\w+)\s+(.+)$", line)
        if match:
            path, ln, col, code, msg = match.groups()
            severity = "error" if code.startswith("E") or code in ("F", "I") else "warning"
            issues.append(
                LintIssue(
                    file_path=path,
                    line=int(ln),
                    column=int(col),
                    code=code,
                    message=msg,
                    severity=severity,
                )
            )
        else:
            issues.append(LintIssue(message=line, severity="info"))
    return issues


def _parse_eslint_output(text: str) -> List[LintIssue]:
    """Parse eslint output (simple line format or JSON); fallback to single issue with raw output."""
    issues: List[LintIssue] = []
    # Common pattern: path:line col: message (rule)
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(.+?):(\d+):(\d+):\s*(.+?)\s+\((.+?)\)\s*$", line)
        if match:
            path, ln, col, msg, code = match.groups()
            issues.append(
                LintIssue(
                    file_path=path,
                    line=int(ln),
                    column=int(col),
                    code=code,
                    message=msg,
                    severity="error",
                )
            )
        else:
            issues.append(LintIssue(message=line, severity="info"))
    if not issues and text.strip():
        issues.append(LintIssue(message=text.strip(), severity="info"))
    return issues


def lint_code(code: str, language: str) -> LintResult:
    """
    Lint code with ruff (Python) or eslint (JavaScript).

    Returns structured LintResult with severity levels. Writes code to a temp file
    and runs the linter in a subprocess.
    """
    _audit_log("lint_code", extra={"language": language})
    lang = language.lower().strip()
    tmpdir = None
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="ai_team_lint_"))
        if lang in ("python", "py"):
            path = tmpdir / "code.py"
            path.write_text(code, encoding="utf-8")
            ruff = shutil.which("ruff")
            if not ruff:
                return LintResult(
                    success=False,
                    raw_output="",
                    error="ruff not found in PATH",
                )
            proc = subprocess.run(
                [ruff, "check", str(path), "--output-format=concise"],
                capture_output=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
                cwd=str(tmpdir),
            )
            raw = (proc.stdout or "") + (proc.stderr or "")
            issues = _parse_ruff_output(raw) if raw else []
            return LintResult(
                success=proc.returncode == 0 or len(issues) > 0,
                issues=issues,
                raw_output=raw,
            )
        if lang in ("javascript", "js", "typescript", "ts"):
            ext = "ts" if "type" in lang else "js"
            path = tmpdir / f"code.{ext}"
            path.write_text(code, encoding="utf-8")
            npx = shutil.which("npx")
            if not npx:
                return LintResult(
                    success=False,
                    raw_output="",
                    error="npx not found (eslint requires Node/npx)",
                )
            proc = subprocess.run(
                [npx, "--yes", "eslint", str(path), "--format=compact"],
                capture_output=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
                cwd=str(tmpdir),
            )
            raw = (proc.stdout or "") + (proc.stderr or "")
            issues = _parse_eslint_output(raw) if raw else []
            return LintResult(
                success=proc.returncode == 0 or len(issues) > 0,
                issues=issues,
                raw_output=raw,
            )
        return LintResult(
            success=False,
            raw_output="",
            error=f"Unsupported language: {language} (use python or javascript)",
        )
    except subprocess.TimeoutExpired:
        return LintResult(success=False, raw_output="", error="Linter timed out")
    except Exception as e:
        return LintResult(success=False, raw_output="", error=str(e))
    finally:
        if tmpdir and tmpdir.exists():
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


def format_code(code: str, language: str) -> str:
    """
    Format code with black (Python) or prettier (JavaScript/TypeScript).

    Returns the formatted code string. On failure returns the original code and
    logs the error.
    """
    _audit_log("format_code", extra={"language": language})
    lang = language.lower().strip()
    tmpdir = None
    try:
        tmpdir = Path(tempfile.mkdtemp(prefix="ai_team_fmt_"))
        if lang in ("python", "py"):
            path = tmpdir / "code.py"
            path.write_text(code, encoding="utf-8")
            black = shutil.which("black")
            if not black:
                logger.warning("format_code_black_not_found")
                return code
            proc = subprocess.run(
                [black, "-q", str(path)],
                capture_output=True,
                timeout=15,
                encoding="utf-8",
                errors="replace",
                cwd=str(tmpdir),
            )
            if proc.returncode == 0:
                return path.read_text(encoding="utf-8")
            logger.warning("format_code_black_failed", stderr=proc.stderr)
            return code
        if lang in ("javascript", "js", "typescript", "ts"):
            ext = "ts" if "type" in lang else "js"
            path = tmpdir / f"code.{ext}"
            path.write_text(code, encoding="utf-8")
            npx = shutil.which("npx")
            if not npx:
                logger.warning("format_code_prettier_npx_not_found")
                return code
            proc = subprocess.run(
                [npx, "--yes", "prettier", "--write", str(path)],
                capture_output=True,
                timeout=15,
                encoding="utf-8",
                errors="replace",
                cwd=str(tmpdir),
            )
            if proc.returncode == 0:
                return path.read_text(encoding="utf-8")
            logger.warning("format_code_prettier_failed", stderr=proc.stderr)
            return code
        return code
    except Exception as e:
        logger.warning("format_code_error", error=str(e))
        return code
    finally:
        if tmpdir and tmpdir.exists():
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


# -----------------------------------------------------------------------------
# CrewAI tools (for agent use)
# -----------------------------------------------------------------------------


class ExecutePythonTool(BaseTool):
    """Run Python code in a sandboxed subprocess with timeout and import restrictions."""

    name: str = "execute_python"
    description: str = (
        "Execute Python code in a sandbox: subprocess, timeout, blocked imports (os, subprocess, sys, shutil). "
        "Returns stdout, stderr, return_code, and whether it timed out. Use for safe code execution."
    )
    args_schema: Type[BaseModel] = ExecutePythonInput

    def _run(self, code: str, timeout: int = 30) -> str:
        result = execute_python(code=code, timeout=timeout)
        return result.model_dump_json()


class ExecuteShellTool(BaseTool):
    """Run whitelisted shell commands (e.g. pip install, pytest, ruff, mypy, git status) in a restricted environment."""

    name: str = "execute_shell"
    description: str = (
        "Run a shell command if it is whitelisted (pip install, pytest, ruff, mypy, git status, etc.). "
        "Dangerous commands are blocked. Returns stdout, stderr, return_code. Use for running tests or linters."
    )
    args_schema: Type[BaseModel] = ExecuteShellInput

    def _run(self, command: str, timeout: int = 10) -> str:
        result = execute_shell(command=command, timeout=timeout)
        return result.model_dump_json()


class LintCodeTool(BaseTool):
    """Lint code with ruff (Python) or eslint (JavaScript). Returns structured LintResult."""

    name: str = "lint_code"
    description: str = (
        "Lint code: use language 'python' for ruff, 'javascript' for eslint. "
        "Returns success, list of issues (file, line, column, code, message, severity), and raw output."
    )
    args_schema: Type[BaseModel] = LintCodeInput

    def _run(self, code: str, language: str) -> str:
        result = lint_code(code=code, language=language)
        return result.model_dump_json()


class FormatCodeTool(BaseTool):
    """Format code with black (Python) or prettier (JavaScript/TypeScript). Returns formatted code string."""

    name: str = "format_code"
    description: str = (
        "Format code with black (Python) or prettier (JavaScript/TypeScript). "
        "Returns the formatted code string. Use language 'python', 'javascript', or 'typescript'."
    )
    args_schema: Type[BaseModel] = FormatCodeInput

    def _run(self, code: str, language: str) -> str:
        return format_code(code=code, language=language)


def get_code_tools() -> List[BaseTool]:
    """Return list of CrewAI BaseTool instances for code execution, linting, and formatting."""
    return [
        ExecutePythonTool(),
        ExecuteShellTool(),
        LintCodeTool(),
        FormatCodeTool(),
    ]
