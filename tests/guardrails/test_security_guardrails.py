"""
Comprehensive guardrail effectiveness tests for security guardrails.

Adversarial inputs: dangerous code, secrets, PII. Uses TaskOutput mocks from conftest.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest

from ai_team.guardrails.security import (
    code_safety_guardrail,
    crewai_code_safety_guardrail,
    crewai_pii_guardrail,
    crewai_secret_detection_guardrail,
    pii_redaction_guardrail,
    secret_detection_guardrail,
)


# -----------------------------------------------------------------------------
# Dangerous code injection
# -----------------------------------------------------------------------------


def test_output_containing_os_system_rm_rf_detected_and_fails(task_output_factory: Any) -> None:
    """Output containing os.system('rm -rf /') should detect and fail."""
    raw = (
        "To clean the cache directory in production, the script runs:\n"
        "import os\n"
        "os.system('rm -rf /')\n"
        "# Run as root for full cleanup."
    )
    result = code_safety_guardrail(raw)
    assert result.status == "fail"
    assert "os.system" in result.message or "dangerous" in result.message.lower() or "root" in result.message.lower()
    ok, msg = crewai_code_safety_guardrail(task_output_factory(raw))
    assert ok is False
    assert isinstance(msg, str)


def test_output_containing_eval_user_input_detected_and_fails(task_output_factory: Any) -> None:
    """Output containing eval(user_input) should detect and fail."""
    raw = (
        "For dynamic configuration we evaluate the user-provided expression:\n"
        "result = eval(user_input)\n"
        "This allows maximum flexibility."
    )
    result = code_safety_guardrail(raw)
    assert result.status == "fail"
    assert "eval" in result.message.lower() or "dangerous" in result.message.lower()


def test_output_containing_import_subprocess_detected_and_fails(task_output_factory: Any) -> None:
    """Output containing __import__('subprocess') should detect and fail."""
    raw = (
        "To run the linter we load the module dynamically:\n"
        "mod = __import__('subprocess')\n"
        "mod.run(['ruff', 'check', path])"
    )
    result = code_safety_guardrail(raw)
    assert result.status == "fail"
    assert "__import__" in result.message or "dangerous" in result.message.lower()


def test_output_containing_base64_encoded_dangerous_code_detected_and_fails(
    task_output_factory: Any,
) -> None:
    """Output containing base64-encoded dangerous code should detect and fail."""
    # exec(base64.b64decode(...)) is caught by exec() pattern
    payload = base64.b64encode(b"import os; os.system('id')").decode("ascii")
    raw = f"# Decode and run the payload:\nexec(base64.b64decode('{payload}'))"
    result = code_safety_guardrail(raw)
    assert result.status == "fail"
    assert "exec" in result.message.lower() or "dangerous" in result.message.lower()


def test_clean_code_with_no_dangerous_patterns_passes(task_output_factory: Any) -> None:
    """Clean code with no dangerous patterns should pass."""
    raw = (
        "def get_user(user_id: int):\n"
        "    return db.session.query(User).filter_by(id=user_id).first()\n"
        "\n"
        "def health_check():\n"
        "    return {'status': 'ok'}\n"
    )
    result = code_safety_guardrail(raw)
    assert result.status == "pass"
    ok, out = crewai_code_safety_guardrail(task_output_factory(raw))
    assert ok is True
    assert out.raw == raw


# -----------------------------------------------------------------------------
# Secret detection
# -----------------------------------------------------------------------------


def test_output_containing_aws_secret_key_detected_and_fails(task_output_factory: Any) -> None:
    """Output containing AWS_SECRET_KEY=AKIA... (or similar) should detect and fail."""
    raw = (
        "# Configure AWS in .env:\n"
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
    )
    result = secret_detection_guardrail(raw)
    assert result.status == "fail"
    assert "secret" in result.message.lower() or "AWS" in result.message
    ok, msg = crewai_secret_detection_guardrail(task_output_factory(raw))
    assert ok is False


def test_output_containing_password_hardcoded_detected_and_fails(task_output_factory: Any) -> None:
    """Output containing password='hardcoded123' (or similar) should detect and fail."""
    raw = (
        "db_config = {\n"
        '    "host": "localhost",\n'
        '    "user": "app",\n'
        '    "password": "hardcoded123",  # secret pattern matches key=value style\n'
        "}\n"
        "api_password = \"hardcoded123\"\n"
    )
    result = secret_detection_guardrail(raw)
    assert result.status == "fail"
    assert "password" in result.message.lower() or "secret" in result.message.lower()


def test_output_referencing_environment_variables_properly_passes(task_output_factory: Any) -> None:
    """Output referencing environment variables properly should pass."""
    raw = (
        "import os\n"
        "db_url = os.environ.get('DATABASE_URL')\n"
        "api_key = os.getenv('API_KEY', '')\n"
    )
    result = secret_detection_guardrail(raw)
    assert result.status == "pass"
    ok, _ = crewai_secret_detection_guardrail(task_output_factory(raw))
    assert ok is True


# -----------------------------------------------------------------------------
# PII detection and redaction
# -----------------------------------------------------------------------------


def test_output_containing_ssn_pattern_redacted(task_output_factory: Any) -> None:
    """Output containing SSN pattern should redact."""
    raw = "Customer SSN on file: 123-45-6789. Please verify identity."
    result = pii_redaction_guardrail(raw)
    assert result.status == "warn"
    assert result.details and "redacted" in result.details
    assert "123-45-6789" not in result.details["redacted"]
    assert "REDACTED" in result.details["redacted"] or "SSN" in str(result.details.get("detected", []))


def test_output_containing_credit_card_pattern_redacted(task_output_factory: Any) -> None:
    """Output containing credit card pattern should redact."""
    raw = "Payment card 1234-5678-9012-3456 was charged successfully."
    result = pii_redaction_guardrail(raw)
    assert result.status == "warn"
    assert result.details and "redacted" in result.details
    assert "1234-5678-9012-3456" not in result.details["redacted"]


def test_clean_output_passes_unchanged(task_output_factory: Any) -> None:
    """Clean output should pass unchanged."""
    raw = "The API returns a list of items. No personal data is included."
    result = pii_redaction_guardrail(raw)
    assert result.status == "pass"
    assert result.details and result.details.get("redacted") == raw
    out = task_output_factory(raw)
    ok, result_out = crewai_pii_guardrail(out)
    assert ok is True
    assert "REDACTED" not in (result_out.raw if hasattr(result_out, "raw") else result_out)
