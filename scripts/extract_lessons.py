#!/usr/bin/env python3
"""
Extract and promote recurring failure patterns into lessons.

Usage:
  poetry run python scripts/extract_lessons.py --extract
  poetry run python scripts/extract_lessons.py --extract --threshold 2
  poetry run python scripts/extract_lessons.py --write-infra-backlog
"""

from __future__ import annotations

import argparse
import json
import sys

from ai_team.memory.lessons import extract_lessons, write_infra_backlog


def main() -> int:
    p = argparse.ArgumentParser(description="Extract lessons from failure records.")
    p.add_argument("--extract", action="store_true", help="Extract/promote lessons.")
    p.add_argument(
        "--threshold",
        type=int,
        default=2,
        help="Occurrences required to promote a lesson (default: 2).",
    )
    p.add_argument(
        "--write-infra-backlog",
        action="store_true",
        help="Write data/infra_backlog.jsonl from stored infra_issue patterns.",
    )
    args = p.parse_args()

    did_any = False
    if args.extract:
        did_any = True
        res = extract_lessons(promote_threshold=args.threshold)
        print(json.dumps(res, indent=2))
    if args.write_infra_backlog:
        did_any = True
        n = write_infra_backlog()
        print(json.dumps({"infra_backlog_lines": n}, indent=2))
    if not did_any:
        p.print_help(sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
