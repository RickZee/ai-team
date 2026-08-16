"""Redaction helpers and CI linter (R11.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.redact import lint_secrets, redact_text, redact_tree

pytestmark = pytest.mark.eval_unit


def test_redact_api_keys_home_email_hex() -> None:
    raw = (
        "key=sk-ant-api03-abcdefghijklmnop "
        "or=sk-or-v1-abcdefghijklmnop "
        "oa=sk-proj-abcdefghijklmnopqrst "
        "hex=deadbeefdeadbeefdeadbeefdeadbeef "
        "path=/Users/alice/dev/proj "
        "mail=alice@example.com "
        'ok_hash={"sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
    )
    out = redact_text(raw)
    assert "sk-ant-" not in out
    assert "sk-or-" not in out
    assert "sk-proj-" not in out
    assert "[REDACTED_HEX]" in out
    assert "/Users/alice" not in out
    assert "/home/user" in out
    assert "alice@example.com" not in out
    assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in out


def test_lint_secrets_finds_residual(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"k": "sk-ant-api03-ABCDEFGH", "p": "/Users/bob/x"}', encoding="utf-8")
    findings = lint_secrets([bad])
    names = {n for _, n, _ in findings}
    assert "anthropic_key" in names
    assert "home_path" in names


def test_fixture_corpus_lint_clean() -> None:
    root = Path("evals/fixtures")
    assert root.is_dir()
    findings = lint_secrets(sorted(root.rglob("*")))
    assert findings == [], findings


def test_redact_tree_dry_run(tmp_path: Path) -> None:
    f = tmp_path / "a.json"
    f.write_text('{"e": "user@example.com"}', encoding="utf-8")
    changed = redact_tree(tmp_path, dry_run=True)
    assert changed == [f]
    assert "user@example.com" in f.read_text(encoding="utf-8")
    changed2 = redact_tree(tmp_path, dry_run=False)
    assert changed2 == [f]
    assert "[REDACTED_EMAIL]" in f.read_text(encoding="utf-8")
