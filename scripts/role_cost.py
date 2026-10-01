"""Print tokens per role for one run directory, or totals for a batch.

Usage:
    uv run python scripts/role_cost.py output/runs/<run_id>
    uv run python scripts/role_cost.py output/runs/<id_a> output/runs/<id_b> ...
    uv run python scripts/role_cost.py --batch output/smoke_batch_<stamp>.json

With more than one run, only runs whose messages account for at least
``--min-coverage`` of the cost log's token total are summed; the rest are
listed with the reason.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_team.harness.role_cost import (
    format_batch_report,
    format_report,
    report_run,
    report_runs,
)


def _batch_run_dirs(batch_file: Path, runs_root: Path) -> list[Path]:
    rows = json.loads(batch_file.read_text(encoding="utf-8"))["runs"]
    return [runs_root / str(row["run_id"]) for row in rows]


def main(argv: list[str] | None = None) -> int:
    """Print the role split for one run, or the summed split for several."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dirs", nargs="*", type=Path, help="output/runs/<run_id> directories")
    parser.add_argument("--batch", type=Path, help="smoke batch JSON; its run ids are read")
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("output/runs"),
        help="where --batch run ids live (default: output/runs)",
    )
    parser.add_argument("--min-coverage", type=float, default=0.9)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    run_dirs = list(args.run_dirs)
    if args.batch is not None:
        run_dirs += _batch_run_dirs(args.batch, args.runs_root)
    if not run_dirs:
        parser.print_usage(sys.stderr)
        return 2
    if len(run_dirs) == 1 and args.batch is None:
        sys.stdout.write(format_report(report_run(run_dirs[0])))
    else:
        sys.stdout.write(format_batch_report(report_runs(run_dirs, args.min_coverage)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
