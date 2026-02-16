"""
Development Crew: implements backend, frontend, and DevOps from planning outputs.

Hierarchical process with Architect as manager/tech lead. Team agents:
Backend Developer, Frontend Developer, DevOps Engineer. Tasks: backend_implementation,
frontend_implementation, devops_configuration. Input: RequirementsDocument +
ArchitectureDocument. Output: List[CodeFile] + DeploymentConfig.

Supports backend-only or frontend-only when architecture indicates a single surface.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from crewai import Crew, Process
import structlog

from ai_team.agents.architect import create_architect_agent
from ai_team.agents.backend_developer import create_backend_developer
from ai_team.agents.frontend_developer import create_frontend_developer
from ai_team.agents.devops_engineer import create_devops_engineer
from ai_team.models.architecture import ArchitectureDocument
from ai_team.models.development import CodeFile, CodeFileList, DeploymentConfig
from ai_team.models.requirements import RequirementsDocument
from ai_team.tasks.development_tasks import (
    create_backend_implementation_task,
    create_frontend_implementation_task,
    create_devops_configuration_task,
)

logger = structlog.get_logger(__name__)

# Max iterations for code generation (prompt: 15)
DEVELOPMENT_MAX_ITERATIONS = 15


def _implementation_tasks_from_architecture(
    architecture: ArchitectureDocument,
) -> Tuple[bool, bool]:
    """
    Determine which implementation tasks are needed from the architecture.

    Returns:
        (include_backend, include_frontend). If architecture has no frontend
        component or no frontend in tech stack, frontend is skipped; similarly
        for backend-only (e.g. API-only or CLI).
    """
    include_backend = True
    include_frontend = True

    component_names = " ".join(
        c.name.lower() for c in architecture.components
    )
    stack_cats = " ".join(
        t.category.lower() for t in architecture.technology_stack
    )

    # Backend-only: no frontend/web/ui component or category
    if not any(
        x in component_names or x in stack_cats
        for x in ("frontend", "web", "ui", "client", "spa", "react", "vue")
    ):
        include_frontend = False
        logger.info("development_crew_backend_only", reason="no frontend in architecture")

    # Frontend-only: no backend/server/api component (e.g. static site)
    if not any(
        x in component_names or x in stack_cats
        for x in ("backend", "server", "api", "service", "database")
    ):
        include_backend = False
        logger.info("development_crew_frontend_only", reason="no backend in architecture")

    return include_backend, include_frontend


def _build_development_tasks(
    backend_agent: Any,
    frontend_agent: Any,
    devops_agent: Any,
    include_backend: bool,
    include_frontend: bool,
    architecture: ArchitectureDocument,
    requirements: RequirementsDocument,
) -> List[Any]:
    """
    Build CrewAI Task list for development: backend, frontend (optional), devops.

    Context: each task receives architecture and requirements via crew inputs;
    task descriptions reference {requirements_doc} and {architecture_doc}.
    """
    arch_dict = architecture.model_dump() if architecture else {}
    req_text = requirements.model_dump_json() if requirements else "{}"
    arch_text = architecture.model_dump_json() if architecture else "{}"

    shared_description_context = (
        " Use the requirements and architecture provided in the crew inputs "
        "(requirements_doc and architecture_doc) as the single source of truth."
    )

    tasks: List[Task] = []
    context_tasks: List[Task] = []

    if include_backend:
        backend_task = create_backend_implementation_task(
            agent=backend_agent,
            context=context_tasks,
            architecture=arch_dict,
        )
        # Inject input references into description for kickoff(inputs=...)
        backend_task.description = (
            backend_task.description + shared_description_context
        )
        tasks.append(backend_task)
        context_tasks.append(backend_task)

    if include_frontend:
        frontend_task = create_frontend_implementation_task(
            agent=frontend_agent,
            context=context_tasks,
        )
        frontend_task.description = (
            frontend_task.description + shared_description_context
        )
        tasks.append(frontend_task)
        context_tasks.append(frontend_task)

    devops_task = create_devops_configuration_task(
        agent=devops_agent,
        context=context_tasks,
    )
    devops_task.description = (
        devops_task.description + shared_description_context
    )
    tasks.append(devops_task)

    return tasks


def _extract_outputs_from_crew_result(
    crew_result: Any,
) -> Tuple[List[CodeFile], Optional[DeploymentConfig]]:
    """
    Extract List[CodeFile] and DeploymentConfig from Crew kickoff result.

    CrewAI result has .tasks_output (list of task outputs). We match by
    output_pydantic type: CodeFileList -> CodeFile list; DeploymentConfig -> config.
    """
    code_files: List[CodeFile] = []
    deployment_config: Optional[DeploymentConfig] = None

    tasks_output = getattr(crew_result, "tasks_output", None) or getattr(
        crew_result, "tasks", []
    )
    if not tasks_output:
        logger.warning("development_crew_no_tasks_output", result_type=type(crew_result).__name__)
        return code_files, deployment_config

    for task_out in tasks_output:
        out = getattr(task_out, "pydantic", None) or getattr(
            task_out, "raw", None
        )
        if out is None:
            continue
        if isinstance(out, CodeFileList):
            for item in out.root:
                code_files.append(item)
        elif isinstance(out, list):
            for item in out:
                if isinstance(item, CodeFile):
                    code_files.append(item)
        elif isinstance(out, DeploymentConfig):
            deployment_config = out
        elif isinstance(out, CodeFile):
            code_files.append(out)

    return code_files, deployment_config


def create_development_crew(
    *,
    verbose: bool = True,
    memory: bool = True,
    max_iterations: int = DEVELOPMENT_MAX_ITERATIONS,
) -> Crew:
    """
    Create the Development Crew with hierarchical process and Architect as manager.

    Agents: Architect (manager), Backend Developer, Frontend Developer, DevOps Engineer.
    Call kickoff(inputs={...}) with requirements_doc and architecture_doc; optionally
    use _implementation_tasks_from_architecture to build a crew with only needed tasks.
    """
    architect = create_architect_agent()
    backend_agent = create_backend_developer()
    frontend_agent = create_frontend_developer()
    devops_agent = create_devops_engineer()

    # Default: all three implementation tasks; caller can replace tasks for backend/frontend-only
    include_backend, include_frontend = True, True
    # Use placeholder docs so task list is built; kickoff will pass real docs
    placeholder_req = RequirementsDocument(
        project_name="Placeholder",
        description="Placeholder for crew creation.",
    )
    placeholder_arch = ArchitectureDocument(
        system_overview="Placeholder",
        components=[],
        technology_stack=[],
    )

    tasks = _build_development_tasks(
        backend_agent=backend_agent,
        frontend_agent=frontend_agent,
        devops_agent=devops_agent,
        include_backend=include_backend,
        include_frontend=include_frontend,
        architecture=placeholder_arch,
        requirements=placeholder_req,
    )

    manager_llm = getattr(architect, "llm", None)
    crew = Crew(
        agents=[architect, backend_agent, frontend_agent, devops_agent],
        tasks=tasks,
        process=Process.hierarchical,
        manager_agent=architect,
        manager_llm=manager_llm,
        memory=memory,
        verbose=verbose,
    )
    return crew


def kickoff(
    requirements: RequirementsDocument,
    architecture: ArchitectureDocument,
    *,
    verbose: bool = True,
    memory: bool = True,
    max_iterations: int = DEVELOPMENT_MAX_ITERATIONS,
) -> Tuple[List[CodeFile], Optional[DeploymentConfig]]:
    """
    Run the Development Crew and return code files and deployment config.

    Accepts planning crew output (RequirementsDocument + ArchitectureDocument).
    When architecture indicates backend-only or frontend-only, only the relevant
    implementation task(s) are included. Returns (list of CodeFile, DeploymentConfig or None).
    """
    include_backend, include_frontend = _implementation_tasks_from_architecture(
        architecture
    )

    architect = create_architect_agent()
    backend_agent = create_backend_developer()
    frontend_agent = create_frontend_developer()
    devops_agent = create_devops_engineer()

    tasks = _build_development_tasks(
        backend_agent=backend_agent,
        frontend_agent=frontend_agent,
        devops_agent=devops_agent,
        include_backend=include_backend,
        include_frontend=include_frontend,
        architecture=architecture,
        requirements=requirements,
    )

    manager_llm = getattr(architect, "llm", None)
    crew = Crew(
        agents=[architect, backend_agent, frontend_agent, devops_agent],
        tasks=tasks,
        process=Process.hierarchical,
        manager_agent=architect,
        manager_llm=manager_llm,
        memory=memory,
        verbose=verbose,
    )

    inputs = {
        "requirements_doc": requirements.model_dump_json(),
        "architecture_doc": architecture.model_dump_json(),
    }

    logger.info(
        "development_crew_kickoff",
        include_backend=include_backend,
        include_frontend=include_frontend,
        task_count=len(tasks),
    )
    result = crew.kickoff(inputs=inputs)
    code_files, deployment_config = _extract_outputs_from_crew_result(result)
    logger.info(
        "development_crew_complete",
        code_file_count=len(code_files),
        has_deployment_config=deployment_config is not None,
    )
    return code_files, deployment_config
