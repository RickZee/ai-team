"""Run the workbench's headless render smoke test (eval-coverage R13.7, R12).

`evals/ui/workbench.html` is a static page with no build step, so nothing
type-checks it and no browser opens it in CI. `workbench/smoke.js` shims enough
DOM to prove the render path executes against a real bundle; this wrapper drives
it from the normal pytest run and builds the bundle from the repo's own fixtures.

Skips when node is unavailable rather than failing — the page is not Python and
its absence from a Python-only environment is not a defect.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.eval_unit

SMOKE = Path("tests/unit/evals/workbench/smoke.js")
FIXTURES = Path("evals/fixtures/traces")


def _bundle_from_fixtures(dest: Path, *, limit: int = 8) -> int:
    """Write a bundle mixing traces that have spans with traces that do not.

    Both shapes matter: the page renders a phase timeline for one and a
    "no spans" finding for the other, and the smoke test asserts each.
    """
    with_spans: list[dict] = []
    without_spans: list[dict] = []
    if FIXTURES.is_dir():
        for path in sorted(FIXTURES.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            (with_spans if doc.get("spans") else without_spans).append(doc)

    traces = with_spans[: limit // 2] + without_spans[: limit // 2]
    dest.write_text(
        json.dumps({"sample_id": "fixture-smoke", "annotator": "pytest", "traces": traces}),
        encoding="utf-8",
    )
    return len(traces)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_workbench_render_path(tmp_path: Path) -> None:
    assert SMOKE.is_file(), "the workbench smoke script must ship with the repo"
    bundle = tmp_path / "bundle.json"
    n = _bundle_from_fixtures(bundle)
    if n == 0:
        pytest.skip("no fixture traces to bundle")

    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [str(shutil.which("node")), str(SMOKE), str(bundle)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, f"workbench smoke failed:\n{proc.stdout}\n{proc.stderr}"
    assert "all passed" in proc.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_workbench_smoke_refuses_without_a_bundle(tmp_path: Path) -> None:
    """The script must not silently pass when given no bundle."""
    proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
        [str(shutil.which("node")), str(SMOKE)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 2
    assert "usage:" in proc.stderr
