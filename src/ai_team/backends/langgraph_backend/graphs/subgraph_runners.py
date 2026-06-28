"""
Invoke compiled Phase-3 subgraphs from main-graph nodes (state mapping + errors).

Subgraphs share ``messages`` with the parent ``LangGraphProjectState`` via ``add_messages``.
Only **new** messages produced after the input seed are merged to avoid duplicating history.

Subgraph compilation is cached per ``(phase, agents, model_overrides)`` so identical
profiles share a compiled graph while different profiles get correctly filtered agents.
"""

from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog
from ai_team.backends.langgraph_backend.graphs.langgraph_chat import _fix_tool_call_args
from ai_team.backends.langgraph_backend.graphs.state import LangGraphProjectState
from ai_team.config.settings import get_settings
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

logger = structlog.get_logger(__name__)

_CACHE_MAX = 16

_FENCED_JSON_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


def _nested_config(config: RunnableConfig, suffix: str) -> RunnableConfig:
    base = dict(config) if config else {}
    conf = dict(base.get("configurable") or {})
    tid = conf.get("thread_id")
    if tid is not None:
        conf["thread_id"] = f"{tid}/{suffix}"
    base["configurable"] = conf
    return base


def _message_delta(seed: list[BaseMessage], out_msgs: list[BaseMessage]) -> list[BaseMessage]:
    """Return messages appended after ``seed``; normalises tool_call args string→dict."""
    delta = list(out_msgs[len(seed) :]) if len(out_msgs) >= len(seed) else list(out_msgs)
    return [_fix_tool_call_args(m) for m in delta]


def _extract_profile_from_state(
    state: LangGraphProjectState,
) -> tuple[frozenset[str], tuple[tuple[str, str], ...]]:
    """Read agents and model_overrides from ``state.metadata``."""
    meta = state.get("metadata") or {}
    agents = frozenset(meta.get("agents") or [])
    raw_overrides: dict[str, str] = meta.get("model_overrides") or {}
    overrides = tuple(sorted(raw_overrides.items()))
    return agents, overrides


@lru_cache(maxsize=_CACHE_MAX)
def _cached_planning(
    agents: frozenset[str],
    overrides: tuple[tuple[str, str], ...],
) -> CompiledStateGraph:
    from ai_team.backends.langgraph_backend.graphs.planning import (
        compile_planning_subgraph,
    )

    return compile_planning_subgraph(agents=agents, model_overrides=dict(overrides))


@lru_cache(maxsize=_CACHE_MAX)
def _cached_development(
    agents: frozenset[str],
    overrides: tuple[tuple[str, str], ...],
) -> CompiledStateGraph:
    from ai_team.backends.langgraph_backend.graphs.development import (
        compile_development_subgraph,
    )

    return compile_development_subgraph(agents=agents, model_overrides=dict(overrides))


@lru_cache(maxsize=_CACHE_MAX)
def _cached_testing(
    agents: frozenset[str],
    overrides: tuple[tuple[str, str], ...],
) -> CompiledStateGraph:
    from ai_team.backends.langgraph_backend.graphs.testing import (
        compile_testing_subgraph,
    )

    return compile_testing_subgraph(agents=agents, model_overrides=dict(overrides))


@lru_cache(maxsize=_CACHE_MAX)
def _cached_deployment(
    agents: frozenset[str],
    overrides: tuple[tuple[str, str], ...],
) -> CompiledStateGraph:
    from ai_team.backends.langgraph_backend.graphs.deployment import (
        compile_deployment_subgraph,
    )

    return compile_deployment_subgraph(agents=agents, model_overrides=dict(overrides))


def reset_subgraph_cache() -> None:
    """Clear all cached compiled subgraphs (for tests)."""
    _cached_planning.cache_clear()
    _cached_development.cache_clear()
    _cached_testing.cache_clear()
    _cached_deployment.cache_clear()


def _subgraph_context(state: LangGraphProjectState) -> dict[str, Any]:
    """Initial keys for Phase-5 ``LangGraphSubgraphState`` (guardrails + scope hints)."""
    return {
        "guardrail_checks": [],
        "project_description": (state.get("project_description") or "").strip(),
        "requirements": state.get("requirements") or {},
        "architecture": state.get("architecture") or {},
        "generated_files": state.get("generated_files") or [],
    }


def _parse_structured_planning(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract requirements + architecture from fenced JSON blocks."""
    req: dict[str, Any] = {}
    arch: dict[str, Any] = {}
    for block in _FENCED_JSON_RE.findall(text or ""):
        try:
            obj = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        if (
            isinstance(obj, dict)
            and "requirements" in obj
            and isinstance(obj["requirements"], dict)
        ):
            req = obj["requirements"]
        if (
            isinstance(obj, dict)
            and "architecture" in obj
            and isinstance(obj["architecture"], dict)
        ):
            arch = obj["architecture"]
    return req, arch


def _workspace_root() -> Path:
    root = Path(get_settings().project.workspace_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_cmd(cmd: list[str], *, timeout_s: int, cwd: Path) -> dict[str, Any]:
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return {"ok": r.returncode == 0, "returncode": r.returncode, "output": out}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "output": f"Timed out after {timeout_s}s"}
    except FileNotFoundError:
        return {"ok": False, "returncode": None, "output": f"Command not found: {cmd[0]}"}
    except Exception as e:
        return {"ok": False, "returncode": None, "output": f"Error running {cmd[0]}: {e}"}


def _ensure_workspace_conftest(root: Path) -> None:
    """Write conftest.py adding workspace root to sys.path so tests import local src files."""
    conftest = root / "conftest.py"
    if conftest.exists():
        return
    conftest.write_text(
        "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n",
        encoding="utf-8",
    )


def _run_real_quality_gate() -> dict[str, Any]:
    """
    Run real lint + tests in the workspace and return a structured QA result.

    This is the authoritative source of truth for `test_results` in state.
    """
    root = _workspace_root()
    # Write conftest.py to add workspace root to sys.path so tests can import src files
    _ensure_workspace_conftest(root)
    # Auto-fix trivial style issues (imports, trailing newlines) before checking
    _run_cmd(
        ["ruff", "check", "--fix", "--select", "I,W292", "--preview", "."], timeout_s=30, cwd=root
    )
    ruff = _run_cmd(["ruff", "check", "."], timeout_s=60, cwd=root)
    # Run pytest with --rootdir=workspace so it ignores the parent pyproject.toml
    pytest = _run_cmd(
        ["pytest", "-q", f"--rootdir={root}", "--no-header", "--tb=short"],
        timeout_s=300,
        cwd=root,
    )
    # pytest exit code 5 == "no tests collected". Surface this distinctly so a
    # retry can tell the developer/QA "no tests were written" rather than
    # leaving it indistinguishable from a normal test failure.
    no_tests = pytest.get("returncode") == 5
    passed = bool(ruff["ok"]) and bool(pytest["ok"])
    result: dict[str, Any] = {
        "passed": passed,
        "lint": {"tool": "ruff", **ruff},
        "tests": {"tool": "pytest", **pytest},
    }
    if no_tests:
        result["no_tests_collected"] = True
        result["reason"] = (
            "No tests were collected (pytest exit 5). QA must write test files "
            "with file_writer (e.g. tests/test_*.py), not emit them as prose."
        )
    return result


def _workspace_has_tests() -> bool:
    """True if the workspace contains at least one pytest-discoverable test file."""
    root = _workspace_root()
    for fp in root.rglob("*.py"):
        name = fp.name
        if name.startswith("test_") or name.endswith("_test.py"):
            return True
    return False


def _snapshot_workspace_files() -> list[dict[str, Any]]:
    """
    Best-effort inventory of files written to the per-run workspace.

    This is needed because some tools (e.g. ``file_writer``) may not explicitly
    return a structured file list. Downstream phases (QA/DevOps) require a real
    file set to operate like an engineering organization.
    """
    root = get_settings().project.workspace_dir
    base = (get_settings().project.workspace_dir and get_settings().project.workspace_dir) or ""
    _ = base
    p = __import__("pathlib").Path(root).resolve()
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    for fp in p.rglob("*"):
        if fp.is_file():
            try:
                rel = fp.relative_to(p).as_posix()
            except ValueError:
                rel = fp.name
            out.append({"path": rel})
    return sorted(out, key=lambda d: d.get("path", ""))


_CODE_BLOCK_RE = re.compile(
    r"(?:#+\s*)?(?P<fname>[\w./\\-]+\.(?:py|js|ts|jsx|tsx|html|css|json|yaml|yml|toml|txt|sh))\s*:?\n"
    r"```(?:\w+)?\n(?P<code>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
_FENCED_NAMED_RE = re.compile(
    r"```(?:\w+)?\s*\n#\s*(?P<fname>[\w./\\-]+\.(?:py|js|ts|jsx|tsx|html|css|json|yaml|yml|toml|txt|sh))\n"
    r"(?P<code>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
# Markdown-header-named blocks, e.g.  "### `test_calc.py`\n```python\n...\n```".
# The filename may be wrapped in backticks and the fence may sit a blank line
# below the header. Common deepseek/QA prose format that the two patterns above
# miss, which previously left tests unwritten and pytest collecting 0 items.
_MD_HEADER_NAMED_RE = re.compile(
    r"#{1,6}\s*`?(?P<fname>[\w./\\-]+\.(?:py|js|ts|jsx|tsx|html|css|json|yaml|yml|toml|txt|sh))`?\s*\n+"
    r"```(?:\w+)?\n(?P<code>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
# Markdown header with a *backtick-wrapped* filename anywhere in the line, allowing
# leading numbering and surrounding words — e.g. "### 1. `main.py` (Flask App)" or
# "#### 2. Updated `tests/test_api.py`". The development supervisor emits this shape
# and the stricter pattern above misses it (filename not immediately after the #s),
# which left main.py unwritten so the build had tests but no app. Backticks are
# REQUIRED here to avoid matching prose that merely mentions a filename mid-sentence.
_MD_HEADER_LOOSE_RE = re.compile(
    r"#{1,6}[^\n`]*`(?P<fname>[\w./\\-]+\.(?:py|js|ts|jsx|tsx|html|css|json|yaml|yml|toml|txt|sh))`[^\n]*\n+"
    r"```(?:\w+)?\n(?P<code>.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_and_write_code_blocks(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """Fallback: parse filename+code-block pairs from AI text and write to workspace.

    When the developer model outputs code as markdown instead of calling file_writer,
    this extracts fenced blocks with adjacent filenames and writes them to disk.
    Called only when workspace is empty after development subgraph.
    """
    root = _workspace_root()
    written: list[dict[str, Any]] = []
    seen: set[str] = set()
    from langchain_core.messages import AIMessage

    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        text = msg.content if isinstance(msg.content, str) else ""
        if not text:
            continue
        for pattern in (
            _CODE_BLOCK_RE,
            _FENCED_NAMED_RE,
            _MD_HEADER_NAMED_RE,
            _MD_HEADER_LOOSE_RE,
        ):
            for m in pattern.finditer(text):
                raw = m.group("fname").strip()
                # Strip at most one leading "./"; do NOT use lstrip("./") — that
                # removes arbitrary leading dot/slash chars and turns "../x.py"
                # into "x.py", defeating the traversal check below.
                fname = raw[2:] if raw.startswith("./") else raw
                code = m.group("code").rstrip()
                if not fname or fname in seen:
                    continue
                # Security: reject absolute paths, traversal, and hidden files.
                safe = Path(fname)
                if (
                    safe.is_absolute()
                    or ".." in safe.parts
                    or any(part.startswith(".") for part in safe.parts)
                ):
                    continue
                dest = root / safe
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(code + "\n", encoding="utf-8")
                seen.add(fname)
                written.append({"path": fname, "source": "extracted_from_message"})
                logger.info("code_block_extracted_to_workspace", path=fname)
    return written


def _guardrail_error_dict(out: dict[str, Any], phase: str) -> dict[str, Any] | None:
    if not out.get("guardrail_terminal"):
        return None
    checks = out.get("guardrail_checks") or []
    last = checks[-1] if checks else {}
    return {
        "phase": phase,
        "message": str(last.get("message") or "Guardrail failed after max retries"),
        "type": "GuardrailError",
        "guardrail": last,
    }


def planning_subgraph_node(
    state: LangGraphProjectState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run planning supervisor (PO + Architect) and merge new messages."""
    desc = (state.get("project_description") or "").strip()
    if not desc:
        return {
            "errors": [
                {
                    "phase": "planning",
                    "message": "Missing project_description",
                    "type": "ValidationError",
                }
            ],
        }
    agents, overrides = _extract_profile_from_state(state)
    sub = _cached_planning(agents, overrides)
    prior = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    seed: list[BaseMessage] = (
        prior + [HumanMessage(content=desc)] if prior else [HumanMessage(content=desc)]
    )
    try:
        out = sub.invoke(
            {**_subgraph_context(state), "messages": seed},
            _nested_config(config, "planning"),
        )
    except Exception as e:
        logger.exception("planning_subgraph_failed", error=str(e))
        return {
            "errors": [
                {
                    "phase": "planning",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ],
            "current_phase": "planning",
        }
    ge = _guardrail_error_dict(out, "planning")
    if ge:
        return {
            "errors": [ge],
            "current_phase": "planning",
        }
    out_msgs = [m for m in (out.get("messages") or []) if isinstance(m, BaseMessage)]
    delta = _message_delta(seed, out_msgs)
    extracted_req: dict[str, Any] = {}
    extracted_arch: dict[str, Any] = {}
    # Prefer explicit keys; otherwise parse structured JSON from the latest delta message.
    if out.get("requirements") or out.get("architecture"):
        extracted_req = out.get("requirements") or {}
        extracted_arch = out.get("architecture") or {}
    else:
        latest_text = ""
        for m in reversed(delta):
            latest_text = getattr(m, "content", "") or ""
            if isinstance(latest_text, str) and latest_text.strip():
                break
        extracted_req, extracted_arch = _parse_structured_planning(latest_text)
    return {
        "messages": delta,
        "current_phase": "planning",
        "requirements": extracted_req,
        "architecture": extracted_arch,
        "phase_history": [{"phase": "planning", "status": "complete"}],
    }


def development_subgraph_node(
    state: LangGraphProjectState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run development supervisor (backend / frontend / fullstack)."""
    desc = (state.get("project_description") or "").strip()
    req = state.get("requirements") or {}
    arch = state.get("architecture") or {}
    prior_tr = state.get("test_results") or {}
    qa_summary = ""
    if prior_tr.get("passed") is False:
        qa_summary = (
            "\n\nPrevious QA failed. Fix the issues below and update the workspace files.\n"
            f"QA result (JSON):\n{json.dumps(prior_tr, default=str)[:12000]}\n"
        )
    ctx = (
        f"Project:\n{desc}\n\nRequirements (JSON):\n{json.dumps(req, default=str)[:8000]}\n\n"
        f"Architecture (JSON):\n{json.dumps(arch, default=str)[:8000]}\n"
        f"{qa_summary}"
    )
    prior = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    seed: list[BaseMessage] = (
        prior + [HumanMessage(content=ctx)] if prior else [HumanMessage(content=ctx)]
    )
    agents, overrides = _extract_profile_from_state(state)
    sub = _cached_development(agents, overrides)
    try:
        out = sub.invoke(
            {**_subgraph_context(state), "messages": seed},
            _nested_config(config, "development"),
        )
    except Exception as e:
        logger.exception("development_subgraph_failed", error=str(e))
        # Even on subgraph exception, try fallback code extraction from whatever
        # messages were written before the error — deepseek often emits markdown
        # prose that can be salvaged even when the subgraph JSON parse fails.
        generated = _snapshot_workspace_files()
        if not generated:
            extracted = _extract_and_write_code_blocks(seed)
            if extracted:
                logger.info("development_exception_fallback", count=len(extracted))
                generated = _snapshot_workspace_files()
        if generated:
            logger.info("development_recovered_via_fallback", files=len(generated))
            return {
                "current_phase": "development",
                "generated_files": generated,
                "errors": [],
                "phase_history": [
                    {"phase": "development", "status": "complete", "files": len(generated)}
                ],
            }
        return {
            "errors": [
                {
                    "phase": "development",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ],
            "current_phase": "development",
        }
    ge = _guardrail_error_dict(out, "development")
    if ge:
        return {
            "errors": [ge],
            "current_phase": "development",
        }
    out_msgs = [m for m in (out.get("messages") or []) if isinstance(m, BaseMessage)]
    delta = _message_delta(seed, out_msgs)
    generated = _snapshot_workspace_files()
    if not generated:
        # Developer output code as markdown prose instead of calling file_writer — extract it.
        extracted = _extract_and_write_code_blocks(delta)
        if extracted:
            logger.info("development_fallback_extraction", count=len(extracted))
            generated = _snapshot_workspace_files()
    return {
        "messages": delta,
        "current_phase": "development",
        "generated_files": generated,
        "deployment_config": out.get("deployment_config"),
        "phase_history": [{"phase": "development", "status": "complete", "files": len(generated)}],
        "errors": [],
    }


def testing_subgraph_node(
    state: LangGraphProjectState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run QA ReAct agent."""
    files = state.get("generated_files") or []
    workspace_dir = get_settings().project.workspace_dir or "./workspace"
    desc = (state.get("project_description") or "").strip()
    ctx = (
        f"Project description: {desc}\n\n"
        f"Workspace directory: {workspace_dir}\n\n"
        "Generated files available for testing:\n"
        f"{json.dumps(files, default=str)[:12000]}\n\n"
        "Your task: write pytest tests for the project using file_writer tool. "
        "Use read_file to inspect source files in the workspace. "
        "Write each test file with file_writer (e.g. tests/test_main.py). "
        "Call file_writer — do not output test code as plain text."
    )
    prior = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    seed: list[BaseMessage] = (
        prior + [HumanMessage(content=ctx)] if prior else [HumanMessage(content=ctx)]
    )
    agents, overrides = _extract_profile_from_state(state)
    sub = _cached_testing(agents, overrides)
    try:
        out = sub.invoke(
            {**_subgraph_context(state), "messages": seed},
            _nested_config(config, "testing"),
        )
    except Exception as e:
        logger.exception("testing_subgraph_failed", error=str(e))
        # A malformed tool-call (e.g. deepseek emitting prose with broken JSON
        # args) can crash the subgraph mid-run. Try to salvage any test code the
        # model wrote as prose in the seed messages before giving up; if we
        # recover tests, run the gate instead of failing the phase outright.
        if not _workspace_has_tests():
            salvaged = _extract_and_write_code_blocks(seed)
            if salvaged:
                logger.info("testing_exception_fallback", count=len(salvaged))
        if _workspace_has_tests():
            tr = _run_real_quality_gate()
            return {
                "current_phase": "testing",
                "test_results": tr,
                "phase_history": [
                    {"phase": "testing", "status": "recovered", "passed": tr.get("passed")}
                ],
            }
        return {
            "errors": [
                {
                    "phase": "testing",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ],
            "current_phase": "testing",
        }
    ge = _guardrail_error_dict(out, "testing")
    if ge:
        return {
            "errors": [ge],
            "current_phase": "testing",
        }
    out_msgs = [m for m in (out.get("messages") or []) if isinstance(m, BaseMessage)]
    delta = _message_delta(seed, out_msgs)
    # Salvage: if the QA model emitted test code as markdown prose instead of
    # calling file_writer, no test file reaches the workspace and pytest collects
    # 0 items. Extract fenced blocks from QA's messages and write them before the
    # quality gate runs, mirroring the development-phase fallback.
    if not _workspace_has_tests():
        salvaged = _extract_and_write_code_blocks(delta)
        if salvaged:
            logger.info("testing_fallback_extraction", count=len(salvaged))
    tr = _run_real_quality_gate()
    return {
        "messages": delta,
        "current_phase": "testing",
        "test_results": tr,
        "phase_history": [{"phase": "testing", "status": "complete", "passed": tr.get("passed")}],
    }


def deployment_subgraph_node(
    state: LangGraphProjectState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Run DevOps then Cloud sequential subgraph."""
    arch = state.get("architecture") or {}
    files = state.get("generated_files") or []
    ctx = (
        "Prepare deployment.\n"
        f"Architecture:\n{json.dumps(arch, default=str)[:6000]}\n"
        f"Files:\n{json.dumps(files, default=str)[:6000]}\n"
    )
    prior = [m for m in (state.get("messages") or []) if isinstance(m, BaseMessage)]
    seed: list[BaseMessage] = (
        prior + [HumanMessage(content=ctx)] if prior else [HumanMessage(content=ctx)]
    )
    agents, overrides = _extract_profile_from_state(state)
    sub = _cached_deployment(agents, overrides)
    try:
        out = sub.invoke(
            {**_subgraph_context(state), "messages": seed},
            _nested_config(config, "deployment"),
        )
    except Exception as e:
        logger.exception("deployment_subgraph_failed", error=str(e))
        return {
            "errors": [
                {
                    "phase": "deployment",
                    "message": str(e),
                    "type": type(e).__name__,
                }
            ],
            "current_phase": "deployment",
        }
    ge = _guardrail_error_dict(out, "deployment")
    if ge:
        return {
            "errors": [ge],
            "current_phase": "deployment",
        }
    out_msgs = [m for m in (out.get("messages") or []) if isinstance(m, BaseMessage)]
    delta = _message_delta(seed, out_msgs)
    return {
        "messages": delta,
        "current_phase": "deployment",
        "deployment_config": state.get("deployment_config") or {"status": "pending"},
        "phase_history": [{"phase": "deployment", "status": "complete"}],
    }
