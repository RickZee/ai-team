"""Print tokens and a dollar share per role for one run directory.

Usage:
    uv run python scripts/role_cost.py output/runs/<run_id>
"""

from __future__ import annotations

import sys
from pathlib import Path

from ai_team.harness.role_cost import format_report, report_run


def main(argv: list[str] | None = None) -> int:
    """Print the role split for the run directory in ``argv[1]``."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: role_cost.py output/runs/<run_id>", file=sys.stderr)
        return 2
    text = format_report(report_run(Path(args[0])))
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
