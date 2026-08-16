"""Purity (no network) and performance guards for the check suite (task 3.7)."""

from __future__ import annotations

import os
import socket
import time

import pytest

from evals.checks import all_checks
from tests.unit.evals.trace_fixtures import ALL_CHECK_IDS, build_for_check

pytestmark = pytest.mark.eval_unit


class TestCheckPurity:
    def test_checks_run_with_sockets_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _blocked(*_a: object, **_k: object) -> None:
            raise OSError("network disabled for check purity test")

        monkeypatch.setattr(socket.socket, "connect", _blocked)
        monkeypatch.setattr(socket.socket, "connect_ex", lambda *_a, **_k: 1)

        for check_id in ALL_CHECK_IDS:
            for outcome in ("fail", "pass", "na"):
                trace = build_for_check(check_id, outcome)  # type: ignore[arg-type]
                for chk in all_checks():
                    if chk.id != check_id:
                        continue
                    result = chk.run(trace)
                    assert result.outcome in {"pass", "fail", "not_applicable", "error"}


class TestCheckPerformance:
    def test_200_synthetic_traces_under_5s(self) -> None:
        checks = all_checks()
        traces = []
        # Cycle through fixtures to build 200 traces
        combos = [(c, o) for c in ALL_CHECK_IDS for o in ("fail", "pass", "na")]
        while len(traces) < 200:
            for check_id, outcome in combos:
                traces.append(build_for_check(check_id, outcome))  # type: ignore[arg-type]
                if len(traces) >= 200:
                    break

        t0 = time.perf_counter()
        for trace in traces:
            for chk in checks:
                chk.run(trace)
        elapsed = time.perf_counter() - t0
        # Spec target is <5s on a laptop (R5.5). CI runners are noisier; keep a
        # still-tight ceiling so a real regression (e.g. uncached flow introspect)
        # still fails while avoiding flake on shared ubuntu-latest hosts.
        limit_s = 15.0 if os.environ.get("CI") else 5.0
        assert (
            elapsed < limit_s
        ), f"check suite over 200 traces took {elapsed:.2f}s (limit {limit_s})"
