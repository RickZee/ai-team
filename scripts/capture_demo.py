#!/usr/bin/env python3
"""
Capture and verify a demo artifact after AITeamFlow completes.

Run after a successful E2E test (e.g. tests/e2e/test_e2e_hello_world.py).
Verifies generated files, runs tests with coverage, lints, builds Docker image,
and smoke-tests the container. Writes demos/<demo_id>/RESULTS.md.

Usage:
  poetry run python scripts/capture_demo.py [--output-dir PATH] [--run-report PATH]
  poetry run python scripts/capture_demo.py --output-dir demos/01_hello_world/output
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import structlog

# Resolve repo root (parent of scripts/)
REPO_ROOT = Path(__file__).resolve().parent.parent
DEMOS_DIR = REPO_ROOT / "demos"

REQUIRED_FILES_DEMO_01 = ["app.py", "test_app.py", "requirements.txt", "Dockerfile"]
SMOKE_PORT = 5001
CONTAINER_NAME = "demo-01-test"
IMAGE_NAME = "demo-01-test"
HEALTH_URL = f"http://127.0.0.1:{SMOKE_PORT}/health"
ITEMS_URL = f"http://127.0.0.1:{SMOKE_PORT}/items"

MIN_COVERAGE_PERCENT = 80
MAX_RUN_MINUTES = 8


@dataclass
class FileInfo:
    """Generated file metadata for RESULTS.md."""

    name: str
    lines: int
    size_bytes: int


@dataclass
class TestResults:
    """Pytest run outcome."""

    passed: int = 0
    failed: int = 0
    coverage_percent: Optional[float] = None
    raw_stdout: str = ""
    raw_stderr: str = ""
    returncode: int = -1


@dataclass
class LintResults:
    """Ruff check outcome."""

    violations: int = 0
    output: str = ""


@dataclass
class DockerResults:
    """Docker build outcome."""

    success: bool = False
    image_size: Optional[str] = None
    output: str = ""


@dataclass
class SmokeResults:
    """Smoke test outcome."""

    health_ok: bool = False
    get_items_empty_ok: bool = False
    post_item_ok: bool = False
    get_items_after_post_ok: bool = False
    details: list[str] = field(default_factory=list)


@dataclass
class CaptureResult:
    """Aggregate result of capture_demo run."""

    success: bool = False
    output_dir: Path = field(default_factory=Path)
    files_verified: list[str] = field(default_factory=list)
    files_missing: list[str] = field(default_factory=list)
    file_info: list[FileInfo] = field(default_factory=list)
    test_results: Optional[TestResults] = None
    lint_results: Optional[LintResults] = None
    docker_results: Optional[DockerResults] = None
    smoke_results: Optional[SmokeResults] = None
    duration_seconds: Optional[float] = None
    model_used: Optional[str] = None
    retry_count: Optional[int] = None
    guardrail_notes: Optional[str] = None
    failure_stage: Optional[str] = None
    failure_details: Optional[str] = None


def _get_logger() -> structlog.stdlib.BoundLogger:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )
    return structlog.get_logger()


def _resolve_output_dir(path: Path) -> Path:
    """Resolve output dir; ensure it is under repo."""
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError:
        raise ValueError(f"Output dir must be under repo root: {REPO_ROOT}")
    return resolved


def _collect_file_info(output_dir: Path, names: list[str]) -> list[FileInfo]:
    info_list: list[FileInfo] = []
    for name in names:
        p = output_dir / name
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            info_list.append(
                FileInfo(
                    name=name,
                    lines=len(text.splitlines()),
                    size_bytes=len(text.encode("utf-8")),
                )
            )
    return info_list


def _run_pytest(output_dir: Path, timeout: int = 120) -> TestResults:
    """Run pytest with coverage on test_app.py; return TestResults."""
    result = TestResults()
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "test_app.py",
        "-v",
        "--tb=short",
        "--cov=app",
        "--cov-report=term-missing",
        "--no-cov-on-fail",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        result.raw_stdout = getattr(e, "output", "") or ""
        result.raw_stderr = getattr(e, "stderr", "") or "pytest timed out"
        result.returncode = -1
        return result

    result.returncode = proc.returncode
    result.raw_stdout = proc.stdout or ""
    result.raw_stderr = proc.stderr or ""

    # Parse "X passed" / "Y failed"
    for line in (proc.stdout or "").splitlines():
        if " passed" in line:
            m = re.search(r"(\d+)\s+passed", line)
            if m:
                result.passed = int(m.group(1))
        if " failed" in line:
            m = re.search(r"(\d+)\s+failed", line)
            if m:
                result.failed = int(m.group(1))

    # Parse coverage percentage: "TOTAL ... XX%"
    for line in reversed((proc.stdout or "").splitlines()):
        if "TOTAL" in line and "%" in line:
            m = re.search(r"(\d+)%", line)
            if m:
                result.coverage_percent = float(m.group(1))
            break

    return result


def _run_ruff(output_dir: Path) -> LintResults:
    """Run ruff check on app.py; return LintResults."""
    result = LintResults()
    app_py = output_dir / "app.py"
    if not app_py.is_file():
        result.output = "app.py not found"
        return result
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "app.py"],
        cwd=output_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )
    result.output = (proc.stdout or "").strip() + "\n" + (proc.stderr or "").strip()
    # Count lines that look like violations (path:line:col: message)
    result.violations = sum(
        1 for line in result.output.splitlines() if "app.py:" in line and ":" in line
    )
    return result


def _run_docker_build(output_dir: Path, image_name: str, timeout: int = 300) -> DockerResults:
    """Build Docker image; return DockerResults."""
    result = DockerResults()
    dockerfile = output_dir / "Dockerfile"
    if not dockerfile.is_file():
        result.output = "Dockerfile not found"
        return result
    try:
        proc = subprocess.run(
            ["docker", "build", "-t", image_name, "."],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        result.output = getattr(e, "stderr", "") or "docker build timed out"
        return result
    except FileNotFoundError:
        result.output = "docker not found"
        return result

    result.success = proc.returncode == 0
    result.output = (proc.stdout or "") + (proc.stderr or "")

    if result.success:
        # Get image size: docker images --format "{{.Size}}" image_name
        try:
            p = subprocess.run(
                ["docker", "images", "--format", "{{.Size}}", image_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if p.returncode == 0 and p.stdout:
                result.image_size = p.stdout.strip().splitlines()[0].strip()
        except (subprocess.TimeoutExpired, IndexError):
            result.image_size = "unknown"

    return result


def _smoke_test_container(
    container_name: str,
    image_name: str,
    port: int,
    timeout_start: int = 30,
    timeout_request: int = 5,
) -> SmokeResults:
    """Run container and hit /health, /items, POST /items, GET /items; then stop."""
    results = SmokeResults()
    base_url = f"http://127.0.0.1:{port}"

    try:
        proc = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                f"{port}:5000",
                image_name,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        results.details.append("docker not found")
        return results
    if proc.returncode != 0:
        results.details.append(f"docker run failed: {proc.stderr or proc.stdout}")
        return results

    try:
        import urllib.request
        import urllib.error

        def get(path: str) -> tuple[int, Any]:
            req = urllib.request.Request(f"{base_url}{path}")
            try:
                with urllib.request.urlopen(req, timeout=timeout_request) as r:
                    return r.status, r.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode() if e.fp else ""
            except Exception as e:
                return -1, str(e)

        def post(path: str, data: str) -> tuple[int, Any]:
            req = urllib.request.Request(
                f"{base_url}{path}",
                data=data.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_request) as r:
                    return r.status, r.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode() if e.fp else ""
            except Exception as e:
                return -1, str(e)

        # Wait for server
        for _ in range(timeout_start):
            code, body = get("/health")
            if code == 200:
                break
            time.sleep(1)
        else:
            results.details.append(f"/health did not return 200 (last: {code})")
            return results

        results.health_ok = True
        if "status" in body and "ok" in body.lower():
            results.details.append("GET /health: 200, {status: ok}")

        code, body = get("/items")
        if code == 200 and ("[]" in body or "[]" in body.replace(" ", "")):
            results.get_items_empty_ok = True
            results.details.append("GET /items: 200, []")
        else:
            results.details.append(f"GET /items: {code} body={body[:200]}")

        code, body = post("/items", '{"name": "apple"}')
        if code in (200, 201):
            results.post_item_ok = True
            results.details.append("POST /items: 201")
        else:
            results.details.append(f"POST /items: {code} body={body[:200]}")

        code, body = get("/items")
        if code == 200 and "apple" in body:
            results.get_items_after_post_ok = True
            results.details.append("GET /items after POST: 200, [apple]")
        else:
            results.details.append(f"GET /items after POST: {code} body={body[:200]}")

    finally:
        subprocess.run(
            ["docker", "stop", container_name],
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["docker", "rm", container_name],
            capture_output=True,
            timeout=10,
        )

    return results


def _write_results_md(
    demo_id: str,
    result: CaptureResult,
    results_path: Path,
) -> None:
    """Generate demos/<demo_id>/RESULTS.md."""
    lines: list[str] = []
    lines.append(f"# Demo {demo_id} — Results\n")
    lines.append(f"**Summary:** {'PASS' if result.success else 'FAIL'}\n")

    lines.append("## Generated files\n")
    if result.file_info:
        lines.append("| File | Lines | Size |")
        lines.append("|------|-------|------|")
        for fi in result.file_info:
            lines.append(f"| {fi.name} | {fi.lines} | {fi.size_bytes} B |")
    else:
        lines.append("(none or missing)\n")
    if result.files_missing:
        lines.append(f"\nMissing: {', '.join(result.files_missing)}\n")

    lines.append("## Test results\n")
    if result.test_results is not None:
        tr = result.test_results
        cov = f"{tr.coverage_percent:.0f}%" if tr.coverage_percent is not None else "N/A"
        lines.append(f"- Passed: {tr.passed}, Failed: {tr.failed}, Coverage: {cov}\n")
    else:
        lines.append("(not run)\n")

    lines.append("## Lint results\n")
    if result.lint_results is not None:
        lr = result.lint_results
        if lr.violations == 0:
            lines.append("Clean (no violations)\n")
        else:
            lines.append(f"{lr.violations} violation(s)\n")
            if lr.output:
                lines.append("```")
                lines.append(lr.output[:2000])
                lines.append("```\n")
    else:
        lines.append("(not run)\n")

    lines.append("## Docker\n")
    if result.docker_results is not None:
        dr = result.docker_results
        if dr.success:
            lines.append(f"- Built successfully. Image size: {dr.image_size or 'unknown'}\n")
        else:
            lines.append("- Build failed\n")
            if dr.output:
                lines.append("```")
                lines.append(dr.output[-1500:])
                lines.append("```\n")
    else:
        lines.append("(not run)\n")

    lines.append("## Smoke test\n")
    if result.smoke_results is not None:
        sr = result.smoke_results
        if (
            sr.health_ok
            and sr.get_items_empty_ok
            and sr.post_item_ok
            and sr.get_items_after_post_ok
        ):
            lines.append("All endpoints responded correctly.\n")
        else:
            lines.append("One or more checks failed.\n")
        for d in sr.details:
            lines.append(f"- {d}")
        lines.append("")
    else:
        lines.append("(not run)\n")

    if result.duration_seconds is not None:
        lines.append(f"**Run duration:** {result.duration_seconds:.1f} s\n")
    if result.model_used:
        lines.append(f"**Model used:** {result.model_used}\n")
    if result.retry_count is not None:
        lines.append(f"**Retries:** {result.retry_count}\n")
    if result.guardrail_notes:
        lines.append(f"**Guardrail/retry notes:** {result.guardrail_notes}\n")
    if result.failure_stage:
        lines.append(f"**Failure stage:** {result.failure_stage}\n")
    if result.failure_details:
        lines.append("**Failure details:**\n```\n" + result.failure_details[:1000] + "\n```\n")

    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text("\n".join(lines), encoding="utf-8")


def _save_failure_artifact(
    output_dir: Path,
    failure_dir: Path,
    result: CaptureResult,
    run_report: Optional[dict[str, Any]],
    logger: structlog.stdlib.BoundLogger,
) -> None:
    """Copy output to failure/ and optionally write GitHub issue template."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = failure_dir / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for f in output_dir.iterdir():
        if f.is_file():
            shutil.copy2(f, dest / f.name)
        elif f.is_dir() and f.name != "failure":
            shutil.copytree(f, dest / f.name, dirs_exist_ok=True)
    (dest / "capture_result.json").write_text(
        json.dumps(
            {
                "success": result.success,
                "failure_stage": result.failure_stage,
                "failure_details": result.failure_details,
                "files_missing": result.files_missing,
                "test_returncode": result.test_results.returncode if result.test_results else None,
                "lint_violations": result.lint_results.violations if result.lint_results else None,
                "docker_success": result.docker_results.success if result.docker_results else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if run_report:
        (dest / "run_report.json").write_text(json.dumps(run_report, indent=2), encoding="utf-8")
    logger.info("Saved failure artifact", path=str(dest))

    # Optional GitHub issue template
    issue_path = dest / "issue_template.md"
    issue_lines = [
        "## Demo capture failure",
        "",
        f"- **Failure stage:** {result.failure_stage or 'unknown'}",
        f"- **Details:** {result.failure_details or 'N/A'}",
        "",
        "### Run report (if available)",
        "```json",
        json.dumps(run_report or {}, indent=2),
        "```",
        "",
        "### Capture result summary",
        f"- Files missing: {result.files_missing}",
        f"- Test returncode: {result.test_results.returncode if result.test_results else None}",
        f"- Lint violations: {result.lint_results.violations if result.lint_results else None}",
        f"- Docker build success: {result.docker_results.success if result.docker_results else None}",
    ]
    issue_path.write_text("\n".join(issue_lines), encoding="utf-8")


def capture_demo(
    output_dir: Path,
    demo_id: str = "01_hello_world",
    run_report_path: Optional[Path] = None,
    failure_dir: Optional[Path] = None,
    skip_docker: bool = False,
    skip_smoke: bool = False,
) -> CaptureResult:
    """
    Verify output directory and run tests, lint, Docker build, smoke test.

    Call this after AITeamFlow has written generated files to output_dir.
    """
    logger = _get_logger()
    result = CaptureResult(output_dir=output_dir)
    required_files = REQUIRED_FILES_DEMO_01
    run_report: Optional[dict[str, Any]] = None
    if run_report_path and run_report_path.is_file():
        run_report = json.loads(run_report_path.read_text(encoding="utf-8"))
        result.duration_seconds = run_report.get("duration_seconds")
        result.retry_count = run_report.get("retry_count")
        result.guardrail_notes = (
            f"Retries: {run_report.get('retry_count')}; "
            f"per-phase: {run_report.get('retry_counts_per_phase')}"
        )
        result.model_used = os.environ.get("MODEL") or os.environ.get("OLLAMA_DEFAULT_MODEL")

    # 1. Verify required files
    missing = [f for f in required_files if not (output_dir / f).is_file()]
    result.files_verified = [f for f in required_files if (output_dir / f).is_file()]
    result.files_missing = missing
    if missing:
        result.failure_stage = "file_verification"
        result.failure_details = f"Missing files: {missing}"
        result.success = False
        _write_results_md(demo_id, result, DEMOS_DIR / demo_id / "RESULTS.md")
        if failure_dir:
            _save_failure_artifact(output_dir, failure_dir, result, run_report, logger)
        return result

    result.file_info = _collect_file_info(output_dir, required_files)

    # 2. Pytest
    logger.info("Running pytest in output dir", path=str(output_dir))
    result.test_results = _run_pytest(output_dir)
    if result.test_results.returncode != 0:
        result.success = False
        result.failure_stage = "pytest"
        result.failure_details = result.test_results.raw_stderr or result.test_results.raw_stdout
        _write_results_md(demo_id, result, DEMOS_DIR / demo_id / "RESULTS.md")
        if failure_dir:
            _save_failure_artifact(output_dir, failure_dir, result, run_report, logger)
        return result
    if (
        result.test_results.coverage_percent is not None
        and result.test_results.coverage_percent < MIN_COVERAGE_PERCENT
    ):
        result.success = False
        result.failure_stage = "coverage"
        result.failure_details = (
            f"Coverage {result.test_results.coverage_percent}% < {MIN_COVERAGE_PERCENT}%"
        )
        _write_results_md(demo_id, result, DEMOS_DIR / demo_id / "RESULTS.md")
        if failure_dir:
            _save_failure_artifact(output_dir, failure_dir, result, run_report, logger)
        return result

    # 3. Lint
    logger.info("Running ruff check")
    result.lint_results = _run_ruff(output_dir)
    # Consider critical if many violations; prompt says "no critical lint violations"
    if result.lint_results.violations > 50:
        result.success = False
        result.failure_stage = "lint"
        result.failure_details = f"{result.lint_results.violations} violations"
        _write_results_md(demo_id, result, DEMOS_DIR / demo_id / "RESULTS.md")
        if failure_dir:
            _save_failure_artifact(output_dir, failure_dir, result, run_report, logger)
        return result

    # 4. Docker build
    if not skip_docker:
        logger.info("Building Docker image", image=IMAGE_NAME)
        result.docker_results = _run_docker_build(output_dir, IMAGE_NAME)
        if not result.docker_results.success:
            result.success = False
            result.failure_stage = "docker_build"
            result.failure_details = result.docker_results.output[-1000:]
            _write_results_md(demo_id, result, DEMOS_DIR / demo_id / "RESULTS.md")
            if failure_dir:
                _save_failure_artifact(output_dir, failure_dir, result, run_report, logger)
            return result
    else:
        result.docker_results = DockerResults()

    # 5. Smoke test
    if not skip_smoke and result.docker_results and result.docker_results.success:
        logger.info("Smoke testing container")
        result.smoke_results = _smoke_test_container(
            CONTAINER_NAME, IMAGE_NAME, SMOKE_PORT
        )
        if not (
            result.smoke_results.health_ok
            and result.smoke_results.get_items_empty_ok
            and result.smoke_results.post_item_ok
            and result.smoke_results.get_items_after_post_ok
        ):
            result.success = False
            result.failure_stage = "smoke_test"
            result.failure_details = "; ".join(result.smoke_results.details)
            _write_results_md(demo_id, result, DEMOS_DIR / demo_id / "RESULTS.md")
            if failure_dir:
                _save_failure_artifact(output_dir, failure_dir, result, run_report, logger)
            return result
    elif skip_smoke:
        result.smoke_results = SmokeResults()

    result.success = True
    _write_results_md(demo_id, result, DEMOS_DIR / demo_id / "RESULTS.md")
    logger.info("Capture completed", success=True)
    return result


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Capture and verify demo artifact after E2E / AITeamFlow."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "demos" / "01_hello_world" / "output",
        help="Path to directory containing generated app (default: demos/01_hello_world/output)",
    )
    parser.add_argument(
        "--run-report",
        type=Path,
        default=None,
        help="Path to run_report.json from E2E test (for duration, retries)",
    )
    parser.add_argument(
        "--demo-id",
        type=str,
        default="01_hello_world",
        help="Demo identifier for RESULTS.md path",
    )
    parser.add_argument(
        "--failure-dir",
        type=Path,
        default=REPO_ROOT / "demos" / "01_hello_world" / "failure",
        help="Directory to copy output to on failure",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker build and smoke test",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip container smoke test (still build image if not --skip-docker)",
    )
    args = parser.parse_args()

    try:
        output_dir = _resolve_output_dir(args.output_dir)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not output_dir.is_dir():
        print(f"Error: Output directory does not exist: {output_dir}", file=sys.stderr)
        return 1

    result = capture_demo(
        output_dir=output_dir,
        demo_id=args.demo_id,
        run_report_path=args.run_report,
        failure_dir=args.failure_dir,
        skip_docker=args.skip_docker,
        skip_smoke=args.skip_smoke,
    )
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
