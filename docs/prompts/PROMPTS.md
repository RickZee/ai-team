# AI-Team: Complete Cursor AI Prompts Reference

## Phase 0: Preparation & Research (Days 1-3)

### Prompt 0.1: Generate pyproject.toml
```
Create a pyproject.toml for a CrewAI multi-agent project called "ai-team" with these dependencies:
- crewai>=0.80.0
- crewai-tools
- langchain-ollama
- pydantic>=2.0
- gradio
- python-dotenv
- structlog
- chromadb
- pytest
- pytest-asyncio

Include development dependencies for testing and linting (black, ruff, mypy, pytest-cov).
Use Poetry as the build system. Set Python requirement to >=3.11.
Include project metadata: name, version, description, authors, license.
Add script entry points for: ai-team (main CLI), ai-team-ui (Gradio launcher).

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 0.2: Generate Ollama setup script
```
Create a bash script scripts/setup_ollama.sh that:
1. Checks if Ollama is installed, installs if not (Linux/Mac detection)
2. Starts the Ollama server if not running
3. Pulls these models with progress indication:
   - qwen3:32b (or :14b for lower VRAM)
   - qwen2.5-coder:32b (or :14b)
   - deepseek-r1:32b (or :14b)
   - deepseek-coder-v2:16b
4. Verifies each model works with a simple test prompt
5. Reports VRAM usage estimates per model
6. Creates a .env file with recommended model assignments per agent role
7. Supports --small flag to pull :14b variants instead of :32b

Include error handling, colored output, and a summary table at the end.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 0.3: Generate model benchmark script
```
Create a Python script scripts/test_models.py that benchmarks Ollama models for agent role suitability:
1. Code generation quality — generate a Python function with docstring, type hints, error handling
2. Reasoning capability — solve a multi-step architectural design problem
3. Instruction following — generate output in a specific JSON schema
4. Response latency — measure time-to-first-token and total generation time
5. Token throughput — tokens per second

Test each model: qwen3:32b, qwen2.5-coder:32b, deepseek-r1:32b, deepseek-coder-v2:16b
Score each on a 1-10 scale per category.
Output results as both JSON and a formatted table.
Include a recommendation mapping: which model is best for which agent role.
Use langchain-ollama for model interaction.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 0.4: Generate CrewAI reference document
```
Create docs/CREWAI_REFERENCE.md — a concise reference guide covering:
1. Agent configuration — YAML vs Python, key parameters (role, goal, backstory, tools, memory, verbose, allow_delegation, max_iter)
2. Task configuration — description, expected_output, agent assignment, context dependencies, output_pydantic, guardrail
3. Crew composition — sequential vs hierarchical process, manager_agent, memory settings, planning
4. Flows — @start(), @listen(), @router(), state management with Pydantic BaseModel, @human_feedback
5. Memory types — short-term (ChromaDB), long-term (SQLite), entity memory, knowledge sources
6. Guardrails — task guardrails (validation functions), LLM guardrails, retry behavior
7. Tools — @tool decorator, BaseTool class, tool schemas, error handling
8. Callbacks — task callbacks, step callbacks, crew callbacks

Include code snippets for each concept. Format as a quick-reference cheat sheet.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 0.5: Generate architecture design document
```
Create docs/ARCHITECTURE.md with:
1. System overview diagram (ASCII art showing Flow → Crews → Agents → Tools)
2. Component descriptions for each layer:
   - Flow Layer: AITeamFlow orchestrator, ProjectState, routing logic
   - Crew Layer: PlanningCrew, DevelopmentCrew, TestingCrew, DeploymentCrew
   - Agent Layer: 7 specialized agents with their responsibilities
   - Tool Layer: File, Code, Git, Test tools with security wrappers
   - Guardrail Layer: Behavioral, Security, Quality guardrails
   - Memory Layer: Short-term, Long-term, Entity memory
3. Data flow diagram showing how a project request flows through the system
4. State machine diagram for ProjectState transitions
5. Technology stack table (CrewAI, Ollama, Pydantic, ChromaDB, SQLite, Gradio)
6. Directory structure mapping to components
7. Integration points and extension guide
8. Architecture Decision Records (ADRs) for key decisions:
   - ADR-001: Why CrewAI Flows over LangGraph
   - ADR-002: Why Ollama over cloud APIs
   - ADR-003: Why hierarchical process for planning/dev crews

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

---

## Phase 1: Repository Setup & Environment (Days 4-6)

### Prompt 1.1: Generate project scaffold
```
Create the complete directory structure for the ai-team project:
- src/ai_team/ with submodules: config/, agents/, crews/, flows/, tools/, guardrails/, memory/, utils/
- tests/ with unit/, integration/, e2e/ folders, each with __init__.py and conftest.py
- docs/ with stub markdown files: ARCHITECTURE.md, AGENTS.md, GUARDRAILS.md, FLOWS.md, TOOLS.md, MEMORY.md
- scripts/ with placeholder scripts: setup_ollama.sh, test_models.py, run_demo.py
- ui/ with Gradio app structure: app.py, components/, pages/
- demos/ with 01_hello_world/, 02_todo_app/ folders containing input.json and expected_output.json

Include __init__.py files with module docstrings in every Python package.
Include .env.example, .gitignore (Python + IDE + Docker).
Include type hints stub in py.typed marker file.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 1.2: Generate settings module
```
Create src/ai_team/config/settings.py — a Pydantic Settings class that:
1. Loads from .env file using pydantic-settings
2. Has OllamaSettings nested model with:
   - base_url (default http://localhost:11434)
   - Per-role model assignments (manager_model, product_owner_model, architect_model,
     backend_dev_model, frontend_dev_model, devops_model, cloud_model, qa_model)
   - Default model fallback
   - Request timeout, max retries
3. Has GuardrailSettings nested model with:
   - max_retries per guardrail type (behavioral, security, quality)
   - Thresholds (code_quality_min_score, test_coverage_min, max_file_size_kb)
   - Dangerous patterns list, PII patterns list
   - Enable/disable flags per guardrail category
4. Has MemorySettings with:
   - chromadb_path, sqlite_path
   - embedding_model, collection_name
   - memory_enabled flag
5. Has LoggingSettings with:
   - log_level, log_format (json/console)
   - log_file path
6. Has ProjectSettings with:
   - output_dir, workspace_dir
   - max_iterations, default_timeout
7. Validates Ollama connection on startup with a health check method
8. Class method to create from YAML file as alternative

Include docstrings, field descriptions, and validators.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 1.3: Generate Dockerfile and docker-compose
```
Create two files:

1. Dockerfile — multi-stage build:
   - Stage 1 (builder): Python 3.11-slim, install Poetry, copy pyproject.toml, install deps
   - Stage 2 (runtime): Python 3.11-slim, copy from builder, create non-root user "aiteam"
   - Install system deps: git, build-essential, curl
   - Expose port 7860 for Gradio
   - Health check endpoint
   - Entrypoint: poetry run ai-team-ui

2. docker-compose.yml:
   - Service "app": builds from Dockerfile, maps port 7860, mounts ./output volume
   - Service "ollama": uses ollama/ollama image, maps port 11434, GPU support with deploy.resources
   - Shared network between services
   - Environment variables from .env file
   - Volume for Ollama model cache persistence

Include .dockerignore file.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 1.4: Generate CI/CD pipeline
```
Create .github/workflows/ci.yml — a GitHub Actions workflow with:
1. Trigger on push to main/develop and all pull requests
2. Matrix strategy: Python 3.11, 3.12
3. Jobs:
   a. lint: Run ruff check, ruff format --check, mypy src/
   b. test: Run pytest tests/unit with coverage report, upload coverage artifact
   c. integration-test: Run pytest tests/integration (only on main branch)
   d. security: Run bandit for security scanning, pip-audit for dependency vulnerabilities
4. Cache Poetry dependencies between runs
5. Upload test results as artifacts
6. Status badge configuration
7. Branch protection rules recommendation in comments

Also create .github/workflows/release.yml:
1. Trigger on tag push (v*)
2. Build and push Docker image to GitHub Container Registry
3. Create GitHub Release with changelog

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 1.5: Generate initial documentation
```
Create these documentation files:

1. README.md — comprehensive project README with:
   - Badges (build, coverage, license, Python version)
   - Project description and key features table
   - Architecture diagram (ASCII art)
   - Quick start guide (3-command setup)
   - Configuration reference
   - Demo projects table
   - Testing instructions
   - Project structure tree
   - Contributing section
   - License and acknowledgments

2. CONTRIBUTING.md:
   - Development setup instructions
   - Code style guide (black, ruff, mypy)
   - PR process and commit message convention
   - Testing requirements
   - Adding new agents/tools/guardrails guide

3. docs/GETTING_STARTED.md:
   - Prerequisites checklist
   - Step-by-step installation
   - First run walkthrough
   - Troubleshooting common issues (Ollama not running, model not found, VRAM errors)

Use professional language suitable for a portfolio project.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

---

## Phase 2: Agent Definition, Tools & Guardrails (Days 7-14)

### Prompt 2.1: Generate Base Agent class
```
Create src/ai_team/agents/base.py with a BaseAgent class that extends CrewAI's Agent:
1. Common configuration loading from YAML and settings
2. Automatic Ollama LLM initialization based on role → model mapping from settings
3. Structured logging integration using structlog (log agent actions, tool calls, decisions)
4. Memory hooks — before_task and after_task callbacks for memory persistence
5. Guardrail integration — wrap tool execution with guardrail checks
6. Retry logic with exponential backoff on LLM failures
7. Token usage tracking per agent
8. Factory method: create_agent(role_name: str) that reads from agents.yaml and returns configured Agent
9. Common tools attachment method
10. Health check method to verify the agent's assigned model is available

Include type hints, docstrings, and a simple unit test.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.2: Generate Manager Agent
```
Create the Manager agent for ai-team with:
1. YAML config in config/agents.yaml (manager section):
   - Role: "Engineering Manager / Project Coordinator"
   - Goal: Coordinate team, resolve blockers, ensure on-time delivery
   - Backstory: 20+ year engineering leader experienced in agile, distributed teams
2. Python implementation in agents/manager.py:
   - Extends BaseAgent
   - Tools: task_delegation, timeline_management, blocker_resolution, status_reporting
   - Delegation logic: assigns tasks based on agent capabilities and current workload
   - Human escalation trigger: when confidence < threshold or critical decisions needed
   - Progress tracking: maintains project status and phase transitions
3. Use CrewAI's hierarchical process support — this agent serves as manager_agent

Include integration with the ProjectState model for status updates.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.3: Generate Product Owner Agent
```
Create the Product Owner agent with:
1. YAML config in config/agents.yaml (product_owner section):
   - Role: "Product Owner / Requirements Analyst"
   - Goal: Transform vague ideas into clear, prioritized requirements with acceptance criteria
   - Backstory: 15+ years in product management, expert at user story mapping, MoSCoW prioritization
2. Python implementation in agents/product_owner.py:
   - Extends BaseAgent
   - Tools: requirements_parser, user_story_generator, acceptance_criteria_writer, priority_scorer
   - Output format: RequirementsDocument Pydantic model with:
     - Project name; a brief top-level description (required—summarize the project in one or two sentences)
     - Target users
     - User stories (as a user, I want, so that) with acceptance criteria
     - MoSCoW priority for each story
     - Non-functional requirements (performance, security, scalability)
     - Assumptions and constraints
   - Includes self-validation: checks completeness, no ambiguous terms, testable criteria
3. Templates for common project types (API, web app, CLI tool, data pipeline)

Include guardrail: reject requirements that are too vague or contain contradictions.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.4: Generate Architect Agent
```
Create the Architect agent with:
1. YAML config in config/agents.yaml (architect section):
   - Role: "Solutions Architect / Tech Lead"
   - Goal: Design scalable, maintainable architectures with clear component interfaces
   - Backstory: Principal Architect with distributed systems, cloud, and modern patterns expertise
2. Python implementation in agents/architect.py:
   - Extends BaseAgent
   - Tools: architecture_designer, technology_selector, interface_definer, diagram_generator
   - Output format: ArchitectureDocument Pydantic model with:
     - System overview, component list with responsibilities
     - Technology stack with justification for each choice
     - API/interface contracts between components
     - Data model / database schema outline
     - ASCII architecture diagram
     - Architecture Decision Records (ADRs)
     - Deployment topology recommendation
   - Pattern library: knows MVC, microservices, event-driven, CQRS, clean architecture
3. Validates architecture against requirements document for completeness
4. allow_delegation: true (can consult with DevOps/Cloud agents)

Include guardrail: architecture must address all functional and non-functional requirements.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.5: Generate Developer Agents (Backend, Frontend, Fullstack)
```
Create three developer agents that share a common developer base:

1. agents/developer_base.py — shared DeveloperBase(BaseAgent):
   - Common tools: code_generation, file_writer, dependency_resolver, code_reviewer
   - Self-review loop: agent reviews own code before marking task complete
   - Code style enforcement: PEP8/ESLint awareness
   - Context awareness: reads architecture doc and requirements for consistency

2. agents/backend_developer.py — BackendDeveloper:
   - YAML config with backend-specific role, goal, backstory
   - Additional tools: database_schema_design, api_implementation, orm_generator
   - Specializes in: Python (Flask/FastAPI/Django), Node.js (Express), Go
   - Generates: source files, requirements.txt/package.json, database migrations

3. agents/frontend_developer.py — FrontendDeveloper:
   - YAML config with frontend-specific role, goal, backstory
   - Additional tools: component_generator, state_management, api_client_generator
   - Specializes in: React, Vue, HTML/CSS/JS, Tailwind
   - Generates: components, pages, styles, API client code

4. agents/fullstack_developer.py — FullstackDeveloper:
   - Combines backend and frontend capabilities
   - Used for simple projects that don't need separate frontend/backend agents

Include guardrail integration for code quality checks on all generated code.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.6: Generate DevOps and Cloud Agents
```
Create two infrastructure agents:

1. agents/devops_engineer.py — DevOpsEngineer:
   - YAML config: Role "DevOps / SRE Engineer"
   - Goal: Design CI/CD pipelines, Docker configs, K8s manifests, monitoring
   - Backstory: SRE from Netflix/Google/Spotify, production incident veteran
   - Tools: dockerfile_generator, compose_generator, ci_pipeline_generator,
     k8s_manifest_generator, monitoring_config_generator
   - Output: Dockerfile, docker-compose.yml, .github/workflows/ci.yml, K8s manifests
   - Best practices: multi-stage builds, non-root users, health checks, resource limits

2. agents/cloud_engineer.py — CloudEngineer:
   - YAML config: Role "Cloud Infrastructure Engineer"
   - Goal: Design cloud infra using IaC, optimize cost/performance/security
   - Backstory: Multi-cloud certified, Fortune 500 experience, least-privilege advocate
   - Tools: terraform_generator, cloudformation_generator, iam_policy_generator,
     cost_estimator, network_designer
   - Output: Terraform modules, CloudFormation templates, IAM policies
   - Best practices: state management, module reuse, security groups, tagging

Both agents share allow_delegation: false and max_iter: 10.
Include validation that generated IaC follows security best practices.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.7: Generate QA Agent
```
Create the QA Engineer agent:
1. YAML config in config/agents.yaml (qa_engineer section):
   - Role: "QA Engineer / Test Automation Specialist"
   - Goal: Ensure code quality through comprehensive testing, find bugs before deployment
   - Backstory: QA lead who has prevented countless production incidents, believes in test pyramids
2. Python implementation in agents/qa_engineer.py:
   - Extends BaseAgent
   - Tools: test_generator, test_runner, coverage_analyzer, bug_reporter, lint_runner
   - Test generation capabilities:
     - Unit tests (pytest) from source code analysis
     - Integration tests for API endpoints
     - Edge case identification and test generation
     - Fixture generation for test data
   - Output format: TestResult Pydantic model with:
     - Test files generated (path, content)
     - Test execution results (passed, failed, errors)
     - Coverage report (line, branch, per-file breakdown)
     - Bug reports with severity and reproduction steps
   - Quality gates: configurable minimum coverage threshold, zero critical bugs
3. Retry logic: if tests fail, provides feedback to developer agents for fixes

Include guardrail: all generated code must have >80% test coverage.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.8: Generate secure file tools
```
Create src/ai_team/tools/file_tools.py with comprehensive file operation tools:
1. read_file(path: str) → str — read file with path traversal prevention
2. write_file(path: str, content: str) → bool — write with directory whitelist enforcement
3. list_directory(path: str) → List[str] — list with restricted scope
4. create_directory(path: str) → bool — mkdir with nesting limits
5. delete_file(path: str) → bool — delete with confirmation and audit log

Security features on every operation:
- Path traversal prevention (no ../, symlink resolution)
- Allowed directory whitelist (only workspace/output dirs)
- Content scanning for dangerous patterns (eval, exec, subprocess, os.system)
- File size limits (configurable max_file_size_kb from settings)
- PII redaction scanning (optional, logs warning if PII detected)
- Audit logging of all file operations with timestamp, operation, path, user

Include both @tool decorator versions (for agent use) and raw function versions (for testing).
Create comprehensive test cases including adversarial path inputs.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.9: Generate code execution sandbox tools
```
Create src/ai_team/tools/code_tools.py with sandboxed code execution:
1. execute_python(code: str, timeout: int = 30) → ExecutionResult
   - Run Python code in subprocess with resource limits
   - Capture stdout, stderr, return code
   - Timeout enforcement
   - Import whitelist (block os, subprocess, sys, shutil by default)
2. execute_shell(command: str, timeout: int = 10) → ExecutionResult
   - Run shell commands in restricted environment
   - Command whitelist (allow pip install, pytest, ruff, mypy, git status)
   - Block dangerous commands (rm -rf, curl, wget, nc, etc.)
3. lint_code(code: str, language: str) → LintResult
   - Run ruff for Python, eslint for JavaScript
   - Return structured lint results with severity levels
4. format_code(code: str, language: str) → str
   - Run black for Python, prettier for JavaScript
   - Return formatted code string

Security features:
- Process isolation with subprocess
- CPU and memory limits via resource module
- Network access disabled during execution
- Temporary directory cleanup after execution
- Execution audit logging

Include ExecutionResult and LintResult Pydantic models.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.10: Generate Git tools
```
Create src/ai_team/tools/git_tools.py with Git/GitHub operations:
1. git_init(path: str) → bool — initialize a new repository
2. git_add(path: str, files: List[str]) → bool — stage files
3. git_commit(path: str, message: str) → str — commit with conventional commit format
4. git_branch(path: str, branch_name: str) → bool — create feature branch
5. git_diff(path: str) → str — show current changes
6. git_log(path: str, n: int = 10) → List[CommitInfo] — recent commit history
7. git_status(path: str) → GitStatus — current repo status
8. generate_commit_message(diff: str) → str — AI-generated conventional commit message
9. create_pr_description(commits: List[str], changes: List[str]) → str — generate PR body

All operations:
- Work with local git (no GitHub API calls in this version)
- Validate repository state before operations
- Use structured logging for all git operations
- Return Pydantic models (CommitInfo, GitStatus)

Include safety checks: no force push, no main branch commits, branch naming convention.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.11: Generate test runner tools
```
Create src/ai_team/tools/test_tools.py with testing tools:
1. run_pytest(test_path: str, source_path: str) → TestRunResult
   - Execute pytest with coverage collection
   - Parse pytest output into structured results
   - Return: total, passed, failed, errors, warnings, duration
   - Coverage: line coverage %, branch coverage %, per-file breakdown
2. run_specific_test(test_file: str, test_name: str) → TestResult
   - Run a single test function for debugging
   - Include full traceback on failure
3. generate_coverage_report(source_path: str) → CoverageReport
   - HTML and JSON coverage reports
   - Identify uncovered lines and branches
   - Suggest what tests to add
4. run_lint(source_path: str) → LintReport
   - Run ruff, mypy on Python files
   - Aggregate results with severity levels
5. validate_test_quality(test_code: str) → TestQualityReport
   - Check for: assertions present, meaningful test names, no hardcoded values,
     proper setup/teardown, edge cases covered

Pydantic models: TestRunResult, TestResult, CoverageReport, LintReport, TestQualityReport.
Include retry logic for flaky tests (run 2x on failure).

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.12: Generate behavioral guardrails module
```
Create src/ai_team/guardrails/behavioral.py with behavioral guardrails:
1. role_adherence_guardrail(task_output: str, agent_role: str) → GuardrailResult
   - Verify agent stayed within its role boundaries
   - Backend dev shouldn't generate frontend code, QA shouldn't modify source
   - Return pass/fail with explanation
2. scope_control_guardrail(task_output: str, original_requirements: str) → GuardrailResult
   - Ensure output addresses the task, doesn't add unrequested features
   - Flag scope creep with specific examples
3. delegation_guardrail(delegating_agent: str, target_agent: str, task: str) → GuardrailResult
   - Validate delegation makes sense (e.g., Manager can delegate, individual contributors shouldn't)
   - Check for circular delegation
4. output_format_guardrail(output: str, expected_format: type) → GuardrailResult
   - Validate output matches expected Pydantic model
   - Attempt to parse and return structured errors if invalid
5. iteration_limit_guardrail(current_iteration: int, max_iterations: int) → GuardrailResult
   - Prevent infinite loops in agent reasoning
   - Log warning at 80% of limit, fail at limit

GuardrailResult Pydantic model: status (pass/fail/warn), message, details, retry_allowed.
All guardrails integrate with CrewAI's task guardrail parameter.
Include unit tests with mock agent outputs.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.13: Generate security guardrails module
```
Create src/ai_team/guardrails/security.py with security guardrails:
1. code_safety_guardrail(code: str) → GuardrailResult
   - Detect dangerous patterns: eval(), exec(), os.system(), subprocess without shell=False,
     __import__, compile(), globals(), pickle.loads(), yaml.load() without SafeLoader
   - Configurable pattern list from settings
   - Severity levels: critical (block), warning (log), info
2. pii_redaction_guardrail(text: str) → GuardrailResult
   - Detect and redact: email addresses, phone numbers, SSNs, credit card numbers,
     IP addresses, API keys, passwords in plaintext
   - Return both detection result and redacted version
3. secret_detection_guardrail(content: str) → GuardrailResult
   - Detect hardcoded secrets: API keys, tokens, passwords, connection strings
   - Check for common patterns: AWS keys, GitHub tokens, JWT secrets
   - Flag .env values that shouldn't be in code
4. prompt_injection_guardrail(input_text: str) → GuardrailResult
   - Detect attempts to override agent instructions
   - Check for: "ignore previous instructions", role-play attacks, encoding tricks
   - Configurable sensitivity level
5. path_security_guardrail(file_path: str) → GuardrailResult
   - Validate file paths are within allowed directories
   - Block: path traversal, symlinks outside workspace, absolute paths to system dirs

Integration with CrewAI task guardrails for automatic enforcement.
Include comprehensive unit tests with adversarial test cases.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 2.14: Generate quality guardrails module
```
Create src/ai_team/guardrails/quality.py with quality guardrails:
1. code_quality_guardrail(code: str, language: str) → GuardrailResult
   - Check: function length (<50 lines), file length (<500 lines), cyclomatic complexity
   - Verify: docstrings present, type hints on public functions, no TODO/FIXME/HACK
   - Check naming conventions (snake_case for Python, camelCase for JS)
   - Return quality score 0-100 with improvement suggestions
2. test_coverage_guardrail(coverage_report: dict) → GuardrailResult
   - Enforce minimum coverage threshold (default 80% from settings)
   - Flag files with 0% coverage
   - Check for meaningful assertions (not just assert True)
3. documentation_guardrail(code: str, docs: str) → GuardrailResult
   - Verify: README exists and is non-empty, all public functions documented
   - Check docstring quality: has description, parameters, returns, examples
4. architecture_compliance_guardrail(code_files: List[str], architecture: dict) → GuardrailResult
   - Verify code follows the architecture document
   - Check: correct module placement, no circular imports, interface compliance
5. dependency_guardrail(requirements: str) → GuardrailResult
   - Check for: known vulnerable packages, unnecessary dependencies, version pinning
   - Flag packages with no recent updates (>2 years)

All return GuardrailResult with actionable fix suggestions.
Include unit tests with examples of passing and failing code.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

---

## Phase 3: Task & Flow Design (Days 15-21)

### Prompt 3.1: Generate Planning Tasks
```
Create src/ai_team/config/tasks.yaml and src/ai_team/tasks/planning_tasks.py:

YAML definitions for:
1. requirements_gathering task:
   - description: "Analyze the project idea and create comprehensive requirements; include a brief top-level description (the description field)"
   - agent: product_owner
   - expected_output: "RequirementsDocument with a brief top-level description, user stories, acceptance criteria, priorities"
   - output_pydantic: RequirementsDocument
   - guardrail: requirements must have at least 3 user stories with acceptance criteria
2. architecture_design task:
   - description: "Design system architecture based on requirements"
   - agent: architect
   - context: [requirements_gathering] (depends on requirements output)
   - expected_output: "ArchitectureDocument with components, interfaces, tech stack"
   - output_pydantic: ArchitectureDocument
   - guardrail: architecture must address all requirements

Python implementation:
- Task factory functions that read YAML and create CrewAI Task objects
- Context passing: architecture task receives requirements as input
- Guardrail functions for each task
- Timeout configuration per task

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.2: Generate Development Tasks
```
Create src/ai_team/tasks/development_tasks.py with:

1. backend_implementation task:
   - description: "Implement backend code based on architecture"
   - agent: backend_developer
   - context: [architecture_design, requirements_gathering]
   - expected_output: "List of CodeFile objects with source, tests, configs"
   - output_pydantic: List[CodeFile]
   - guardrail: code must pass lint, have docstrings, follow architecture

2. frontend_implementation task:
   - description: "Implement frontend UI based on architecture"
   - agent: frontend_developer
   - context: [architecture_design, backend_implementation]
   - expected_output: "List of CodeFile objects for frontend components"
   - guardrail: components must be responsive, accessible

3. devops_configuration task:
   - description: "Create Docker, CI/CD, deployment configs"
   - agent: devops_engineer
   - context: [architecture_design, backend_implementation, frontend_implementation]
   - expected_output: "DeploymentConfig with Dockerfile, compose, CI pipeline"

Each task:
- Receives context from previous tasks via CrewAI's context parameter
- Has a guardrail validation function
- Supports retry with feedback on failure
- Logs task start, progress, and completion

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.3: Generate Testing Tasks
```
Create src/ai_team/tasks/testing_tasks.py with:

1. test_generation task:
   - description: "Generate comprehensive tests for all code files"
   - agent: qa_engineer
   - context: [backend_implementation, frontend_implementation]
   - expected_output: "List of CodeFile objects containing test files"
   - guardrail: tests must have meaningful assertions, cover edge cases

2. test_execution task:
   - description: "Run all generated tests and report results"
   - agent: qa_engineer
   - context: [test_generation]
   - expected_output: "TestRunResult with pass/fail counts and coverage"
   - guardrail: minimum 80% coverage, zero critical failures

3. code_review task:
   - description: "Review all generated code for quality, security, best practices"
   - agent: qa_engineer
   - context: [backend_implementation, frontend_implementation, test_execution]
   - expected_output: "CodeReviewReport with findings and severity"
   - guardrail: no critical or high-severity findings

Include retry logic: if tests fail, return feedback to development tasks for fixes.
Maximum 3 retry cycles before escalating to human.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.4: Generate Deployment Tasks
```
Create src/ai_team/tasks/deployment_tasks.py with:

1. infrastructure_design task:
   - description: "Design cloud infrastructure for the application"
   - agent: cloud_engineer
   - context: [architecture_design, devops_configuration]
   - expected_output: "IaC templates (Terraform/CloudFormation)"
   - guardrail: IaC must follow security best practices, least privilege

2. deployment_packaging task:
   - description: "Package application for deployment with all configs"
   - agent: devops_engineer
   - context: [infrastructure_design, test_execution]
   - expected_output: "Complete deployment package with README"
   - guardrail: deployment must include health checks, rollback strategy

3. documentation_generation task:
   - description: "Generate comprehensive project documentation"
   - agent: product_owner (with architect context)
   - context: [all previous tasks]
   - expected_output: "README.md, API docs, setup guide, architecture docs"
   - guardrail: documentation must cover installation, usage, API reference

Include dependency chain: infra depends on arch + devops, packaging depends on infra + tests.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.5: Generate Planning Crew
```
Create src/ai_team/crews/planning_crew.py — the Planning Crew:
1. Process: hierarchical (Manager delegates to team)
2. Manager agent: Manager (as manager_agent parameter)
3. Team agents: Product Owner, Architect
4. Tasks: requirements_gathering → architecture_design (sequential dependency)
5. Output: RequirementsDocument and ArchitectureDocument
6. Memory: enabled (short-term for task context passing)
7. Planning: enabled (CrewAI planning feature for task breakdown)

Configuration:
- verbose: true for development, configurable via settings
- max_rpm: rate limiting for Ollama
- task dependencies via context parameter
- Guardrails applied at task level
- Callbacks: on_task_start, on_task_complete for logging/metrics

Include kickoff() method that accepts project_description string and returns crew output.
Include test with mock LLM responses.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.6: Generate Development Crew
```
Create src/ai_team/crews/development_crew.py — the Development Crew:
1. Process: hierarchical (Architect as tech lead / manager_agent)
2. Manager agent: Architect (technical decisions)
3. Team agents: Backend Developer, Frontend Developer, DevOps Engineer
4. Tasks: backend_implementation, frontend_implementation, devops_configuration
5. Input: RequirementsDocument + ArchitectureDocument from Planning Crew
6. Output: List[CodeFile] + DeploymentConfig

Configuration:
- Allow parallel execution where possible (backend/frontend can run concurrently)
- Context passing: each task receives architecture doc + requirements
- Guardrails: code quality, security scanning on all outputs
- Max iterations: 15 (code generation may need more passes)
- Memory: enabled for cross-task context

Include kickoff() that accepts planning crew output and returns code files.
Handle the case where only backend OR frontend is needed (based on architecture).

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.7: Generate Testing Crew
```
Create src/ai_team/crews/testing_crew.py — the Testing Crew:
1. Process: sequential (tests must run in order)
2. Agents: QA Engineer (single agent, multiple tasks)
3. Tasks: test_generation → test_execution → code_review
4. Input: List[CodeFile] from Development Crew
5. Output: TestRunResult + CodeReviewReport

Configuration:
- Sequential process: generate tests, run them, then review
- Retry integration: if test_execution fails, provide feedback dict
- Quality gates: configurable pass/fail thresholds from settings
- Coverage thresholds: line and branch coverage minimums
- Guardrails: test quality validation, coverage enforcement

Include kickoff() that accepts code files and returns test results.
Include get_feedback() method that formats test failures as actionable feedback
for the Development Crew to fix.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.8: Generate Deployment Crew
```
Create src/ai_team/crews/deployment_crew.py — the Deployment Crew:
1. Process: sequential
2. Agents: Cloud Engineer, DevOps Engineer
3. Tasks: infrastructure_design → deployment_packaging → documentation_generation
4. Input: Code files + Architecture doc + Test results
5. Output: Complete deployment package

Configuration:
- Sequential: infra design → packaging → docs
- Include Product Owner for documentation task (via context, not as crew member)
- Guardrails: IaC security validation, deployment completeness check
- Output structure: organized directory with all files, README at root

Include kickoff() that accepts code files, architecture, and test results.
Include package_output() that creates a clean output directory structure.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.9: Generate State Models
```
Create src/ai_team/flows/state.py with Pydantic models for flow state:

1. ProjectState(BaseModel) — the main flow state:
   - project_id: str (UUID)
   - project_description: str
   - current_phase: ProjectPhase (enum: INTAKE, PLANNING, DEVELOPMENT, TESTING, DEPLOYMENT, COMPLETE, ERROR)
   - requirements: Optional[RequirementsDocument]
   - architecture: Optional[ArchitectureDocument]
   - generated_files: List[CodeFile]
   - test_results: Optional[TestRunResult]
   - deployment_config: Optional[DeploymentConfig]
   - phase_history: List[PhaseTransition]
   - errors: List[ProjectError]
   - retry_counts: Dict[str, int]  (per-phase retry tracking)
   - max_retries: int = 3
   - started_at: datetime
   - completed_at: Optional[datetime]
   - metadata: Dict[str, Any]

2. Supporting models:
   - ProjectPhase (enum)
   - PhaseTransition(BaseModel): from_phase, to_phase, timestamp, reason
   - ProjectError(BaseModel): phase, error_type, message, timestamp, recoverable
   - RequirementsDocument, ArchitectureDocument, CodeFile, TestRunResult, DeploymentConfig
     (detailed Pydantic models for each output type)

3. State methods:
   - add_phase_transition(), add_error(), increment_retry()
   - can_retry(phase) → bool
   - get_duration() → timedelta
   - to_summary() → str (human-readable status)

Include validators: phase transitions must be valid (no skipping), retry limits enforced.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.10: Generate Main Flow
```
Create src/ai_team/flows/main_flow.py — the main AITeamFlow orchestration:
1. Class AITeamFlow(Flow[ProjectState]):
2. @start() method: intake_request(project_description: str)
   - Initialize ProjectState
   - Validate input (non-empty, reasonable length)
   - Log project start
3. @listen(intake_request) → run_planning_crew
   - Execute PlanningCrew with project description
   - Store requirements and architecture in state
4. @router(run_planning_crew) → route_after_planning
   - Success → "run_development"
   - Needs clarification → "request_human_feedback"
   - Error → "handle_planning_error"
5. @listen("run_development") → run_development_crew
   - Execute DevelopmentCrew with planning outputs
   - Store generated files in state
6. @router(run_development_crew) → route_after_development
   - Success → "run_testing"
   - Error → "handle_development_error"
7. @listen("run_testing") → run_testing_crew
   - Execute TestingCrew with code files
   - Store test results in state
8. @router(run_testing_crew) → route_after_testing
   - All pass → "run_deployment"
   - Retryable failures → "retry_development"
   - Fatal failures → "escalate_to_human"
9. @listen("run_deployment") → run_deployment_crew
   - Execute DeploymentCrew
   - Store deployment config
10. @listen after deployment → finalize_project
   - Package outputs, generate summary, log completion

Include: error handling at every step, state persistence, guardrail integration,
flow visualization with plot() method, comprehensive logging.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.11: Generate conditional routing
```
Create routing logic in src/ai_team/flows/routing.py:

1. route_after_planning(planning_result: Dict) → str:
   - "run_development" if requirements AND architecture are complete
   - "request_human_feedback" if requirements are ambiguous (confidence < 0.7)
   - "handle_planning_error" if crew execution failed

2. route_after_development(dev_result: Dict) → str:
   - "run_testing" if code files generated successfully
   - "retry_planning" if architecture was insufficient (rare)
   - "handle_development_error" on failure

3. route_after_testing(test_result: Dict) → str:
   - "run_deployment" if all tests pass and coverage meets threshold
   - "retry_development" if tests failed AND retry count < max (with feedback)
   - "escalate_to_human" if retries exhausted or critical failures

4. route_after_deployment(deploy_result: Dict) → str:
   - "finalize_project" on success
   - "handle_deployment_error" on failure

Each router:
- Uses @router decorator with string-based routing
- Logs the routing decision with reasoning
- Updates ProjectState phase transitions
- Checks retry limits before allowing retries
- Includes confidence scoring where applicable

Include routing diagram as docstring comment.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.12: Generate Human-in-the-Loop
```
Create src/ai_team/flows/human_feedback.py with human interaction support:

1. HumanFeedbackHandler class:
   - request_feedback(question: str, context: Dict, options: List[str]) → str
     - Present question to user via Gradio UI or CLI prompt
     - Include relevant context (what failed, what agents produced)
     - Offer structured options + free-text input
     - Timeout with default action after configurable wait

2. Integration points in the flow:
   - @listen("request_human_feedback") on AITeamFlow
   - Called when: requirements ambiguous, tests keep failing, security concern
   - Feedback types:
     a. Clarification: "The requirements mention 'fast' — define performance target"
     b. Approval: "Architecture uses microservices — confirm or simplify?"
     c. Escalation: "Tests failed 3 times on authentication — please review"
     d. Override: "Security guardrail flagged this pattern — allow or reject?"

3. Feedback processing:
   - Parse human response into structured format
   - Inject feedback into appropriate agent's context
   - Resume flow from the appropriate step
   - Log all human interactions for audit trail

4. CLI mode: input() prompts for non-UI usage
5. UI mode: Gradio callback for web interface

Include mock feedback handler for automated testing.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 3.13: Generate Error Handling
```
Create src/ai_team/flows/error_handling.py with flow error recovery:

1. Error handler methods for AITeamFlow:
   - handle_planning_error(error: Dict) → handles crew execution failures
   - handle_development_error(error: Dict) → handles code generation failures
   - handle_testing_error(error: Dict) → handles test execution failures
   - handle_deployment_error(error: Dict) → handles packaging failures

2. Error classification:
   - RetryableError: LLM timeout, rate limit, temporary Ollama failure
   - RecoverableError: invalid output format, guardrail soft failure
   - FatalError: model not found, out of memory, critical security violation

3. Recovery strategies:
   - RetryableError: exponential backoff retry (1s, 2s, 4s, 8s) up to max_retries
   - RecoverableError: provide error feedback to agent, retry with adjusted prompt
   - FatalError: log error, save partial state, escalate to human

4. Circuit breaker pattern:
   - Track consecutive failures per phase
   - If 3 consecutive failures in same phase → skip to human escalation
   - Reset circuit on success

5. State preservation:
   - Save ProjectState to JSON on every error
   - Support flow resume from last successful phase
   - Include rollback capability (undo last phase)

6. Error reporting:
   - Structured error log with phase, agent, tool, error type, stack trace
   - Summary report for human review
   - Metrics: error rate per phase, retry count distribution

Include unit tests for each error scenario.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

---

## Phase 4: Memory, Reasoning & Integration (Days 22-28)

### Prompt 4.1-4.3: Generate unified memory configuration
```
Create src/ai_team/memory/memory_config.py with unified memory setup:

1. Short-term memory (ChromaDB):
   - Collection per project (project_id as namespace)
   - Store task outputs as embeddings for RAG
   - Agents can search previous task results
   - Auto-cleanup after project completion
   - Configuration: chromadb_path, embedding_model, max_results

2. Long-term memory (SQLite):
   - Store conversation history across projects
   - Agent performance metrics (which models produce best results)
   - Learned patterns (common architecture decisions, code patterns)
   - Configuration: sqlite_path, retention_days

3. Entity memory:
   - Track project entities: files, APIs, databases, services
   - Relationships: file depends on file, service calls service
   - Used by agents to understand project structure
   - Auto-populated from task outputs

4. MemoryManager class:
   - initialize(settings: MemorySettings) — set up all memory stores
   - store(key, value, memory_type) — write to appropriate store
   - retrieve(query, memory_type, top_k) — search with embeddings
   - get_entity(name) — look up entity info
   - cleanup(project_id) — remove project-specific memory
   - export(project_id) — dump memory for debugging

Include initialization in src/ai_team/memory/__init__.py.
Include memory sharing configuration between crews.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 4.4: Generate Knowledge Base
```
Create src/ai_team/memory/knowledge_base.py with reference knowledge:

1. KnowledgeBase class with embedded best practices:
   - Python best practices: PEP8, type hints, project structure, common patterns
   - API design: REST conventions, status codes, pagination, error responses
   - Database design: normalization, indexing, migration patterns
   - Testing: test pyramid, fixture patterns, mocking, edge cases
   - DevOps: Docker best practices, CI/CD patterns, 12-factor app principles
   - Security: OWASP top 10, input validation, authentication patterns

2. Template library:
   - Flask/FastAPI API template
   - React component template
   - Pytest test file template
   - Dockerfile template
   - docker-compose template
   - GitHub Actions workflow template
   - README template

3. Integration with CrewAI knowledge sources:
   - Load knowledge as CrewAI knowledge source
   - Agents can query knowledge base during task execution
   - Configurable knowledge scope per agent role

4. Knowledge retrieval:
   - get_best_practices(topic: str) → List[str]
   - get_template(template_type: str) → str
   - search_knowledge(query: str) → List[KnowledgeItem]

Store as structured YAML/JSON files in src/ai_team/memory/knowledge/.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 4.5: Generate Reasoning Enhancement
```
Create src/ai_team/utils/reasoning.py with chain-of-thought prompting templates:

1. Reasoning templates per task type:
   - requirements_reasoning: "Think step by step: 1) Identify user types, 2) List core features,
     3) Define acceptance criteria, 4) Prioritize by business value, 5) Identify risks"
   - architecture_reasoning: "Think step by step: 1) List system components, 2) Define interfaces,
     3) Choose technologies with justification, 4) Design data flow, 5) Identify failure modes"
   - code_reasoning: "Think step by step: 1) Understand requirements, 2) Design module structure,
     3) Implement core logic, 4) Add error handling, 5) Write docstrings, 6) Self-review"
   - test_reasoning: "Think step by step: 1) Identify test cases from requirements,
     2) Design test structure, 3) Create fixtures, 4) Write happy path tests,
     5) Write edge cases, 6) Verify coverage"

2. Structured output enforcement:
   - JSON schema templates for each output type
   - Response format instructions appended to agent prompts
   - Parsing helpers to extract structured data from LLM responses

3. Self-reflection prompts:
   - After each task: "Review your output. Does it meet all requirements?
     What could be improved? Rate your confidence 1-10."
   - Used to trigger retries or human feedback when confidence is low

4. ReasoningEnhancer class:
   - enhance_prompt(base_prompt: str, task_type: str) → str
   - add_self_reflection(prompt: str) → str
   - parse_confidence(response: str) → float

Include integration with agent backstory prompts.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 4.6: Generate structured output models
```
Create src/ai_team/models/outputs.py with Pydantic models for all task outputs:

1. RequirementsDocument:
   - project_name, description, target_users: List[str]
   - user_stories: List[UserStory] (as_a, i_want, so_that, acceptance_criteria: List[str], priority: MoSCoW)
   - non_functional_requirements: List[NFR] (category, description, metric)
   - assumptions: List[str], constraints: List[str]
   - Validators: at least 3 user stories, all have acceptance criteria

2. ArchitectureDocument:
   - system_overview: str, components: List[Component]
   - technology_stack: Dict[str, TechChoice] (technology, justification)
   - interfaces: List[Interface] (name, endpoints: List[Endpoint])
   - data_model: List[Entity] (name, fields, relationships)
   - deployment_topology: str
   - adrs: List[ADR] (title, context, decision, consequences)

3. CodeFile:
   - path, content, language, file_type (source/test/config/doc)
   - dependencies: List[str], size_bytes: int
   - Validators: content non-empty, path is valid, language recognized

4. TestResult:
   - total, passed, failed, errors, skipped
   - coverage_line, coverage_branch: float
   - failures: List[TestFailure] (test_name, error, traceback)
   - duration_seconds: float

5. DeploymentConfig:
   - dockerfile, docker_compose, ci_pipeline: str
   - environment_variables: Dict[str, str]
   - infrastructure: Optional[str] (Terraform/CF template)

6. ProjectReport:
   - project_id, project_name, status
   - files: List[CodeFile], test_results: TestResult
   - summary: str, duration: timedelta, agent_metrics: Dict

Include JSON schema export, from_llm_response() class methods, validation error messages.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 4.7: Generate callback system
```
Create src/ai_team/utils/callbacks.py with an event callback system:

1. AITeamCallback class implementing CrewAI callback interfaces:
   - on_task_start(task, agent) — log task beginning, start timer
   - on_task_complete(task, agent, output) — log completion, stop timer, record metrics
   - on_task_error(task, agent, error) — log error, increment failure counter
   - on_agent_action(agent, action, tool) — log tool usage
   - on_crew_start(crew) — log crew kickoff
   - on_crew_complete(crew, output) — log crew completion with summary
   - on_guardrail_trigger(guardrail, result) — log guardrail evaluation

2. Structured logging with structlog:
   - JSON format for production, colored console for development
   - Context binding: project_id, phase, agent_role, task_name
   - Log levels: DEBUG (tool calls), INFO (phase transitions), WARN (retries), ERROR (failures)

3. Metrics collection:
   - Task duration (start to complete)
   - Token usage per agent (estimated from response length)
   - Retry counts per task and phase
   - Guardrail trigger frequency
   - Tool call counts per agent
   - Store as MetricsReport Pydantic model

4. Optional webhook notifications:
   - POST to configurable URL on phase transitions
   - Payload: project_id, event_type, details, timestamp

Support both sync and async callbacks.
Include MetricsReport model with to_dict() and to_table() methods.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 4.8: Generate Integration Testing
```
Create tests/integration/test_full_flow.py with end-to-end integration tests:

1. test_planning_crew_integration:
   - Input: simple project description ("Create a REST API for todo items")
   - Mock Ollama responses with realistic LLM outputs
   - Assert: PlanningCrew returns valid RequirementsDocument and ArchitectureDocument
   - Assert: task dependencies executed in order

2. test_development_crew_integration:
   - Input: pre-built RequirementsDocument + ArchitectureDocument
   - Mock: Ollama responses with generated code
   - Assert: DevelopmentCrew returns valid CodeFile list
   - Assert: code files contain required imports, functions, classes

3. test_testing_crew_integration:
   - Input: pre-built CodeFile list
   - Mock: pytest execution results
   - Assert: TestingCrew returns TestRunResult with coverage data

4. test_full_flow_happy_path:
   - Input: project description
   - Mock: all LLM responses for complete flow
   - Assert: AITeamFlow completes all phases in order
   - Assert: ProjectState transitions: INTAKE → PLANNING → DEVELOPMENT → TESTING → DEPLOYMENT → COMPLETE

5. test_flow_retry_on_test_failure:
   - Mock: first test run fails, second succeeds
   - Assert: flow retries development, succeeds on second attempt

6. test_flow_escalation_on_repeated_failure:
   - Mock: all retries fail
   - Assert: flow escalates to human feedback

Use pytest fixtures for: mock_ollama, sample_project_description, mock_crew_outputs.
Include conftest.py with shared fixtures and mock helpers.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

---

## Phase 5: Testing, Iteration & Guardrail Validation (Days 29-35)

> **Key Change:** Demo projects (5.6–5.8) are no longer static definition files.
> They are **live runs of the AITeamFlow** — the team builds itself.
> This validates the system end-to-end AND produces real portfolio artifacts.

**Objectives:** Validate the system works by using it. Run AITeamFlow on real project
descriptions. Capture outputs as demo artifacts. Measure quality. Iterate until passing.

| Task ID | Task | Description | Cursor AI Optimization | Dependencies |
|---------|------|-------------|----------------------|--------------|
| 5.1 | Unit Tests | Test individual components | pytest with fixtures | 4.8 |
| 5.2 | Integration Tests | Test crew interactions | Mock LLM responses | 5.1 |
| 5.3 | Guardrail Tests | Test guardrail effectiveness | Adversarial inputs | 5.2 |
| 5.4 | E2E Tests | Full flow on Demo 1 spec | Real AITeamFlow run | 5.2 |
| 5.5 | Performance Tests | Benchmark execution times | Profile bottlenecks | 5.4 |
| 5.6 | Demo Run 1 | Hello World Flask API | **AITeamFlow builds it** | 5.4 |
| 5.7 | Demo Run 2 | TODO App (full-stack) | **AITeamFlow builds it** | 5.6 |
| 5.8 | Demo Run 3 | Data Pipeline | **AITeamFlow builds it** | 5.6 |
| 5.9 | Iteration | Fix issues, optimize | Based on real run results | 5.3–5.8 |

### Prompt 5.1: Generate Unit Test Suite
```
Create tests/unit/ with comprehensive unit tests for all components:

1. tests/unit/test_agents.py:
   - Test BaseAgent initialization with each role
   - Test model assignment from settings
   - Test guardrail attachment
   - Test before_task / after_task hook invocation
   - Mock Ollama LLM responses

2. tests/unit/test_guardrails.py:
   - Test each behavioral guardrail in isolation
   - Test each security guardrail with known-bad inputs
   - Test each quality guardrail with known-low-quality inputs
   - Verify guardrail pass/fail return signatures
   - Test guardrail chaining and ordering

3. tests/unit/test_memory.py:
   - Test MemoryManager ChromaDB storage and retrieval
   - Test SQLite session persistence
   - Test CrewAI crew embedder config (verify no OpenAI fallback)
   - Mock Ollama embedder responses
   - Test memory cleanup and TTL expiry

4. tests/unit/test_tools.py:
   - Test each agent tool in isolation
   - Verify tool schemas and return types
   - Test error handling for each tool

5. tests/unit/test_settings.py:
   - Test Pydantic settings loading from env
   - Test model assignment per role
   - Test validation errors for missing required fields

Use pytest fixtures for all shared setup. Aim for 85%+ coverage on
src/ai_team/. Run: `poetry run pytest tests/unit/ --cov=src/ai_team`

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 5.2: Generate Integration Test Suite
```
Create tests/integration/ with crew and flow integration tests:

1. tests/integration/test_crews.py:
   - Test RequirementsCrew produces valid RequirementsDocument
   - Test ArchitectureCrew produces valid ArchitectureDocument
   - Test DevelopmentCrew produces valid CodeFile list
   - Test QACrew produces valid TestResult
   - Test DeploymentCrew produces valid DeploymentConfig
   - Use lightweight mock LLM that returns structured valid responses
   - Verify crew-to-crew handoffs pass correct context

2. tests/integration/test_flow_routing.py:
   - Test AITeamFlow state transitions (INTAKE → PLANNING → DEV → QA → DEPLOY)
   - Test routing logic for each phase gate
   - Test failure routing (QA fail → back to DEV)
   - Test human escalation trigger
   - Mock individual crew outputs to test flow logic independently

3. tests/integration/test_memory_integration.py:
   - Test MemoryManager wired into before_task hook: stores task context
   - Test MemoryManager wired into after_task hook: stores task output
   - Test cross-session retrieval: simulate second run, verify memory available
   - Test CrewAI crew memory uses local embedder (no network calls to OpenAI)
   - Use a temporary ChromaDB/SQLite path for test isolation

4. tests/integration/test_guardrails_in_flow.py:
   - Test guardrail rejection triggers retry logic
   - Test max retry exceeded raises correct error
   - Test guardrail callback fires on rejection
   - Test flow continues normally when guardrails pass

Keep integration tests fast by mocking LLM responses. Label slow tests
with @pytest.mark.slow. Run fast subset: `poetry run pytest tests/integration/ -m "not slow"`

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 5.3: Generate Guardrail Test Suite
```
Create tests/guardrails/ with comprehensive guardrail effectiveness tests:

1. tests/guardrails/test_behavioral_guardrails.py:
   Adversarial inputs for role adherence:
   - Test: Frontend developer output containing SQL DELETE statements → should fail
   - Test: Architect output containing raw data mutations → should fail
   - Test: Manager output containing code implementation → should fail
   - Test: Valid role-appropriate output → should pass
   
   Adversarial inputs for scope control:
   - Test: Output discussing unrelated features → should fail
   - Test: Output within defined scope → should pass
   
   Adversarial inputs for reasoning:
   - Test: Short output with no reasoning indicators → should fail
   - Test: Output with clear rationale statements → should pass

2. tests/guardrails/test_security_guardrails.py:
   Dangerous code injection:
   - Test: Output containing os.system("rm -rf /") → should detect and fail
   - Test: Output containing eval(user_input) → should detect and fail
   - Test: Output containing __import__("subprocess") → should detect and fail
   - Test: Output containing base64-encoded dangerous code → should detect and fail
   - Test: Clean code with no dangerous patterns → should pass
   
   Secret detection:
   - Test: Output containing AWS_SECRET_KEY=AKIA... → should detect and fail
   - Test: Output containing password="hardcoded123" → should detect and fail
   - Test: Output referencing environment variables properly → should pass
   
   PII detection and redaction:
   - Test: Output containing SSN pattern → should redact
   - Test: Output containing credit card pattern → should redact
   - Test: Clean output → should pass unchanged

3. tests/guardrails/test_quality_guardrails.py:
   Code quality:
   - Test: Python code with syntax error → should fail with specific message
   - Test: Code with no error handling on I/O → should fail
   - Test: Code with hardcoded credentials → should fail
   - Test: Well-structured code → should pass
   
   Test coverage:
   - Test: Output with 0 test cases when tests expected → should fail
   - Test: Output with tests below minimum threshold → should fail
   - Test: Output with adequate test cases → should pass
   
   Output format:
   - Test: Malformed JSON when JSON expected → should fail
   - Test: Missing required fields in structured output → should fail
   - Test: Valid structured output → should pass

4. tests/guardrails/test_retry_behavior.py:
   - Test: Guardrail fails once, retry succeeds → task completes
   - Test: Guardrail fails max_retries times → raises MaxRetriesExceeded
   - Test: Retry includes failure context in next attempt prompt
   - Test: Retry counter resets between tasks

Use pytest fixtures for TaskOutput mock objects. All inputs should be
realistic AI-generated text, not trivial synthetic strings.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 5.4: Generate E2E Test — Hello World Flask API
```
Create tests/e2e/test_e2e_hello_world.py — the first real end-to-end test
using an actual AITeamFlow run (not mocked).

This test IS the same run as Demo 1. It validates the system produces
working code for the simplest possible project.

Project specification to feed into AITeamFlow:
  "Create a simple Flask REST API with:
   - GET /health endpoint returning {status: ok, version: 1.0}
   - GET /items returning a list of items from in-memory storage
   - POST /items accepting {name: str} and adding to the list
   - Proper error handling (400 for bad input, 404 for not found)
   - Unit tests with pytest covering all endpoints and edge cases
   - Requirements.txt and Dockerfile"

Test assertions:
1. Flow completes without exception
2. Output directory contains: app.py, test_app.py, requirements.txt, Dockerfile
3. Generated app.py is valid Python (ast.parse check)
4. Generated requirements.txt contains flask, pytest
5. Generated Dockerfile is non-empty and contains FROM instruction
6. Running `python -m pytest` on generated test_app.py exits 0
   (subprocess call against the generated code)
7. Starting the Flask app and hitting /health returns 200
   (use subprocess + requests, clean up after)

On success:
  - Copy generated output to demos/01_hello_world/output/
  - Save run metrics (duration, token estimate, retry count) to
    demos/01_hello_world/run_report.json

On failure:
  - Save the full error context and last agent output to
    demos/01_hello_world/failure_report.json
  - Fail the test with a clear message indicating which assertion failed

Mark this test: @pytest.mark.e2e @pytest.mark.slow
Run: `poetry run pytest tests/e2e/test_e2e_hello_world.py -v -s`

The test output IS the demo artifact. No separate demo script needed.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 5.5: Generate Performance Benchmarks
```
Create tests/performance/test_benchmarks.py — execution time profiling:

1. Benchmark each crew independently:
   - RequirementsCrew: time from input to RequirementsDocument
   - ArchitectureCrew: time from requirements to ArchitectureDocument
   - DevelopmentCrew: time from architecture to code files
   - QACrew: time from code to test results
   - DeploymentCrew: time from code to deployment config
   - Record: wall time, agent think time, tool call time, token count estimate

2. Benchmark full flow for Demo 1 spec (beginner complexity):
   - Expected: complete in under 10 minutes on target hardware
   - Record phase-by-phase breakdown
   - Flag any phase exceeding its budget:
     Requirements: 1 min, Architecture: 2 min, Development: 4 min,
     QA: 2 min, Deployment: 1 min

3. Identify bottlenecks:
   - Use cProfile or time.perf_counter per phase
   - Report: slowest agents, slowest tools, retry overhead
   - Save profiling report to docs/performance_report.md

4. Hardware profiles:
   - Test and record results for: 8GB VRAM config, 16GB VRAM config
   - Note which models are active per profile (from settings)

5. Token usage estimation:
   - Count approximate tokens in/out per agent
   - Project cost if using OpenAI API equivalent (for README comparison)
   - Highlight local-first cost savings

Run: `poetry run pytest tests/performance/ -v -s --tb=short`
Save results to: docs/benchmark_results.json

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 5.6: Run Demo Project 1 — Hello World Flask API
```
The E2E test in 5.4 already runs this demo. This prompt covers:
capturing, verifying, and packaging the demo artifact.

Create scripts/capture_demo.py — run after a successful E2E test:

1. Input for this demo (same spec as 5.4 E2E test):
   Already defined in test_e2e_hello_world.py. Canonical copy lives at:
   demos/01_hello_world/project_description.txt

2. After AITeamFlow completes, capture_demo.py does:
   a. Verify all required files exist in the output directory
   b. Run the generated tests: `python -m pytest output/test_app.py -v`
      - Record: passed, failed, coverage percentage
   c. Lint the generated code: `ruff check output/app.py`
      - Record: violations found
   d. Verify Dockerfile builds: `docker build -t demo-01-test output/`
      - Record: build success/fail, image size
   e. Smoke test the running container:
      - docker run -d -p 5001:5000 demo-01-test
      - GET /health → expect 200 and {status: ok}
      - GET /items → expect 200 and []
      - POST /items {"name": "apple"} → expect 201
      - GET /items → expect 200 and [{name: "apple"}]
      - docker stop + rm

3. Generate demos/01_hello_world/RESULTS.md:
   - Summary: PASS / FAIL
   - Generated files table (name, lines, size)
   - Test results: X passed, Y failed, Z% coverage
   - Lint results: clean / N violations
   - Docker: built successfully, image size
   - Smoke test: all endpoints responded correctly
   - Run duration and model used

4. Failure handling:
   - If tests fail: save generated code + failure output to failure/
   - Log: which guardrail fired, how many retries occurred
   - Create GitHub issue template with the failure details (optional)

SUCCESS CRITERIA for Demo 1:
  ✅ All 5 files generated
  ✅ Tests pass with ≥80% coverage
  ✅ No critical lint violations
  ✅ Docker image builds
  ✅ All smoke test endpoints return expected responses
  ✅ Total run time < 8 minutes

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 5.7: Run Demo Project 2 — TODO App (Full-Stack)
```
Run AITeamFlow on a medium-complexity full-stack project.
This validates multi-file, multi-layer code generation and agent coordination.

Create demos/02_todo_app/project_description.txt with this specification:
  "Build a full-stack TODO application:
   
   Backend (FastAPI + SQLite):
   - POST /api/todos — create todo {title: str, description: str}
   - GET /api/todos — list all todos
   - GET /api/todos/{id} — get single todo
   - PUT /api/todos/{id} — update todo (title, description, completed)
   - DELETE /api/todos/{id} — delete todo
   - Todo model: id, title, description, completed (bool), created_at (datetime)
   - SQLAlchemy ORM, Alembic migrations, Pydantic schemas
   - Proper HTTP status codes and error responses
   - Comprehensive pytest tests with 85%+ coverage
   
   Frontend (plain HTML/CSS/JS, no framework):
   - List all todos with title, status indicator
   - Form to add new todo (title + description)
   - Click todo to mark complete/incomplete (toggle)
   - Delete button per todo
   - Fetch API calls to backend, no page reload
   - Clean, minimal styling
   
   Infrastructure:
   - Dockerfile for backend
   - docker-compose.yml: backend + serves frontend static files
   - README.md with setup, usage, API reference"

Run AITeamFlow with this spec. The flow should invoke all crews.

Capture and validate using capture_demo.py extended for this demo:
  a. Verify required files: backend/main.py, backend/models.py,
     backend/schemas.py, frontend/index.html, frontend/app.js,
     requirements.txt, docker-compose.yml, tests/test_api.py
  b. Run: `pytest backend/tests/ -v --cov=backend`
     Require: ≥10 test cases, ≥85% coverage
  c. Verify all 5 CRUD endpoints present in main.py (regex check)
  d. Verify frontend contains fetch() calls to /api/todos
  e. Docker compose build: `docker compose build`
  f. Docker compose up + integration test:
     - Hit all 5 endpoints with test data
     - Verify CRUD roundtrip: create → list → update → delete
     - docker compose down

Generate demos/02_todo_app/RESULTS.md with same structure as Demo 1.

SUCCESS CRITERIA for Demo 2:
  ✅ All required files generated
  ✅ Backend tests pass with ≥85% coverage
  ✅ All 5 CRUD endpoints verified
  ✅ Frontend contains working fetch calls
  ✅ Docker compose builds and CRUD roundtrip passes
  ✅ Total run time < 18 minutes

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 5.8: Run Demo Project 3 — Data Pipeline
```
Run AITeamFlow on a data-engineering project.
This validates the system handles non-web projects, CLI tools, and file I/O.

Create demos/03_data_pipeline/project_description.txt:
  "Build an ETL data pipeline with CLI interface:

   Extract:
   - Read CSV files from a configurable input directory
   - Support multiple CSV schemas (auto-detect columns)
   - Report file count, row count, detected schema per file

   Transform:
   - Handle missing values: configurable fill strategy (drop row, fill mean, fill value)
   - Remove duplicate rows (configurable dedup key columns)
   - Type conversion: str → int/float/datetime where parseable
   - Validate rows against configurable rules (min/max value, required fields, regex)
   - Enrich: add computed columns (e.g., row hash, processing timestamp)
   - Report: rows passed, rows failed validation, transformations applied

   Load:
   - Write cleaned data to SQLite database
   - Support upsert (insert or update by primary key)
   - Create table from schema if not exists
   - Report rows loaded, rows updated, rows skipped

   CLI (click):
   - `pipeline run --input ./data --config pipeline.yaml --db output.db`
   - `pipeline validate --input ./data --config pipeline.yaml` (dry run)
   - `pipeline report --db output.db` (stats on loaded data)

   Config (YAML):
   - input_dir, db_path
   - schema: column definitions with type and validation rules
   - transform: fill_strategy, dedup_keys
   - load: primary_key, table_name

   Tests:
   - Unit tests for each module (extract, transform, load)
   - Integration test: full pipeline run on sample CSV data
   - Include sample CSV files with intentional quality issues
   - Minimum 15 test cases, 80% coverage"

Run AITeamFlow with this spec.

Validate:
  a. Verify: pipeline/cli.py, pipeline/extract.py, pipeline/transform.py,
     pipeline/load.py, config/pipeline_config.yaml, data/sample_input.csv,
     tests/test_pipeline.py, requirements.txt
  b. Run: `pytest tests/ -v --cov=pipeline`
     Require: ≥15 test cases, ≥80% coverage
  c. Functional test: run CLI on sample CSV
     - `python -m pipeline run --input data/ --config config/pipeline_config.yaml --db test.db`
     - Verify: exit 0, test.db created, rows loaded > 0
     - `python -m pipeline report --db test.db`
     - Verify: outputs non-empty stats
  d. Validate test: `python -m pipeline validate --input data/ --config config/pipeline_config.yaml`
     - Verify: exits 0 (or 1 with validation report if sample data has issues)

Generate demos/03_data_pipeline/RESULTS.md.

SUCCESS CRITERIA for Demo 3:
  ✅ All required files generated
  ✅ Tests pass with ≥80% coverage (≥15 test cases)
  ✅ CLI runs successfully on sample data
  ✅ SQLite DB created with data loaded
  ✅ Report command outputs data stats
  ✅ Total run time < 20 minutes

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 5.9: Generate Iteration and Fix Workflow
```
Create scripts/run_all_demos.py — runs all demos and produces a master report.
This is the primary tool for validating and improving the system.

1. For each demo in [demos/01_hello_world, demos/02_todo_app, demos/03_data_pipeline]:
   a. Load project_description.txt
   b. Execute AITeamFlow (real run, not mock)
   c. Run capture_demo.py for that demo
   d. Load RESULTS.md and parse pass/fail
   e. Record: demo name, status, duration, failed criteria

2. Master report output (docs/DEMO_RESULTS.md):
   | Demo | Status | Duration | Tests | Coverage | Docker | Issues |
   |------|--------|----------|-------|----------|--------|--------|
   | Hello World Flask | ✅ PASS | 7m 12s | 8/8 | 84% | ✅ | - |
   | TODO App | ⚠️ PARTIAL | 16m 45s | 11/12 | 82% | ✅ | 1 test failed |
   | Data Pipeline | ❌ FAIL | 22m 10s | 9/15 | 71% | N/A | Coverage below threshold |
   Summary: 2/3 demos passed. Common issues: ...

3. --fix mode (run after reviewing failures):
   a. For each failed demo:
      - Load failure_report.json from that demo
      - Extract: which criterion failed, what the agent output was, guardrail logs
      - Identify root cause category: prompt issue / guardrail too strict /
        model capability / task decomposition / tool failure
      - Generate a fix recommendation in docs/fix_recommendations.md
      - Optionally re-run the demo with enhanced system prompt context
   b. Track improvement: compare new RESULTS.md to previous

4. --compare mode:
   - Diff current output against previous run's captured output
   - Flag: new files added, files removed, test count changes, coverage changes
   - Useful for verifying fixes didn't regress passing demos

5. Iteration log:
   - Append each run to docs/iteration_log.json:
     {timestamp, demo_results, models_used, total_duration, pass_rate}
   - Used to track improvement over iterations

6. GitHub Actions integration:
   - Exit 0 only if ALL demos pass all criteria
   - JUnit XML output: reports/junit_demos.xml
   - Artifacts: upload RESULTS.md, DEMO_RESULTS.md, iteration_log.json

Create docs/ITERATION_PLAYBOOK.md explaining:
- How to interpret failure reports
- Common failure patterns and fixes (prompt engineering vs config vs model)
- How to update guardrail thresholds based on demo results
- When to switch models vs when to improve prompts

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

---

## Phase 6: UI, Deployment & Showcase (Days 36-42)

### Prompt 6.1: Generate Gradio UI
```
Create ui/app.py — the main Gradio application:

1. Sidebar:
   - Configuration panel: select Ollama models per role (dropdowns)
   - Settings: max retries, coverage threshold, guardrail toggles
   - Ollama status indicator (green/red dot)
   - Project history (list of past runs with links)

2. Main area:
   - Project input: large text area for project description
   - Template buttons: "Flask API", "Todo App", "Data Pipeline" (pre-fill description)
   - "Generate Project" button with loading state
   - Real-time progress: phase indicator (Planning → Development → Testing → Deployment)
   - Agent activity feed: scrolling log of what each agent is doing

3. Output area:
   - File tree: expandable tree showing all generated files
   - Code viewer: syntax-highlighted code display with tabs per file
   - Test results: pass/fail badge, coverage bar chart, failure details
   - Download button: ZIP of entire generated project

4. Styling:
   - Custom CSS for professional dark/light theme
   - Animated progress indicators
   - Responsive layout for different screen sizes

5. Error display:
   - Human feedback modal when flow requests clarification
   - Error details with recovery suggestions
   - Retry button with modified parameters

Import from ui/components/ and ui/pages/ for modularity.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 6.2: Generate Project Input Component
```
Create ui/components/project_input.py with a structured input form:

1. ProjectInputForm Gradio component:
   - Project name (text input, required)
   - Project description (large text area, required, min 50 chars)
   - Project type selector (API, Web App, CLI Tool, Data Pipeline, Library)
   - Complexity selector (Simple, Intermediate, Advanced)
   - Technology preferences (optional multi-select: Python/Node/Go, Flask/FastAPI/Django, etc.)
   - Features checklist: Authentication, Database, Docker, CI/CD, Tests, Documentation
   - Additional notes (optional text area)

2. Template system:
   - Load templates from demos/ input.json files
   - "Use Template" button pre-fills all fields
   - Custom templates can be saved to JSON

3. Input validation:
   - Real-time validation with Gradio warning/alert messages
   - Minimum description length check
   - Conflicting options detection (e.g., Go + Django)

4. Output: ProjectRequest Pydantic model with all form fields
   - to_prompt() method that formats as natural language for the flow

Include form state persistence using Gradio state (gr.State) or session.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 6.3: Generate Progress Display Component
```
Create ui/components/progress_display.py with real-time progress tracking:

1. PhaseProgressBar component:
   - Horizontal bar showing all phases: Intake → Planning → Development → Testing → Deployment → Complete
   - Current phase highlighted, completed phases checked
   - Animated transition between phases
   - Estimated time remaining per phase

2. AgentActivityFeed component:
   - Scrolling feed of agent actions in real-time
   - Format: [timestamp] [agent_icon] Agent Name: Action description
   - Color-coded by agent role
   - Expandable details for each action (tool used, input/output preview)
   - Auto-scroll to latest with manual scroll override

3. LiveMetrics component:
   - Elapsed time counter
   - Tasks completed: X/Y
   - Files generated: count
   - Test status: running/passed/failed
   - Token usage estimate

4. Integration:
   - Uses Gradio's progress/state and dynamic updates for real-time updates
   - Polls flow state via callback or session state
   - Supports both synchronous and streaming updates

5. Error overlay:
   - Red banner on error with phase and message
   - "Details" expander with full error context
   - "Retry" and "Skip" buttons for recovery

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 6.4: Generate Output Display Component
```
Create ui/components/output_display.py with generated project display:

1. FileTreeViewer component:
   - Expandable tree structure showing all generated files
   - Icons per file type (.py, .js, .html, .yml, .md, .json)
   - File size display
   - Click to view file contents

2. CodeViewer component:
   - Syntax-highlighted code display (using Gradio Code component or gr.HighlightedCode)
   - Tab interface for multiple files
   - Line numbers
   - Search within file
   - Copy button per file

3. TestResultsPanel component:
   - Summary badges: X passed, Y failed, Z% coverage
   - Coverage bar chart (per-file breakdown)
   - Failure details: test name, expected vs actual, traceback
   - Re-run button for individual failed tests

4. ArchitectureDiagram component:
   - Display ASCII architecture diagram from ArchitectureDocument
   - Component list with descriptions
   - Technology stack table

5. DownloadPanel component:
   - "Download as ZIP" button for entire project
   - Individual file download links
   - "Open in GitHub" button (creates gist or repo)
   - Copy project structure to clipboard

Include tab layout: Files | Tests | Architecture | Download

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 6.5: Generate demo recording scripts
```
Demo output directories (demos/01_hello_world/output/, etc.) are populated by
Phase 5's run_all_demos.py. The recording script should use these existing outputs
rather than triggering new AITeamFlow runs.

Create scripts/record_demo.py — automated demo recording:

1. DemoRecorder class:
   - Uses Gradio's testing utilities or Selenium/Playwright
   - Records screen during demo execution
   - Captures: input, progress, output, download

2. Demo scenarios to record:
   a. Quick demo (2 min): Hello World Flask API from input to download
   b. Full demo (5 min): Todo App showing all phases, agent activity, test results
   c. Error recovery demo (3 min): Show test failure, retry, and success
   d. Human feedback demo (2 min): Show clarification request and response

3. Output:
   - GIF recordings for README (compressed, < 5MB)
   - Full MP4 for YouTube/LinkedIn
   - Screenshot gallery for documentation

4. Annotations:
   - Add captions explaining each phase
   - Highlight key moments (agent decisions, guardrail triggers)

Also create scripts/screenshot_gallery.py:
   - Take screenshots of key UI states
   - Save to docs/screenshots/ with descriptive names
   - Generate markdown image gallery for README

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 6.6: Generate comprehensive documentation
```
Create/update all documentation files:

1. README.md (update with final content):
   - Badges: build, coverage, license, Python, CrewAI
   - Hero GIF showing the system in action
   - Features table with icons
   - Quick start: 3-command setup (git clone, poetry install, poetry run)
   - Architecture diagram (refined ASCII art)
   - Agent role descriptions with capabilities
   - Configuration reference table
   - Demo project screenshots/recordings
   - Performance benchmarks table
   - Contributing link
   - License (MIT) and acknowledgments

2. docs/AGENTS.md:
   - Detailed profile for each agent: role, goal, backstory, tools, model assignment
   - Decision-making patterns per agent
   - Interaction diagram showing which agents communicate

3. docs/GUARDRAILS.md:
   - Complete catalog of all guardrails by category
   - Configuration options per guardrail
   - Examples of what each guardrail catches
   - How to add custom guardrails

4. docs/FLOWS.md:
   - Flow diagram (ASCII or Mermaid)
   - State machine transitions
   - Routing logic explanation
   - Error handling and recovery procedures

5. docs/API.md:
   - Python API reference for key classes
   - CLI usage reference
   - Configuration file format reference

Use professional language suitable for a senior engineering portfolio.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 6.7: Generate GitHub polish
```
Create scripts/polish_repo.py and associated files for GitHub showcase quality:

1. GitHub-specific files:
   - .github/ISSUE_TEMPLATE/bug_report.md
   - .github/ISSUE_TEMPLATE/feature_request.md
   - .github/PULL_REQUEST_TEMPLATE.md
   - .github/FUNDING.yml (optional)
   - .github/CODEOWNERS

2. Repository metadata:
   - LICENSE (MIT full text)
   - CHANGELOG.md (initial release v1.0.0 with all features)
   - SECURITY.md (vulnerability reporting instructions)
   - CODE_OF_CONDUCT.md

3. Badge generation:
   - Build status badge URL
   - Coverage badge URL
   - License badge
   - Python version badge
   - CrewAI version badge
   - Custom "Local-First" badge
   - Custom "Guardrails" badge

4. Release automation:
   - scripts/create_release.sh: tags version, generates changelog, creates GitHub release
   - Includes built Docker image reference
   - Includes ZIP of demo project outputs

5. Social preview:
   - Generate social preview image (1280x640) for GitHub repo card
   - Include project name, key stats, architecture diagram thumbnail

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

### Prompt 6.8: Generate LinkedIn/social announcement
```
Create docs/ANNOUNCEMENT.md with social media content:

1. LinkedIn post (300 words):
   - Hook: compelling opening about AI-augmented development
   - What it is: autonomous multi-agent dev team on local hardware
   - Key differentiators: local-first, enterprise guardrails, CrewAI Flows
   - Technical highlights: 7 agents, 3 guardrail categories, 5 demo projects
   - Personal angle: what was learned building it
   - Call to action: link to GitHub, invite to try it
   - Relevant hashtags

2. Twitter/X thread (5 tweets):
   - Tweet 1: Hook + what it does
   - Tweet 2: Architecture overview
   - Tweet 3: Guardrails and safety
   - Tweet 4: Demo GIF or screenshot
   - Tweet 5: Link + call to action

3. Dev.to / Hashnode article outline:
   - Title options (3 alternatives)
   - Article structure: problem, solution, architecture, demo, lessons
   - Key screenshots to include
   - Code snippets to highlight

4. README-friendly summary (50 words):
   - One-paragraph project description for portfolio site

Tone: professional but enthusiastic, technical depth without jargon overload.
Focus on: practical value, engineering quality, portfolio-worthy demonstration.

At the end, update docs/prompts/PROMPT_TRACKING.md: set this prompt's Status to Done and add any Notes.
```

---

## Phase 7: AWS Bedrock AgentCore Deployment (Days 43–52)

Deploy ai-team to production on Amazon Bedrock AgentCore using AWS CDK (Python). LLM switches from local Ollama to Bedrock (Claude Sonnet 4 / Haiku 4.5); ARM64 container; AgentCore Runtime, Memory, Gateway, Observability, and Identity. Full phase spec (architecture, WBS, cursor rules): [.archive/phase-7-agentcore-deployment.md](../.archive/phase-7-agentcore-deployment.md).

### Prompt 7.1: Initialize CDK Project
```
Create an AWS CDK Python project for deploying ai-team to Amazon Bedrock AgentCore.

Directory structure:
infra/
├── app.py                    # CDK app entry point
├── cdk.json                  # CDK configuration
├── requirements.txt          # CDK dependencies
├── cdk.context.json          # Context values
├── stacks/
│   ├── __init__.py
│   ├── base_stack.py         # Shared resources (ECR repo, S3 bucket, base IAM)
│   ├── runtime_stack.py      # AgentCore Runtime + container deployment
│   ├── memory_stack.py       # AgentCore Memory configuration
│   ├── gateway_stack.py      # AgentCore Gateway + Lambda tools
│   ├── observability_stack.py # CloudWatch + AgentCore Observability
│   └── identity_stack.py     # Cognito + AgentCore Identity
├── constructs/
│   ├── __init__.py
│   ├── agentcore_runtime.py  # Reusable Runtime construct
│   └── lambda_tool.py        # Reusable Lambda tool construct
└── tests/
    ├── __init__.py
    └── test_stacks.py        # CDK assertion tests

CDK app.py should:
1. Accept environment parameter (dev/staging/prod) via context
2. Define stack dependencies: base → runtime → memory/gateway/observability/identity
3. Tag all resources with: project=ai-team, environment={env}, managed-by=cdk
4. Use us-east-1 as default region (AgentCore availability)

requirements.txt:
- aws-cdk-lib>=2.150.0
- constructs>=10.0.0
- aws-cdk.aws-bedrock-alpha (if available, otherwise use CfnResource for AgentCore)
- boto3
- pytest

Include cdk.json with app command pointing to app.py.
```

### Prompt 7.2: Create AgentCore Runtime Adapter
```
Create src/ai_team/adapters/agentcore_adapter.py — wraps AITeamFlow for AgentCore Runtime.

The adapter must:
1. Import BedrockAgentCoreApp from bedrock_agentcore.runtime
2. Create a BedrockAgentCoreApp instance
3. Define @app.entrypoint that:
   a. Extracts "prompt" from payload (the project description)
   b. Extracts optional config overrides (model, guardrail settings)
   c. Initializes AITeamFlow with production settings
   d. Calls flow.kickoff() with the prompt
   e. Returns structured response: {project_id, status, files: [...], summary}
   f. Handles errors gracefully — return error details, never crash the runtime
4. Support session context from AgentCore (context.session_id)
5. Integrate with AgentCore Memory for session state persistence
6. Include health check endpoint

Code structure:

    from bedrock_agentcore.runtime import BedrockAgentCoreApp
    from ai_team.flows.main_flow import AITeamFlow
    from ai_team.config.settings import get_settings

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke_ai_team(payload, context):
        """Main entrypoint for AgentCore Runtime invocation."""
        prompt = payload.get("prompt", "")
        config = payload.get("config", {})
        session_id = context.session_id

        settings = get_settings(deployment_mode="agentcore", overrides=config)
        flow = AITeamFlow(settings=settings, session_id=session_id)

        try:
            result = flow.kickoff(project_description=prompt)
            return {
                "project_id": result.project_id,
                "status": result.status,
                "files": [f.dict() for f in result.files],
                "summary": result.summary,
                "metrics": result.metrics
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "phase": flow.current_phase}

    if __name__ == "__main__":
        app.run()

Also create src/ai_team/adapters/__init__.py.
Include ability to run locally with `python -m ai_team.adapters.agentcore_adapter`.
```

### Prompt 7.3: Add Bedrock Model Integration
```
Extend src/ai_team/config/settings.py to support Amazon Bedrock as an LLM provider alongside Ollama.

1. Add DeploymentMode enum: LOCAL (Ollama), AGENTCORE (Bedrock), HYBRID
2. Add BedrockModelConfig(BaseSettings):
   - region: str = "us-east-1"
   - Per-role model assignments using Bedrock model IDs:
     - manager_model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
     - product_owner_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
     - architect_model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
     - backend_developer_model: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
     - frontend_developer_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
     - devops_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
     - cloud_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
     - qa_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
   - temperature, max_tokens, top_p defaults
3. Modify BaseAgent to select LLM based on deployment_mode:
   - LOCAL → LangChain ChatOllama
   - AGENTCORE → LangChain ChatBedrock (from langchain_aws)
   - HYBRID → try Bedrock, fallback to Ollama
4. Add langchain-aws to pyproject.toml dependencies
5. Add DEPLOYMENT_MODE env var (default: "local")

Ensure backward compatibility — existing Ollama setup continues to work unchanged.
Environment variable: DEPLOYMENT_MODE=agentcore activates Bedrock models.
```

### Prompt 7.4: Create Production Dockerfile
```
Create docker/Dockerfile.agentcore — an ARM64-optimized container for AgentCore Runtime.

Requirements:
1. Base image: python:3.11-slim (ARM64 compatible)
2. Multi-stage build:
   Stage 1 (builder):
   - Install Poetry, build-essential, git
   - Copy pyproject.toml and poetry.lock
   - Install dependencies with Poetry (no dev deps)
   - Export to requirements.txt for slim install
   Stage 2 (runtime):
   - Python 3.11-slim
   - Install only runtime system deps (git for GitPython)
   - Copy installed packages from builder
   - Copy src/ directory
   - Create non-root user "agentcore"
   - Set DEPLOYMENT_MODE=agentcore as default env
   - Set entrypoint: python -m ai_team.adapters.agentcore_adapter
3. ARM64 specific:
   - Platform: linux/arm64 (AgentCore requires ARM64)
   - No platform-specific binary deps that would break on ARM
4. Optimization:
   - .dockerignore: tests/, docs/, demos/, ui/, .git/, __pycache__/
   - Layer caching: deps installed before code copy
   - Final image < 500MB target
5. Health check: HEALTHCHECK CMD python -c "import ai_team; print('ok')"

Also create docker/.dockerignore.
Test locally: docker build --platform linux/arm64 -f docker/Dockerfile.agentcore -t ai-team:latest .
```

### Prompt 7.5: Create Runtime CDK Stack
```
Create infra/stacks/runtime_stack.py — CDK stack for AgentCore Runtime deployment.

The stack must:
1. Build and push the ARM64 container to ECR using aws_cdk.aws_ecr_assets.DockerImageAsset:
   - Point to docker/Dockerfile.agentcore
   - Platform: linux/arm64
   - This eliminates the need for separate CodeBuild configuration

2. Create IAM role for the AgentCore Runtime with permissions:
   - bedrock:InvokeModel (for Bedrock model access)
   - bedrock-agentcore:* (for AgentCore services)
   - ecr:GetAuthorizationToken, ecr:BatchGetImage (for container pull)
   - logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents (CloudWatch)
   - s3:PutObject, s3:GetObject (for project output storage)
   - Scoped to least-privilege with specific resource ARNs

3. Create the AgentCore Runtime resource:
   - Use CfnResource or L2 construct if available:
     Type: AWS::BedrockAgentCore::AgentRuntime (or equivalent)
   - Properties:
     - agentRuntimeName: f"ai-team-{environment}"
     - containerImage: Docker image URI from DockerImageAsset
     - roleArn: IAM role ARN
     - networkMode: DEFAULT
     - protocolConfiguration: HTTP
   - If L2 construct not yet available, use aws_cdk.CfnResource with proper type

4. Create S3 bucket for project output artifacts:
   - Bucket name: f"ai-team-outputs-{account}-{region}"
   - Versioning enabled, encryption with SSE-S3
   - Lifecycle rule: expire after 90 days

5. Stack outputs:
   - AgentRuntimeArn
   - AgentRuntimeEndpoint
   - ECRRepositoryUri
   - OutputBucketName

Accept parameters: environment (dev/prod), container_path, runtime_name.
Include CDK assertion test in infra/tests/test_stacks.py.
```

### Prompt 7.6: Create Memory CDK Stack
```
Create infra/stacks/memory_stack.py — CDK stack for AgentCore Memory.

The stack must provision AgentCore Memory with:
1. Memory resource configuration:
   - memoryName: f"ai-team-memory-{environment}"
   - Short-term memory (STM): enabled for multi-turn conversation context within a session
   - Long-term memory (LTM): enabled with strategies:
     a. semantic — stores factual information about projects
     b. summary — maintains condensed project state across sessions
     c. user_preference — (optional) stores per-user customization preferences
   - Associate with the Runtime from runtime_stack via runtime ARN

2. Use CfnResource if no L2 construct available:
   Type: AWS::BedrockAgentCore::Memory
   Properties:
     memoryName, memoryStrategies configuration

3. IAM permissions:
   - Grant the Runtime role access to AgentCore Memory APIs
   - bedrock-agentcore:CreateMemory, GetMemory, UpdateMemory, SearchMemory

4. Integration code adapter:
   Also create src/ai_team/adapters/agentcore_memory.py that:
   - Wraps AgentCore Memory SDK calls
   - Provides same interface as local MemoryManager
   - store(key, value), retrieve(query, top_k), cleanup(session_id)
   - Auto-detects: if running in AgentCore → use managed memory, else → use local ChromaDB

5. Stack outputs:
   - MemoryId
   - MemoryArn

Stack depends on runtime_stack (needs runtime ARN).
```

### Prompt 7.7: Create Gateway CDK Stack
```
Create infra/stacks/gateway_stack.py — CDK stack for AgentCore Gateway.

The stack must:
1. Create AgentCore Gateway resource:
   - gatewayName: f"ai-team-gateway-{environment}"
   - Protocol: MCP (Model Context Protocol)
   - This Gateway exposes the agent's custom tools as MCP-compatible endpoints

2. Register Lambda-backed tools with the Gateway:
   a. file_operations tool:
      - Lambda function that wraps file_tools.py operations
      - Reads/writes to S3 output bucket
      - IAM: s3:GetObject, s3:PutObject on output bucket
   b. code_execution tool:
      - Lambda function that wraps code_tools.py
      - Alternatively, configure AgentCore Code Interpreter as a built-in tool
      - Timeout: 60 seconds, memory: 512MB
   c. test_runner tool:
      - Lambda function that runs pytest on generated code
      - Lambda layer with pytest, coverage pre-installed
      - Timeout: 120 seconds, memory: 1024MB

3. Each Lambda tool:
   - Python 3.11 runtime, ARM64 architecture
   - Bundled from src/ai_team/tools/ directory
   - Structured logging via structlog
   - Error handling that returns Gateway-compatible error responses

4. Gateway authorization:
   - Connect to AgentCore Identity (from identity_stack)
   - Tools require authenticated agent identity to invoke

5. Stack outputs:
   - GatewayId, GatewayArn, GatewayEndpoint
   - Per-tool Lambda ARNs

Stack depends on runtime_stack (output bucket, IAM roles).
```

### Prompt 7.8: Create Observability CDK Stack
```
Create infra/stacks/observability_stack.py — CDK stack for AgentCore Observability.

The stack must:
1. Enable AgentCore Observability for the Runtime:
   - Enable CloudWatch Transaction Search (prerequisite for AgentCore tracing)
   - Configure log group: /aws/bedrock-agentcore/ai-team-{environment}
   - Retention: 30 days (dev), 90 days (prod)

2. Create CloudWatch dashboard: f"ai-team-{environment}-dashboard"
   Widgets:
   a. Agent invocation count (time series, 5min granularity)
   b. Average latency per phase (Planning, Development, Testing, Deployment)
   c. Error rate (percentage of failed invocations)
   d. Token usage per invocation (estimated from response sizes)
   e. Session duration distribution
   f. Guardrail trigger frequency (by category: behavioral, security, quality)

3. CloudWatch alarms:
   a. High error rate: > 20% over 5 minutes → SNS notification
   b. High latency: p95 > 300 seconds → SNS notification
   c. Throttling: > 10 throttles in 5 minutes → SNS notification
   d. Create SNS topic: f"ai-team-{environment}-alerts" with email subscription

4. AgentCore Evaluations (if available):
   - Enable built-in evaluators: correctness, helpfulness, tool_selection_accuracy
   - Configure continuous online evaluation

5. OpenTelemetry integration:
   - Add opentelemetry SDK to container dependencies
   - Emit traces from AITeamFlow phase transitions
   - Span per crew execution, tool invocation, guardrail check

6. Stack outputs:
   - DashboardUrl
   - LogGroupName
   - AlarmTopicArn
```

### Prompt 7.9: Create Identity CDK Stack
```
Create infra/stacks/identity_stack.py — CDK stack for AgentCore Identity + authentication.

The stack must:
1. Create Amazon Cognito User Pool:
   - Pool name: f"ai-team-users-{environment}"
   - Self-signup: enabled (dev), disabled (prod)
   - Password policy: min 8 chars, require uppercase + number + symbol
   - MFA: optional (dev), required (prod)
   - Email verification enabled
   - Standard attributes: email (required), name (optional)

2. Create Cognito User Pool Client:
   - Client name: f"ai-team-client-{environment}"
   - Auth flows: USER_PASSWORD_AUTH, USER_SRP_AUTH
   - OAuth: authorization_code grant, implicit grant
   - Callback URLs: configurable (localhost for dev, domain for prod)
   - Token validity: access=1h, id=1h, refresh=30d

3. Configure AgentCore Identity:
   - Inbound auth: OAuth 2.0 with Cognito as identity provider
   - Discovery URL: Cognito's OpenID Connect endpoint
   - Allowed audiences: [user pool client ID]
   - This controls who can invoke the AgentCore Runtime

4. Create admin user for testing:
   - Only in dev environment
   - Username from CDK context parameter
   - Temporary password, force change on first login

5. Stack outputs:
   - UserPoolId
   - UserPoolClientId
   - CognitoDomain
   - OAuthEndpoint
   - IdentityProviderUrl

Stack is independent but feeds into runtime_stack for auth configuration.
```

### Prompt 7.10: Refactor Settings for Deployment Mode
```
Refactor src/ai_team/config/settings.py to cleanly support both local and cloud deployments.

Changes:
1. Add DeploymentMode enum: LOCAL, AGENTCORE, HYBRID
   - LOCAL: Ollama models, local ChromaDB/SQLite, local file system
   - AGENTCORE: Bedrock models, AgentCore Memory, S3 output, AgentCore tools
   - HYBRID: Bedrock models, local memory (for development with cloud LLMs)

2. Settings factory method:

    def get_settings(deployment_mode: str = None, overrides: dict = None) -> AITeamSettings:
        mode = deployment_mode or os.getenv("DEPLOYMENT_MODE", "local")
        if mode == "agentcore":
            return AgentCoreSettings(**overrides or {})
        elif mode == "hybrid":
            return HybridSettings(**overrides or {})
        else:
            return LocalSettings(**overrides or {})

3. AgentCoreSettings(AITeamSettings):
   - LLM: BedrockModelConfig (Claude Sonnet 4, Haiku 4.5)
   - Memory: AgentCore Memory (no local ChromaDB/SQLite)
   - Output: S3 bucket path
   - Tools: AgentCore Gateway endpoints
   - Logging: CloudWatch + structlog

4. LocalSettings(AITeamSettings):
   - LLM: OllamaModelConfig (existing behavior, unchanged)
   - Memory: local ChromaDB + SQLite
   - Output: local filesystem
   - Tools: local tool implementations
   - Logging: structlog console/file

5. HybridSettings(AITeamSettings):
   - LLM: BedrockModelConfig (use Bedrock for quality)
   - Memory: local ChromaDB + SQLite (no AWS memory dependency)
   - Output: local filesystem
   - Useful for: development with production-quality LLM responses

6. Update BaseAgent.get_llm() to dispatch based on deployment mode:

    if settings.deployment_mode == DeploymentMode.LOCAL:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_name, base_url=settings.ollama.base_url)
    else:
        from langchain_aws import ChatBedrock
        return ChatBedrock(model_id=model_name, region_name=settings.bedrock.region)

Ensure zero breaking changes to existing local workflow.
All new settings have sensible defaults.
```

### Prompt 7.11: Create Cloud Integration Tests
```
Create tests/cloud/ directory with integration tests for the deployed AgentCore system.

1. tests/cloud/conftest.py:
   - Fixtures: boto3 client for bedrock-agentcore, runtime ARN from env/SSM
   - Skip decorator: @pytest.mark.skipif(not os.getenv("AGENTCORE_RUNTIME_ARN"))
   - Timeout: 600 seconds per test (cloud execution is slower)

2. tests/cloud/test_runtime_invocation.py:
   a. test_health_check:
      - Invoke runtime with {"prompt": "health check"}
      - Assert response contains status: "ok"
   b. test_simple_project:
      - Invoke with {"prompt": "Create a Python function that calculates fibonacci numbers"}
      - Assert response has: project_id, status=complete/in_progress, files list
   c. test_hello_world_demo:
      - Invoke with Demo 01 input (Flask API)
      - Assert response contains expected files: app.py, test_app.py, requirements.txt
      - Assert status is not "error"
   d. test_error_handling:
      - Invoke with empty prompt
      - Assert graceful error response (not 500/crash)
   e. test_session_persistence:
      - Invoke twice with same session_id
      - Assert second invocation can reference context from first

3. tests/cloud/test_observability.py:
   a. test_cloudwatch_logs_exist:
      - After invoking runtime, check CloudWatch for log entries
      - Assert log group exists, recent log streams present
   b. test_metrics_published:
      - Check CloudWatch metrics namespace for ai-team metrics

4. tests/cloud/test_memory.py:
   a. test_memory_store_and_retrieve:
      - Store a value via AgentCore Memory API
      - Retrieve and assert match

5. scripts/run_cloud_tests.py:
   - Reads runtime ARN from CDK outputs or SSM Parameter Store
   - Sets env vars
   - Runs: pytest tests/cloud/ -v --timeout=600

Use boto3 bedrock-agentcore client for all invocations.
```

### Prompt 7.12: Create Deploy and Destroy Scripts
```
Create deployment automation scripts:

1. scripts/deploy_agentcore.sh:
   #!/bin/bash
   # Deploy ai-team to AWS Bedrock AgentCore
   # Usage: ./scripts/deploy_agentcore.sh [dev|staging|prod]

   Steps:
   a. Parse environment argument (default: dev)
   b. Check prerequisites: aws cli configured, cdk installed, docker available
   c. Verify AWS credentials: aws sts get-caller-identity
   d. Verify Bedrock model access: check that Claude models are enabled
   e. Bootstrap CDK if needed: cdk bootstrap
   f. Build and deploy stacks in order:
      - cdk deploy AiTeamBase-{env} --require-approval never
      - cdk deploy AiTeamRuntime-{env} --require-approval never
      - cdk deploy AiTeamMemory-{env} AiTeamGateway-{env} AiTeamObservability-{env} AiTeamIdentity-{env} --require-approval never
   g. Print outputs: Runtime ARN, Dashboard URL, Cognito domain
   h. Store outputs in SSM Parameter Store for script access
   i. Run smoke test: invoke runtime with simple prompt
   j. Total expected time: ~15-20 minutes

2. scripts/destroy_agentcore.sh:
   #!/bin/bash
   # Tear down ai-team AgentCore deployment
   # Usage: ./scripts/destroy_agentcore.sh [dev|staging|prod]

   Steps:
   a. Confirmation prompt (skip with --force flag)
   b. Empty S3 buckets first (CDK can't delete non-empty buckets)
   c. cdk destroy --all --force
   d. Clean up SSM parameters
   e. Verify all resources removed

3. scripts/deploy_quick.sh:
   - Minimal deployment using AgentCore starter toolkit instead of CDK
   - For rapid iteration during development:
     pip install bedrock-agentcore-starter-toolkit
     agentcore configure -e src/ai_team/adapters/agentcore_adapter.py
     agentcore launch
   - Outputs runtime ARN for immediate testing

4. Makefile targets:
   deploy-dev: ## Deploy to dev environment
   deploy-prod: ## Deploy to prod environment
   destroy-dev: ## Tear down dev environment
   cloud-test: ## Run cloud integration tests
   smoke-test: ## Quick runtime health check
```

### Prompt 7.13: Create Cost Estimation and Budget Alerts
```
Create infra/stacks/budget_stack.py and docs/COST_ESTIMATION.md:

1. budget_stack.py — CDK stack for AWS Budgets:
   a. Monthly budget alert:
      - Dev: $50/month threshold
      - Prod: $500/month threshold
   b. Notification thresholds: 50%, 80%, 100% of budget
   c. SNS notifications to configurable email
   d. Tag-based cost allocation: filter by project=ai-team tag

2. docs/COST_ESTIMATION.md — cost breakdown:

   | Service | Dev (estimated) | Prod (estimated) | Notes |
   |---------|----------------|------------------|-------|
   | AgentCore Runtime | $50-100/mo | $200-500/mo | Per invocation + session time |
   | Bedrock Models (Claude Sonnet 4) | $3/1M input + $15/1M output | Scales with usage | Dominant cost for complex projects |
   | Bedrock Models (Claude Haiku 4.5) | $0.80/1M input + $4/1M output | Scales with usage | Used for simpler agent roles |
   | AgentCore Memory | $5-10/mo | $20-50/mo | Based on storage + queries |
   | AgentCore Gateway | $5-10/mo | $20-50/mo | Per tool invocation |
   | ECR | $1-5/mo | $1-5/mo | Container storage |
   | S3 | $1-5/mo | $5-20/mo | Project outputs |
   | CloudWatch | $5-10/mo | $20-50/mo | Logs + metrics + dashboards |
   | Cognito | Free tier | Free tier | Up to 50K MAU free |
   | **Total** | **~$70-150/mo** | **~$270-700/mo** | |

3. Cost optimization tips:
   - Use Haiku 4.5 for simple agent roles (PO, DevOps, QA) — 4-5x cheaper than Sonnet
   - Use Sonnet 4 only for Architect and Backend Dev (where quality matters most)
   - Set max_tokens limits per agent to prevent runaway costs
   - Enable Bedrock caching for repeated tool descriptions
   - Use dev environment for development, destroy when not in use
   - Budget alerts prevent surprise bills

4. Include a per-invocation cost estimator:
   - Estimate tokens per phase based on demo runs
   - Calculate cost per project generation
   - Target: < $1 per simple project, < $5 per complex project
```

---

## Summary: Prompt Coverage Matrix

| Phase | Tasks | Prompts | Status |
|-------|-------|---------|--------|
| Phase 0: Preparation | 0.1–0.5 | 5/5 | ✅ Complete |
| Phase 1: Setup | 1.1–1.5 | 5/5 | ✅ Complete |
| Phase 2: Agents & Tools | 2.1–2.14 | 14/14 | ✅ Complete |
| Phase 3: Tasks & Flows | 3.1–3.13 | 13/13 | ✅ Complete |
| Phase 4: Memory & Integration | 4.1–4.8 | 7/8* | ✅ Complete |
| Phase 5: Testing & Demos | 5.1–5.9 | 9/9 | ✅ Complete |
| Phase 6: UI & Showcase | 6.1–6.8 | 8/8 | ✅ Complete |
| Phase 7: AgentCore Deployment | 7.1–7.13 | 13/13 | Pending |
| **TOTAL** | **74 tasks** | **74 prompts** | |

*Phase 4 combines tasks 4.1-4.3 into a single prompt by design.
