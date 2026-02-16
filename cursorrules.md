# AI-Team Project: Cursor Rules
# Autonomous Multi-Agent Software Development System using CrewAI
# Last Updated: February 2026

## Project Identity

You are working on `ai-team`, an autonomous multi-agent software development system built with CrewAI. The system simulates a complete engineering organization with 7+ specialized AI agents (Manager, Product Owner, Architect, Backend/Frontend Developers, DevOps, Cloud Engineer, QA Engineer) that accept natural language project descriptions and autonomously deliver working, tested, deployable code.

This is a portfolio-grade capstone project demonstrating AI technical leadership. All code must be production-quality, well-documented, and security-conscious.

---

## Technology Stack

- **Python**: 3.11+ (required minimum)
- **CrewAI**: >=0.80.0 — multi-agent orchestration framework
- **CrewAI Tools**: >=0.14.0 — tool extensions
- **LangChain-Ollama**: >=0.2.0 — local LLM integration
- **Pydantic**: >=2.7.0 — data validation and settings
- **Pydantic-Settings**: >=2.2.0 — environment-based configuration
- **Streamlit**: >=1.35.0 — web UI
- **structlog**: >=24.1.0 — structured logging
- **ChromaDB**: >=0.5.0 — vector memory store
- **SQLAlchemy**: >=2.0.0 — long-term memory persistence
- **GitPython**: >=3.1.0 — Git operations
- **httpx**: >=0.27.0 — async HTTP client
- **tenacity**: >=8.2.0 — retry logic
- **pytest**: >=8.0.0 — testing framework
- **ruff**: >=0.3.0 — linting
- **mypy**: >=1.9.0 — type checking
- **black**: >=24.3.0 — formatting
- **Poetry**: build system and dependency management

**Local LLM Models (via Ollama)**:
- qwen3:32b / :14b — general reasoning, management, product ownership
- deepseek-r1:32b / :14b — architecture, deep reasoning
- qwen2.5-coder:32b / :14b — code generation, frontend, devops
- deepseek-coder-v2:16b — backend code generation

---

## Project Structure

```
ai-team/
├── src/ai_team/              # Main package
│   ├── __init__.py
│   ├── main.py               # Entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py       # Pydantic Settings (OllamaModelConfig, GuardrailConfig, etc.)
│   │   ├── agents.yaml       # Agent definitions (role, goal, backstory per agent)
│   │   └── tasks.yaml        # Task definitions (description, expected_output, guardrails)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py           # BaseAgent — extends CrewAI Agent with logging, guardrails, retry
│   │   ├── manager.py        # Manager agent — hierarchical coordinator
│   │   ├── product_owner.py  # Product Owner — requirements, user stories
│   │   ├── architect.py      # Architect — system design, tech selection
│   │   ├── developers/
│   │   │   ├── __init__.py
│   │   │   ├── developer_base.py  # Shared developer capabilities
│   │   │   ├── backend.py    # Backend Developer
│   │   │   ├── frontend.py   # Frontend Developer
│   │   │   └── fullstack.py  # Fullstack Developer
│   │   ├── devops.py         # DevOps / SRE Engineer
│   │   ├── cloud_engineer.py # Cloud Infrastructure Engineer
│   │   └── qa_engineer.py    # QA / Test Automation Engineer
│   ├── crews/
│   │   ├── __init__.py
│   │   ├── planning_crew.py      # PlanningCrew — hierarchical, Manager + PO + Architect
│   │   ├── development_crew.py   # DevelopmentCrew — hierarchical, Architect leads devs
│   │   ├── testing_crew.py       # TestingCrew — sequential, QA Engineer
│   │   └── deployment_crew.py    # DeploymentCrew — sequential, DevOps + Cloud
│   ├── flows/
│   │   ├── __init__.py
│   │   ├── main_flow.py      # AITeamFlow(Flow[ProjectState]) — primary orchestration
│   │   ├── state.py          # ProjectState, PhaseTransition, ProjectError Pydantic models
│   │   ├── routing.py        # @router functions for conditional flow branching
│   │   ├── human_feedback.py # Human-in-the-loop feedback handler
│   │   └── error_handling.py # Error classification, recovery, circuit breaker
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── file_tools.py     # Secure file I/O with path traversal prevention
│   │   ├── code_tools.py     # Sandboxed code execution
│   │   ├── git_tools.py      # Git operations (init, commit, branch, diff)
│   │   └── test_tools.py     # pytest runner, coverage analyzer
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── behavioral.py     # Role adherence, scope control, delegation, output format
│   │   ├── security.py       # Code safety, PII redaction, secret detection, prompt injection
│   │   ├── quality.py        # Code quality scoring, coverage thresholds, docs validation
│   │   └── validators.py     # Shared validation utilities, GuardrailResult model
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── memory_config.py  # MemoryManager — ChromaDB + SQLite + Entity memory
│   │   ├── knowledge_base.py # Best practices, templates, patterns
│   │   └── knowledge/        # YAML/JSON knowledge files
│   ├── models/
│   │   ├── __init__.py
│   │   └── outputs.py        # RequirementsDocument, ArchitectureDocument, CodeFile, TestResult, etc.
│   └── utils/
│       ├── __init__.py
│       ├── logging.py        # structlog configuration
│       ├── callbacks.py      # AITeamCallback — task/crew/guardrail event callbacks
│       └── reasoning.py      # Chain-of-thought templates, self-reflection prompts
├── tests/
│   ├── conftest.py           # Shared fixtures: mock_ollama, sample_project, mock_crew_outputs
│   ├── unit/
│   │   ├── conftest.py
│   │   ├── test_agents.py
│   │   ├── test_tools.py
│   │   ├── test_guardrails.py
│   │   ├── test_guardrails_adversarial.py
│   │   ├── test_models.py
│   │   ├── test_memory.py
│   │   └── test_callbacks.py
│   ├── integration/
│   │   ├── conftest.py
│   │   ├── test_crew_interactions.py
│   │   ├── test_tool_chains.py
│   │   ├── test_guardrail_integration.py
│   │   ├── test_memory_integration.py
│   │   └── test_flow_integration.py
│   ├── e2e/
│   │   ├── conftest.py
│   │   └── test_end_to_end.py
│   ├── performance/
│   │   └── test_benchmarks.py
│   └── fixtures/             # JSON mock responses, sample data
├── ui/
│   ├── app.py                # Main Streamlit application
│   ├── components/
│   │   ├── project_input.py  # ProjectInputForm component
│   │   ├── progress_display.py # PhaseProgressBar, AgentActivityFeed
│   │   └── output_display.py # FileTreeViewer, CodeViewer, TestResultsPanel
│   └── pages/
├── demos/
│   ├── 01_hello_world/       # Simple Flask API demo
│   │   ├── input.json
│   │   ├── validation_criteria.json
│   │   └── expected_output/
│   ├── 02_todo_app/          # Full-stack TODO demo
│   ├── 03_data_pipeline/     # ETL pipeline demo
│   ├── 04_ml_api/            # ML inference demo
│   └── 05_microservices/     # Multi-service demo
├── docs/
│   ├── ARCHITECTURE.md
│   ├── AGENTS.md
│   ├── GUARDRAILS.md
│   ├── FLOWS.md
│   ├── TOOLS.md
│   ├── MEMORY.md
│   ├── GETTING_STARTED.md
│   ├── CREWAI_REFERENCE.md
│   └── API.md
├── scripts/
│   ├── setup_ollama.sh       # Ollama install + model pull
│   ├── test_models.py        # Model benchmarking
│   ├── run_demo.py           # Demo runner
│   ├── run_all_demos.py      # Batch demo validation
│   └── validate_demo.py      # Single demo output validator
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── release.yml
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
├── pyproject.toml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── Makefile
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
└── SECURITY.md
```

---

## Code Style & Conventions

### Python Style
- **Formatter**: black with line length 100
- **Linter**: ruff (rules: E, F, I, N, W, UP, B, C4, SIM)
- **Type checker**: mypy with strict mode for src/
- **Line length**: 100 characters maximum
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE for constants
- **Imports**: sorted with isort (profile=black), grouped: stdlib → third-party → local
- **Docstrings**: Google style on all public classes, methods, and functions
- **Type hints**: required on all function signatures, use `from __future__ import annotations` in every file

### File Headers
Every Python file must start with a module docstring:
```python
"""
Module name and one-line description.

Detailed description of what this module does and how it fits into the system.
"""
```

### Pydantic Conventions
- All data models use Pydantic v2 BaseModel
- Use `Field()` with `description` for all fields
- Add validators using `@field_validator` or `@model_validator`
- Include `model_config` with `json_schema_extra` for examples where helpful
- Settings classes use `pydantic_settings.BaseSettings` with `SettingsConfigDict`
- All output models go in `src/ai_team/models/outputs.py`
- All state models go in `src/ai_team/flows/state.py`

### Error Handling
- Use custom exception classes defined in `src/ai_team/utils/exceptions.py`
- Exception hierarchy: `AITeamError` → `AgentError`, `ToolError`, `GuardrailError`, `FlowError`
- Always catch specific exceptions, never bare `except:`
- Use `tenacity` for retry logic with exponential backoff
- Log all errors with structlog including context (agent, tool, phase)

### Logging
- Use `structlog` everywhere, never `print()` or `logging` directly
- Get loggers with: `logger = structlog.get_logger(__name__)`
- Always bind context: `logger.bind(agent=self.role, phase=current_phase)`
- Log levels: DEBUG (tool calls, internal), INFO (phase transitions, completions), WARNING (retries, soft failures), ERROR (hard failures)
- JSON format in production, colored console in development (configured in settings)

---

## CrewAI Patterns

### Agent Definition Pattern
Agents are defined in two places — YAML for declarative config, Python for behavior:

```python
# src/ai_team/agents/architect.py
from ai_team.agents.base import BaseAgent

class ArchitectAgent(BaseAgent):
    """Solutions Architect agent for system design."""
    
    role_name: str = "architect"  # maps to agents.yaml key
    
    def create(self) -> Agent:
        config = self.load_yaml_config()  # from agents.yaml
        llm = self.get_ollama_llm()       # from settings role→model mapping
        return Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            tools=self.get_tools(),
            llm=llm,
            verbose=config.get("verbose", True),
            memory=config.get("memory", True),
            allow_delegation=config.get("allow_delegation", False),
            max_iter=config.get("max_iter", 10),
        )
```

### Crew Composition Pattern
```python
# src/ai_team/crews/planning_crew.py
from crewai import Crew, Process

class PlanningCrew:
    def kickoff(self, inputs: dict) -> CrewOutput:
        crew = Crew(
            agents=[self.product_owner, self.architect],
            tasks=[self.requirements_task, self.architecture_task],
            process=Process.hierarchical,
            manager_agent=self.manager,
            memory=True,
            verbose=True,
            planning=True,
        )
        return crew.kickoff(inputs=inputs)
```

### Flow Orchestration Pattern
```python
# src/ai_team/flows/main_flow.py
from crewai.flow.flow import Flow, listen, start, router

class AITeamFlow(Flow[ProjectState]):
    @start()
    def intake_request(self):
        # Initialize state, validate input
        ...
    
    @listen(intake_request)
    def run_planning_crew(self):
        # Execute PlanningCrew, store results in state
        ...
    
    @router(run_planning_crew)
    def route_after_planning(self):
        if self.state.requirements and self.state.architecture:
            return "run_development"
        return "request_human_feedback"
```

### Task with Guardrail Pattern
```python
from crewai import Task

def create_requirements_task(agent, guardrail_fn):
    return Task(
        description="Analyze project and create requirements...",
        expected_output="RequirementsDocument with user stories...",
        agent=agent,
        output_pydantic=RequirementsDocument,
        guardrail=guardrail_fn,  # CrewAI calls this to validate output
    )
```

### Guardrail Function Pattern
```python
# Guardrail functions receive (task_output: TaskOutput) and return TaskOutput or raise
def requirements_completeness_guardrail(task_output: TaskOutput) -> TaskOutput:
    """Validate requirements document completeness."""
    result = validate_requirements(task_output.pydantic)
    if result.status == "fail":
        raise GuardrailFailure(result.message)  # triggers retry
    return task_output
```

### Tool Definition Pattern
```python
from crewai.tools import tool

@tool("Read File")
def read_file(file_path: str) -> str:
    """Read a file from the workspace directory securely.
    
    Args:
        file_path: Relative path to the file within the workspace.
    
    Returns:
        The file contents as a string.
    """
    # Security checks first
    validated_path = validate_path(file_path)
    audit_log("read_file", validated_path)
    return validated_path.read_text()
```

---

## Security Requirements

### Mandatory Security Practices
1. **Path traversal prevention**: All file operations validate paths against a whitelist of allowed directories. No `..` traversal. Resolve symlinks before access.
2. **Code execution sandboxing**: All code execution uses subprocess with timeouts, resource limits, and restricted imports. Never `eval()` or `exec()` on untrusted input.
3. **PII detection**: Scan all generated content for emails, phone numbers, SSNs, credit cards, API keys before output.
4. **Secret detection**: Scan for hardcoded AWS keys, GitHub tokens, passwords, connection strings, JWT secrets.
5. **Prompt injection defense**: Validate all external inputs for instruction override attempts.
6. **Dangerous pattern blocking**: Block `eval`, `exec`, `os.system`, `subprocess.call(shell=True)`, `__import__`, `pickle.loads`, `yaml.load` (without SafeLoader).
7. **Audit logging**: Log all file operations, code executions, and tool invocations with timestamps.

### Security Guardrail Integration
Every tool wraps operations with security checks:
```python
def secure_tool_wrapper(func):
    def wrapper(*args, **kwargs):
        # Pre-execution: validate inputs
        security_result = run_security_guardrails(args, kwargs)
        if security_result.status == "fail":
            raise SecurityViolation(security_result.message)
        # Execute
        result = func(*args, **kwargs)
        # Post-execution: scan output
        output_scan = scan_output_for_secrets(result)
        if output_scan.has_findings:
            result = redact_secrets(result)
        return result
    return wrapper
```

---

## Testing Standards

### Test Requirements
- **Unit test coverage**: ≥90% for src/ai_team/
- **Integration test coverage**: all crew handoffs and tool chains
- **All guardrails**: adversarial test cases with known-bad inputs
- **All Pydantic models**: validation, serialization, edge cases

### Test File Naming
- Unit tests: `tests/unit/test_{module}.py`
- Integration tests: `tests/integration/test_{feature}_integration.py`
- E2E tests: `tests/e2e/test_end_to_end.py`
- Performance: `tests/performance/test_benchmarks.py`

### Fixture Patterns
```python
# tests/conftest.py
import pytest

@pytest.fixture
def mock_ollama(mocker):
    """Mock Ollama HTTP responses for testing without a running model."""
    ...

@pytest.fixture
def sample_project_description():
    return "Create a Flask REST API with GET /health and GET /items endpoints"

@pytest.fixture
def sample_requirements_doc():
    return RequirementsDocument(project_name="test", ...)

@pytest.fixture
def sample_code_files():
    return [CodeFile(path="app.py", content="...", language="python")]
```

### Test Structure
```python
class TestSecurityGuardrails:
    """Tests for security guardrail module."""
    
    def test_detects_eval_in_code(self, security_guardrail):
        result = security_guardrail.code_safety_guardrail("x = eval(user_input)")
        assert result.status == "fail"
        assert "eval" in result.message
    
    @pytest.mark.parametrize("dangerous_code", [
        "eval('1+1')",
        "__builtins__['eval']('1+1')",
        "getattr(__builtins__, 'eval')('1+1')",
    ])
    def test_detects_eval_variants(self, security_guardrail, dangerous_code):
        result = security_guardrail.code_safety_guardrail(dangerous_code)
        assert result.status == "fail"
```

---

## Pydantic Model Reference

### Core Output Models (src/ai_team/models/outputs.py)

```
RequirementsDocument
├── project_name: str
├── description: str
├── target_users: List[str]
├── user_stories: List[UserStory]
│   ├── as_a: str
│   ├── i_want: str
│   ├── so_that: str
│   ├── acceptance_criteria: List[str]
│   └── priority: MoSCoW (must/should/could/wont)
├── non_functional_requirements: List[NFR]
├── assumptions: List[str]
└── constraints: List[str]

ArchitectureDocument
├── system_overview: str
├── components: List[Component]
├── technology_stack: Dict[str, TechChoice]
├── interfaces: List[Interface]
├── data_model: List[Entity]
├── deployment_topology: str
└── adrs: List[ADR]

CodeFile
├── path: str
├── content: str
├── language: str
├── file_type: str (source/test/config/doc)
├── dependencies: List[str]
└── size_bytes: int

TestResult / TestRunResult
├── total, passed, failed, errors, skipped: int
├── coverage_line: float
├── coverage_branch: float
├── failures: List[TestFailure]
└── duration_seconds: float

DeploymentConfig
├── dockerfile: str
├── docker_compose: str
├── ci_pipeline: str
├── environment_variables: Dict[str, str]
└── infrastructure: Optional[str]

ProjectReport
├── project_id, project_name, status: str
├── files: List[CodeFile]
├── test_results: TestResult
├── summary: str
└── duration: timedelta
```

### Flow State Model (src/ai_team/flows/state.py)

```
ProjectState(BaseModel)
├── project_id: str (UUID)
├── project_description: str
├── current_phase: ProjectPhase (enum)
├── requirements: Optional[RequirementsDocument]
├── architecture: Optional[ArchitectureDocument]
├── generated_files: List[CodeFile]
├── test_results: Optional[TestRunResult]
├── deployment_config: Optional[DeploymentConfig]
├── phase_history: List[PhaseTransition]
├── errors: List[ProjectError]
├── retry_counts: Dict[str, int]
├── max_retries: int = 3
├── started_at: datetime
├── completed_at: Optional[datetime]
└── metadata: Dict[str, Any]

ProjectPhase (enum): INTAKE, PLANNING, DEVELOPMENT, TESTING, DEPLOYMENT, COMPLETE, ERROR
```

### Guardrail Result Model

```
GuardrailResult(BaseModel)
├── status: str ("pass" / "fail" / "warn")
├── message: str
├── details: Dict[str, Any]
├── retry_allowed: bool
└── severity: str ("info" / "warning" / "critical")
```

---

## Agent Role Reference

| Agent | Role | Model | Process Role | Key Tools |
|-------|------|-------|--------------|-----------|
| Manager | Engineering Manager / Coordinator | qwen3 | manager_agent (hierarchical) | task_delegation, status_reporting |
| Product Owner | Requirements Analyst | qwen3 | PlanningCrew member | requirements_parser, user_story_generator |
| Architect | Solutions Architect / Tech Lead | deepseek-r1 | PlanningCrew + DevelopmentCrew manager | architecture_designer, technology_selector |
| Backend Dev | Backend Developer | deepseek-coder-v2 | DevelopmentCrew member | code_generation, api_implementation |
| Frontend Dev | Frontend Developer | qwen2.5-coder | DevelopmentCrew member | component_generator, api_client_generator |
| DevOps | DevOps / SRE Engineer | qwen2.5-coder | DevelopmentCrew + DeploymentCrew | dockerfile_generator, ci_pipeline_generator |
| Cloud Engineer | Cloud Infrastructure Engineer | qwen2.5-coder | DeploymentCrew member | terraform_generator, iam_policy_generator |
| QA Engineer | QA / Test Automation | qwen3 | TestingCrew member | test_generator, test_runner, coverage_analyzer |

---

## Flow Routing Reference

```
INTAKE → PLANNING → DEVELOPMENT → TESTING → DEPLOYMENT → COMPLETE
                ↓                      ↓
         HUMAN_FEEDBACK          RETRY_DEVELOPMENT (max 3x)
                                       ↓
                                 HUMAN_ESCALATION
```

Routing decisions:
- Planning → Development: requirements AND architecture both complete
- Planning → Human Feedback: requirements ambiguous (confidence < 0.7)
- Development → Testing: code files generated successfully
- Testing → Deployment: all tests pass, coverage ≥ threshold
- Testing → Retry Development: tests failed, retries remaining (with feedback)
- Testing → Human Escalation: retries exhausted or critical failures
- Deployment → Complete: packaging successful
- Any phase → Error: unrecoverable error with state preservation

---

## Configuration Reference

### Environment Variables (.env)
```
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MANAGER_MODEL=qwen3:14b
OLLAMA_ARCHITECT_MODEL=deepseek-r1:14b
OLLAMA_BACKEND_DEVELOPER_MODEL=deepseek-coder-v2:16b
OLLAMA_FRONTEND_DEVELOPER_MODEL=qwen2.5-coder:14b

# Guardrails
GUARDRAIL_MAX_RETRIES=3
GUARDRAIL_CODE_QUALITY_MIN_SCORE=7.0
GUARDRAIL_TEST_COVERAGE_MIN=80
GUARDRAIL_ENABLE_SECURITY=true
GUARDRAIL_ENABLE_BEHAVIORAL=true
GUARDRAIL_ENABLE_QUALITY=true

# Memory
MEMORY_CHROMADB_PATH=./data/chromadb
MEMORY_SQLITE_PATH=./data/memory.db
MEMORY_ENABLED=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json  # or "console"

# Project
PROJECT_OUTPUT_DIR=./output
PROJECT_WORKSPACE_DIR=./workspace
PROJECT_MAX_ITERATIONS=15
PROJECT_DEFAULT_TIMEOUT=300
```

---

## Common Patterns to Follow

### When creating a new agent:
1. Add YAML config to `config/agents.yaml` with role, goal, backstory, verbose, memory, allow_delegation, max_iter
2. Create Python class in `agents/` extending `BaseAgent`
3. Define tools as `@tool` decorated functions in `tools/`
4. Add model assignment in `config/settings.py` `OllamaModelConfig`
5. Register in the appropriate crew's agent list
6. Add unit test in `tests/unit/test_agents.py`

### When creating a new tool:
1. Create in `src/ai_team/tools/` with `@tool` decorator
2. Include security wrapper (path validation, content scanning)
3. Add audit logging for all operations
4. Define Pydantic models for structured input/output
5. Add unit test with normal and adversarial inputs
6. Register in the appropriate agent's tool list

### When creating a new guardrail:
1. Add to appropriate module: `behavioral.py`, `security.py`, or `quality.py`
2. Return `GuardrailResult` Pydantic model
3. Integrate with CrewAI task `guardrail` parameter
4. Add configuration toggles in `GuardrailConfig` settings
5. Add unit test with passing, failing, and edge-case inputs
6. Add adversarial test in `test_guardrails_adversarial.py`

### When creating a new crew:
1. Create in `src/ai_team/crews/` with `kickoff()` method
2. Define tasks in `tasks/` with YAML + Python
3. Set process type (hierarchical or sequential)
4. Configure memory, planning, verbose settings
5. Add context dependencies between tasks
6. Integrate guardrails at task level
7. Add integration test for crew execution with mocked LLM

### When adding to the flow:
1. Add `@listen` method to `AITeamFlow` in `flows/main_flow.py`
2. Add `@router` for conditional branching if needed
3. Update `ProjectState` with new fields if needed
4. Add phase to `ProjectPhase` enum if new
5. Add error handler in `error_handling.py`
6. Update routing documentation
7. Add integration test for new flow path

---

## Quality Gates

Before marking any phase complete:
- [ ] All new code has type hints on function signatures
- [ ] All public classes and functions have Google-style docstrings
- [ ] ruff check passes with zero warnings
- [ ] mypy passes with zero errors (for modified files)
- [ ] black formatting applied
- [ ] Unit tests written and passing
- [ ] Integration tests updated if cross-module changes
- [ ] Security guardrails cover any new file/code/network operations
- [ ] structlog logging added for significant operations
- [ ] Settings configurable via environment variables where appropriate
- [ ] Pydantic models used for all structured data

---

## Common Pitfalls to Avoid

1. **Never use `print()`** — always use structlog
2. **Never use bare `except:`** — always catch specific exceptions
3. **Never hardcode model names** — always read from settings
4. **Never access files outside workspace** — always validate paths
5. **Never use `eval()`, `exec()`, `os.system()`** in tools or generated code
6. **Never skip guardrails** — even in tests, test that guardrails fire correctly
7. **Never use `yaml.load()` without `SafeLoader`**
8. **Never store secrets in code** — always use environment variables
9. **Never skip type hints** — mypy runs in CI
10. **Never create circular imports** — follow the dependency direction: utils → models → guardrails → tools → agents → crews → flows
11. **Never use `subprocess.call(shell=True)`** — always use `shell=False` with explicit command lists
12. **Never commit `.env`** — only `.env.example` with placeholder values

---

## Dependency Direction (Import Order)

```
utils/logging.py, utils/reasoning.py  (no internal deps)
       ↓
models/outputs.py  (depends on utils)
       ↓
guardrails/behavioral.py, security.py, quality.py  (depends on models)
       ↓
tools/file_tools.py, code_tools.py, etc.  (depends on guardrails, models)
       ↓
agents/base.py, agents/*.py  (depends on tools, models)
       ↓
config/settings.py  (can be imported anywhere, no internal deps)
       ↓
crews/*.py  (depends on agents, tasks)
       ↓
flows/*.py  (depends on crews, state models)
       ↓
main.py, ui/app.py  (top-level, depends on flows)
```

Never import upward in this chain. If you need something from a higher layer, pass it as a parameter.

---

## Performance Targets

- Individual guardrail execution: < 100ms
- Total guardrail overhead: < 10% of task time
- Memory operations (store/retrieve): < 50ms per operation
- Full flow (with mocked LLM): < 30 seconds
- Full flow (with real Ollama): depends on model, target < 10 minutes for simple projects
- Test suite (unit): < 30 seconds
- Test suite (full): < 5 minutes

---

## Git Conventions

- **Branch naming**: `feature/phase-{N}-{description}`, `fix/{description}`, `test/{description}`
- **Commit messages**: Conventional Commits format
  - `feat(agents): add Architect agent with ADR generation`
  - `fix(guardrails): correct PII regex for international phone numbers`
  - `test(crews): add integration test for planning→development handoff`
  - `docs(readme): add architecture diagram and quick start`
- **PR scope**: one phase or one feature per PR
- **Required checks**: ruff, mypy, pytest (unit), pytest (integration)
