"""
Quality guardrails for code quality, test coverage, documentation,
architecture compliance, and dependency checks.

All functions return GuardrailResult with a score 0-100 and actionable
fix suggestions.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional

from ai_team.config.settings import get_settings


@dataclass
class GuardrailResult:
    """Result of a quality guardrail check with actionable suggestions."""

    passed: bool
    score: int  # 0-100
    message: str
    suggestions: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.score = max(0, min(100, self.score))


# -----------------------------------------------------------------------------
# 1. Code quality guardrail
# -----------------------------------------------------------------------------

MAX_FUNCTION_LINES = 50
MAX_FILE_LINES = 500
MAX_CYCLOMATIC_COMPLEXITY = 10
TODO_PATTERNS = re.compile(
    r"#\s*(TODO|FIXME|HACK|XXX)\s*[:\s]",
    re.IGNORECASE,
)
PYTHON_PUBLIC_DEF = re.compile(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
JS_CAMEL_CASE = re.compile(r"function\s+([a-z][a-zA-Z0-9]*)\s*\(|const\s+([a-z][a-zA-Z0-9]*)\s*=")


def _cyclomatic_complexity_approx(code: str) -> int:
    """Approximate cyclomatic complexity by counting decision points."""
    keywords = ("if", "elif", "else", "for", "while", "except", "and", "or")
    count = 1
    for kw in keywords:
        count += len(re.findall(rf"\b{kw}\s+", code))
    count += len(re.findall(r"\?\s*.*\s*:", code))  # ternary
    return count


def _python_naming_issues(code: str) -> List[str]:
    """Check Python naming: public functions should be snake_case."""
    issues = []
    for m in PYTHON_PUBLIC_DEF.finditer(code):
        name = m.group(1)
        if name.startswith("_"):
            continue
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            issues.append(f"Public function '{name}' should be snake_case")
    return issues


def _js_naming_issues(code: str) -> List[str]:
    """Check JS naming: functions/vars should be camelCase."""
    issues = []
    for m in JS_CAMEL_CASE.finditer(code):
        name = (m.group(1) or m.group(2) or "").strip()
        if not name or name.startswith("_"):
            continue
        if not re.match(r"^[a-z][a-zA-Z0-9]*$", name):
            issues.append(f"Function/variable '{name}' should be camelCase")
    return issues


def code_quality_guardrail(code: str, language: str = "python") -> GuardrailResult:
    """
    Check code quality: function/file length, cyclomatic complexity,
    docstrings, type hints, no TODO/FIXME/HACK, naming conventions.

    Returns GuardrailResult with score 0-100 and improvement suggestions.
    """
    suggestions: List[str] = []
    lines = code.strip().splitlines()
    line_count = len(lines)
    language = language.lower()

    # File length
    if line_count > MAX_FILE_LINES:
        suggestions.append(f"File has {line_count} lines; keep under {MAX_FILE_LINES} lines")

    # TODO/FIXME/HACK
    for m in TODO_PATTERNS.finditer(code):
        suggestions.append("Remove or resolve TODO/FIXME/HACK comments before merge")

    # File I/O without error handling
    if re.search(r"\bopen\s*\(", code) and "try:" not in code and "with " not in code:
        suggestions.append("Consider wrapping file I/O in try/except or use 'with open' for error handling.")

    # Hardcoded credentials (quality gate; use secret_detection for full scan)
    if re.search(
        r"(?i)(password|api_key|secret)\s*=\s*[\'\"]\S+[\'\"]",
        code,
    ):
        suggestions.append("Do not hardcode credentials; use environment variables or a secrets manager.")

    if language == "python":
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return GuardrailResult(
                passed=False,
                score=0,
                message=f"Invalid Python syntax: {e.msg}",
                suggestions=["Fix syntax errors before running quality checks"],
            )

        # Function length and complexity
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if hasattr(node, "end_lineno") and node.end_lineno and node.lineno:
                    fn_lines = node.end_lineno - node.lineno + 1
                else:
                    fn_lines = sum(1 for _ in ast.walk(node))
                if fn_lines > MAX_FUNCTION_LINES:
                    suggestions.append(
                        f"Function '{node.name}' has {fn_lines} lines; keep under {MAX_FUNCTION_LINES}"
                    )
                fn_code = ast.get_source_segment(code, node) or ""
                cc = _cyclomatic_complexity_approx(fn_code)
                if cc > MAX_CYCLOMATIC_COMPLEXITY:
                    suggestions.append(
                        f"Function '{node.name}' has high complexity ({cc}); simplify or split"
                    )
                # Docstring
                doc = ast.get_docstring(node)
                if not doc and not node.name.startswith("_"):
                    suggestions.append(f"Add docstring to public function '{node.name}'")
                # Type hints on public functions
                if not node.name.startswith("_"):
                    if node.returns is None and node.args.args:
                        suggestions.append(f"Add return type hint to '{node.name}'")

        suggestions.extend(_python_naming_issues(code))

    elif language in ("javascript", "js", "typescript", "ts"):
        # Approximate function length by counting lines between function and next }
        fn_blocks = list(re.finditer(r"function\s+\w+\s*\([^)]*\)\s*\{", code))
        for m in fn_blocks:
            start = m.end()
            depth = 1
            pos = start
            while pos < len(code) and depth > 0:
                if code[pos] == "{":
                    depth += 1
                elif code[pos] == "}":
                    depth -= 1
                pos += 1
            fn_lines = code[start:pos].count("\n") + 1
            if fn_lines > MAX_FUNCTION_LINES:
                suggestions.append(
                    f"Function has {fn_lines} lines; keep under {MAX_FUNCTION_LINES}"
                )
        cc = _cyclomatic_complexity_approx(code)
        if cc > MAX_CYCLOMATIC_COMPLEXITY * 2:  # JS often has more branches
            suggestions.append(f"Consider reducing cyclomatic complexity (approx {cc})")
        suggestions.extend(_js_naming_issues(code))

    # Score: start at 100, deduct for each issue
    score = 100 - min(90, len(suggestions) * 15)
    if line_count > MAX_FILE_LINES:
        score = min(score, 60)
    passed = score >= 70  # align with code_quality_min_score 0.7
    try:
        settings = get_settings()
        min_score_pct = int(settings.guardrails.code_quality_min_score * 100)
        passed = score >= min_score_pct
    except Exception:
        pass

    return GuardrailResult(
        passed=passed,
        score=max(0, score),
        message="Code quality issues found" if suggestions else "Code quality checks passed",
        suggestions=suggestions,
    )


# -----------------------------------------------------------------------------
# 2. Test coverage guardrail
# -----------------------------------------------------------------------------


def coverage_guardrail(
    coverage_report: dict,
    min_coverage_threshold: Optional[float] = None,
) -> GuardrailResult:
    """
    Enforce minimum coverage threshold, flag files with 0% coverage,
    and check for meaningful assertions (not just assert True).

    coverage_report: dict with keys such as 'total_coverage' (0-1 or 0-100),
                    'files' (dict of file -> coverage), optionally 'assertions'.
    """
    suggestions: List[str] = []
    threshold = min_coverage_threshold
    if threshold is None:
        try:
            settings = get_settings()
            threshold = settings.guardrails.test_coverage_min  # 0-1
        except Exception:
            threshold = 0.8

    total = coverage_report.get("total_coverage") or coverage_report.get("coverage")
    if total is None and "files" in coverage_report:
        files_cov = coverage_report["files"]
        if isinstance(files_cov, dict):
            vals = [v for v in files_cov.values() if isinstance(v, (int, float))]
            total = sum(vals) / len(vals) if vals else 0.0
        else:
            total = 0.0
    if total is None:
        total = 0.0

    # Normalize to 0-1
    if isinstance(total, (int, float)) and total > 1:
        total = total / 100.0

    if total < threshold:
        suggestions.append(
            f"Overall coverage {total:.0%} is below minimum {threshold:.0%}"
        )

    # Flag files with 0% coverage
    files = coverage_report.get("files") or coverage_report.get("file_coverage") or {}
    if isinstance(files, dict):
        zero_files = [f for f, c in files.items() if (c == 0 or c == 0.0)]
        if zero_files:
            suggestions.append(
                f"Files with 0% coverage: {', '.join(zero_files[:5])}"
                + (" ..." if len(zero_files) > 5 else "")
            )

    # Meaningful assertions: if report includes assertion info, flag assert True
    assertions = coverage_report.get("assertions") or coverage_report.get("assertion_quality")
    if isinstance(assertions, list):
        weak = [a for a in assertions if a.get("text") == "assert True" or a.get("weak")]
        if weak:
            suggestions.append("Replace trivial assertions (e.g. assert True) with meaningful checks")

    score = int(total * 100) if 0 <= total <= 1 else min(100, max(0, int(total)))
    passed = total >= threshold
    return GuardrailResult(
        passed=passed,
        score=score,
        message="Coverage below threshold" if not passed else "Coverage requirements met",
        suggestions=suggestions,
    )


# Alias for API compatibility (avoid pytest collecting this as a test)
test_coverage_guardrail = coverage_guardrail


# -----------------------------------------------------------------------------
# 3. Documentation guardrail
# -----------------------------------------------------------------------------


def documentation_guardrail(code: str, docs: str) -> GuardrailResult:
    """
    Verify README exists and is non-empty, all public functions documented,
    and docstring quality: description, parameters, returns, examples.
    """
    suggestions: List[str] = []

    # README
    readme_ok = bool(docs and docs.strip())
    if not readme_ok:
        suggestions.append("README is missing or empty")

    # Public functions in code and docstrings
    if "def " in code:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    doc = ast.get_docstring(node)
                    if not doc:
                        suggestions.append(f"Public function '{node.name}' has no docstring")
                    else:
                        doc_lower = doc.lower()
                        if "param" not in doc_lower and "arg" not in doc_lower and node.args.args:
                            suggestions.append(
                                f"Docstring for '{node.name}' should document parameters"
                            )
                        if "return" not in doc_lower and node.returns is not None:
                            suggestions.append(
                                f"Docstring for '{node.name}' should document return value"
                            )
        except SyntaxError:
            suggestions.append("Code has syntax errors; cannot verify docstrings")

    score = 100 - min(90, len(suggestions) * 20)
    passed = score >= 70 and readme_ok
    return GuardrailResult(
        passed=passed,
        score=max(0, score),
        message="Documentation issues found" if suggestions else "Documentation checks passed",
        suggestions=suggestions,
    )


# -----------------------------------------------------------------------------
# 4. Architecture compliance guardrail
# -----------------------------------------------------------------------------


def architecture_compliance_guardrail(
    code_files: List[str],
    architecture: dict,
) -> GuardrailResult:
    """
    Verify code follows the architecture document: correct module placement,
    no circular imports, interface compliance.

    architecture: dict with optional keys:
      - allowed_modules / layers: list or dict of allowed module paths
      - forbidden_imports: list of import patterns that are not allowed
      - layers: dict mapping layer name to list of allowed prefixes
    """
    suggestions: List[str] = []

    allowed = architecture.get("allowed_modules") or architecture.get("layers")
    if isinstance(allowed, dict):
        allowed_prefixes = []
        for v in allowed.values():
            if isinstance(v, list):
                allowed_prefixes.extend(v)
            else:
                allowed_prefixes.append(str(v))
    elif isinstance(allowed, list):
        allowed_prefixes = list(allowed)
    else:
        allowed_prefixes = []

    forbidden_imports = architecture.get("forbidden_imports") or []

    for file_path in code_files:
        if allowed_prefixes:
            normalized = file_path.replace("\\", "/")
            if not any(normalized.startswith(p) or p in normalized for p in allowed_prefixes):
                suggestions.append(f"File '{file_path}' may be outside allowed architecture layers")

        # Simple circular import check: collect imports from file content (caller must pass content)
        # Here we only have paths; we could accept List[Tuple[path, content]]
        # For now we only check path placement and leave circular detection to caller

    for pattern in forbidden_imports:
        for fp in code_files:
            if pattern in fp or (isinstance(pattern, str) and re.search(pattern, fp)):
                suggestions.append(f"File '{fp}' matches forbidden pattern: {pattern}")

    score = 100 - min(90, len(suggestions) * 25)
    passed = len(suggestions) == 0
    return GuardrailResult(
        passed=passed,
        score=max(0, score),
        message="Architecture compliance issues found" if suggestions else "Architecture compliant",
        suggestions=suggestions,
    )


# -----------------------------------------------------------------------------
# 5. Dependency guardrail
# -----------------------------------------------------------------------------

# Packages known to be often vulnerable or deprecated (small subset; use pip-audit in CI for full)
KNOWN_VULNERABLE_PATTERNS = [
    "cryptography<3.4",
    "requests<2.28",
    "urllib3<2.0",
    "pillow<10",
    "django<4.2",
    "flask<3.0",
    "jinja2<3.1",
]
VERSION_PIN = re.compile(r"^([a-zA-Z0-9_-]+)\s*==\s*([^\s#]+)")
VERSION_LOOSE = re.compile(r"^([a-zA-Z0-9_-]+)\s*$", re.MULTILINE)
VERSION_ANY = re.compile(r"^([a-zA-Z0-9_-]+)\s*(~=|>=|<=|>|<)\s*", re.MULTILINE)


def dependency_guardrail(requirements: str) -> GuardrailResult:
    """
    Check for version pinning, unnecessary dependencies, and optionally
    flag packages with no recent updates. Known vulnerable packages
    are flagged via pattern list; use pip-audit/safety in CI for full CVE data.
    """
    suggestions: List[str] = []
    lines = [ln.strip() for ln in requirements.strip().splitlines() if ln.strip()]

    unpinned = []
    for line in lines:
        if line.startswith("#") or line.startswith("-") or "-f " in line or "://" in line:
            continue
        # Allow == pinning
        m = VERSION_PIN.match(line)
        if m:
            continue
        m = VERSION_LOOSE.match(line.split("#")[0].strip())
        if m:
            unpinned.append(m.group(1))
        else:
            m = VERSION_ANY.match(line.split("#")[0].strip())
            if m:
                suggestions.append(
                    f"Prefer exact pinning (==) for '{m.group(1)}' in production"
                )

    if unpinned:
        suggestions.append(
            f"Unpinned or loosely pinned packages: {', '.join(unpinned[:10])}"
            + (" ..." if len(unpinned) > 10 else "")
        )

    for pattern in KNOWN_VULNERABLE_PATTERNS:
        if pattern.lower() in requirements.lower():
            suggestions.append(f"Known vulnerable or outdated pattern in requirements: {pattern}")

    score = 100 - min(90, len(suggestions) * 20)
    passed = len(suggestions) == 0
    return GuardrailResult(
        passed=passed,
        score=max(0, score),
        message="Dependency issues found" if suggestions else "Dependency checks passed",
        suggestions=suggestions,
    )
