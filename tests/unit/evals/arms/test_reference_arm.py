"""Reference arm, vendor pin, and stdout-to-trace assembly (R3)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.arms.base import ScenarioContract
from evals.arms.reference import (
    MAX_FEATURES,
    VENDOR_DIR,
    VENDOR_PIN,
    ReferenceArm,
    assemble_reference_spans,
)
from evals.arms.registry import get_arm

pytestmark = pytest.mark.eval_unit

_MANIFEST = (
    Path(__file__).resolve().parents[4] / "evals/arms/vendor/autonomous_coding.manifest.json"
)


def test_vendor_manifest_matches_tree() -> None:
    recorded = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert recorded["sha"].startswith(VENDOR_PIN[:7])
    files = recorded["files"]
    actual = {
        p.relative_to(VENDOR_DIR).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(VENDOR_DIR.rglob("*"))
        if p.is_file()
    }
    assert actual == files
    assert (VENDOR_DIR / "PROVENANCE.md").is_file()
    assert "do not edit" in (VENDOR_DIR / "PROVENANCE.md").read_text(encoding="utf-8").lower()


def test_reference_registered() -> None:
    arm = get_arm("reference")
    spec = arm.describe()
    assert spec.arm_id == "reference"
    assert any(d.field == "max_features" and d.actual == MAX_FEATURES for d in spec.divergences)


def test_unavailable_causes(tmp_path: Path) -> None:
    missing_claude = ReferenceArm(which=lambda n: None if n == "claude" else "/bin/true")
    run = missing_claude.run(ScenarioContract(id="s", description="x"), tmp_path / "a", 1.0)
    assert run.status == "unavailable"
    missing_node = ReferenceArm(which=lambda n: None if n == "node" else "/bin/true")
    assert (
        missing_node.run(ScenarioContract(id="s", description="x"), tmp_path / "b", 1.0).status
        == "unavailable"
    )
    missing_vendor = ReferenceArm(which=lambda n: "/bin/true", vendor_dir=tmp_path / "no-vendor")
    assert (
        missing_vendor.run(ScenarioContract(id="s", description="x"), tmp_path / "c", 1.0).status
        == "unavailable"
    )


def test_happy_path_stubbed_subprocess(tmp_path: Path) -> None:
    def runner(cmd, cwd):  # noqa: ANN001
        del cmd, cwd
        return SimpleNamespace(returncode=0, stdout="[Tool: Read]\n[Done]\n", stderr="")

    arm = ReferenceArm(which=lambda n: "/bin/true", runner=runner)
    ws = tmp_path / "ref"
    run = arm.run(ScenarioContract(id="s", description="Build todos"), ws, 8.0)
    assert run.status == "ok"
    assert (ws / "app_spec.txt").read_text(encoding="utf-8") == "Build todos"
    assert (ws / ".arm_id").read_text(encoding="utf-8") == "reference"


def test_ceiling_kill(tmp_path: Path) -> None:
    def runner(cmd, cwd):  # noqa: ANN001
        del cmd, cwd
        raise subprocess.TimeoutExpired(cmd="python", timeout=1)

    arm = ReferenceArm(which=lambda n: "/bin/true", runner=runner)
    run = arm.run(ScenarioContract(id="s", description="x"), tmp_path / "kill", 8.0)
    assert run.status == "budget_exhausted"


def test_stdout_fixture_warns_absent_streams() -> None:
    stdout = "[Tool: Bash]\n[BLOCKED] wait\n[Done]\n"
    assembled = assemble_reference_spans(stdout, workspace=Path("/tmp/no-such-ref-ws"))
    warns = " ".join(assembled["warnings"])
    assert "cost" in warns
    assert "guardrail" in warns
    types = {s.type for s in assembled["spans"]}
    assert "tool_use" in types
    assert "error" in types
