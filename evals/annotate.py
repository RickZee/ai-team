"""Open-coding annotation TUI for error analysis (R3 / design §4.3).

IMPORTANT (R3.7): This interface MUST NEVER display LLM-generated output —
no judge verdicts, no model-proposed tags, no autocomplete from an LLM, and
no "suggested" failure modes. Anchoring a human annotator on a model's guess
corrupts the ground truth the entire eval harness rests on. Do not "helpfully"
add AI assistance here; open coding is deliberately unguided.

Task 5.2 (production open-coding of a live corpus) remains a human step —
see ``evals/golden/README.md``. This module only provides the tooling.

``render_trace_card`` is also reused as a judge ``evidence_builder`` so humans
and judges see comparable evidence (design §4.3 / R7.8).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from evals.sampling import SampleManifest
from evals.store import TraceStore
from evals.trace.models import Trace

_DEFAULT_ANNOTATIONS_ROOT = Path("evals/annotations")
_DEFAULT_SAMPLES_ROOT = Path("evals/samples")
_DEFAULT_FIXTURES_ROOT = Path("evals/fixtures/traces")
_PREVIEW_LINES = 60

_SECURITY_REPORT_NAMES = ("docs/security_report.md", "security_report.md")
_TEST_OUTPUT_NAMES = (
    "docs/test_results.json",
    "test_results.json",
    "docs/pytest_output.txt",
)


class AnnotationRecord(BaseModel):
    """One append-only open-coding annotation line (R3.3–R3.4)."""

    trace_id: str = Field(description="Annotated trace id")
    sample_id: str = Field(description="Sample manifest id this session used")
    annotator: str = Field(description="Annotator identity (local username or flag)")
    annotated_at: datetime = Field(description="UTC timestamp when the record was written")
    note: str = Field(default="", description="Free-text open-coding note")
    tags: list[str] = Field(
        default_factory=list,
        description="Provisional tags invented during open coding (not taxonomy ids)",
    )
    first_failure_span_id: str | None = Field(
        default=None,
        description="First upstream failure span id, if selected",
    )


def annotations_path(
    annotator: str,
    *,
    annotations_root: Path | None = None,
) -> Path:
    """Return ``evals/annotations/<annotator>.jsonl``."""
    root = Path(annotations_root) if annotations_root is not None else _DEFAULT_ANNOTATIONS_ROOT
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in annotator.strip()) or "anon"
    return root / f"{safe}.jsonl"


def load_annotations(path: Path) -> list[AnnotationRecord]:
    """Load annotation records from an append-only JSONL file."""
    if not path.is_file():
        return []
    out: list[AnnotationRecord] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            out.append(AnnotationRecord.model_validate_json(text))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid annotation at {path}:{line_no}: {exc}") from exc
    return out


def annotated_trace_ids(path: Path) -> set[str]:
    """Return the set of ``trace_id`` values already present in *path*."""
    return {a.trace_id for a in load_annotations(path)}


def append_annotation(
    record: AnnotationRecord,
    *,
    annotations_root: Path | None = None,
) -> Path:
    """Append one annotation line; never rewrite prior lines (R3.4)."""
    path = annotations_path(record.annotator, annotations_root=annotations_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(record.model_dump_json() + "\n")
    return path


def saturation_streak(records: Sequence[AnnotationRecord]) -> int:
    """Count consecutive trailing annotations that introduced no new tag (R3.6)."""
    if not records:
        return 0
    seen: set[str] = set()
    streak = 0
    for rec in records:
        new_tags = [t for t in rec.tags if t not in seen]
        if new_tags:
            streak = 0
            seen.update(new_tags)
        else:
            streak += 1
            seen.update(rec.tags)
    return streak


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


def _preview_text(text: str, *, max_lines: int = _PREVIEW_LINES) -> str:
    lines = text.splitlines()
    clipped = lines[:max_lines]
    body = "\n".join(clipped)
    if len(lines) > max_lines:
        body += f"\n… ({len(lines) - max_lines} more lines omitted)"
    return body


def _artifact_preview(trace: Trace, names: Sequence[str]) -> str | None:
    """Return first matching artifact text preview, or None."""
    by_path = {a.path: a for a in trace.artifacts}
    for name in names:
        if name not in by_path:
            continue
        content = trace.read_artifact(name)
        if content is None:
            inline = (trace.raw_result.get("artifact_text") or {}).get(name)
            if isinstance(inline, str):
                content = inline
        if content:
            return f"## {name} (first {_PREVIEW_LINES} lines)\n{_preview_text(content)}"
    return None


def render_trace_card(trace: Trace, *, max_spans: int = 40) -> str:
    """Render a compact review card for open coding / judge evidence (R3.2).

    Deliberately omits LLM message bodies and any model-generated suggestions
    (R3.7). Phase payloads may include truncated structural fields only.

    Args:
        trace: Trace to summarize.
        max_spans: Cap on the numbered span list (judge evidence builders use this).
    """
    lines: list[str] = [
        f"trace_id:     {trace.trace_id}",
        f"scenario_id:  {trace.scenario_id}",
        f"backend:      {trace.backend}",
        f"status:       {trace.status}",
        f"started_at:   {trace.started_at.isoformat()}",
        f"ended_at:     {trace.ended_at.isoformat() if trace.ended_at else '—'}",
        f"tier:         {trace.provenance.tier}",
        "",
        "## Phase timeline",
    ]
    phase_spans = [s for s in trace.spans if s.type in ("phase_start", "phase_end")]
    if not phase_spans:
        lines.append("  (none)")
    else:
        for s in phase_spans:
            lines.append(
                f"  [{s.span_id}] {s.type} phase={s.phase or '?'} "
                f"agent={s.agent_role or '—'} dur={_fmt_duration(s.duration_s)}"
            )

    retries = trace.spans_of("retry")
    errors = trace.errors()
    lines.extend(["", f"## Retries ({len(retries)}) / Errors ({len(errors)})"])
    if not retries and not errors:
        lines.append("  (none)")
    for s in retries[:20]:
        reason = s.payload.get("reason") or s.payload.get("error") or ""
        lines.append(f"  retry [{s.span_id}] {reason!s}"[:120])
    for s in errors[:20]:
        msg = s.payload.get("message") or s.payload.get("error") or s.payload
        lines.append(f"  error [{s.span_id}] {msg!s}"[:120])

    guards = trace.spans_of("guardrail_check")
    lines.extend(["", f"## Guardrails ({len(guards)})"])
    if not guards:
        lines.append("  (none)")
    for s in guards[:20]:
        outcome = s.payload.get("outcome") or s.payload.get("status") or "?"
        name = s.payload.get("name") or s.payload.get("guardrail") or "guardrail"
        lines.append(f"  [{s.span_id}] {name} → {outcome}")

    cost = trace.cost
    lines.extend(
        [
            "",
            "## Spend",
            f"  usd={cost.usd} source={cost.source} "
            f"in={cost.input_tokens} out={cost.output_tokens}",
        ]
    )

    lines.extend(["", "## File tree"])
    if not trace.artifacts:
        lines.append("  (empty)")
    else:
        for art in sorted(trace.artifacts, key=lambda a: a.path)[:80]:
            lines.append(f"  [{art.kind}] {art.path} ({art.size_bytes} B)")

    for preview in (
        _artifact_preview(trace, _SECURITY_REPORT_NAMES),
        _artifact_preview(trace, _TEST_OUTPUT_NAMES),
    ):
        if preview:
            lines.extend(["", preview])

    lines.extend(["", "## Spans (select first_failure by number)"])
    if not trace.spans:
        lines.append("  (no spans — use 'run' if needed)")
    else:
        shown = trace.spans[:max_spans]
        for i, s in enumerate(shown):
            lines.append(
                f"  {i:3d}. [{s.span_id}] type={s.type} phase={s.phase or '—'} "
                f"agent={s.agent_role or '—'}"
            )
        if len(trace.spans) > max_spans:
            lines.append(f"  ... ({len(trace.spans) - max_spans} more spans)")

    if trace.warnings:
        lines.extend(["", "## Warnings"])
        for w in trace.warnings[:20]:
            lines.append(f"  - {w}")

    return "\n".join(lines)


def load_sample_manifest(
    sample_id: str,
    *,
    samples_root: Path | None = None,
) -> SampleManifest:
    """Load ``evals/samples/<sample_id>.json``."""
    root = Path(samples_root) if samples_root is not None else _DEFAULT_SAMPLES_ROOT
    path = root / f"{sample_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"sample manifest not found: {path}")
    return SampleManifest.model_validate_json(path.read_text(encoding="utf-8"))


def resolve_trace(
    trace_id: str,
    *,
    store: TraceStore | None = None,
    fixtures_root: Path | None = None,
) -> Trace:
    """Load a trace from the corpus store, then fixture redacted examples."""
    if store is not None:
        try:
            return store.load(trace_id)
        except (OSError, FileNotFoundError, ValueError, json.JSONDecodeError):
            pass
    fixtures = Path(fixtures_root) if fixtures_root is not None else _DEFAULT_FIXTURES_ROOT
    fixture_path = fixtures / f"{trace_id}.json"
    if fixture_path.is_file():
        return Trace.model_validate_json(fixture_path.read_text(encoding="utf-8"))
    tests_dir = Path("tests/fixtures/traces")
    if tests_dir.is_dir():
        for path in tests_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("trace_id") == trace_id:
                return Trace.model_validate(data)
    raise FileNotFoundError(f"trace not found: {trace_id}")


def _capture_note_via_editor(initial: str = "") -> str:
    """Open ``$EDITOR`` on a temp file and return the saved note."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(initial)
        tmp_path = Path(tmp.name)
    try:
        subprocess.run([editor, str(tmp_path)], check=False)  # noqa: S603
        return tmp_path.read_text(encoding="utf-8").strip()
    finally:
        tmp_path.unlink(missing_ok=True)


def _parse_tags(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def apply_batch_item(
    *,
    sample_id: str,
    annotator: str,
    item: dict[str, Any],
    annotations_root: Path | None = None,
) -> AnnotationRecord:
    """Persist one batch annotation dict (non-interactive / test mode)."""
    trace_id = item.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ValueError("batch item requires string trace_id")
    tags_raw = item.get("tags") or []
    if isinstance(tags_raw, str):
        tags = _parse_tags(tags_raw)
    elif isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if str(t).strip()]
    else:
        raise ValueError("tags must be a list or comma-separated string")
    ff = item.get("first_failure_span_id")
    if ff is not None and not isinstance(ff, str):
        raise ValueError("first_failure_span_id must be a string or null")
    note = item.get("note") or ""
    if not isinstance(note, str):
        raise ValueError("note must be a string")
    record = AnnotationRecord(
        trace_id=trace_id.strip(),
        sample_id=sample_id,
        annotator=annotator,
        annotated_at=datetime.now(tz=UTC),
        note=note,
        tags=tags,
        first_failure_span_id=ff,
    )
    append_annotation(record, annotations_root=annotations_root)
    return record


def run_batch_annotate(
    *,
    sample_id: str,
    annotator: str,
    batch_items: Sequence[dict[str, Any]],
    annotations_root: Path | None = None,
    skip_annotated: bool = True,
) -> dict[str, Any]:
    """Annotate from a batch file / list; skip already-annotated ids when resuming."""
    path = annotations_path(annotator, annotations_root=annotations_root)
    done = annotated_trace_ids(path) if skip_annotated else set()
    written = 0
    skipped = 0
    for item in batch_items:
        tid = str(item.get("trace_id") or "")
        if tid in done:
            skipped += 1
            continue
        apply_batch_item(
            sample_id=sample_id,
            annotator=annotator,
            item=item,
            annotations_root=annotations_root,
        )
        done.add(tid)
        written += 1
    records = load_annotations(path)
    return {
        "written": written,
        "skipped": skipped,
        "path": str(path),
        "line_count": len(records),
        "saturation_streak": saturation_streak(records),
    }


def run_annotate_session(
    *,
    sample_id: str,
    annotator: str,
    store: TraceStore | None = None,
    samples_root: Path | None = None,
    annotations_root: Path | None = None,
    fixtures_root: Path | None = None,
    batch_file: Path | None = None,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
    editor_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Run interactive (or batch) annotation with resume support (R3.1–R3.6).

    Non-interactive modes:
    - ``batch_file``: JSONL of ``{trace_id, note?, tags?, first_failure_span_id?}``
    - ``EVALS_ANNOTATE_BATCH`` env: path to the same JSONL format
    - ``input_fn`` / ``output_fn``: inject I/O for unit tests without a TTY
    """
    out = output_fn or print
    inp = input_fn or input
    edit = editor_fn or _capture_note_via_editor

    batch_path = batch_file
    if batch_path is None:
        env_batch = os.environ.get("EVALS_ANNOTATE_BATCH")
        if env_batch:
            batch_path = Path(env_batch)

    if batch_path is not None:
        items: list[dict[str, Any]] = []
        for line in Path(batch_path).read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError(f"batch line must be a JSON object: {text[:80]}")
            items.append(parsed)
        return run_batch_annotate(
            sample_id=sample_id,
            annotator=annotator,
            batch_items=items,
            annotations_root=annotations_root,
            skip_annotated=True,
        )

    manifest = load_sample_manifest(sample_id, samples_root=samples_root)
    path = annotations_path(annotator, annotations_root=annotations_root)
    already = annotated_trace_ids(path)
    pending = [tid for tid in manifest.selection if tid not in already]
    skipped = len(manifest.selection) - len(pending)
    out(
        f"sample={sample_id} annotator={annotator} "
        f"pending={len(pending)} skipped_already={skipped}"
    )

    session_records = load_annotations(path)
    written = 0
    for tid in pending:
        try:
            trace = resolve_trace(tid, store=store, fixtures_root=fixtures_root)
        except FileNotFoundError as exc:
            out(f"skip missing: {exc}")
            continue

        out("")
        out("=" * 72)
        out(render_trace_card(trace))
        out("=" * 72)
        streak = saturation_streak(session_records)
        out(f"saturation: new tags: 0 for last {streak} traces (target 20)")

        note = ""
        tags: list[str] = []
        first_failure: str | None = None

        while True:
            cmd = (
                inp("[n]ext/save  [t]ags  [f]irst-failure  [e]dit-note  [q]uit > ").strip().lower()
            )
            if cmd in {"q", "quit"}:
                out(
                    f"quit. saturation_streak={saturation_streak(session_records)} "
                    f"file={path} lines={len(session_records)}"
                )
                return {
                    "written": written,
                    "skipped": skipped,
                    "path": str(path),
                    "line_count": len(session_records),
                    "saturation_streak": saturation_streak(session_records),
                    "quit": True,
                }
            if cmd in {"e", "edit", "note"}:
                note = edit(note)
                out(f"note saved ({len(note)} chars)")
                continue
            if cmd in {"t", "tag", "tags"}:
                raw = inp("tags (comma-separated): ")
                tags = _parse_tags(raw)
                out(f"tags={tags}")
                continue
            if cmd in {"f", "first", "failure"}:
                raw = inp("span number or span_id (empty to clear): ").strip()
                if not raw:
                    first_failure = None
                elif raw.isdigit():
                    idx = int(raw)
                    if 0 <= idx < len(trace.spans):
                        first_failure = trace.spans[idx].span_id
                    else:
                        out("index out of range")
                        continue
                else:
                    first_failure = raw
                out(f"first_failure_span_id={first_failure}")
                continue
            if cmd in {"n", "next", "s", "save", ""}:
                break
            out("unknown command")

        record = AnnotationRecord(
            trace_id=tid,
            sample_id=sample_id,
            annotator=annotator,
            annotated_at=datetime.now(tz=UTC),
            note=note,
            tags=tags,
            first_failure_span_id=first_failure,
        )
        append_annotation(record, annotations_root=annotations_root)
        session_records.append(record)
        written += 1
        out(f"saved {tid}")

    out(
        f"done. saturation_streak={saturation_streak(session_records)} "
        f"file={path} lines={len(session_records)}"
    )
    return {
        "written": written,
        "skipped": skipped,
        "path": str(path),
        "line_count": len(session_records),
        "saturation_streak": saturation_streak(session_records),
        "quit": False,
    }
