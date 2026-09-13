"""CLI entrypoint: ``python -m evals.cli``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, cast

from evals.sampling import StrategyName, sample, write_manifest
from evals.store import TraceExistsError, TraceStore
from evals.trace.builder import TraceBuilder


def _cmd_trace_backfill(args: argparse.Namespace) -> int:
    root = Path(args.workspace_root)
    store = TraceStore(root=Path(args.traces_root) if args.traces_root else None)
    if not root.is_dir():
        print(f"workspace root not found: {root}", file=sys.stderr)
        return 1

    built = 0
    warned = 0
    skipped = 0
    by_backend: Counter[str] = Counter()
    by_status: Counter[str] = Counter()

    dirs = sorted(d for d in root.iterdir() if d.is_dir())
    if args.limit is not None:
        dirs = dirs[: args.limit]

    for ws in dirs:
        # Skip obvious non-run dirs
        if ws.name in {".git", "__pycache__", "docs", "node_modules"}:
            continue
        builder = TraceBuilder(backend="crewai", tier="C", store=store)
        try:
            trace = builder.from_workspace(ws)
            store.write(trace)
            built += 1
            by_backend[trace.backend] += 1
            by_status[trace.status] += 1
            if trace.warnings:
                warned += 1
            print(f"built {trace.trace_id} from {ws.name}")
        except TraceExistsError:
            skipped += 1
            print(f"skip existing for {ws.name}")
        except Exception as exc:  # noqa: BLE001 — backfill must continue
            warned += 1
            print(f"warn {ws.name}: {exc}", file=sys.stderr)

    print(
        json.dumps(
            {
                "built": built,
                "warned": warned,
                "skipped": skipped,
                "by_backend": dict(by_backend),
                "by_status": dict(by_status),
            },
            indent=2,
        )
    )
    return 0


def _cmd_index_rebuild(args: argparse.Namespace) -> int:
    store = TraceStore(root=Path(args.traces_root) if args.traces_root else None)
    n = store.rebuild_index()
    print(f"indexed {n} traces")
    return 0


def _cmd_index_stats(args: argparse.Namespace) -> int:
    store = TraceStore(root=Path(args.traces_root) if args.traces_root else None)
    rows = store.stats()
    print(f"{'backend':<20} {'scenario':<40} {'status':<16} n")
    for backend, scenario, status, n in rows:
        print(f"{backend:<20} {scenario:<40} {status:<16} {n}")
    return 0


def _cmd_sample(args: argparse.Namespace) -> int:
    store = TraceStore(root=Path(args.traces_root) if args.traces_root else None)
    filters: dict[str, Any] = {}
    if args.backend:
        filters["backend"] = args.backend
    if args.scenario_id:
        filters["scenario_id"] = args.scenario_id
    if args.status:
        filters["status"] = args.status

    rows = store.query(**filters)
    strategy = cast(StrategyName, args.strategy)
    manifest = sample(rows, strategy, args.n, args.seed, filters=filters)
    samples_root = Path(args.samples_root) if args.samples_root else None
    path = write_manifest(manifest, samples_root=samples_root)
    print(
        json.dumps(
            {
                "sample_id": manifest.sample_id,
                "path": str(path),
                "strategy": manifest.strategy,
                "seed": manifest.seed,
                "n_requested": manifest.n,
                "n_selected": len(manifest.selection),
                "corpus_state_hash": manifest.corpus_state_hash,
                "imbalances": len(manifest.imbalances),
            },
            indent=2,
        )
    )
    return 0


def _cmd_taxonomy_coverage(args: argparse.Namespace) -> int:
    from evals.checks import all_checks, ensure_checks_loaded
    from evals.taxonomy.loader import load_taxonomy, write_coverage_md

    ensure_checks_loaded()
    tax = load_taxonomy(require_examples=bool(getattr(args, "require_examples", False)))
    by_fm: dict[str, list[str]] = {}
    for chk in all_checks():
        if chk.failure_mode_id:
            by_fm.setdefault(chk.failure_mode_id, []).append(chk.id)
    out = Path(args.out) if args.out else None
    path = write_coverage_md(tax, check_ids_by_fm=by_fm, out_path=out)
    print(f"wrote {path}")
    return 0


def _cmd_taxonomy_propose(args: argparse.Namespace) -> int:
    from evals.taxonomy.propose import (
        format_proposals,
        proposals_as_dicts,
        propose_from_annotations,
    )

    if not args.from_annotations:
        print("error: pass --from-annotations", file=sys.stderr)
        return 2
    root = Path(args.annotations_root) if args.annotations_root else None
    clusters = propose_from_annotations(annotations_root=root)
    if args.json:
        print(json.dumps(proposals_as_dicts(clusters), indent=2))
    else:
        print(format_proposals(clusters))
    return 0


def _cmd_annotate(args: argparse.Namespace) -> int:
    from evals.annotate import run_annotate_session

    annotator = args.annotator or os.environ.get("USER") or os.environ.get("LOGNAME") or "anon"
    store = TraceStore(root=Path(args.traces_root) if args.traces_root else None)
    batch = Path(args.batch_file) if args.batch_file else None
    result = run_annotate_session(
        sample_id=args.sample,
        annotator=annotator,
        store=store,
        samples_root=Path(args.samples_root) if args.samples_root else None,
        annotations_root=Path(args.annotations_root) if args.annotations_root else None,
        fixtures_root=Path(args.fixtures_root) if args.fixtures_root else None,
        batch_file=batch,
    )
    print(json.dumps(result, indent=2))
    return 0


def _cmd_golden_stats(args: argparse.Namespace) -> int:
    from evals.golden import golden_stats_table

    root = Path(args.golden_root) if args.golden_root else None
    print(golden_stats_table(golden_root=root))
    return 0


def _cmd_golden_label(args: argparse.Namespace) -> int:
    """Confirm labels for a judge FM (interactive or --batch-file)."""
    from evals.golden import append_golden, load_golden, make_label
    from evals.taxonomy.loader import load_taxonomy

    tax = load_taxonomy()
    fm = tax.by_id().get(args.fm)
    if fm is None:
        print(f"unknown failure mode: {args.fm}", file=sys.stderr)
        return 1

    golden_root = Path(args.golden_root) if args.golden_root else None
    annotator = args.annotator or os.environ.get("USER") or "anon"
    existing = {u.labeling_unit_id for u in load_golden(args.fm, golden_root=golden_root)}

    if args.batch_file:
        written = 0
        skipped = 0
        for line in Path(args.batch_file).read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            item = json.loads(text)
            unit = make_label(
                trace_id=str(item["trace_id"]),
                span_id=str(item.get("span_id") or "run"),
                failure_mode_id=args.fm,
                human_label=item["human_label"],
                annotator=annotator,
                notes=str(item.get("notes") or ""),
            )
            if unit.labeling_unit_id in existing:
                skipped += 1
                continue
            append_golden(unit, golden_root=golden_root)
            existing.add(unit.labeling_unit_id)
            written += 1
        print(json.dumps({"written": written, "skipped": skipped, "fm": args.fm}, indent=2))
        return 0

    candidates = [*fm.positive_examples, *fm.negative_examples]
    if not candidates:
        print(
            f"no candidate units for {args.fm} "
            "(detection:check FMs use fixtures; judge FMs need examples first)"
        )
        return 0

    print(
        f"Interactive labeling for {args.fm} ({fm.detection}). "
        f"{len(candidates)} taxonomy example(s). "
        "Use --batch-file for non-interactive tests."
    )
    written = 0
    for ex in candidates:
        default = "present" if ex in fm.positive_examples else "absent"
        if args.confirm_examples:
            label = default
        else:
            raw = (
                input(
                    f"{ex.trace_id} / {ex.span_id}  present|absent "
                    f"[default={default}, s=skip, q=quit]: "
                )
                .strip()
                .lower()
            )
            if raw in {"q", "quit"}:
                break
            if raw in {"s", "skip"}:
                continue
            if raw in {"", "d"}:
                label = default
            elif raw in {"present", "p", "1"}:
                label = "present"
            elif raw in {"absent", "a", "0"}:
                label = "absent"
            else:
                print("unrecognized; skip")
                continue
        unit = make_label(
            trace_id=ex.trace_id,
            span_id=ex.span_id,
            failure_mode_id=args.fm,
            human_label=label,  # type: ignore[arg-type]
            annotator=annotator,
        )
        if unit.labeling_unit_id in existing:
            print(f"skip existing {unit.labeling_unit_id}")
            continue
        append_golden(unit, golden_root=golden_root)
        existing.add(unit.labeling_unit_id)
        written += 1
        print(f"wrote {unit.labeling_unit_id} split={unit.split} label={unit.human_label}")
    print(json.dumps({"written": written, "fm": args.fm}, indent=2))
    return 0


def _cmd_checks_validate(args: argparse.Namespace) -> int:
    from evals.checks.validation import (
        format_validation_report,
        validate_all_check_fms,
        validate_fm_checks,
    )

    payload = validate_fm_checks(args.fm) if args.fm else validate_all_check_fms()
    print(format_validation_report(payload))
    if args.json:
        print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 1


def _cmd_fixtures_redact(args: argparse.Namespace) -> int:
    from evals.redact import lint_secrets, redact_tree

    root = Path(args.root)
    changed = redact_tree(root, dry_run=args.dry_run)
    print(f"{'would change' if args.dry_run else 'redacted'}: {len(changed)} files under {root}")
    for p in changed:
        print(f"  {p}")
    if args.lint:
        findings = lint_secrets(sorted(root.rglob("*")) if root.is_dir() else [root])
        if findings:
            for path, name, snippet in findings:
                print(f"LINT {name}: {path}: {snippet}", file=sys.stderr)
            return 1
        print("redaction lint: clean")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    tier = args.tier.upper()
    if tier == "A":
        from evals.tier_a import run_tier_a

        report, code, paths = run_tier_a(
            traces_dir=Path(args.traces_dir) if args.traces_dir else None,
            out_dir=Path(args.out) if args.out else None,
            warn_only=bool(args.warn_only),
            block_network=not bool(args.allow_network),
        )
        print(f"tier A verdict={report.verdict} cost=${report.cost.total_usd:.4f}")
        for name, path in paths.items():
            print(f"  {name}: {path}")
        gate_md = paths["report.json"].parent / "gate.md"
        if gate_md.exists() and args.github_summary:
            summary_path = Path(args.github_summary)
            summary_path.write_text(gate_md.read_text(encoding="utf-8"), encoding="utf-8")
        return code

    if tier in {"B", "C"}:
        print(
            f"Tier {tier} live runs are handled by evals.run_evals; "
            "use that entrypoint for budgeted live execution.",
            file=sys.stderr,
        )
        return 2
    print(f"unknown tier: {tier}", file=sys.stderr)
    return 2


def _cmd_cache_warm(args: argparse.Namespace) -> int:
    """Populate judge cache from a live tier (R11.7). Stub when warm helper absent."""
    tier = args.tier.upper()
    try:
        from evals.judges import base as judges_base
    except ImportError:
        print(f"cache warm --tier {tier}: judges package unavailable; no-op stub.")
        return 0
    warm = getattr(judges_base, "warm_cache_from_tier", None)
    if warm is None:
        print(
            f"cache warm --tier {tier}: no warm helper registered yet; "
            "no-op stub (populate evals/judges/cache via a live run)."
        )
        return 0
    return int(warm(tier=tier))


def _cmd_baseline_accept(args: argparse.Namespace) -> int:
    from evals.aggregate import SuiteReport
    from evals.gate import accept_baseline

    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"report not found: {report_path}", file=sys.stderr)
        return 2
    report = SuiteReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    # Ensure tier matches flag
    if args.tier:
        report = report.model_copy(update={"tier": args.tier.upper()})
    try:
        path = accept_baseline(
            report,
            reason=args.reason,
            baselines_dir=Path(args.baselines_dir) if args.baselines_dir else None,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"accepted baseline → {path}")
    return 0


def _cmd_guardrail_mine(args: argparse.Namespace) -> int:
    from evals.guardrail_eval import mine_false_positive_candidates

    store = TraceStore(root=Path(args.traces_root) if args.traces_root else None)
    out = Path(args.out)
    queue = mine_false_positive_candidates(store, out_path=out)
    print(json.dumps({"candidates": len(queue), "out": str(out)}, indent=2))
    return 0


def _cmd_guardrail_eval(args: argparse.Namespace) -> int:
    from evals.corpora.format import load_corpus
    from evals.guardrail_eval import (
        CORPORA_DIR,
        DEFAULT_INVOKERS,
        GuardrailEvaluator,
        evaluate_all,
        scope_relevance_sweep_values,
    )

    results = evaluate_all(
        Path(args.corpora_dir) if args.corpora_dir else None,
        thresholds_path=Path(args.thresholds) if args.thresholds else None,
    )
    exit_code = 0
    for result in results:
        print(result.report_line)
        if result.gate_fail:
            exit_code = 1
            print(
                f"  GATE FAIL: recall<{result.thresholds.recall_floor} or "
                f"FPR>{result.thresholds.fpr_ceiling}",
                file=sys.stderr,
            )

    if args.sweep:
        corpora_dir = Path(args.corpora_dir) if args.corpora_dir else None
        root = corpora_dir or CORPORA_DIR
        path = root / "scope_relevance.jsonl"
        if path.is_file() and "scope_relevance" in DEFAULT_INVOKERS:
            corpus = load_corpus(path)
            evaluator = GuardrailEvaluator("scope_relevance", DEFAULT_INVOKERS["scope_relevance"])
            values = scope_relevance_sweep_values()
            curve = evaluator.sweep(corpus, "min_relevance", values)
            configured = 0.15
            print("scope_relevance sweep (min_relevance):")
            for value, counts in curve:
                marker = " <-- configured" if abs(value - configured) < 1e-9 else ""
                print(
                    f"  floor={value:.2f} precision={counts.precision:.2f} "
                    f"recall={counts.recall:.2f} FPR={counts.false_positive_rate:.2f}"
                    f"{marker}"
                )
    return exit_code


def _cmd_judge_align(args: argparse.Namespace) -> int:
    """Dev-split alignment only (R8.4). No live API calls."""
    from evals.alignment import ADVISORY_NO_LIVE_REASON, write_advisory_alignment
    from evals.judges.base import load_judge_spec, validate_prompts

    specs = [load_judge_spec(Path(args.prompt))] if args.prompt else validate_prompts()
    for spec in specs:
        path = write_advisory_alignment(spec.judge_id, prompt_hash=spec.prompt_hash)
        print(
            json.dumps(
                {
                    "judge_id": spec.judge_id,
                    "split": "dev",
                    "path": str(path),
                    "eligible_to_gate": False,
                    "reason": ADVISORY_NO_LIVE_REASON,
                },
                indent=2,
            )
        )
    return 0


def _cmd_judge_validate(args: argparse.Namespace) -> int:
    """Test-split validation once per prompt_hash unless --allow-retest (R8.4)."""
    from evals.alignment import (
        ADVISORY_NO_LIVE_REASON,
        append_validation_log,
        validation_log_has,
        write_advisory_alignment,
    )
    from evals.judges.base import load_judge_spec, validate_prompts

    specs = [load_judge_spec(Path(args.prompt))] if args.prompt else validate_prompts()
    for spec in specs:
        if validation_log_has(spec.judge_id, spec.prompt_hash) and not args.allow_retest:
            print(
                f"refusing retest of {spec.judge_id} "
                f"prompt_hash={spec.prompt_hash[:12]}… "
                f"(pass --allow-retest to override)",
                file=sys.stderr,
            )
            return 1
        path = write_advisory_alignment(spec.judge_id, prompt_hash=spec.prompt_hash)
        append_validation_log(
            spec.judge_id,
            spec.prompt_hash,
            allow_retest=bool(args.allow_retest),
        )
        print(
            json.dumps(
                {
                    "judge_id": spec.judge_id,
                    "split": "test",
                    "path": str(path),
                    "eligible_to_gate": False,
                    "reason": ADVISORY_NO_LIVE_REASON,
                    "allow_retest": bool(args.allow_retest),
                },
                indent=2,
            )
        )
    return 0


def _cmd_ladder_run(args: argparse.Namespace) -> int:
    from evals.arms.ladder import SweepBudgetError, run_sweep

    arm_ids = [a.strip() for a in str(args.arms).split(",") if a.strip()]
    try:
        result = run_sweep(
            args.scenario,
            arm_ids,
            int(args.n),
            execute=bool(args.execute),
            out_dir=Path(args.out) if args.out else None,
        )
    except SweepBudgetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, default=str))
    return 0


def _cmd_ladder_report(args: argparse.Namespace) -> int:
    """Render a ladder table from a traces JSON file (offline)."""
    from evals.ladder_report import ClaimRefusalError, markdown_from_ladder_json, render_ladder

    raw = json.loads(Path(args.traces).read_text(encoding="utf-8"))
    traces = raw if isinstance(raw, list) else list(raw.get("traces") or [])
    try:
        doc = render_ladder(
            traces,
            allow_mixed_model=bool(args.allow_mixed_model),
            allow_underpowered=bool(args.allow_underpowered),
        )
    except ClaimRefusalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.format == "md":
        print(markdown_from_ladder_json(doc))
    else:
        print(json.dumps(doc, indent=2, default=str))
    return 0


def _cmd_ablation_status(args: argparse.Namespace) -> int:
    from evals.arms.ablation_store import status_table

    print(status_table(Path(args.results_dir) if args.results_dir else None))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse parser."""
    parser = argparse.ArgumentParser(prog="python -m evals.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    trace = sub.add_parser("trace", help="trace corpus commands")
    trace_sub = trace.add_subparsers(dest="trace_command", required=True)
    backfill = trace_sub.add_parser("backfill", help="build traces from workspaces")
    backfill.add_argument("--workspace-root", default="./workspace")
    backfill.add_argument("--traces-root", default=None)
    backfill.add_argument("--limit", type=int, default=None)
    backfill.set_defaults(func=_cmd_trace_backfill)

    index = sub.add_parser("index", help="SQLite index commands")
    index_sub = index.add_subparsers(dest="index_command", required=True)
    rebuild = index_sub.add_parser("rebuild", help="rebuild index from traces")
    rebuild.add_argument("--traces-root", default=None)
    rebuild.set_defaults(func=_cmd_index_rebuild)
    stats = index_sub.add_parser("stats", help="print corpus stats")
    stats.add_argument("--traces-root", default=None)
    stats.set_defaults(func=_cmd_index_stats)

    sample_p = sub.add_parser("sample", help="sample traces into a manifest")
    sample_p.add_argument(
        "--strategy",
        required=True,
        choices=["random", "stratified", "extremes", "failed-only", "unlabeled"],
    )
    sample_p.add_argument("-n", type=int, required=True, help="sample size")
    sample_p.add_argument("--seed", type=int, default=0)
    sample_p.add_argument("--traces-root", default=None)
    sample_p.add_argument("--samples-root", default=None)
    sample_p.add_argument("--backend", default=None)
    sample_p.add_argument("--scenario-id", default=None)
    sample_p.add_argument("--status", default=None)
    sample_p.set_defaults(func=_cmd_sample)

    annotate = sub.add_parser("annotate", help="open-coding annotation TUI (R3)")
    annotate.add_argument("--sample", required=True, help="sample_id from evals/samples/")
    annotate.add_argument("--annotator", default=None)
    annotate.add_argument("--batch-file", default=None, help="JSONL for non-interactive tests")
    annotate.add_argument("--traces-root", default=None)
    annotate.add_argument("--samples-root", default=None)
    annotate.add_argument("--annotations-root", default=None)
    annotate.add_argument("--fixtures-root", default=None)
    annotate.set_defaults(func=_cmd_annotate)

    taxonomy = sub.add_parser("taxonomy", help="failure taxonomy commands")
    taxonomy_sub = taxonomy.add_subparsers(dest="taxonomy_command", required=True)
    coverage = taxonomy_sub.add_parser("coverage", help="write evals/taxonomy/COVERAGE.md")
    coverage.add_argument("--out", default=None, help="override COVERAGE.md path")
    coverage.add_argument(
        "--require-examples",
        action="store_true",
        help="fail load if any active FM lacks pos/neg examples",
    )
    coverage.set_defaults(func=_cmd_taxonomy_coverage)
    propose = taxonomy_sub.add_parser(
        "propose",
        help="cluster open-coding tags into FM candidates (does not auto-add)",
    )
    propose.add_argument(
        "--from-annotations",
        action="store_true",
        help="read evals/annotations/*.jsonl",
    )
    propose.add_argument("--annotations-root", default=None)
    propose.add_argument("--json", action="store_true")
    propose.set_defaults(func=_cmd_taxonomy_propose)

    golden = sub.add_parser("golden", help="golden labeling set (R8)")
    golden_sub = golden.add_subparsers(dest="golden_command", required=True)
    g_label = golden_sub.add_parser("label", help="append labels for one FM")
    g_label.add_argument("--fm", required=True, help="FM-###")
    g_label.add_argument("--annotator", default=None)
    g_label.add_argument("--batch-file", default=None)
    g_label.add_argument("--golden-root", default=None)
    g_label.add_argument(
        "--confirm-examples",
        action="store_true",
        help="accept taxonomy example polarity without prompting",
    )
    g_label.set_defaults(func=_cmd_golden_label)
    g_stats = golden_sub.add_parser("stats", help="print golden-set counts")
    g_stats.add_argument("--golden-root", default=None)
    g_stats.set_defaults(func=_cmd_golden_stats)

    checks = sub.add_parser("checks", help="deterministic check commands")
    checks_sub = checks.add_subparsers(dest="checks_command", required=True)
    c_val = checks_sub.add_parser(
        "validate",
        help="TPR/TNR of check FMs against fixture fail/pass labels",
    )
    c_val.add_argument("--fm", default=None, help="single FM-### (default: all check FMs)")
    c_val.add_argument("--json", action="store_true")
    c_val.set_defaults(func=_cmd_checks_validate)

    fixtures = sub.add_parser("fixtures", help="fixture corpus commands")
    fixtures_sub = fixtures.add_subparsers(dest="fixtures_command", required=True)
    redact = fixtures_sub.add_parser("redact", help="scrub secrets from fixture files")
    redact.add_argument(
        "--root",
        default="evals/fixtures",
        help="directory to redact (default: evals/fixtures)",
    )
    redact.add_argument("--dry-run", action="store_true")
    redact.add_argument(
        "--lint",
        action="store_true",
        help="fail if residual secrets remain after redaction",
    )
    redact.set_defaults(func=_cmd_fixtures_redact)

    run_p = sub.add_parser("run", help="run an eval tier")
    run_p.add_argument("--tier", required=True, choices=["A", "B", "C", "a", "b", "c"])
    run_p.add_argument("--traces-dir", default=None, help="Tier A fixture traces dir")
    run_p.add_argument("--out", default=None, help="output directory for report artifacts")
    run_p.add_argument(
        "--warn-only",
        action="store_true",
        help="exit 0 even on gate regressions (Phase 9 soak)",
    )
    run_p.add_argument(
        "--allow-network",
        action="store_true",
        help="do not block sockets (Tier A default: blocked)",
    )
    run_p.add_argument(
        "--github-summary",
        default=None,
        help="write gate markdown to this path (e.g. $GITHUB_STEP_SUMMARY)",
    )
    run_p.set_defaults(func=_cmd_run)

    cache = sub.add_parser("cache", help="judge verdict cache commands")
    cache_sub = cache.add_subparsers(dest="cache_command", required=True)
    warm = cache_sub.add_parser("warm", help="populate cache from a live tier")
    warm.add_argument("--tier", required=True, choices=["A", "B", "C", "a", "b", "c"])
    warm.set_defaults(func=_cmd_cache_warm)

    baseline = sub.add_parser("baseline", help="baseline management")
    baseline_sub = baseline.add_subparsers(dest="baseline_command", required=True)
    accept = baseline_sub.add_parser("accept", help="accept a report as the new baseline")
    accept.add_argument("--tier", required=True, choices=["A", "B", "C", "a", "b", "c"])
    accept.add_argument("--reason", required=True, help="why this baseline is accepted")
    accept.add_argument("--report", required=True, help="path to report.json")
    accept.add_argument("--baselines-dir", default=None)
    accept.set_defaults(func=_cmd_baseline_accept)

    guardrail = sub.add_parser("guardrail", help="guardrail corpus evaluation (R6)")
    guardrail_sub = guardrail.add_subparsers(dest="guardrail_command", required=True)
    mine = guardrail_sub.add_parser(
        "mine",
        help="mine FP candidates from accepted runs with guardrail fails",
    )
    mine.add_argument("--traces-root", default=None)
    mine.add_argument(
        "--out",
        default="evals/corpora/guardrails/mine_queue.jsonl",
        help="labeling queue JSONL path",
    )
    mine.set_defaults(func=_cmd_guardrail_mine)
    geval = guardrail_sub.add_parser("eval", help="score labeled guardrail corpora")
    geval.add_argument("--corpora-dir", default=None)
    geval.add_argument("--thresholds", default=None)
    geval.add_argument(
        "--sweep",
        action="store_true",
        help="emit scope-relevance min_relevance PR curve (0.05–0.50)",
    )
    geval.set_defaults(func=_cmd_guardrail_eval)

    judge = sub.add_parser("judge", help="binary judge alignment (R7/R8)")
    judge_sub = judge.add_subparsers(dest="judge_command", required=True)
    align = judge_sub.add_parser("align", help="dev-split alignment (no test leakage)")
    align.add_argument("--prompt", default=None, help="single prompt file path")
    align.set_defaults(func=_cmd_judge_align)
    jvalidate = judge_sub.add_parser(
        "validate",
        help="test-split validation once per prompt_hash",
    )
    jvalidate.add_argument("--prompt", default=None, help="single prompt file path")
    jvalidate.add_argument(
        "--allow-retest",
        action="store_true",
        help="permit a second test-split run for the same prompt_hash",
    )
    jvalidate.set_defaults(func=_cmd_judge_validate)

    drift = sub.add_parser("drift", help="week-over-week receipt drift (warn-only, $0)")
    drift.add_argument("--current", required=True, help="directory of current receipts")
    drift.add_argument("--previous", required=True, help="directory of previous receipts")
    drift.set_defaults(func=_cmd_drift)

    ladder = sub.add_parser("ladder", help="harness-alignment ladder sweeps")
    ladder_sub = ladder.add_subparsers(dest="ladder_command", required=True)
    lrun = ladder_sub.add_parser("run", help="resolve (default) or execute a ladder sweep")
    lrun.add_argument("--scenario", required=True)
    lrun.add_argument("--arms", required=True, help="comma-separated arm ids")
    lrun.add_argument("-n", "--n", type=int, default=1)
    lrun.add_argument(
        "--execute",
        action="store_true",
        help="required for any live call; default is dry-run",
    )
    lrun.add_argument("--out", default=None)
    lrun.set_defaults(func=_cmd_ladder_run)

    lreport = ladder_sub.add_parser(
        "report",
        help="render ladder JSON/Markdown from traces (activates evals.ladder_report)",
    )
    lreport.add_argument("--traces", required=True, help="JSON file: a list of traces")
    lreport.add_argument("--format", choices=("json", "md"), default="json")
    lreport.add_argument("--allow-mixed-model", action="store_true")
    lreport.add_argument("--allow-underpowered", action="store_true")
    lreport.set_defaults(func=_cmd_ladder_report)

    ablation = sub.add_parser("ablation", help="ablation result store")
    ablation_sub = ablation.add_subparsers(dest="ablation_command", required=True)
    astatus = ablation_sub.add_parser("status", help="current | STALE | never measured")
    astatus.add_argument("--results-dir", default=None)
    astatus.set_defaults(func=_cmd_ablation_status)

    coverage = sub.add_parser(
        "coverage", help="check liveness and signal-chain coverage ($0, offline)"
    )
    coverage_sub = coverage.add_subparsers(dest="coverage_command", required=True)

    cov_live = coverage_sub.add_parser(
        "liveness", help="which checks ever decided anything over a corpus"
    )
    cov_live.add_argument("--traces-root", default=None, help="default: evals/traces")
    cov_live.add_argument(
        "--fixtures", default=None, help="fixture corpus root; default: evals/fixtures/traces"
    )
    cov_live.add_argument(
        "--no-fixtures", action="store_true", help="corpus column only, no comparison"
    )
    cov_live.add_argument(
        "--from-report",
        default=None,
        help="fold an existing SuiteReport JSON instead of re-running checks",
    )
    cov_live.add_argument("--json", action="store_true")
    cov_live.add_argument("--out", default=None)
    cov_live.set_defaults(func=_cmd_coverage_liveness)

    cov_sig = coverage_sub.add_parser(
        "signals", help="span type -> harness writer -> parser -> check inventory"
    )
    cov_sig.add_argument("--json", action="store_true")
    cov_sig.add_argument("--out", default=None)
    cov_sig.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when a check reads a span type no parser produces (R4.6)",
    )
    cov_sig.set_defaults(func=_cmd_coverage_signals)

    return parser


def _cmd_drift(args: argparse.Namespace) -> int:
    from evals.drift import drift_from_dirs

    report = drift_from_dirs(Path(args.current), Path(args.previous))
    print(report.model_dump_json(indent=2))
    return 0


def _cmd_coverage_liveness(args: argparse.Namespace) -> int:
    """Report which checks ever decided anything (eval-coverage R2.7, R2.8)."""
    from evals.coverage import (
        liveness_from_report,
        liveness_over_corpus,
        load_traces,
        render_markdown,
        render_side_by_side,
    )

    if args.from_report:
        report = liveness_from_report(Path(args.from_report))
        text = report.model_dump_json(indent=2) if args.json else render_markdown(report)
        _emit_coverage(text, args.out)
        return 0

    corpus_root = Path(args.traces_root) if args.traces_root else Path("evals/traces")
    traces, unloadable = load_traces(corpus_root)
    corpus = liveness_over_corpus(
        traces,
        corpus_label=str(corpus_root),
        corpus_kind="CORPUS",
        n_unloadable=unloadable,
    )

    fixtures_root = Path(args.fixtures) if args.fixtures else Path("evals/fixtures/traces")
    fixtures = None
    if fixtures_root.is_dir() and not args.no_fixtures:
        fixture_traces, fixture_unloadable = load_traces(fixtures_root)
        fixtures = liveness_over_corpus(
            fixture_traces,
            corpus_label=str(fixtures_root),
            corpus_kind="FIXTURE-ONLY",
            n_unloadable=fixture_unloadable,
        )

    if args.json:
        payload: dict[str, Any] = {"corpus": corpus.model_dump(mode="json")}
        if fixtures is not None:
            payload["fixtures"] = fixtures.model_dump(mode="json")
        _emit_coverage(json.dumps(payload, indent=2), args.out)
        return 0

    if fixtures is not None:
        text = render_side_by_side(fixtures, corpus) + "\n" + render_markdown(corpus)
    else:
        text = render_markdown(corpus)
    _emit_coverage(text, args.out)
    return 0


def _cmd_coverage_signals(args: argparse.Namespace) -> int:
    """Report the signal chain statically — correct on an empty repo (R4.5, R4.6)."""
    from evals.coverage import render_signals_markdown, signal_chain

    rows = signal_chain()
    if args.json:
        _emit_coverage(json.dumps([r.model_dump(mode="json") for r in rows], indent=2), args.out)
    else:
        _emit_coverage(render_signals_markdown(rows), args.out)

    if args.strict:
        broken = [r.span_type for r in rows if "unreachable_signal" in r.flags]
        if broken:
            print(
                f"unreachable signals (a check reads them, no parser produces them): {broken}",
                file=sys.stderr,
            )
            return 1
    return 0


def _emit_coverage(text: str, out: str | None) -> None:
    """Write *text* to *out* or stdout."""
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    else:
        print(text)


def main(argv: list[str] | None = None) -> int:
    """CLI main."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
