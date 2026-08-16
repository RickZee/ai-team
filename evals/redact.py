"""Redact secrets and personal identifiers from fixture traces (R11.2)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

# Ordered: more-specific API key prefixes before generic ``sk-``.
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"sk-or-[A-Za-z0-9_-]{8,}"), "[REDACTED_OPENROUTER_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "[REDACTED_API_KEY]"),
    # Long hex blobs (tokens, hashes mistaken for secrets in free text).
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "[REDACTED_HEX]"),
]

_HOME_PATH = re.compile(r"/Users/[^/\s\"']+")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Patterns that the CI linter treats as a hard fail when found in fixtures.
LINT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}")),
    ("openrouter_key", re.compile(r"sk-or-[A-Za-z0-9_-]{8,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("long_hex", re.compile(r"\b[0-9a-fA-F]{40,}\b")),  # 40+ to allow sha256 in schema
    ("home_path", re.compile(r"/Users/[^/\s\"']+")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]


_HASH_FIELD_CTX = re.compile(
    r"(sha256|scenario_content_sha256|corpus_state_hash|prompt_hash|"
    r"content_sha|cache_key|git_sha)\s*[\"']?\s*[:=]\s*[\"']?",
    re.IGNORECASE,
)
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")


def _redact_hex(match: re.Match[str], full: str) -> str:
    """Replace long hex unless it is a known content-hash JSON/YAML value."""
    start = max(0, match.start() - 64)
    prefix = full[start : match.start()]
    if _HASH_FIELD_CTX.search(prefix):
        return match.group(0)
    return "[REDACTED_HEX]"


def redact_text(text: str) -> str:
    """Scrub API keys, home paths, emails, and free-text long hex from *text*."""
    out = text
    for pat, repl in _SECRET_PATTERNS[:-1]:  # all but generic long-hex
        out = pat.sub(repl, out)
    out = _LONG_HEX.sub(lambda m: _redact_hex(m, out), out)
    out = _HOME_PATH.sub("/home/user", out)
    out = _EMAIL.sub("[REDACTED_EMAIL]", out)
    return out


def redact_file(path: Path, *, dry_run: bool = False) -> bool:
    """Redact a single file in place. Returns True when content changed."""
    original = path.read_text(encoding="utf-8")
    redacted = redact_text(original)
    if redacted == original:
        return False
    if not dry_run:
        path.write_text(redacted, encoding="utf-8")
    return True


def redact_tree(root: Path, *, dry_run: bool = False) -> list[Path]:
    """Redact all ``.json`` / ``.jsonl`` / ``.md`` / ``.txt`` files under *root*."""
    changed: list[Path] = []
    if not root.exists():
        return changed
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml"}:
            continue
        if redact_file(path, dry_run=dry_run):
            changed.append(path)
    return changed


def lint_secrets(paths: Iterable[Path]) -> list[tuple[Path, str, str]]:
    """Return ``(path, pattern_name, snippet)`` for each forbidden match.

    Structured content-hash fields (``sha256``, ``scenario_content_sha256``, …)
    are exempted from the long-hex rule so legitimate digests do not fail CI.
    """
    findings: list[tuple[Path, str, str]] = []
    text_suffixes = {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml", ".py", ".html"}
    for path in paths:
        if not path.is_file():
            continue
        if path.suffix.lower() not in text_suffixes and path.name not in {".gitkeep"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for name, pat in LINT_PATTERNS:
            if name == "long_hex":
                for m in pat.finditer(text):
                    start = max(0, m.start() - 40)
                    ctx = text[start : m.end() + 10]
                    if any(
                        k in ctx
                        for k in (
                            '"sha256"',
                            "scenario_content_sha256",
                            "corpus_state_hash",
                            "prompt_hash",
                            "[REDACTED_HEX]",
                        )
                    ):
                        continue
                    findings.append((path, name, m.group(0)[:48]))
                continue
            for m in pat.finditer(text):
                findings.append((path, name, m.group(0)[:48]))
    return findings
