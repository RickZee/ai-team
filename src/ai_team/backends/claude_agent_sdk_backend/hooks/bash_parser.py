"""Fail-closed bash command extractor for default-deny confinement (R14).

Anything the parser cannot decompose is blocked. This is the opposite of a
denylist that fails open on novel spellings.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

_WRAPPERS = frozenset({"nohup", "timeout", "nice", "ionice", "stdbuf", "env", "command", "exec"})
_GIT_DANGEROUS_CONFIG = frozenset({"core.hookspath", "core.pager"})
_PIPE_TO_SHELL = re.compile(r"\|\s*/?(?:usr/bin/)?(?:ba)?sh(?:\s|$)")


@dataclass(frozen=True)
class ParsedCommand:
    """One extracted simple command."""

    name: str
    argv: list[str]
    absolute: bool


@dataclass(frozen=True)
class ParseResult:
    """Successful decomposition, or a block reason when ``ok`` is False."""

    ok: bool
    commands: list[ParsedCommand]
    reason: str = ""


def _unclosed_quotes(command: str) -> bool:
    try:
        shlex.split(command, posix=True)
    except ValueError:
        return True
    return False


def _has_substitution(command: str) -> bool:
    if "`" in command:
        return True
    if "$(" in command or "${" in command:
        return True
    return False


def _normalize_for_danger(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip().lower())


def looks_like_rm_root(command: str) -> bool:
    """True for ``rm -rf /`` and trivial spelling variants."""
    norm = _normalize_for_danger(command)
    return bool(re.search(r"\brm\b(?:\s+-[a-z]*)*\s+/(\s|$)", norm)) or bool(
        re.search(r"\brm\b.*\s+-[a-z]*f[a-z]*.*/(\s|$)", norm)
    )


def looks_like_pipe_to_shell(command: str) -> bool:
    """True for ``… | sh`` including no-space and trailing-arg variants."""
    return bool(_PIPE_TO_SHELL.search(command.lower()))


def extract_commands(command: str) -> ParseResult:
    """Decompose *command* into simple commands, or fail closed.

    Handles ``&&``, ``||``, ``;``, pipes, ``env VAR=x cmd``, ``xargs``,
    ``nohup``, ``timeout``, absolute paths, and ``git -c`` danger flags.
    Command substitution, backticks, and unclosed quotes are blocked.
    """
    raw = command.strip()
    if not raw:
        return ParseResult(ok=False, commands=[], reason="empty command")
    if _unclosed_quotes(raw):
        return ParseResult(ok=False, commands=[], reason="unclosed quotes")
    if _has_substitution(raw):
        return ParseResult(ok=False, commands=[], reason="command substitution")
    if looks_like_pipe_to_shell(raw):
        return ParseResult(ok=False, commands=[], reason="pipe to shell")
    if looks_like_rm_root(raw):
        return ParseResult(ok=False, commands=[], reason="rm of filesystem root")

    # Split on control operators that start a new command. Pipes are also
    # command boundaries for allowlist purposes.
    chunks = re.split(r"(?:&&|\|\||;|\n|\|)", raw)
    commands: list[ParsedCommand] = []
    for chunk in chunks:
        piece = chunk.strip()
        if not piece:
            continue
        try:
            tokens = shlex.split(piece, posix=True)
        except ValueError as exc:
            return ParseResult(ok=False, commands=[], reason=f"undecomposable: {exc}")
        if not tokens:
            continue
        parsed = _unwrap(tokens)
        if parsed is None:
            return ParseResult(ok=False, commands=[], reason="undecomposable wrapper")
        commands.append(parsed)
    if not commands:
        return ParseResult(ok=False, commands=[], reason="no commands extracted")
    for cmd in commands:
        if cmd.name == "git" and _git_dangerous(cmd.argv):
            return ParseResult(
                ok=False,
                commands=commands,
                reason="git -c core.hooksPath/core.pager is blocked",
            )
        if cmd.name == "xargs":
            # xargs can invoke an arbitrary command; fail closed unless the
            # remainder itself decomposes to a single allowed name later.
            rest = _xargs_inner(cmd.argv)
            if rest is None:
                return ParseResult(ok=False, commands=[], reason="undecomposable xargs")
            commands.append(rest)
    return ParseResult(ok=True, commands=commands)


def _unwrap(tokens: list[str]) -> ParsedCommand | None:
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        base = PathName(tok).name
        if base == "env":
            idx += 1
            while idx < len(tokens) and "=" in tokens[idx] and not tokens[idx].startswith("-"):
                idx += 1
            continue
        if base in {"timeout", "nice", "ionice", "stdbuf"}:
            idx += 1
            while idx < len(tokens) and tokens[idx].startswith("-"):
                idx += 1
                if idx < len(tokens) and not tokens[idx].startswith("-"):
                    idx += 1
            if (
                base == "timeout"
                and idx < len(tokens)
                and re.fullmatch(r"\d+(?:\.\d+)?[smhd]?", tokens[idx])
            ):
                idx += 1
            continue
        if base in {"nohup", "command", "exec"}:
            idx += 1
            continue
        name = PathName(tok).name
        return ParsedCommand(name=name, argv=tokens[idx:], absolute=tok.startswith("/"))
    return None


def _xargs_inner(argv: list[str]) -> ParsedCommand | None:
    # drop 'xargs' and its flags; remaining first non-flag is the command
    rest = argv[1:] if argv and PathName(argv[0]).name == "xargs" else argv
    i = 0
    while i < len(rest) and rest[i].startswith("-"):
        i += 1
        # skip flag arguments that are not new commands (best-effort)
        if (
            i < len(rest)
            and not rest[i].startswith("-")
            and rest[i - 1] in {"-n", "-P", "-I", "-L"}
        ):
            i += 1
    if i >= len(rest):
        return None
    return _unwrap(rest[i:])


def _git_dangerous(argv: list[str]) -> bool:
    for i, tok in enumerate(argv):
        if tok == "-c" and i + 1 < len(argv):
            key = argv[i + 1].split("=", 1)[0].lower()
            if key in _GIT_DANGEROUS_CONFIG:
                return True
    return False


class PathName:
    """Tiny helper so we do not import pathlib in the hot path unnecessarily."""

    def __init__(self, value: str) -> None:
        self.name = value.rsplit("/", 1)[-1] or value
