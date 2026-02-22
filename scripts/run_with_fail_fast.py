"""
Run the AI-team flow and stop on first error (fail-fast mode).

Spawns the real flow (ai_team.main), streams stdout/stderr, and exits
as soon as a failure pattern is seen so you can fix issues before
running long jobs.

Usage:
    poetry run python scripts/run_with_fail_fast.py [--monitor] [--project-name NAME] "Project description"
    poetry run python scripts/run_with_fail_fast.py --stop-on-guardrail-block --monitor "Create a REST API"

Failure patterns (stop run and exit 1):
  - [ERROR] in log output
  - "Failed to add to long term memory"
  - If --stop-on-guardrail-block: "Guardrail  blocked"

See docs/STABILITY_ANALYSIS.md for recommended settings (e.g. PROJECT__PLANNING_SEQUENTIAL=1).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Pattern


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AI-team flow and stop on first error (fail-fast).",
    )
    parser.add_argument(
        "description",
        nargs="?",
        default="",
        help="Project description (required).",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Pass --monitor to ai-team (Rich TUI).",
    )
    parser.add_argument(
        "--project-name",
        default="AI-Team Project",
        help="Pass --project-name to ai-team.",
    )
    parser.add_argument(
        "--stop-on-guardrail-block",
        action="store_true",
        help="Also stop on first 'Guardrail  blocked' (otherwise only ERROR / long-term memory).",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Run normally without watching for failure patterns.",
    )
    args = parser.parse_args()

    description = (args.description or "").strip()
    if not description:
        parser.error("Project description is required.")

    cmd = [
        sys.executable,
        "-m",
        "ai_team.main",
        "--project-name",
        args.project_name,
    ]
    if args.monitor:
        cmd.append("--monitor")
    cmd.append(description)

    # Patterns that trigger fail-fast (in order of check).
    patterns: list[tuple[str, Pattern[str]]] = [
        ("[ERROR] in logs", re.compile(r"\[ERROR\]")),
        ("Failed to add to long term memory", re.compile(r"Failed to add to long term memory", re.I)),
    ]
    if args.stop_on_guardrail_block:
        patterns.append(("Guardrail  blocked", re.compile(r"Guardrail\s+blocked")))

    if args.no_fail_fast:
        return subprocess.run(cmd).returncode

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    trigger_name: str | None = None
    trigger_line: str | None = None
    for line in proc.stdout:
        print(line, end="")
        if trigger_name is not None:
            continue
        for name, pat in patterns:
            if pat.search(line):
                trigger_name = name
                trigger_line = line.strip()
                break
        if trigger_name is not None:
            break

    if trigger_name is not None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print("\n--- Fail-fast: stopping on first error ---", file=sys.stderr)
        print(f"Trigger: {trigger_name}", file=sys.stderr)
        if trigger_line:
            print(f"Line: {trigger_line[:200]}", file=sys.stderr)
        return 1
    proc.wait()
    return proc.returncode if proc.returncode is not None else 0


if __name__ == "__main__":
    sys.exit(main())
