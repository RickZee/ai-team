"""
Security guardrails for code safety, PII, secrets, prompt injection, and path validation.

All functions return GuardrailResult for consistent handling and integrate with
CrewAI task guardrails via adapter functions.
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from ai_team.config.settings import get_settings


# =============================================================================
# GUARDRAIL RESULT
# =============================================================================


class GuardrailResult(BaseModel):
    """Result of a guardrail check. Used across behavioral, security, and quality guardrails."""

    status: Literal["pass", "fail", "warn"] = Field(
        description="pass=allowed, fail=block, warn=log but allow"
    )
    message: str = Field(default="", description="Human-readable outcome message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Extra data (e.g. redacted text, matched patterns, severity)",
    )
    retry_allowed: bool = Field(
        default=True,
        description="Whether the agent/task may retry after this result",
    )

    def is_ok(self) -> bool:
        """True if output is allowed (pass or warn)."""
        return self.status in ("pass", "warn")

    def should_block(self) -> bool:
        """True if output should be blocked."""
        return self.status == "fail"


# =============================================================================
# CODE SAFETY
# =============================================================================

# Severity: critical → block, warning → log, info → log only
_SEVERITY_CRITICAL = "critical"
_SEVERITY_WARNING = "warning"
_SEVERITY_INFO = "info"

# Built-in dangerous patterns: (regex, description, severity)
_DEFAULT_DANGEROUS_PATTERNS: List[Tuple[str, str, str]] = [
    (r"\beval\s*\(", "eval()", _SEVERITY_CRITICAL),
    (r"\bexec\s*\(", "exec()", _SEVERITY_CRITICAL),
    (r"os\.system\s*\(", "os.system()", _SEVERITY_CRITICAL),
    (r"subprocess\.(run|call|Popen|check_output)\s*\([^)]*shell\s*=\s*True", "subprocess with shell=True", _SEVERITY_CRITICAL),
    (r"subprocess\.(run|call|Popen|check_output)\s*\([^)]*\)", "subprocess call", _SEVERITY_WARNING),  # may be ok if shell=False
    (r"__import__\s*\(", "__import__()", _SEVERITY_CRITICAL),
    (r"\bcompile\s*\(", "compile()", _SEVERITY_CRITICAL),
    (r"\bglobals\s*\(", "globals()", _SEVERITY_WARNING),
    (r"pickle\.loads\s*\(", "pickle.loads()", _SEVERITY_CRITICAL),
    (r"yaml\.load\s*\([^)]*\)(?!\s*Loader\s*=)", "yaml.load() without Loader", _SEVERITY_CRITICAL),
    (r"open\s*\([^)]*[\'\"]/etc/", "system file access", _SEVERITY_CRITICAL),
    (r"chmod\s+[0-7]*7[0-7]*", "world-writable chmod", _SEVERITY_WARNING),
    (r"rm\s+-rf\s+/", "root filesystem deletion", _SEVERITY_CRITICAL),
    (r"DROP\s+(TABLE|DATABASE|INDEX)", "SQL DROP", _SEVERITY_CRITICAL),
    (r"TRUNCATE\s+TABLE", "SQL TRUNCATE", _SEVERITY_WARNING),
    (r"<\s*script[^>]*>", "XSS script tag", _SEVERITY_CRITICAL),
]


def code_safety_guardrail(code: str) -> GuardrailResult:
    """
    Detect dangerous patterns in code. Uses configurable pattern list from settings
    plus built-in patterns. Severity: critical → block, warning → log, info → log.
    """
    settings = get_settings()
    critical_matches: List[str] = []
    warning_matches: List[str] = []
    info_matches: List[str] = []

    # Configurable patterns from settings (treated as critical if not regex)
    for pattern in settings.guardrails.dangerous_patterns:
        try:
            if re.search(pattern, code, re.IGNORECASE):
                critical_matches.append(pattern)
        except re.error:
            if pattern in code:
                critical_matches.append(pattern)

    # Built-in patterns with severity
    for regex, desc, severity in _DEFAULT_DANGEROUS_PATTERNS:
        if re.search(regex, code, re.IGNORECASE):
            if severity == _SEVERITY_CRITICAL:
                critical_matches.append(desc)
            elif severity == _SEVERITY_WARNING:
                warning_matches.append(desc)
            else:
                info_matches.append(desc)

    if critical_matches:
        return GuardrailResult(
            status="fail",
            message=f"Code safety violation (critical): {', '.join(set(critical_matches))}",
            details={"critical": list(set(critical_matches)), "warning": warning_matches, "info": info_matches},
            retry_allowed=True,
        )
    if warning_matches or info_matches:
        return GuardrailResult(
            status="warn",
            message=f"Code safety warnings: {', '.join(set(warning_matches + info_matches))}",
            details={"warning": warning_matches, "info": info_matches},
            retry_allowed=True,
        )
    return GuardrailResult(status="pass", message="No dangerous patterns detected.", retry_allowed=True)


# =============================================================================
# PII REDACTION
# =============================================================================

_PII_PATTERNS: List[Tuple[str, str]] = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "EMAIL"),
    (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "PHONE"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "CREDIT_CARD"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP_ADDRESS"),
    (r"(?i)(api[_-]?key|apikey)\s*[:=]\s*[\'\"]?\S+[\'\"]?", "API_KEY"),
    (r"(?i)(password|passwd|pwd)\s*[:=]\s*[\'\"]?\S+[\'\"]?", "PASSWORD"),
]


def pii_redaction_guardrail(text: str) -> GuardrailResult:
    """
    Detect and redact PII: email, phone, SSN, credit card, IP, API keys, plaintext passwords.
    Returns both detection result and redacted version in details["redacted"].
    """
    settings = get_settings()
    patterns_to_use: List[Tuple[str, str]] = list(_PII_PATTERNS)
    for p in settings.guardrails.pii_patterns:
        try:
            re.compile(p)
            patterns_to_use.append((p, "PII"))
        except re.error:
            pass

    redacted = text
    detected: List[str] = []
    for pattern, label in patterns_to_use:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            detected.append(f"{label}:{len(matches)}")
            redacted = re.sub(pattern, f"[REDACTED_{label}]", redacted, flags=re.IGNORECASE)

    details: Dict[str, Any] = {"redacted": redacted, "detected": detected}
    if detected:
        return GuardrailResult(
            status="warn",
            message=f"PII detected and redacted: {', '.join(detected)}",
            details=details,
            retry_allowed=True,
        )
    return GuardrailResult(
        status="pass",
        message="No PII detected.",
        details=details,
        retry_allowed=True,
    )


# =============================================================================
# SECRET DETECTION
# =============================================================================

_SECRET_PATTERNS: List[Tuple[str, str]] = [
    (r"(?i)(api[_-]?key|apikey)\s*[:=]\s*[\'\"]\S+[\'\"]", "API_KEY"),
    (r"(?i)(password|passwd|pwd)\s*[:=]\s*[\'\"]\S+[\'\"]", "PASSWORD"),
    (r"(?i)(secret|token|auth)\s*[:=]\s*[\'\"]\S+[\'\"]", "SECRET_TOKEN"),
    (r"(?i)aws_access_key_id\s*[:=]\s*[\'\"]?\w{20}[\'\"]?", "AWS_ACCESS_KEY"),
    (r"(?i)aws_secret_access_key\s*[:=]\s*[\'\"]?\S+[\'\"]?", "AWS_SECRET_KEY"),
    (r"Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", "JWT_TOKEN"),
    (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "PRIVATE_KEY"),
    (r"ghp_[A-Za-z0-9]{36}", "GITHUB_TOKEN"),
    (r"gho_[A-Za-z0-9]{36}", "GITHUB_OAuth"),
    (r"sk-[A-Za-z0-9]{48}", "OPENAI_KEY"),
    (r"sk-[A-Za-z0-9]{24,}", "OPENAI_LIKE_KEY"),
    (r"(?i)(mongodb|postgres|mysql|redis)://[^\s\'\"<>]+", "CONNECTION_STRING"),
    (r"(?i)\.env\s*[\r\n]+[A-Z_][A-Z0-9_]*\s*=\s*[\'\"]?\S+[\'\"]?", "ENV_VALUE_IN_CODE"),
]


def secret_detection_guardrail(content: str) -> GuardrailResult:
    """
    Detect hardcoded secrets: API keys, tokens, passwords, connection strings.
    Flags .env-style values that should not appear in code.
    """
    found: List[str] = []
    for pattern, label in _SECRET_PATTERNS:
        if re.search(pattern, content):
            found.append(label)

    if found:
        return GuardrailResult(
            status="fail",
            message=f"Hardcoded secrets detected: {', '.join(set(found))}. Use environment variables.",
            details={"secret_types": list(set(found))},
            retry_allowed=True,
        )
    return GuardrailResult(status="pass", message="No secrets detected.", retry_allowed=True)


# =============================================================================
# PROMPT INJECTION
# =============================================================================

_INJECTION_PATTERNS_HIGH: List[str] = [
    r"ignore\s+(previous|all|above)\s+instructions",
    r"disregard\s+(your|the)\s+(rules|instructions)",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"pretend\s+(to\s+be|you\s+are)",
    r"forget\s+(everything|your\s+training)",
    r"jailbreak",
    r"DAN\s+mode",
    r"system\s*:\s*you\s+are",
    r"\[INST\]\s*ignore",
    r"<\|im_end\|>\s*<\|im_start\|>\s*system",
]
_INJECTION_PATTERNS_MEDIUM: List[str] = [
    r"override\s+your\s+instructions",
    r"new\s+instructions\s*:",
    r"disregard\s+above",
    r"ignore\s+all\s+above",
]
_INJECTION_PATTERNS_LOW: List[str] = [
    r"ignore\s+previous",
    r"new\s+role\s*:",
]


def prompt_injection_guardrail(
    input_text: str,
    sensitivity: Literal["low", "medium", "high"] = "medium",
) -> GuardrailResult:
    """
    Detect attempts to override agent instructions: ignore instructions, role-play,
    encoding tricks. Sensitivity: low (fewer patterns), medium, high (strict).
    """
    text_lower = input_text.lower().strip()
    # Simple encoding tricks: unicode homoglyphs or repeated spaces
    if re.search(r"i\s{5,}gnore", text_lower) or "ｉｇｎｏｒｅ" in input_text:
        return GuardrailResult(
            status="fail",
            message="Prompt injection detected (encoding trick).",
            details={"reason": "encoding_trick"},
            retry_allowed=False,
        )

    patterns = _INJECTION_PATTERNS_HIGH
    if sensitivity == "low":
        patterns = _INJECTION_PATTERNS_LOW
    elif sensitivity == "medium":
        patterns = _INJECTION_PATTERNS_HIGH + _INJECTION_PATTERNS_MEDIUM
    else:
        patterns = _INJECTION_PATTERNS_HIGH + _INJECTION_PATTERNS_MEDIUM + _INJECTION_PATTERNS_LOW

    for pattern in patterns:
        if re.search(pattern, input_text, re.IGNORECASE):
            return GuardrailResult(
                status="fail",
                message="Prompt injection detected.",
                details={"matched_pattern": pattern},
                retry_allowed=False,
            )
    return GuardrailResult(status="pass", message="No prompt injection detected.", retry_allowed=True)


# =============================================================================
# PATH SECURITY
# =============================================================================

# Paths that should never be allowed (absolute system dirs).
# Use normalized paths so /var/folders/... (macOS temp) is not blocked by /var.
_SYSTEM_PATH_PREFIXES = ("/etc", "/usr", "/bin", "/sbin", "/root", "/boot", "/sys", "/proc", "/dev")


def _is_system_path(resolved: str) -> bool:
    """True if path is under a system directory. Excludes /var/folders, /var/tmp, /tmp."""
    norm = os.path.normpath(resolved)
    for prefix in _SYSTEM_PATH_PREFIXES:
        if norm == prefix or norm.startswith(prefix + os.sep):
            return True
    if norm.startswith("/var" + os.sep) and "/var/folders" not in norm and "/var/tmp" not in norm:
        return True
    return False


def path_security_guardrail(
    file_path: str,
    allowed_dirs: Optional[List[str]] = None,
) -> GuardrailResult:
    """
    Validate file path is within allowed directories. Blocks path traversal,
    symlinks outside workspace, and absolute paths to system dirs.
    """
    settings = get_settings()
    if allowed_dirs is None:
        allowed_dirs = [
            os.path.abspath(settings.project.workspace_dir),
            os.path.abspath(settings.project.output_dir),
        ]

    path_str = file_path.strip()
    if "\x00" in path_str:
        return GuardrailResult(
            status="fail",
            message="Invalid path: embedded null character.",
            details={"path": path_str},
            retry_allowed=True,
        )
    if ".." in path_str or path_str.startswith(".."):
        return GuardrailResult(
            status="fail",
            message="Path traversal detected (..).",
            details={"path": path_str},
            retry_allowed=True,
        )

    try:
        resolved = os.path.normpath(os.path.abspath(path_str))
    except (ValueError, OSError) as e:
        return GuardrailResult(
            status="fail",
            message=f"Invalid path: {e!s}",
            details={"path": path_str},
            retry_allowed=True,
        )

    # Block absolute paths to system directories (exclude temp dirs under /var)
    if _is_system_path(resolved):
        return GuardrailResult(
            status="fail",
            message="Path not allowed: system directory.",
            details={"path": resolved},
            retry_allowed=True,
        )

    # Normalize with realpath so symlinked dirs (e.g. /var -> /private/var) match
    def _norm(p: str) -> str:
        try:
            return os.path.normpath(os.path.realpath(p))
        except (OSError, ValueError):
            return os.path.normpath(os.path.abspath(p))

    resolved_real = _norm(resolved)
    allowed_abs = [_norm(os.path.abspath(d)) for d in allowed_dirs]

    if not any(resolved_real == d or (resolved_real + os.sep).startswith(d + os.sep) for d in allowed_abs):
        return GuardrailResult(
            status="fail",
            message="Path outside allowed directories.",
            details={"path": resolved_real, "allowed": allowed_dirs},
            retry_allowed=True,
        )

    return GuardrailResult(
        status="pass",
        message="Path is within allowed directories.",
        details={"path": resolved_real},
        retry_allowed=True,
    )


# =============================================================================
# CREWAI TASK GUARDRAIL ADAPTERS
# =============================================================================

def _task_output_text(result: Any) -> str:
    """Extract raw text from CrewAI TaskOutput or similar."""
    if hasattr(result, "raw"):
        return getattr(result, "raw") or ""
    if isinstance(result, str):
        return result
    return str(result)


def crewai_code_safety_guardrail(result: Any) -> Tuple[bool, Any]:
    """CrewAI task guardrail: validate task output with code_safety_guardrail."""
    text = _task_output_text(result)
    r = code_safety_guardrail(text)
    if r.should_block():
        return (False, r.message)
    return (True, result)


def crewai_pii_guardrail(result: Any) -> Tuple[bool, Any]:
    """CrewAI task guardrail: redact PII in task output."""
    text = _task_output_text(result)
    r = pii_redaction_guardrail(text)
    redacted = (r.details or {}).get("redacted", text)
    if hasattr(result, "raw"):
        result.raw = redacted
        return (True, result)
    return (True, redacted)


def crewai_secret_detection_guardrail(result: Any) -> Tuple[bool, Any]:
    """CrewAI task guardrail: block output if secrets detected."""
    text = _task_output_text(result)
    r = secret_detection_guardrail(text)
    if r.should_block():
        return (False, r.message)
    return (True, result.raw if hasattr(result, "raw") else text)


def crewai_prompt_injection_guardrail(result: Any) -> Tuple[bool, Any]:
    """CrewAI task guardrail: validate input (use on user input task output)."""
    text = _task_output_text(result)
    r = prompt_injection_guardrail(text)
    if r.should_block():
        return (False, r.message)
    return (True, result.raw if hasattr(result, "raw") else text)


def crewai_path_security_guardrail(result: Any) -> Tuple[bool, Any]:
    """CrewAI task guardrail: validate that output is a path within allowed dirs."""
    text = _task_output_text(result).strip()
    r = path_security_guardrail(text)
    if r.should_block():
        return (False, r.message)
    return (True, result.raw if hasattr(result, "raw") else text)


# Convenience list for Task(guardrails=[...])
SECURITY_TASK_GUARDRAILS: List[Callable[[Any], Tuple[bool, Any]]] = [
    crewai_code_safety_guardrail,
    crewai_pii_guardrail,
    crewai_secret_detection_guardrail,
]
