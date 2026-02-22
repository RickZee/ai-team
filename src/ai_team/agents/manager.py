"""
Manager agent for ai-team: coordinates the team, resolves blockers, ensures on-time delivery.

Extends BaseAgent with tools for task_delegation, timeline_management, blocker_resolution,
and status_reporting. Delegation assigns tasks based on agent capabilities and current
workload. Human escalation should be triggered when confidence is below
HUMAN_ESCALATION_CONFIDENCE_THRESHOLD or when critical decisions are needed. Progress
tracking is maintained via timeline_management and status_reporting, with integration
to ProjectState when used inside AITeamFlow (phase transitions, status updates).
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import structlog

from ai_team.agents.base import BaseAgent, create_agent
from ai_team.tools.manager_tools import get_manager_tools

logger = structlog.get_logger(__name__)

# When manager confidence is below this threshold, escalate to human (e.g. set
# ProjectState.awaiting_human_input and human_feedback).
HUMAN_ESCALATION_CONFIDENCE_THRESHOLD = 0.6


def create_manager_agent(
    *,
    tools: Optional[Any] = None,
    before_task: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    after_task: Optional[Callable[[str, Any], None]] = None,
    guardrail_tools: bool = True,
    config_path: Optional[Path] = None,
    agents_config: Optional[Dict[str, Any]] = None,
) -> BaseAgent:
    """
    Create the Manager agent (Engineering Manager / Project Coordinator).

    Uses config from config/agents.yaml (manager section), attaches
    task_delegation, timeline_management, blocker_resolution, and status_reporting
    tools. Suitable as manager_agent in CrewAI hierarchical process.

    Delegation logic: task_delegation tool assigns tasks based on agent
    capabilities and optional current workload. Use timeline_management and
    status_reporting to maintain project status and phase transitions; when
    run inside AITeamFlow, the flow can apply suggested updates to ProjectState.

    Human escalation: when confidence < HUMAN_ESCALATION_CONFIDENCE_THRESHOLD or
    critical decisions are needed, the manager should recommend setting
    ProjectState.awaiting_human_input = True and populating human_feedback
    (e.g. via blocker_resolution or status_reporting with state_updates_json).

    :param tools: Tool list for the manager; default is get_manager_tools(). Pass [] for
        use as CrewAI hierarchical manager_agent (CrewAI requires manager to have no tools).
    :param before_task: Optional callback(task_id, context) for memory/state before task.
    :param after_task: Optional callback(task_id, output) for memory/state after task.
    :param guardrail_tools: Wrap tools with security guardrails.
    :param config_path: Override path to agents YAML (for tests).
    :param agents_config: Pre-loaded agents config dict (for tests).
    :return: Configured BaseAgent instance for the manager role.
    """
    if tools is None:
        tools = get_manager_tools()
    agent = create_agent(
        "manager",
        tools=tools,
        before_task=before_task,
        after_task=after_task,
        guardrail_tools=guardrail_tools,
        config_path=config_path,
        agents_config=agents_config,
    )
    logger.info(
        "manager_agent_created",
        tools=[getattr(t, "name", str(t)) for t in tools],
        allow_delegation=getattr(agent, "allow_delegation", True),
    )
    return agent
