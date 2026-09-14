#!/usr/bin/env python3
"""minieval — a single-file eval harness you can read in one sitting.

Standard library only. No install, no API key, no network, no cost. Copy this one
file into any project that writes logs and run it against them.

About 370 lines, half of them comments. It does four things, in the order
that matters:

    ingest   turn your existing log files into immutable traces
    stats    tell you what your corpus actually is, and what it is short by
    run      score three deterministic checks over it
    audit    answer the five questions in one pass

The three checks are not about your application. They are about your instrument,
and they are the three defects a real 13,000-line eval harness turned out to have
after seven months of looking correct:

    CHK-trace-has-spans      a trace with no spans is a shell; nothing can read it
    CHK-writer-is-code       telemetry the model was asked to write is not evidence
    CHK-run-record-complete  a run with no end time and no status poisons denominators

If those three pass on your logs, your instrument can see. That is a lower bar
than "my agents work", and it is the bar almost nobody checks first.

Usage
-----
    python3 minieval.py ingest --logs ./path/to/your/runs --out ./traces
    python3 minieval.py stats  --traces ./traces
    python3 minieval.py run    --traces ./traces --kind CORPUS
    python3 minieval.py audit  --traces ./traces

What "ingest" expects: a directory whose subdirectories are runs. In each run
directory it reads any *.jsonl as a stream of span records (one JSON object per
line) and, if present, run.json / meta.json for run-level fields. Nothing is
required. Whatever is missing is reported as missing rather than guessed, which
is the entire point.

Run-level fields are looked up at the top level and one level inside an "extra",
"meta" or "metadata" wrapper, because that is where real run records put half of
them. If your records nest deeper, widen that list — a field reported missing
when it was one level down is your instrument being blind, not your system being
broken, and mistaking the first for the second is this file's whole subject.

License: MIT. Attribution welcome, not required.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Vocabulary. Small on purpose: every word here has to earn its place.
# --------------------------------------------------------------------------- #

#: What kind of corpus a number came from. Render this next to every rate you
#: publish. Most eval suites are FIXTURE-ONLY and their owners do not know it.
CORPUS_KINDS = ("FIXTURE-ONLY", "CORPUS", "LIVE")

#: Why a check declined to answer. A closed list, so you can count causes
#: instead of clustering sentences.
NA_REASONS = ("no_spans", "no_run_record", "no_writer_field", "not_in_scope")

#: Diversity floors. Below any of these, no rate from this corpus means
#: anything, and `stats` says so. Volume is not diversity: fifty traces from one
#: source in a two-second window is n=1 wearing n=50's clothes.
FLOORS = {
    "traces": 100,
    "distinct_sources": 3,
    "distinct_statuses": 2,
    "span_days": 14,
}

#: Share of abstentions above which a report is stamped EVIDENCE-STARVED.
EVIDENCE_STARVED_THRESHOLD = 0.50

#: n below which a rate renders as a bare count. A confidence interval over four
#: results is arithmetic performing a confidence it does not have.
MIN_N_FOR_RATE = 10

_ISO = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


# --------------------------------------------------------------------------- #
# Ingest — your logs become traces. Missing things stay missing.
# --------------------------------------------------------------------------- #


def _parse_time(value: Any) -> str | None:
    """Return an ISO-8601 string if *value* looks like a timestamp, else None."""
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and _ISO.match(value.strip()):
        return value.strip()
    return None


def _first(record: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSON-lines file, skipping unparseable lines rather than dying."""
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            out.append(record)
    return out


def build_trace(run_dir: Path) -> dict[str, Any]:
    """Build one trace from one run directory. Records what it could not find."""
    warnings: list[str] = []
    spans: list[dict[str, Any]] = []

    jsonl_files = sorted(run_dir.rglob("*.jsonl"))
    if not jsonl_files:
        warnings.append(f"no *.jsonl under {run_dir.name}")

    for jf in jsonl_files:
        records = _read_jsonl(jf)
        if not records:
            warnings.append(f"empty or unparseable: {jf.name}")
        for record in records:
            spans.append(
                {
                    "type": str(_first(record, ("type", "event", "phase", "name")) or "unknown"),
                    # The field that matters most and is almost never present.
                    "writer": _first(record, ("writer", "written_by", "source")),
                    "t": _parse_time(_first(record, ("t", "ts", "time", "timestamp"))),
                    "file": jf.name,
                }
            )

    record_names = ("run.json", "meta.json", "session.json")
    record_path = next(
        (run_dir / name for name in record_names if (run_dir / name).is_file()),
        None,
    )
    run_record: dict[str, Any] = {}
    if record_path is None:
        warnings.append("no run.json / meta.json / session.json")
    else:
        try:
            loaded = json.loads(record_path.read_text(encoding="utf-8", errors="replace"))
            run_record = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            warnings.append(f"unparseable: {record_path.name}")

    # Real run records nest fields one level deep as often as not. Look inside the
    # usual wrapper keys before concluding a field is absent — reporting "missing"
    # when the value was one level down is the instrument being blind, not the
    # system being broken, and it is the exact mistake this file exists to catch.
    for wrapper in ("extra", "meta", "metadata"):
        nested = run_record.get(wrapper)
        if isinstance(nested, dict):
            for key, value in nested.items():
                run_record.setdefault(key, value)

    started = _parse_time(_first(run_record, ("started_at", "start", "created_at")))
    if started is None:
        span_times = [s["t"] for s in spans if s["t"]]
        started = min(span_times) if span_times else None

    return {
        "trace_id": run_dir.name,
        "source": str(_first(run_record, ("backend", "source", "engine", "model")) or "unset"),
        "status": str(_first(run_record, ("status", "final_status", "outcome")) or "unknown"),
        "started_at": started,
        "ended_at": _parse_time(_first(run_record, ("completed_at", "ended_at", "finished_at"))),
        "has_run_record": record_path is not None,
        "spans": spans,
        "warnings": warnings,
    }


def cmd_ingest(args: argparse.Namespace) -> int:
    logs = Path(args.logs)
    if not logs.is_dir():
        print(f"error: {logs} is not a directory")
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    run_dirs = sorted(p for p in logs.iterdir() if p.is_dir())
    if not run_dirs:
        print(f"error: no subdirectories under {logs} — expected one per run")
        return 2

    for run_dir in run_dirs:
        trace = build_trace(run_dir)
        (out / f"{trace['trace_id']}.json").write_text(
            json.dumps(trace, indent=2, sort_keys=True), encoding="utf-8"
        )

    n_spans = sum(len(json.loads(p.read_text())["spans"]) for p in out.glob("*.json"))
    print(f"ingested {len(run_dirs)} runs -> {out}/  ({n_spans} spans total)")
    if n_spans == 0:
        print("\n  Zero spans across every trace. Your logs and your reader do not agree")
        print("  on where logs live. Check that --logs points at the tree your code")
        print("  writes to, not the tree it writes output into. This is question 0.")
    return 0


# --------------------------------------------------------------------------- #
# Stats — what the corpus is, and what it is short by.
# --------------------------------------------------------------------------- #


def load_traces(root: Path) -> list[dict[str, Any]]:
    traces = []
    for path in sorted(root.glob("*.json")):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict) and "trace_id" in loaded:
            traces.append(loaded)
    return traces


def profile(traces: list[dict[str, Any]]) -> dict[str, Any]:
    times = sorted(t["started_at"] for t in traces if t.get("started_at"))
    span_days = 0.0
    if len(times) >= 2:
        try:
            lo = datetime.fromisoformat(times[0].replace("Z", "+00:00"))
            hi = datetime.fromisoformat(times[-1].replace("Z", "+00:00"))
            span_days = (hi - lo).total_seconds() / 86400.0
        except ValueError:
            span_days = 0.0
    return {
        "traces": len(traces),
        "distinct_ids": len({t["trace_id"] for t in traces}),
        "total_spans": sum(len(t.get("spans", [])) for t in traces),
        "traces_with_spans": sum(1 for t in traces if t.get("spans")),
        "distinct_sources": len({t.get("source", "unset") for t in traces}),
        "distinct_statuses": len({t.get("status", "unknown") for t in traces}),
        "span_days": span_days,
        "sources": Counter(t.get("source", "unset") for t in traces),
        "statuses": Counter(t.get("status", "unknown") for t in traces),
        "first": times[0] if times else None,
        "last": times[-1] if times else None,
    }


def unmet_floors(prof: dict[str, Any]) -> list[str]:
    unmet = []
    for key, floor in FLOORS.items():
        value = prof.get(key, 0)
        if value < floor:
            shown = f"{value:.1f}" if isinstance(value, float) else value
            unmet.append(f"{key} {shown}/{floor}")
    return unmet


def cmd_stats(args: argparse.Namespace) -> int:
    traces = load_traces(Path(args.traces))
    if not traces:
        print(f"no traces under {args.traces} — run `ingest` first")
        return 2
    prof = profile(traces)
    unmet = unmet_floors(prof)

    print(f"corpus    {prof['traces']} traces ({prof['distinct_ids']} distinct ids)")
    print(f"spans     {prof['total_spans']} across {prof['traces_with_spans']} traces")
    print(f"sources   {dict(prof['sources'])}")
    print(f"statuses  {dict(prof['statuses'])}")
    print(f"span      {prof['first']} -> {prof['last']}  ({prof['span_days']:.2f} days)")
    print(f"floors    {'UNMET: ' + ' · '.join(unmet) if unmet else 'all met'}")
    if unmet:
        print("\n  NON-REPRESENTATIVE. No rate from this corpus may be published.")
        print("  Volume is not diversity: if one value dominates a column, n is a fiction.")
    return 0


# --------------------------------------------------------------------------- #
# Checks — three deterministic questions about the instrument.
# --------------------------------------------------------------------------- #


def check_has_spans(trace: dict[str, Any]) -> tuple[str, str | None, str]:
    if not trace.get("spans"):
        return "fail", None, "0 spans — nothing downstream can read this run"
    return "pass", None, f"{len(trace['spans'])} spans"


def check_writer_is_code(trace: dict[str, Any]) -> tuple[str, str | None, str]:
    spans = trace.get("spans") or []
    if not spans:
        return "not_applicable", "no_spans", "no spans to attribute"
    writers = Counter(s.get("writer") or "unset" for s in spans)
    if set(writers) == {"unset"}:
        return "not_applicable", "no_writer_field", "no span carries a writer field"
    modelish = sum(n for w, n in writers.items() if str(w).lower() in {"model", "agent", "llm"})
    if modelish:
        return "fail", None, f"{modelish} of {len(spans)} spans written by the model, not by code"
    return "pass", None, f"all {len(spans)} spans attributed to code ({dict(writers)})"


def check_run_record_complete(trace: dict[str, Any]) -> tuple[str, str | None, str]:
    if not trace.get("has_run_record"):
        return "not_applicable", "no_run_record", "no run record on disk"
    missing = [k for k in ("ended_at", "status") if not trace.get(k) or trace.get(k) == "unknown"]
    if missing:
        return "fail", None, f"run record missing {', '.join(missing)}"
    return "pass", None, f"status={trace['status']}, ended_at set"


CHECKS = {
    "CHK-trace-has-spans": check_has_spans,
    "CHK-writer-is-code": check_writer_is_code,
    "CHK-run-record-complete": check_run_record_complete,
}


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval. Every rate you publish gets one of these."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def _liveness(n_decided: int) -> str:
    """blind = never decided · thin = decided too rarely to rate · live = usable."""
    if n_decided == 0:
        return "blind"
    return "thin" if n_decided < MIN_N_FOR_RATE else "live"


def score(traces: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for check_id, fn in CHECKS.items():
        outcomes = Counter()
        reasons: Counter = Counter()
        examples: list[str] = []
        for trace in traces:
            outcome, reason, detail = fn(trace)
            outcomes[outcome] += 1
            if outcome == "not_applicable" and reason:
                reasons[reason] += 1
            if outcome == "fail" and len(examples) < 2:
                examples.append(f"{trace['trace_id']}: {detail}")
        n_decided = outcomes["pass"] + outcomes["fail"]
        rows.append(
            {
                "check_id": check_id,
                "pass": outcomes["pass"],
                "fail": outcomes["fail"],
                "na": outcomes["not_applicable"],
                "n_decided": n_decided,
                "ci": wilson(outcomes["pass"], n_decided) if n_decided else None,
                "top_reason": reasons.most_common(1)[0][0] if reasons else None,
                "examples": examples,
                "liveness": _liveness(n_decided),
            }
        )
    total = sum(r["pass"] + r["fail"] + r["na"] for r in rows)
    na_in_scope = sum(r["na"] for r in rows)  # no not_in_scope checks in this kit
    return {
        "rows": rows,
        "n_results": total,
        "n_na": na_in_scope,
        "na_share": (na_in_scope / total) if total else 0.0,
    }


def cmd_run(args: argparse.Namespace) -> int:
    traces = load_traces(Path(args.traces))
    if not traces:
        print(f"no traces under {args.traces} — run `ingest` first")
        return 2

    prof = profile(traces)
    result = score(traces)
    stamps = [args.kind]
    if unmet_floors(prof):
        stamps.append("NON-REPRESENTATIVE")
    if result["na_share"] > EVIDENCE_STARVED_THRESHOLD:
        stamps.append("EVIDENCE-STARVED")
    blind = [r["check_id"] for r in result["rows"] if r["liveness"] == "blind"]

    print(f"stamps    {' · '.join(stamps)}")
    print(f"corpus    {prof['traces']} traces, {prof['total_spans']} spans")
    print(
        f"results   {result['n_results']} total, {result['n_na']} abstained "
        f"({result['na_share']:.1%}), {len(blind)} check(s) blind"
    )
    print()
    print(f"{'check':<26} {'pass':>5} {'fail':>5} {'n/a':>5} {'decided':>8}  rate")
    print("-" * 76)
    for row in result["rows"]:
        if row["n_decided"] >= MIN_N_FOR_RATE and row["ci"]:
            lo, hi = row["ci"]
            share = row["pass"] / row["n_decided"]
            rate = f"{share:.2f} [95% CI {lo:.2f}, {hi:.2f}]"
        elif row["n_decided"]:
            rate = f"n={row['n_decided']} (too few for a rate)"
        else:
            rate = f"BLIND — {row['top_reason'] or 'never decided'}"
        print(
            f"{row['check_id']:<26} {row['pass']:>5} {row['fail']:>5} "
            f"{row['na']:>5} {row['n_decided']:>8}  {rate}"
        )
    print()
    for row in result["rows"]:
        for example in row["examples"]:
            print(f"  FAIL {row['check_id']}  {example}")

    print()
    print("A green run here asserts exactly one thing:")
    print('  "my instrument can see these three signals on this corpus."')
    print("It asserts nothing about whether the system under test is any good.")
    return 0


# --------------------------------------------------------------------------- #
# Audit — the five questions, answered from the corpus in one pass.
# --------------------------------------------------------------------------- #


def cmd_audit(args: argparse.Namespace) -> int:
    traces = load_traces(Path(args.traces))
    if not traces:
        print(f"no traces under {args.traces} — run `ingest` first")
        return 2
    prof = profile(traces)
    result = score(traces)
    unmet = unmet_floors(prof)

    q0 = "PASS" if prof["total_spans"] else "FAIL"
    q1 = "PASS" if not unmet else "FAIL"
    q4 = "PASS" if result["na_share"] <= EVIDENCE_STARVED_THRESHOLD else "FAIL"

    print("The ten-minute audit\n")
    print(f"0. Writer and reader agree on where logs live?      {q0}")
    seen = f"{prof['traces_with_spans']}/{prof['traces']}"
    print(f"     {prof['total_spans']} spans across {seen} traces")
    print(f"1. Enough traces, and diverse enough?               {q1}")
    print(f"     {' · '.join(unmet) if unmet else 'all floors met'}")
    print("2. How many has a human read, with notes?           ASK YOURSELF")
    print("     This file cannot answer it and neither can any model.")
    print("3. Where did your failure categories come from?     ASK YOURSELF")
    print("     If you cannot point from a category to specific traces, you are")
    print("     testing your imagination.")
    print(f"4. What does a green run assert, in one sentence?    {q4}")
    print(f"     {result['na_share']:.1%} of check results abstained")
    print()
    print("Questions 2 and 3 are the ones that matter and the only ones that cost")
    print("an afternoon. Questions 0, 1 and 4 are free and were the ones I failed.")
    return 0


# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="minieval", description="A tiny eval harness that checks your instrument first."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="turn log directories into traces")
    p_ingest.add_argument("--logs", required=True, help="dir whose subdirs are runs")
    p_ingest.add_argument("--out", default="./traces")
    p_ingest.set_defaults(func=cmd_ingest)

    p_stats = sub.add_parser("stats", help="what the corpus is and what it lacks")
    p_stats.add_argument("--traces", default="./traces")
    p_stats.set_defaults(func=cmd_stats)

    p_run = sub.add_parser("run", help="score the three checks")
    p_run.add_argument("--traces", default="./traces")
    p_run.add_argument("--kind", default="CORPUS", choices=CORPUS_KINDS)
    p_run.set_defaults(func=cmd_run)

    p_audit = sub.add_parser("audit", help="answer the five questions")
    p_audit.add_argument("--traces", default="./traces")
    p_audit.set_defaults(func=cmd_audit)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # `minieval.py run | head` is a normal thing to do. Exit quietly.
        raise SystemExit(0) from None
