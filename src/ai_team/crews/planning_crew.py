"""
Planning Crew: requirements gathering and architecture design.

Hierarchical crew with Manager delegating to Product Owner and Architect.
Tasks: requirements_gathering → architecture_design (sequential dependency).
Output: RequirementsDocument and ArchitectureDocument (via task output_pydantic).
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import structlog
from crewai import Crew, Process
from crewai.crew import CrewOutput

from ai_team.agents.architect import create_architect_agent
from ai_team.agents.manager import create_manager_agent
from ai_team.agents.product_owner import create_product_owner_agent
from ai_team.config.settings import get_settings
from ai_team.memory import get_crew_embedder_config
from ai_team.tasks.planning_tasks import create_planning_tasks
from ai_team.utils.llm_wrapper import NoFunctionCallingLLMWrapper

logger = structlog.get_logger(__name__)


def _task_callback_for_logging() -> Callable[..., None]:
    """Build a task_callback that logs on task completion (for metrics/logging)."""
    def on_task_complete(callback_arg: Any) -> None:
        # CrewAI task_callback receives (task, output) or similar; log generically
        logger.info(
            "planning_crew_task_complete",
            callback_arg_type=type(callback_arg).__name__,
        )
    return on_task_complete


def create_planning_crew(
    *,
    config_path: Optional[Path] = None,
    agents_config: Optional[Dict[str, Any]] = None,
    verbose: Optional[bool] = None,
    max_rpm: Optional[int] = None,
    memory: bool = True,
    planning: bool = True,
    on_task_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_task_complete: Optional[Callable[[str, Any], None]] = None,
    step_callback: Optional[Callable[..., None]] = None,
    task_callback: Optional[Callable[..., None]] = None,
) -> Crew:
    """
    Create the Planning Crew with hierarchical process.

    Manager delegates to Product Owner (requirements_gathering) and Architect
    (architecture_design). Task dependencies: architecture_design receives
    requirements_gathering output via context. Guardrails are applied at task
    level. Memory and planning are enabled by default for task context passing.

    :param config_path: Optional path to agents/tasks config (for tests).
    :param agents_config: Pre-loaded agents config dict (for tests).
    :param verbose: Override crew verbose (default from settings.project.crew_verbose).
    :param max_rpm: Override max requests per minute (default from settings.project.crew_max_rpm).
    :param memory: Enable short-term memory for task context passing.
    :param planning: Enable CrewAI planning for task breakdown.
    :param on_task_start: Optional callback(task_id, context) for logging/metrics.
    :param on_task_complete: Optional callback(task_id, output) for logging/metrics.
    :return: Configured Crew instance (not yet run).
    """
    settings = get_settings()
    if verbose is None:
        verbose = settings.project.crew_verbose
    if max_rpm is None:
        max_rpm = settings.project.crew_max_rpm

    # When planning_sequential is True (Ollama), use sequential process and no tools for PO
    # to avoid "Instructor does not support multiple tool calls" when the model uses tools.
    use_sequential = getattr(settings.project, "planning_sequential", False)

    # CrewAI hierarchical requires manager_agent to have no tools
    manager = create_manager_agent(
        tools=[],
        config_path=config_path,
        agents_config=agents_config,
    )
    product_owner = create_product_owner_agent(
        tools=[] if use_sequential else None,
        config_path=config_path,
        agents_config=agents_config,
    )
    architect = create_architect_agent(tools=[] if use_sequential else None)

    # When memory is enabled and we use sequential (Ollama), wrap agents' LLMs so that
    # CrewAI's TaskEvaluator (long-term memory) uses the non-Instructor path. Otherwise
    # Ollama can trigger "Instructor does not support multiple tool calls" when storing LTM.
    if use_sequential and memory:
        object.__setattr__(
            product_owner, "llm", NoFunctionCallingLLMWrapper(product_owner.llm)
        )
        object.__setattr__(
            architect, "llm", NoFunctionCallingLLMWrapper(architect.llm)
        )

    agents_map = {
        "product_owner": product_owner,
        "architect": architect,
    }
    tasks_list, _timeouts = create_planning_tasks(
        agents_map,
        config_path=config_path,
    )

    # step_callback / task_callback: when provided (e.g. from flow with monitor), use them.
    # Otherwise build task_callback from on_task_complete or default logging.
    final_step_cb = step_callback
    final_task_cb: Optional[Callable[..., None]] = task_callback
    if final_task_cb is None:
        if on_task_complete is not None:
            def _task_callback(callback_arg: Any) -> None:
                task_id = getattr(callback_arg, "task", None)
                tid = str(getattr(task_id, "description", callback_arg)[:80]) if task_id else "unknown"
                on_task_complete(tid, callback_arg)
            final_task_cb = _task_callback
        else:
            final_task_cb = _task_callback_for_logging()

    # Apply sequential process and no planning when use_sequential (set above).
    use_memory = memory
    if use_sequential:
        process = Process.sequential
        manager_agent = None
        planning = False
        planning_llm = None
    else:
        process = Process.hierarchical
        manager_agent = manager
        planning_llm = getattr(manager, "llm", None) if planning else None

    crew = Crew(
        agents=[product_owner, architect],
        tasks=tasks_list,
        process=process,
        manager_agent=manager_agent,
        memory=use_memory,
        embedder=get_crew_embedder_config() if use_memory else None,
        planning=planning,
        planning_llm=planning_llm,
        verbose=verbose,
        max_rpm=max_rpm,
        step_callback=final_step_cb,
        task_callback=final_task_cb,
    )
    logger.info(
        "planning_crew_created",
        process=process.name if hasattr(process, "name") else str(process),
        num_tasks=len(tasks_list),
        memory=use_memory,
        planning=planning,
        verbose=verbose,
    )
    return crew


def kickoff(
    project_description: str,
    *,
    config_path: Optional[Path] = None,
    agents_config: Optional[Dict[str, Any]] = None,
    verbose: Optional[bool] = None,
    max_rpm: Optional[int] = None,
    step_callback: Optional[Callable[..., None]] = None,
    task_callback: Optional[Callable[..., None]] = None,
) -> CrewOutput:
    """
    Run the Planning Crew with the given project description.

    :param project_description: Natural language description of the project idea.
    :param config_path: Optional path to config (for tests).
    :param agents_config: Optional pre-loaded agents config (for tests).
    :param verbose: Override crew verbose.
    :param max_rpm: Override max RPM.
    :return: CrewOutput containing task outputs (RequirementsDocument and
             ArchitectureDocument from requirements_gathering and architecture_design).
    """
    crew = create_planning_crew(
        config_path=config_path,
        agents_config=agents_config,
        verbose=verbose,
        max_rpm=max_rpm,
        step_callback=step_callback,
        task_callback=task_callback,
    )
    inputs = {"project_description": project_description}
    logger.info("planning_crew_kickoff", project_description_len=len(project_description))
    result = crew.kickoff(inputs=inputs)
    logger.info("planning_crew_complete", has_result=result is not None)
    return result
