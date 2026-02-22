#!/usr/bin/env python3
"""
Monitor AITeamFlow output directory: print latest state and detect problems.

Analyzes phase, errors, and history to surface problems and suggest fixes
(e.g. Ollama 404, connection refused, repeated errors, stuck phase).

Usage:
  poetry run python scripts/monitor_output.py [--output-dir PATH] [--interval SEC]
  poetry run python scripts/monitor_output.py --interval 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"

# Thresholds
ERROR_COUNT_WARN = 5
ERROR_COUNT_CRITICAL = 50
REPEAT_SAME_MESSAGE_MIN = 3

# Known error patterns -> (short_label, suggestion)
ERROR_PATTERNS = [
    (
        r"404\s+(page\s+)?not\s+found|NotFoundError|OpenAIException.*404",
        "Ollama model or API not found",
        "Check Ollama is running (http://localhost:11434). For E2E set OPENAI_API_KEY=ollama and use models from scripts/setup_ollama.sh (e.g. qwen3:14b).",
    ),
    (
        r"connection\s+refused|ConnectionRefusedError|ECONNREFUSED",
        "Cannot reach Ollama",
        "Start Ollama: ollama serve (or run scripts/setup_ollama.sh).",
    ),
    (
        r"timeout|TimeoutError|timed\s+out",
        "Request timeout",
        "Ollama may be overloaded or model loading. Increase timeout in settings or try a smaller model.",
    ),
    (
        r"authentication|401|403|API\s+key|invalid.*key",
        "Auth / API key issue",
        "For local Ollama set OPENAI_API_KEY=ollama and OPENAI_BASE_URL=http://localhost:11434.",
    ),
    (
        r"rate\s+limit|429|too\s+many\s+requests",
        "Rate limited",
        "Slow down or use a local model (Ollama) to avoid rate limits.",
    ),
    (
        r"guardrail|guard\s+rail|rejected",
        "Guardrail rejected output",
        "Check guardrail config and input; may need to relax thresholds or adjust prompt.",
    ),
    (
        r"retry|MaxRetriesExceeded|max.*retries",
        "Max retries exceeded",
        "Flow gave up after retries. Check logs for root cause; consider increasing retry limits.",
    ),
]


def load_latest_state(output_dir: Path) -> tuple[Path | None, dict | None]:
    """Return (path, state_dict) for the most recently modified *_state.json."""
    if not output_dir.is_dir():
        return None, None
    state_files = list(output_dir.glob("*_state.json"))
    if not state_files:
        return None, None
    latest = max(state_files, key=lambda p: p.stat().st_mtime)
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        return latest, data
    except (json.JSONDecodeError, OSError):
        return latest, None


def detect_problems(data: dict) -> list[tuple[str, str, str]]:
    """
    Analyze state and return list of (severity, title, detail).
    severity: "CRITICAL" | "WARN" | "INFO"
    """
    problems: list[tuple[str, str, str]] = []
    phase = (data.get("current_phase") or "").lower()
    errors = data.get("errors") or []
    history = data.get("phase_history") or []
    error_count = len(errors)

    # Flow in error state
    if phase == "error":
        problems.append((
            "CRITICAL",
            "Flow in error state",
            f"Phase is 'error' with {error_count} error(s). Flow will not continue until the cause is fixed.",
        ))

    # High error count
    if error_count >= ERROR_COUNT_CRITICAL:
        problems.append((
            "CRITICAL",
            "Very high error count",
            f"{error_count} errors recorded. Likely a repeating failure (e.g. wrong API or model).",
        ))
    elif error_count >= ERROR_COUNT_WARN and phase == "error":
        problems.append((
            "WARN",
            "Elevated error count",
            f"{error_count} errors. Check last error message and suggestions below.",
        ))

    # Repeated same error
    if errors:
        messages = [e.get("message") or str(e) for e in errors[-100:]]  # last 100
        if len(messages) >= REPEAT_SAME_MESSAGE_MIN:
            most_common = Counter(messages).most_common(1)[0]
            msg, count = most_common[0], most_common[1]
            if count >= REPEAT_SAME_MESSAGE_MIN:
                short_msg = (msg[:80] + "…") if len(msg) > 80 else msg
                problems.append((
                    "CRITICAL" if count >= 20 else "WARN",
                    "Same error repeating",
                    f"Last error repeated {count} time(s): {short_msg}",
                ))

    # Match last error to known patterns and add suggestion
    if errors:
        last_msg = (errors[-1].get("message") or str(errors[-1])).strip()
        for pattern, label, suggestion in ERROR_PATTERNS:
            if re.search(pattern, last_msg, re.IGNORECASE):
                problems.append((
                    "INFO",
                    f"Likely cause: {label}",
                    suggestion,
                ))
                break

    # Stuck in planning with many errors (common Ollama misconfig)
    if phase == "error" and history:
        last_from = history[-1].get("from_phase") if history else None
        if last_from == "planning":
            if not any(p[0] == "INFO" and "Likely cause" in p[1] for p in problems):
                problems.append((
                    "INFO",
                    "Failed during planning",
                    "Planning crew (Manager, PO, Architect) failed. Often Ollama model/endpoint: ensure Ollama is running and E2E env (OPENAI_API_KEY=ollama, OPENAI_BASE_URL=http://localhost:11434) is set.",
                ))

    return problems


def format_state(path: Path | None, data: dict | None) -> str:
    """Format summary of state and problems for terminal output."""
    if not data:
        return f"(could not read {path})" if path else "No state files found."

    project_id = data.get("project_id", "?")[:8]
    phase = data.get("current_phase", "?")
    errors = data.get("errors") or []
    history = data.get("phase_history") or []
    last_n = history[-5:] if len(history) > 5 else history

    lines = [
        f"Project: {project_id}...",
        f"Phase:  {phase}",
        f"Errors: {len(errors)}",
    ]
    if last_n:
        lines.append("Recent transitions:")
        for h in last_n:
            lines.append(f"  {h.get('from_phase')} → {h.get('to_phase')} ({h.get('reason', '')})")
    if errors:
        last_err = errors[-1]
        lines.append("Last error:")
        lines.append(f"  {(last_err.get('message') or str(last_err))[:250]}")

    # Problems section
    problems = detect_problems(data)
    if problems:
        lines.append("")
        lines.append("--- PROBLEMS / SUGGESTIONS ---")
        for severity, title, detail in problems:
            icon = "🔴" if severity == "CRITICAL" else "🟡" if severity == "WARN" else "🔵"
            lines.append(f"{icon} [{severity}] {title}")
            lines.append(f"   {detail}")
            lines.append("")
    else:
        if phase == "complete":
            lines.append("")
            lines.append("--- No problems detected (phase: complete). ---")
        elif phase != "error" and len(errors) == 0:
            lines.append("")
            lines.append("--- No problems detected. ---")

    return "\n".join(lines).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor flow output directory and report problems"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory containing *_state.json",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Refresh interval in seconds (0 = once)",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()

    if args.interval <= 0:
        path, data = load_latest_state(output_dir)
        print(format_state(path, data))
        return 0

    try:
        while True:
            path, data = load_latest_state(output_dir)
            header = f"--- {path.name if path else 'no state'} (output dir: {output_dir}) ---"
            print("\033[2J\033[H" + header + "\n" + format_state(path, data) + "\n")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
