#!/usr/bin/env python3
"""Run one lab command the way a learner would, with a real time limit.

For the course test agent (see .cursor/skills/course-test/SKILL.md). macOS has no
``timeout(1)``, and killing only the shell leaves ``run_demo.py`` children running — and
spending. This starts the command in its own process group, kills the whole group at the
limit, then reports any ``run_demo`` / ``run_smoke_batch`` processes still alive.

Usage:
    python3 course/testing/run_step.py --cwd "$TEST" --log "$REPORT/logs/W1.S3.c1.txt" \
        --timeout 900 -- 'AI_TEAM_ENV=dev uv run python scripts/run_demo.py ...'

Writes the log, plus ``<log>.meta`` with exit code, seconds and whether it timed out.
Exit code 124 means the limit was hit. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import time
from pathlib import Path

WATCH = ("run_demo.py", "run_smoke_batch.py", "ai-team-web")


def _leftovers() -> list[str]:
    """Return ``ps`` lines for course processes that are still alive."""
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid,ppid,etime,command"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except OSError:
        return []
    me = str(os.getpid())
    return [
        line.strip()
        for line in out.splitlines()
        if any(w in line for w in WATCH)
        and "run_step.py" not in line
        and me not in line.split()[:1]
    ]


def _kill_group(pid: int) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            return
        time.sleep(8 if sig == signal.SIGTERM else 1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cwd", required=True, help="the test checkout")
    ap.add_argument("--log", required=True, help="where to write combined output")
    ap.add_argument("--timeout", type=int, default=900, help="seconds (default 900)")
    ap.add_argument(
        "--shell",
        default=os.environ.get("SHELL", "/bin/bash"),
        help="shell to run the command in (default: $SHELL, i.e. what the learner has)",
    )
    ap.add_argument("command", nargs=argparse.REMAINDER, help="-- then the command, quoted")
    args = ap.parse_args()
    cmd = " ".join(c for c in args.command if c != "--")

    log = Path(args.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    timed_out = False
    with log.open("w", encoding="utf-8") as f:
        f.write(f"$ {cmd}\n")
        f.flush()
        proc = subprocess.Popen(  # noqa: S603 - running the lab's own command is the point
            [args.shell, "-c", cmd],
            stdout=f,
            stderr=subprocess.STDOUT,
            cwd=args.cwd,
            start_new_session=True,
        )
        try:
            rc = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc.pid)
            proc.wait()
            rc = 124
    seconds = round(time.time() - start, 1)
    left = _leftovers()
    meta = [f"exit={rc}", f"seconds={seconds}", f"timed_out={timed_out}", f"shell={args.shell}"]
    if left:
        meta.append("LEFTOVER PROCESSES (still running, may be spending):")
        meta.extend(left)
    Path(f"{log}.meta").write_text("\n".join(meta) + "\n", encoding="utf-8")
    print("\n".join(meta))


if __name__ == "__main__":
    main()
