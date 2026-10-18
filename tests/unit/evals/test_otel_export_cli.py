"""`python -m evals.cli trace export-otel`: files, status, endpoint, batching, backfill (R2)."""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from evals.cli import main as evals_main
from evals.trace import otel_run
from evals.trace.otel_export import export_requests, to_jsonl
from tests.unit.evals.otel_helpers import make_trace, span

pytestmark = pytest.mark.eval_unit


def _make_run(root: Path, name: str = "run-1") -> Path:
    run = root / name
    (run / "logs").mkdir(parents=True)
    now = "2026-10-18T12:00:0{}+00:00"
    (run / "run.json").write_text(
        json.dumps(
            {
                "project_id": name,
                "backend": "langgraph",
                "started_at": now.format(0),
                "output_dir": str(run),
                "workspace_dir": str(run),
                "extra": {"model_tier": "local"},
            }
        )
    )
    rows = []
    for i, tool in enumerate(["write_file", "run_tests"]):
        base = {
            "tool": tool,
            "tool_name": tool,
            "agent_role": "dev",
            "phase": "development",
            "run_id": name,
        }
        rows.append({**base, "type": "tool_use", "timestamp": now.format(2 * i + 1)})
        rows.append(
            {
                **base,
                "type": "tool_result",
                "timestamp": now.format(2 * i + 2),
                "ok": True,
                "summary": "done",
            }
        )
    (run / "logs" / "audit.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return run


class _Sink(BaseHTTPRequestHandler):
    bodies: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", "0"))
        type(self).bodies.append(json.loads(self.rfile.read(length)))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def sink():
    _Sink.bodies = []
    server = HTTPServer(("127.0.0.1", 0), _Sink)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", _Sink.bodies
    server.shutdown()


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_writes_file_and_status_without_endpoint(tmp_path: Path, capsys) -> None:
    run = _make_run(tmp_path)
    assert evals_main(["trace", "export-otel", str(run)]) == 0
    status = json.loads((run / "logs" / "otel.export.json").read_text())
    assert status["status"] == "written_only"
    assert status["spans"] == 3  # root + two merged tool spans
    lines = (run / "logs" / "otel.harness.jsonl").read_text().splitlines()
    resource = json.loads(lines[0])["resourceSpans"][0]["resource"]["attributes"]
    keys = {a["key"]: a["value"]["stringValue"] for a in resource}
    assert keys["ai_team.run_id"] == "run-1"
    assert keys["ai_team.model_tier"] == "local"
    assert keys["ai_team.source"] == "harness"


def test_closed_port_warns_and_exits_zero_quickly(tmp_path: Path, capsys) -> None:
    run = _make_run(tmp_path)
    started = time.monotonic()
    code = evals_main(
        [
            "trace",
            "export-otel",
            str(run),
            "--endpoint",
            f"http://127.0.0.1:{_closed_port()}",
            "--timeout",
            "1",
        ]
    )
    assert code == 0
    assert time.monotonic() - started < 5
    assert "warning:" in capsys.readouterr().err
    assert json.loads((run / "logs" / "otel.export.json").read_text())["status"] == "written_only"


def test_posts_valid_otlp_and_skips_unchanged(tmp_path: Path, sink) -> None:
    url, bodies = sink
    run = _make_run(tmp_path)
    assert evals_main(["trace", "export-otel", str(run), "--endpoint", url, "--if-changed"]) == 0
    assert json.loads((run / "logs" / "otel.export.json").read_text())["status"] == "posted"
    assert len(bodies) == 1
    assert bodies[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"] == "run"
    assert evals_main(["trace", "export-otel", str(run), "--endpoint", url, "--if-changed"]) == 0
    assert len(bodies) == 1  # unchanged: nothing re-sent


def test_changed_run_is_re_sent(tmp_path: Path, sink) -> None:
    url, bodies = sink
    run = _make_run(tmp_path)
    otel_run.export_run(run, endpoint=url, if_changed=True)
    with (run / "logs" / "audit.jsonl").open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "type": "tool_use",
                    "tool": "x",
                    "timestamp": "2026-10-18T12:00:09+00:00",
                    "run_id": "run-1",
                }
            )
            + "\n"
        )
    assert otel_run.export_run(run, endpoint=url, if_changed=True)["status"] == "posted"
    assert len(bodies) == 2


def test_post_requests_sends_each_batch(sink) -> None:
    url, bodies = sink
    trace = make_trace([span("qa_verdict", i, sid=f"q{i}") for i in range(1100)])
    lines = to_jsonl(export_requests(trace)).splitlines()
    assert otel_run.post_requests(url, lines, timeout=5) is None
    assert len(bodies) == 3


def test_all_exports_good_runs_and_lists_the_broken_one(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    good = _make_run(tmp_path, "good")
    broken = _make_run(tmp_path, "broken")
    real = otel_run.build_trace

    def flaky(run_dir: Path):
        if run_dir.name == "broken":
            raise ValueError("cannot build")
        return real(run_dir)

    monkeypatch.setattr(otel_run, "build_trace", flaky)
    assert evals_main(["trace", "export-otel", "--all", "--runs-root", str(tmp_path)]) == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["exported"] == 1
    assert summary["failed"][0]["run"] == "broken"
    assert json.loads((broken / "logs" / "otel.export.json").read_text())["status"] == "failed"
    assert (good / "logs" / "otel.harness.jsonl").is_file()


def test_all_skips_runs_already_posted(tmp_path: Path, sink) -> None:
    url, bodies = sink
    _make_run(tmp_path, "a")
    otel_run.export_all(tmp_path, endpoint=url)
    summary = otel_run.export_all(tmp_path, endpoint=url)
    assert summary["skipped"] == 1
    assert len(bodies) == 1


def test_missing_run_folder_is_an_error(tmp_path: Path) -> None:
    assert evals_main(["trace", "export-otel", str(tmp_path / "nope")]) == 1


def test_traces_url() -> None:
    assert otel_run.traces_url("http://h:4318") == "http://h:4318/v1/traces"
    assert otel_run.traces_url("http://h:4318/v1/traces/") == "http://h:4318/v1/traces"
