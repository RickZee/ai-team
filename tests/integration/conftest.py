"""Pytest configuration and fixtures for integration tests.

Shared fixtures and mock helpers for crew and full-flow integration tests.
By default all LLM calls are mocked. Set AI_TEAM_USE_REAL_LLM=1 to run
crew-level integration tests against real Ollama (full-flow tests stay mock-only).
When using real LLM, CrewAI crew memory is forced off (memory=False) so CrewAI's
built-in RAG/embedder is not used (it can default to an API-key-based embedder).
AI-Team's own memory (ChromaDB + Ollama) is local and separate. Use 14B+ models for fewer skips.

Full-flow tests (marked with @pytest.mark.full_flow) use a manual flow driver
(_run_flow_manually) and do not call flow.kickoff(), so they run synchronously
and do not hang or spike memory.
"""

from __future__ import annotations

import os
import json
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

from ai_team.models.architecture import (
    ArchitectureDocument,
    Component,
    TechnologyChoice,
)
from ai_team.models.development import CodeFile
from ai_team.models.requirements import (
    AcceptanceCriterion,
    MoSCoW,
    RequirementsDocument,
    UserStory,
)
from ai_team.tools.test_tools import TestRunResult


def pytest_configure(config: Any) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "full_flow: full AITeamFlow tests driven by manual runner (no kickoff).",
    )
    config.addinivalue_line(
        "markers",
        "real_llm: integration tests that use real Ollama when AI_TEAM_USE_REAL_LLM=1.",
    )
    config.addinivalue_line(
        "markers",
        "test_memory: memory/embedder tests; run when AI_TEAM_TEST_MEMORY=1 and Ollama (and embedding model) available.",
    )


@pytest.fixture
def use_real_llm() -> bool:
    """Whether to use real Ollama in crew-level integration tests (default: False)."""
    return os.environ.get("AI_TEAM_USE_REAL_LLM", "").lower() in ("1", "true", "yes")


@pytest.fixture
def test_memory_enabled() -> bool:
    """Whether to run memory/embedder integration tests (default: False)."""
    return os.environ.get("AI_TEAM_TEST_MEMORY", "").lower() in ("1", "true", "yes")


def _wrap_ollama_llm_for_crewai(llm: Any) -> Any:
    """Wrap a LangChain-style LLM (has invoke) so CrewAI's llm.call(messages, ...) works.
    CrewAI expects .call(); LangChain uses .invoke(). Adapter converts messages and returns content."""
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

    def _to_langchain_messages(messages: Any) -> list[BaseMessage]:
        out: list[BaseMessage] = []
        for m in messages:
            role = m.get("role", "user") if isinstance(m, dict) else getattr(m, "role", "user")
            content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
            if role == "user":
                out.append(HumanMessage(content=content))
            elif role == "assistant":
                out.append(AIMessage(content=content))
            else:
                out.append(SystemMessage(content=content))
        return out

    class _OllamaCallAdapter:
        def __init__(self, inner: Any) -> None:
            self._llm = inner
            self.model = getattr(inner, "model", None)
            self.base_url = getattr(inner, "base_url", None)
            self.invoke = inner.invoke
            self.stop: list[str] = []

        def supports_stop_words(self) -> bool:
            return True

        def supports_function_calling(self) -> bool:
            return False

        def call(
            self,
            messages: Any,
            callbacks: Any = None,
            from_task: Any = None,
            from_agent: Any = None,
            response_model: Any = None,
            **kwargs: Any,
        ) -> str:
            lc_messages = _to_langchain_messages(messages)
            config: dict[str, Any] = {}
            # Do not pass CrewAI callbacks (e.g. TokenCalcHandler) to LangChain; they are
            # incompatible (LangChain expects BaseCallbackHandler with raise_error, etc.).
            kwargs_invoke: dict[str, Any] = {}
            if self.stop:
                kwargs_invoke["stop"] = self.stop
            result = self._llm.invoke(
                lc_messages, config=config or None, **kwargs_invoke
            )
            content = getattr(result, "content", str(result)) or ""
            if not content or not content.strip():
                result = self._llm.invoke(
                    lc_messages, config=config or None, **kwargs_invoke
                )
                content = getattr(result, "content", str(result)) or ""
            return content

    return _OllamaCallAdapter(llm)


@pytest.fixture(autouse=True)
def _patch_create_llm_for_real_ollama(use_real_llm: bool) -> Any:
    """When using real Ollama, ensure every LLM is Ollama (no OpenAI path). Pass through
    our LangChain ChatOllama instances; when CrewAI passes a string model name (e.g.
    for its planning agent), build a ChatOllama from settings. Wrap in an adapter so
    CrewAI's .call(messages, ...) works (LangChain uses .invoke()). When use_real_llm,
    also force CrewAI crew memory off so its built-in RAG/embedder is not used
    (that path can default to an API-key-based embedder; AI-Team memory is local)."""
    if not use_real_llm:
        yield
        return

    import crewai.agent.core as crewai_core
    from langchain_ollama import ChatOllama

    from ai_team.config.settings import get_settings
    from ai_team.crews import development_crew as development_crew_mod
    from ai_team.crews import planning_crew as planning_crew_mod
    from ai_team.crews import testing_crew as testing_crew_mod

    _original_create_llm = crewai_core.create_llm

    def _create_llm_passthrough(llm_value: Any) -> Any:
        if (
            llm_value is not None
            and not isinstance(llm_value, str)
            and hasattr(llm_value, "invoke")
        ):
            return _wrap_ollama_llm_for_crewai(llm_value)
        if isinstance(llm_value, str) and llm_value.strip():
            settings = get_settings()
            model = llm_value.strip()
            # CrewAI may pass a cloud model name (e.g. gpt-4o-mini) for its planning agent;
            # use our default Ollama model so we never call a non-Ollama API.
            if model.startswith("gpt-") or model.startswith("claude-") or "openai" in model.lower():
                model = settings.ollama.default_model
            chat = ChatOllama(
                model=model,
                base_url=settings.ollama.base_url,
                request_timeout=settings.ollama.request_timeout,
            )
            return _wrap_ollama_llm_for_crewai(chat)
        return _original_create_llm(llm_value)

    _orig_create_planning = planning_crew_mod.create_planning_crew
    _orig_create_development = development_crew_mod.create_development_crew
    _orig_create_testing = testing_crew_mod.create_testing_crew

    def _create_planning_no_memory(*args: Any, **kwargs: Any) -> Any:
        return _orig_create_planning(*args, **{**kwargs, "memory": False})

    def _create_development_no_memory(*args: Any, **kwargs: Any) -> Any:
        return _orig_create_development(*args, **{**kwargs, "memory": False})

    def _create_testing_no_memory(*args: Any, **kwargs: Any) -> Any:
        return _orig_create_testing(*args, **{**kwargs, "memory": False})

    with patch.object(crewai_core, "create_llm", side_effect=_create_llm_passthrough), patch.object(
        planning_crew_mod, "create_planning_crew", _create_planning_no_memory
    ), patch.object(
        development_crew_mod, "create_development_crew", _create_development_no_memory
    ), patch.object(testing_crew_mod, "create_testing_crew", _create_testing_no_memory):
        yield


# -----------------------------------------------------------------------------
# Sample project and mock outputs
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_project_description() -> str:
    """Simple project description for integration tests."""
    return "Create a REST API for todo items"


@pytest.fixture
def sample_requirements_document() -> RequirementsDocument:
    """Minimal valid RequirementsDocument with at least 3 user stories."""
    return RequirementsDocument(
        project_name="Todo API",
        description="REST API for managing todo items",
        target_users=["developers", "end users"],
        user_stories=[
            UserStory(
                as_a="user",
                i_want="to list all todos",
                so_that="I can see my tasks",
                acceptance_criteria=[
                    AcceptanceCriterion(description="GET /todos returns 200 and JSON list", testable=True),
                ],
                priority=MoSCoW.MUST,
                story_id="US-1",
            ),
            UserStory(
                as_a="user",
                i_want="to create a todo",
                so_that="I can add tasks",
                acceptance_criteria=[
                    AcceptanceCriterion(description="POST /todos creates a todo and returns 201", testable=True),
                ],
                priority=MoSCoW.MUST,
                story_id="US-2",
            ),
            UserStory(
                as_a="user",
                i_want="to delete a todo",
                so_that="I can remove completed tasks",
                acceptance_criteria=[
                    AcceptanceCriterion(description="DELETE /todos/{id} returns 204", testable=True),
                ],
                priority=MoSCoW.MUST,
                story_id="US-3",
            ),
        ],
        non_functional_requirements=[],
        assumptions=[],
        constraints=[],
    )


@pytest.fixture
def sample_architecture_document() -> ArchitectureDocument:
    """Minimal valid ArchitectureDocument."""
    return ArchitectureDocument(
        system_overview="REST API backend for todo CRUD with in-memory store.",
        components=[
            Component(name="API", responsibilities="HTTP endpoints for todo CRUD"),
            Component(name="Backend", responsibilities="Business logic and storage"),
        ],
        technology_stack=[
            TechnologyChoice(name="FastAPI", category="backend", justification="Async, OpenAPI"),
        ],
        interface_contracts=[],
        data_model_outline="Todo(id, title, done)",
        ascii_diagram="",
        adrs=[],
        deployment_topology="Single process",
    )


@pytest.fixture
def sample_code_files() -> List[CodeFile]:
    """Minimal list of CodeFile with imports and functions."""
    return [
        CodeFile(
            path="src/app/main.py",
            content=(
                "from fastapi import FastAPI\n\napp = FastAPI()\n\n"
                "@app.get(\"/todos\")\ndef list_todos():\n    return []\n"
            ),
            language="python",
            description="FastAPI app and todo list endpoint",
            has_tests=True,
        ),
        CodeFile(
            path="tests/test_main.py",
            content=(
                "import pytest\nfrom fastapi.testclient import TestClient\n"
                "from app.main import app\n\nclient = TestClient(app)\n\n"
                "def test_list_todos():\n    r = client.get(\"/todos\")\n    assert r.status_code == 200\n"
            ),
            language="python",
            description="Tests for todo API",
            has_tests=False,
        ),
    ]


@pytest.fixture
def sample_test_run_result_passed() -> TestRunResult:
    """TestRunResult indicating all tests passed with coverage."""
    return TestRunResult(
        total=5,
        passed=5,
        failed=0,
        errors=0,
        skipped=0,
        warnings=0,
        duration_seconds=1.2,
        line_coverage_pct=85.0,
        branch_coverage_pct=80.0,
        per_file_coverage=[],
        raw_output="5 passed in 1.20s",
        success=True,
    )


@pytest.fixture
def sample_test_run_result_failed() -> TestRunResult:
    """TestRunResult indicating test failures."""
    return TestRunResult(
        total=5,
        passed=3,
        failed=2,
        errors=0,
        skipped=0,
        warnings=0,
        duration_seconds=1.0,
        line_coverage_pct=60.0,
        branch_coverage_pct=None,
        per_file_coverage=[],
        raw_output="3 passed, 2 failed",
        success=False,
    )


# -----------------------------------------------------------------------------
# Mock crew outputs (CrewOutput and task outputs)
# -----------------------------------------------------------------------------


def _task_output_with_raw(raw: str) -> SimpleNamespace:
    """Build a task output object with .raw attribute (for _parse_planning_output)."""
    return SimpleNamespace(raw=raw)


def mock_planning_crew_output(
    requirements: RequirementsDocument,
    architecture: ArchitectureDocument,
) -> SimpleNamespace:
    """Build a crew result that _parse_planning_output can consume (tasks_output with .raw)."""
    req_json = json.dumps(requirements.model_dump(mode="json"))
    arch_json = json.dumps(architecture.model_dump(mode="json"))
    tasks_output = [
        _task_output_with_raw(req_json),
        _task_output_with_raw(arch_json),
    ]
    return SimpleNamespace(raw="", tasks_output=tasks_output)


def mock_development_crew_output(
    code_files: List[CodeFile],
) -> MagicMock:
    """Build a mock development crew kickoff result (tuple of code_files, deployment_config)."""
    return code_files, None


def mock_testing_crew_output(
    test_run_result: TestRunResult,
    quality_gate_passed: bool,
) -> Any:
    """Build a TestingCrewOutput-like object for testing."""
    from ai_team.crews.testing_crew import TestingCrewOutput

    return TestingCrewOutput(
        test_run_result=test_run_result,
        code_review_report=None,
        quality_gate_passed=quality_gate_passed,
        raw_outputs=[],
    )


@pytest.fixture
def mock_crew_outputs(
    sample_requirements_document: RequirementsDocument,
    sample_architecture_document: ArchitectureDocument,
    sample_code_files: List[CodeFile],
    sample_test_run_result_passed: TestRunResult,
    sample_test_run_result_failed: TestRunResult,
) -> dict[str, Any]:
    """Bundle of mock crew outputs for full-flow tests."""
    return {
        "planning": mock_planning_crew_output(
            sample_requirements_document,
            sample_architecture_document,
        ),
        "development": mock_development_crew_output(sample_code_files),
        "testing_passed": mock_testing_crew_output(
            sample_test_run_result_passed,
            quality_gate_passed=True,
        ),
        "testing_failed": mock_testing_crew_output(
            sample_test_run_result_failed,
            quality_gate_passed=False,
        ),
        "requirements": sample_requirements_document,
        "architecture": sample_architecture_document,
        "code_files": sample_code_files,
        "test_result_passed": sample_test_run_result_passed,
    }
