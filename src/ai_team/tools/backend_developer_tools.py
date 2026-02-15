"""Backend Developer agent tools: code generation, DB schema, API implementation, quality guardrails."""

import ast
import re
from pathlib import Path
from typing import Any

from crewai.tools import tool

from ai_team.config.settings import get_settings


# ----- Guardrail helpers (code quality) -----

_PLACEHOLDER_PATTERNS = re.compile(
    r"\b(TODO|FIXME|XXX|HACK|placeholder|pass\s*#|\.\.\.|NotImplemented|raise NotImplementedError)\b",
    re.IGNORECASE,
)


def _check_python_syntax(code: str) -> tuple[bool, str]:
    """Validate Python syntax. Returns (ok, message)."""
    try:
        ast.parse(code)
        return True, "Python syntax OK"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"


def _check_placeholders(code: str) -> tuple[bool, list[str]]:
    """Detect placeholder/TODO patterns. Returns (no_placeholders, list of findings)."""
    findings = _PLACEHOLDER_PATTERNS.findall(code)
    return len(findings) == 0, list(set(findings))


def _run_quality_checks(
    code: str,
    language: str,
    *,
    require_syntax: bool = True,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Run guardrail-backed quality checks on code. Returns a report dict."""
    settings = get_settings()
    cfg = settings.guardrails
    report: dict[str, Any] = {
        "passed": True,
        "checks": [],
        "score": 10.0,
        "issues": [],
    }

    if language == "python" and require_syntax and cfg.require_syntax_validation:
        ok, msg = _check_python_syntax(code)
        report["checks"].append({"name": "syntax", "passed": ok, "message": msg})
        if not ok:
            report["passed"] = False
            report["issues"].append(msg)
            report["score"] = min(report["score"], 3.0)

    if require_complete and cfg.require_complete_implementation:
        no_placeholders, findings = _check_placeholders(code)
        report["checks"].append({
            "name": "no_placeholders",
            "passed": no_placeholders,
            "findings": findings,
        })
        if not no_placeholders:
            report["passed"] = False
            report["issues"].append(f"Placeholders or TODOs found: {findings}")
            report["score"] = min(report["score"], 6.0)

    report["score"] = max(0.0, min(10.0, report["score"]))
    if report["score"] < cfg.min_code_quality_score:
        report["passed"] = False
    return report


# ----- Tools -----


@tool("Code generation")
def code_generation(
    language: str,
    module_or_file: str,
    requirements: str,
    implementation_notes: str = "",
) -> str:
    """Generate backend code in the specified language. language must be one of 'python', 'node', or 'go'. Provide module_or_file (e.g. 'user_service' or 'pkg/handlers/user.go'), requirements (what the code should do), and optional implementation_notes. Use for services, utilities, and business logic."""
    lang = language.lower().strip()
    if lang not in ("python", "node", "go"):
        return f"Unsupported language '{language}'. Use one of: python, node, go."
    return (
        f"Code generation requested: language={lang}, target={module_or_file}. "
        f"Requirements: {requirements}. Notes: {implementation_notes or 'None'}. "
        "Produce the implementation in the appropriate style for that language, then run code_quality_check (and self_review before completing)."
    )


@tool("Database schema design")
def database_schema_design(
    schema_description: str,
    dialect: str = "sql",
    constraints_and_indexes: str = "",
) -> str:
    """Design a database schema (tables, columns, types). schema_description explains the domain and entities; dialect can be 'sql' (generic), 'postgres', 'mysql', or 'sqlite'. Optionally specify constraints_and_indexes (unique, foreign keys, indexes). Output should be valid DDL or a clear schema spec."""
    return (
        f"Schema design requested: {schema_description}. "
        f"Dialect: {dialect}. Constraints/indexes: {constraints_and_indexes or 'None'}. "
        "Produce DDL or a clear schema specification."
    )


@tool("API implementation")
def api_implementation(
    spec_or_description: str,
    language: str = "python",
    style: str = "rest",
) -> str:
    """Implement an API from a spec or description. spec_or_description is the OpenAPI snippet, user story, or endpoint description. language is 'python', 'node', or 'go'; style is 'rest', 'rpc', or 'graphql'. Include request/response validation and error handling."""
    lang = language.lower().strip()
    if lang not in ("python", "node", "go"):
        return f"Unsupported language '{language}'. Use one of: python, node, go."
    return (
        f"API implementation requested: {spec_or_description}. "
        f"Language: {lang}, style: {style}. "
        "Produce endpoints with validation and error handling, then run code_quality_check and self_review."
    )


@tool("Code quality check")
def code_quality_check(
    code_or_path: str,
    language: str = "python",
) -> str:
    """Run guardrail-backed code quality checks on a snippet or file path. language is 'python', 'node', or 'go'. Checks include syntax validation and completeness (no TODOs/placeholders). Use after generating or editing code to ensure it meets project guardrails before completing a task."""
    settings = get_settings()
    cfg = settings.guardrails

    # If it looks like a path, try to read file
    code = code_or_path
    if len(code_or_path) < 2000 and not code_or_path.strip().startswith(("def ", "class ", "import ", "from ", "func ", "package ", "const ", "{")):
        p = Path(code_or_path.strip())
        if p.exists() and p.is_file():
            try:
                code = p.read_text(encoding="utf-8")
            except Exception as e:
                return f"Cannot read file: {e}. Pass code snippet directly for quality check."
    if language.lower() != "python":
        # Only Python has ast-based syntax check for now; still run placeholder check
        report = _run_quality_checks(code, "python", require_syntax=False, require_complete=cfg.require_complete_implementation)
    else:
        report = _run_quality_checks(
            code,
            "python",
            require_syntax=cfg.require_syntax_validation,
            require_complete=cfg.require_complete_implementation,
        )

    passed = report["passed"] and report["score"] >= cfg.min_code_quality_score
    summary = (
        f"Quality check: {'PASSED' if passed else 'FAILED'} (score={report['score']:.1f}, min={cfg.min_code_quality_score}). "
        f"Checks: {report['checks']}. "
    )
    if report["issues"]:
        summary += f"Issues: {report['issues']}."
    return summary


@tool("Self-review")
def self_review(
    artifact_summary: str,
    checklist: str = "",
) -> str:
    """Run a self-review before marking a task complete. Provide artifact_summary (what was implemented: files, endpoints, schema). Optionally provide checklist (e.g. 'tests pass, no secrets, API documented'). Use this tool after implementing code and running code_quality_check; only then consider the task complete."""
    return (
        f"Self-review recorded. Artifact: {artifact_summary}. "
        f"Checklist: {checklist or 'Default: code_quality_check run, no placeholders, implementation complete.'}. "
        "If checklist is satisfied, task can be marked complete."
    )


def get_backend_developer_tools(**kwargs: Any) -> list:
    """Return CrewAI tools for the Backend Developer agent."""
    return [
        code_generation,
        database_schema_design,
        api_implementation,
        code_quality_check,
        self_review,
    ]
