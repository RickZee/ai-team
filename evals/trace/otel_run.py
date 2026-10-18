"""Export run folders to OTLP files and, optionally, a collector (``trace export-otel``).

Writes ``logs/otel.harness.jsonl`` and records the outcome in ``logs/otel.export.json``. A
refused or slow endpoint is a warning, never a failure: the file is still written and the
status is ``written_only``. Spec: ``.kiro/specs/otel-observability/`` R2.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.store import TraceStore
from evals.trace.builder import TraceBuilder
from evals.trace.models import Trace
from evals.trace.otel_export import ExportOptions, export_requests, to_jsonl

DEFAULT_ENDPOINT = "http://localhost:4318"
EXPORT_FILE = "otel.harness.jsonl"
STATUS_FILE = "otel.export.json"


def traces_url(endpoint: str) -> str:
    """``http://host:4318`` → ``http://host:4318/v1/traces`` (left alone if already there)."""
    base = endpoint.rstrip("/")
    return base if base.endswith("/v1/traces") else f"{base}/v1/traces"


def post_requests(endpoint: str, lines: list[str], timeout: float) -> str | None:
    """POST each OTLP request; return an error string, or None when all were accepted."""
    url = traces_url(endpoint)
    for line in lines:
        req = urllib.request.Request(
            url,
            data=line.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (operator URL)
                if resp.status >= 300:
                    return f"HTTP {resp.status} from {url}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return f"{type(exc).__name__}: {exc} ({url})"
    return None


def _run_record(run_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def build_trace(run_dir: Path) -> Trace:
    """Build the run's trace without writing blobs into the real trace corpus."""
    with tempfile.TemporaryDirectory(prefix="otel-export-") as tmp:
        builder = TraceBuilder(backend=None, store=TraceStore(root=Path(tmp)))
        return builder.from_workspace(run_dir)


def options_for(run_dir: Path, *, with_content: bool) -> ExportOptions:
    """Resource tags from the run record (backend, run id, model tier)."""
    record = _run_record(run_dir)
    extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
    tier = extra.get("model_tier") if isinstance(extra, dict) else None
    return ExportOptions(
        with_content=with_content,
        run_id=str(record.get("project_id") or run_dir.name),
        model_tier=str(tier) if tier else None,
    )


def _read_status(run_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((run_dir / "logs" / STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_status(run_dir: Path, status: dict[str, Any]) -> None:
    logs = run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / STATUS_FILE).write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")


def _by_kind(requests: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for req in requests:
        for rs in req["resourceSpans"]:
            for ss in rs["scopeSpans"]:
                for span in ss["spans"]:
                    kind = next(
                        (
                            a["value"]["stringValue"]
                            for a in span["attributes"]
                            if a["key"] == "openinference.span.kind"
                        ),
                        "CHAIN",
                    )
                    counts[kind] += 1
    return dict(sorted(counts.items()))


def export_run(
    run_dir: Path,
    *,
    endpoint: str | None = None,
    with_content: bool = False,
    if_changed: bool = False,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Export one run folder. Returns the status record (also written to ``otel.export.json``)."""
    started = time.monotonic()
    status: dict[str, Any] = {"endpoint": endpoint, "with_content": with_content, "error": None}
    try:
        trace = build_trace(run_dir)
        requests = export_requests(trace, options_for(run_dir, with_content=with_content))
    except Exception as exc:  # noqa: BLE001 - one broken run must not stop a backfill
        status.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        status["exported_at"] = datetime.now(UTC).isoformat()
        _write_status(run_dir, status)
        return status
    body = to_jsonl(requests)
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    previous = _read_status(run_dir)
    if (
        if_changed
        and endpoint
        and previous.get("status") == "posted"
        and previous.get("sha256") == sha
        and previous.get("endpoint") == endpoint
    ):
        return {**previous, "status": "unchanged"}
    logs = run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / EXPORT_FILE).write_text(body, encoding="utf-8")
    spans = sum(
        len(ss["spans"]) for r in requests for rs in r["resourceSpans"] for ss in rs["scopeSpans"]
    )
    status.update(sha256=sha, spans=spans, batches=len(requests), by_kind=_by_kind(requests))
    status["status"] = "written_only"
    if endpoint:
        error = post_requests(endpoint, body.splitlines(), timeout)
        status["status"] = "posted" if error is None else "written_only"
        status["error"] = error
    status["duration_ms"] = int((time.monotonic() - started) * 1000)
    status["exported_at"] = datetime.now(UTC).isoformat()
    _write_status(run_dir, status)
    return status


def export_all(runs_root: Path, **kwargs: Any) -> dict[str, Any]:
    """Backfill: export every run whose last export wasn't ``posted``. Never stops on one run."""
    summary: dict[str, Any] = {"exported": 0, "skipped": 0, "written_only": 0, "failed": []}
    for run_dir in sorted(p for p in runs_root.iterdir() if (p / "run.json").is_file()):
        if _read_status(run_dir).get("status") == "posted":
            summary["skipped"] += 1
            continue
        result = export_run(run_dir, **kwargs)
        if result.get("status") == "failed":
            summary["failed"].append({"run": run_dir.name, "error": result.get("error")})
        elif result.get("status") == "written_only":
            summary["written_only"] += 1
            summary["exported"] += 1
        else:
            summary["exported"] += 1
    return summary
