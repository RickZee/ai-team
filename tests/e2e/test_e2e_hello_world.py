"""
End-to-end test: real AITeamFlow run for Hello World Flask API (Demo 1).

Uses an actual AITeamFlow run (not mocked). Validates the system produces
working code for the simplest possible project. Test output is the demo artifact.

Requires: Ollama running locally (e.g. http://localhost:11434) with models
qwen3:14b, deepseek-r1:14b, deepseek-coder-v2:16b, qwen2.5-coder:14b pulled.
Do not set OPENAI_API_KEY when running this test; the test forces all CrewAI
LLM paths to use Ollama via env and patches. If you need to use OpenAI instead,
run with a valid OPENAI_API_KEY and do not rely on the Ollama-only patches.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests

from ai_team.config.settings import get_settings, reload_settings
from ai_team.flows.human_feedback import MockHumanFeedbackHandler
from ai_team.flows.main_flow import AITeamFlow


def _patch_crewai_llm_for_ollama() -> None:
    """Force CrewAI to use Ollama: patch create_llm and LLM.__new__ (Crew may call LLM() directly)."""
    from crewai.llm import LLM as CrewAILLM
    from crewai.llms.base_llm import BaseLLM
    from crewai.utilities import llm_utils

    _original_create_llm = llm_utils.create_llm

    def _create_llm(llm_value: object) -> object:
        if isinstance(llm_value, (CrewAILLM, BaseLLM)):
            return llm_value
        if isinstance(llm_value, str):
            if not llm_value.startswith("ollama/"):
                llm_value = f"ollama/{llm_value}"
            return _original_create_llm(llm_value)
        if llm_value is not None:
            model = getattr(llm_value, "model", None) or getattr(llm_value, "model_name", None)
            base_url = getattr(llm_value, "base_url", None) or ""
            api_base = getattr(llm_value, "api_base", None) or ""
            if model and isinstance(model, str) and "ollama" not in model.lower():
                if "11434" in str(base_url) or "11434" in str(api_base):
                    base = api_base or base_url or "http://localhost:11434"
                    return CrewAILLM(
                        model=f"ollama/{model}",
                        api_base=base,
                        base_url=base,
                        timeout=getattr(llm_value, "timeout", None),
                    )
        return _original_create_llm(llm_value)

    llm_utils.create_llm = _create_llm

    # Crew/hierarchical path may call LLM(model="gpt-4.1-mini") directly; always force Ollama in e2e
    # so every LLM path (including Task Execution Planner) uses LiteLLM → Ollama, not OpenAI.
    # Set a dummy api_key so LiteLLM's client doesn't raise AuthenticationError; api_base sends requests to Ollama.
    _original_new = CrewAILLM.__new__

    def _llm_new(cls: type, model: str, is_litellm: bool = False, **kwargs: Any) -> Any:
        if model and not model.startswith("ollama/"):
            model = "ollama/qwen3:14b"
            kwargs.setdefault("api_base", "http://localhost:11434")
            kwargs.setdefault("base_url", "http://localhost:11434")
        if model and (model.startswith("ollama/") or "11434" in str(kwargs.get("api_base") or "")):
            kwargs.setdefault("api_key", "ollama")  # Satisfy LiteLLM client check; Ollama ignores key
            kwargs.setdefault("base_url", kwargs.get("base_url") or "http://localhost:11434")
            kwargs.setdefault("api_base", kwargs.get("api_base") or "http://localhost:11434")
        return _original_new(cls, model, is_litellm=is_litellm, **kwargs)

    CrewAILLM.__new__ = _llm_new


def _patch_litellm_for_ollama() -> None:
    """Ensure LiteLLM completion calls use Ollama base URL when model is ollama/*."""
    import litellm

    # Global fallback so any call without api_base uses Ollama (CrewAI may not pass it in some paths).
    litellm.api_base = "http://localhost:11434"

    _original_completion = litellm.completion
    _original_acompletion = getattr(litellm, "acompletion", None)
    _ollama_base = "http://localhost:11434"

    def _inject_ollama_base(kwargs: dict) -> None:
        model = kwargs.get("model")
        if model and "ollama" in str(model).lower():
            if not kwargs.get("api_base"):
                kwargs["api_base"] = _ollama_base
            kwargs.setdefault("api_key", "ollama")

    def _completion(*args: Any, **kwargs: Any) -> Any:
        _inject_ollama_base(kwargs)
        return _original_completion(*args, **kwargs)

    litellm.completion = _completion
    if _original_acompletion:

        async def _acompletion(*args: Any, **kwargs: Any) -> Any:
            _inject_ollama_base(kwargs)
            return await _original_acompletion(*args, **kwargs)

        litellm.acompletion = _acompletion

    # CrewAI may strip None from params, so LLM instances created without api_base
    # never pass it. Patch CrewAI LLM to inject api_base in _prepare_completion_params.
    from crewai.llm import LLM as CrewAILLM

    _orig_prepare = CrewAILLM._prepare_completion_params

    def _prepare_completion_params(self: Any, messages: Any, tools: Any = None) -> dict:
        params = _orig_prepare(self, messages, tools)
        if self.model and "ollama" in str(self.model).lower():
            params.setdefault("api_base", _ollama_base)
            params.setdefault("api_key", "ollama")
        return params

    CrewAILLM._prepare_completion_params = _prepare_completion_params


# Project specification (same as Demo 1)
PROJECT_SPEC = """Create a simple Flask REST API with:
 - GET /health endpoint returning {status: ok, version: 1.0}
 - GET /items returning a list of items from in-memory storage
 - POST /items accepting {name: str} and adding to the list
 - Proper error handling (400 for bad input, 404 for not found)
 - Unit tests with pytest covering all endpoints and edge cases
 - Requirements.txt and Dockerfile"""

DEMO_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "demos" / "01_hello_world" / "output"
RUN_REPORT_PATH = Path(__file__).resolve().parent.parent.parent / "demos" / "01_hello_world" / "run_report.json"
FAILURE_REPORT_PATH = Path(__file__).resolve().parent.parent.parent / "demos" / "01_hello_world" / "failure_report.json"

REQUIRED_FILES = ["app.py", "test_app.py", "requirements.txt", "Dockerfile"]
FLASK_PORT = 17542  # Unlikely to conflict


def _materialize_generated_files(output_dir: Path, generated_files: List[Dict[str, Any]]) -> None:
    """Write state.generated_files (list of dicts) to output_dir."""
    for gf in generated_files or []:
        path = gf.get("path") or ""
        content = gf.get("content") or ""
        if not path:
            continue
        dest = output_dir / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _run_report(
    state: Dict[str, Any],
    duration_seconds: float,
    token_estimate: int = 0,
) -> Dict[str, Any]:
    """Build run_report.json payload."""
    retry_counts = state.get("retry_counts") or {}
    total_retries = sum(retry_counts.values())
    return {
        "duration_seconds": round(duration_seconds, 2),
        "token_estimate": token_estimate,
        "retry_count": total_retries,
        "retry_counts_per_phase": retry_counts,
        "project_id": state.get("project_id"),
        "current_phase": state.get("current_phase"),
        "files_generated": len(state.get("generated_files") or []),
    }


def _failure_report(
    assertion_failed: str,
    error_context: Dict[str, Any],
    last_agent_output: str = "",
) -> Dict[str, Any]:
    """Build failure_report.json payload."""
    return {
        "assertion_failed": assertion_failed,
        "error_context": error_context,
        "last_agent_output": last_agent_output,
    }


@pytest.mark.e2e
@pytest.mark.slow
def test_e2e_hello_world_flask_api() -> None:
    """
    Run real AITeamFlow for Hello World Flask spec; assert output and behavior.

    Requires Ollama running; OPENAI_API_KEY must be unset so all LLM paths use Ollama.
    On success: copy output to demos/01_hello_world/output/, save run_report.json.
    On failure: save failure_report.json and fail with clear message.
    """
    # Force CrewAI to use Ollama: env for create_llm(None), and __new__ patch for direct LLM() calls.
    os.environ["MODEL"] = "ollama/qwen3:14b"
    os.environ["API_BASE"] = "http://localhost:11434"
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
    # LiteLLM reads OPENAI_API_KEY from env; point base URL to Ollama so requests don't hit api.openai.com.
    os.environ["OPENAI_API_KEY"] = "ollama"
    os.environ["OPENAI_BASE_URL"] = "http://localhost:11434"
    os.environ["OPENAI_API_BASE"] = "http://localhost:11434"
    # Avoid hierarchical planner "Instructor multiple tool calls" with Ollama
    os.environ["PROJECT_PLANNING_SEQUENTIAL"] = "1"
    # Reduce Rich/guardrail console output to avoid segfault in CrewAI's handle_guardrail_completed
    os.environ["PROJECT_CREW_VERBOSE"] = "false"
    # Use coder model for PO/Architect to reduce Instructor multi-tool-call issues with structured output
    os.environ["OLLAMA_PRODUCT_OWNER_MODEL"] = "qwen2.5-coder:14b"
    os.environ["OLLAMA_ARCHITECT_MODEL"] = "qwen2.5-coder:14b"
    reload_settings()  # so planning crew and flow see PROJECT_* and OLLAMA_* from env
    # Patch default model where it's used (llm_utils caches the import).
    try:
        import crewai.cli.constants as _c
        import crewai.utilities.llm_utils as _u
        _c.DEFAULT_LLM_MODEL = "ollama/qwen3:14b"
        _u.DEFAULT_LLM_MODEL = "ollama/qwen3:14b"
    except Exception:
        pass
    _patch_crewai_llm_for_ollama()
    _patch_litellm_for_ollama()

    settings = get_settings()
    base_output = Path(settings.project.output_dir).resolve()
    base_output.mkdir(parents=True, exist_ok=True)

    flow = AITeamFlow(feedback_handler=MockHumanFeedbackHandler(default_response="Proceed as-is"))
    flow.state.project_description = PROJECT_SPEC

    start = time.monotonic()
    try:
        flow.kickoff()
    except Exception as e:
        duration_seconds = time.monotonic() - start
        state_dump = flow.state.model_dump(mode="json")
        failure = _failure_report(
            assertion_failed="Flow completes without exception",
            error_context={
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "state_current_phase": state_dump.get("current_phase"),
                "state_errors": state_dump.get("errors"),
                "duration_seconds": round(duration_seconds, 2),
            },
            last_agent_output=state_dump.get("metadata", {}).get("last_crew_error", ""),
        )
        FAILURE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        FAILURE_REPORT_PATH.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        pytest.fail(f"E2E assertion 1 failed: Flow raised {type(e).__name__}: {e}")

    duration_seconds = time.monotonic() - start
    state_dump = flow.state.model_dump(mode="json")
    project_id = state_dump.get("project_id") or "unknown"
    output_dir = base_output / project_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Materialize generated code files into output_dir (flow only writes deployment package there)
    generated_files = state_dump.get("generated_files") or []
    _materialize_generated_files(output_dir, generated_files)

    def save_failure(assertion_failed: str, error_context: Dict[str, Any], last_agent: str = "") -> None:
        failure = _failure_report(assertion_failed, error_context, last_agent)
        FAILURE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        FAILURE_REPORT_PATH.write_text(json.dumps(failure, indent=2), encoding="utf-8")

    # Assertion 2: Output directory contains app.py, test_app.py, requirements.txt, Dockerfile
    missing = [f for f in REQUIRED_FILES if not (output_dir / f).exists()]
    if missing:
        save_failure(
            "Output directory contains app.py, test_app.py, requirements.txt, Dockerfile",
            {"missing_files": missing, "output_dir": str(output_dir), "listed": list(output_dir.iterdir())},
        )
        pytest.fail(f"E2E assertion 2 failed: Missing files: {missing}")

    # Assertion 3: app.py is valid Python
    app_py = (output_dir / "app.py").read_text(encoding="utf-8")
    try:
        ast.parse(app_py)
    except SyntaxError as e:
        save_failure(
            "Generated app.py is valid Python (ast.parse check)",
            {"syntax_error": str(e), "file": "app.py"},
        )
        pytest.fail(f"E2E assertion 3 failed: app.py invalid Python: {e}")

    # Assertion 4: requirements.txt contains flask, pytest
    reqs = (output_dir / "requirements.txt").read_text(encoding="utf-8").lower()
    for pkg in ("flask", "pytest"):
        if pkg not in reqs:
            save_failure(
                "Generated requirements.txt contains flask, pytest",
                {"missing_package": pkg, "requirements_preview": reqs[:500]},
            )
            pytest.fail(f"E2E assertion 4 failed: requirements.txt does not contain '{pkg}'")

    # Assertion 5: Dockerfile non-empty and contains FROM
    dockerfile = (output_dir / "Dockerfile").read_text(encoding="utf-8")
    if not dockerfile.strip():
        save_failure("Generated Dockerfile is non-empty", {"file": "Dockerfile"})
        pytest.fail("E2E assertion 5 failed: Dockerfile is empty")
    if "FROM" not in dockerfile.upper():
        save_failure(
            "Generated Dockerfile contains FROM instruction",
            {"dockerfile_preview": dockerfile[:500]},
        )
        pytest.fail("E2E assertion 5 failed: Dockerfile does not contain FROM")

    # Assertion 6: pytest on generated test_app.py exits 0
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "test_app.py", "-v", "--tb=short"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        save_failure(
            "Running pytest on generated test_app.py exits 0",
            {"reason": "pytest timed out after 120s"},
        )
        pytest.fail("E2E assertion 6 failed: pytest timed out")
    if proc.returncode != 0:
        save_failure(
            "Running pytest on generated test_app.py exits 0",
            {
                "returncode": proc.returncode,
                "stdout": proc.stdout[-2000:] if proc.stdout else "",
                "stderr": proc.stderr[-2000:] if proc.stderr else "",
            },
        )
        pytest.fail(f"E2E assertion 6 failed: pytest exited {proc.returncode}\n{proc.stderr or proc.stdout}")

    # Assertion 7: Start Flask app and hit /health returns 200
    try:
        app_proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from app import app; app.run(host='127.0.0.1', port=%d, use_reloader=False)" % FLASK_PORT,
            ],
            cwd=output_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy(),
        )
    except Exception as e:
        save_failure(
            "Starting Flask app and hitting /health returns 200",
            {"start_error": str(e)},
        )
        pytest.fail(f"E2E assertion 7 failed: could not start app: {e}")

    try:
        url = f"http://127.0.0.1:{FLASK_PORT}/health"
        for _ in range(30):
            try:
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            stderr = app_proc.stderr.read() if app_proc.stderr else ""
            app_proc.terminate()
            app_proc.wait(timeout=5)
            save_failure(
                "Starting Flask app and hitting /health returns 200",
                {"reason": "health check did not return 200", "stderr": stderr[-1500:]},
            )
            pytest.fail("E2E assertion 7 failed: /health did not return 200 within 15s")
        if r.status_code != 200:
            app_proc.terminate()
            app_proc.wait(timeout=5)
            save_failure(
                "Starting Flask app and hitting /health returns 200",
                {"status_code": r.status_code, "body": r.text[:500]},
            )
            pytest.fail(f"E2E assertion 7 failed: /health returned {r.status_code}")
    finally:
        app_proc.terminate()
        try:
            app_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app_proc.kill()

    # Success: copy to demos/01_hello_world/output/ and save run_report.json
    DEMO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in output_dir.iterdir():
        if p.is_file():
            shutil.copy2(p, DEMO_OUTPUT_DIR / p.name)
        elif p.is_dir():
            dest = DEMO_OUTPUT_DIR / p.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(p, dest)
    report = _run_report(state_dump, duration_seconds, token_estimate=0)
    RUN_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUN_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
