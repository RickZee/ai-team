#!/usr/bin/env python3
"""List every lab step and its commands, with stable ids, for the course test agent.

Not for learners — the course itself has no wrapper on purpose. This exists so every
test run numbers steps the same way (W3.S2.c1 = week 3, step 2, first code block) and
reports stay comparable across runs.

Usage:
    python3 course/testing/extract_steps.py            # human-readable
    python3 course/testing/extract_steps.py --json     # for the agent's plan

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

COURSE = Path(__file__).resolve().parents[1]
WEEK_RE = re.compile(r"week-(\d+)-")
STEP_RE = re.compile(r"^## Step (\d+)\s*[—-]\s*(.+?)\s*$")
BEAT_RE = re.compile(r"^\*\*(Predict|Run|Observe|Explain|Change|Write)\b")
FENCE_RE = re.compile(r"^```(\w*)\s*$")


def parse_week(path: Path) -> list[dict]:
    """Return steps for one week file: id, title, beats present, code blocks."""
    week = int(WEEK_RE.search(path.name).group(1))  # type: ignore[union-attr]
    steps: list[dict] = []
    cur: dict | None = None
    in_code = False
    lang = ""
    buf: list[str] = []
    start = 0
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fence = FENCE_RE.match(line)
        if fence and not in_code:
            in_code, lang, buf, start = True, fence.group(1), [], n
            continue
        if fence and in_code:
            in_code = False
            if cur is not None:
                cur["blocks"].append(
                    {
                        "id": f"{cur['id']}.c{len(cur['blocks']) + 1}",
                        "lang": lang or "text",
                        "line": start,
                        "runnable": lang in ("bash", "sh"),
                        "text": "\n".join(buf),
                    }
                )
            continue
        if in_code:
            buf.append(line)
            continue
        m = STEP_RE.match(line)
        if m:
            cur = {
                "id": f"W{week}.S{m.group(1)}",
                "file": f"course/{path.name}",
                "line": n,
                "title": m.group(2),
                "beats": [],
                "blocks": [],
            }
            steps.append(cur)
            continue
        b = BEAT_RE.match(line)
        if b and cur is not None and b.group(1) not in cur["beats"]:
            cur["beats"].append(b.group(1))
    return steps


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    steps = [s for p in sorted(COURSE.glob("week-*-*.md")) for s in parse_week(p)]
    if args.json:
        print(json.dumps(steps, indent=2))
        return
    for s in steps:
        runnable = sum(b["runnable"] for b in s["blocks"])
        missing = [x for x in ("Predict", "Run", "Observe", "Explain") if x not in s["beats"]]
        flag = f"  missing beats: {', '.join(missing)}" if missing else ""
        print(f"{s['id']:<7} {s['file']}:{s['line']:<4} {s['title']}  [{runnable} runnable]{flag}")


if __name__ == "__main__":
    main()
