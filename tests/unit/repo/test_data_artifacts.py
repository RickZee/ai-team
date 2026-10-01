"""Fixture↔check mapping, baseline coverage, image references (R21).

to see this fail: add ``docs/images/unreferenced.png`` (not under publication/).
"""

from __future__ import annotations

import json
import subprocess

from tests.unit.repo._paths import REPO_ROOT

PUBLICATION_DIR = "docs/images/publication"


def test_fixture_check_mapping_both_ways() -> None:
    from evals.checks.registry import all_checks, ensure_checks_loaded

    ensure_checks_loaded()
    checks = {c.id for c in all_checks()}
    if not checks:
        raise AssertionError("check registry is empty — import path broken")
    traces = list((REPO_ROOT / "evals" / "fixtures" / "traces").rglob("*.json"))
    if not traces:
        raise AssertionError("evals/fixtures/traces matched zero files")
    mentioned: set[str] = set()
    for path in traces:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for key in ("check_id", "expected_check"):
            if isinstance(data.get(key), str):
                mentioned.add(data[key])
        stem = path.stem
        for cid in checks:
            slug = cid.replace("CHK-", "")
            if slug in stem or cid in stem:
                mentioned.add(cid)
    # Fixtures are named for checks; require every check has at least one path mention
    missing_fix = [
        c for c in sorted(checks) if not any(c.replace("CHK-", "") in p.name for p in traces)
    ]
    assert not missing_fix, "CHK has no fixture: " + ", ".join(missing_fix)


def test_baseline_covers_every_registered_check() -> None:
    from evals.checks.registry import all_checks, ensure_checks_loaded

    ensure_checks_loaded()
    checks = {c.id for c in all_checks() if str(getattr(c, "tier", "A")) == "A"}
    if not checks:
        raise AssertionError("no Tier A checks registered")
    baseline_path = REPO_ROOT / "evals" / "baselines" / "tier_a.json"
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    covered = set(data.get("check_outcomes") or {})
    missing = sorted(checks - covered)
    assert not missing, (
        f"baseline covers {len(covered)} of {len(checks)} checks; missing: {missing}. "
        "Run `python -m evals.cli baseline accept --reason …` or add an exemption."
    )


def test_no_unreferenced_images_outside_publication() -> None:
    images_root = REPO_ROOT / "docs" / "images"
    images = [
        p
        for p in images_root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".png", ".svg", ".gif", ".jpg", ".jpeg", ".webp"}
    ]
    if not images:
        raise AssertionError("docs/images contained zero images — walker broken")
    # Tracked files only. Walking the working tree read the untracked workspace/ and
    # output/ run folders: slow (tens of seconds), different on every machine, and racy
    # under xdist while other tests create and delete run directories.
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO_ROOT)
    tracked = [REPO_ROOT / rel for rel in raw.decode().split("\0") if rel]
    if not tracked:
        raise AssertionError("git ls-files returned empty — not a clone?")
    blob_parts: list[str] = []
    for path in tracked:
        if path.suffix.lower() not in {".md", ".html", ".py", ".ts", ".tsx", ".json", ".yml"}:
            continue
        if "node_modules" in path.parts or path.is_relative_to(images_root):
            continue
        try:
            blob_parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    blob = "\n".join(blob_parts)
    unreferenced: list[str] = []
    for img in images:
        rel = img.relative_to(REPO_ROOT).as_posix()
        if PUBLICATION_DIR in rel:
            continue
        if img.name not in blob and rel not in blob:
            unreferenced.append(rel)
    assert not unreferenced, (
        "images referenced by nothing (move to docs/images/publication/ or delete):\n"
        + "\n".join(unreferenced)
    )
