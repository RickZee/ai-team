"""Manager agent tools: delegation, timeline, and blocker resolution."""

from typing import Any

from crewai.tools import tool


@tool("Task delegation")
def task_delegation(
    task_description: str,
    assignee_role: str,
    reason: str,
    priority: str = "normal",
) -> str:
    """Delegate a task to another agent. Use when work should be done by a specific role (e.g. Product Owner, Architect, Backend Developer). Provide task_description, assignee_role, and reason. Priority is 'low', 'normal', or 'high'."""
    # In a full implementation this would enqueue work or update shared state.
    return (
        f"Delegated: '{task_description}' -> {assignee_role} (priority={priority}). "
        f"Reason: {reason}"
    )


@tool("Timeline management")
def timeline_management(
    action: str,
    milestone_or_date: str = "",
    notes: str = "",
) -> str:
    """Manage project timeline and milestones. action can be 'get' (return current timeline), 'set_milestone' (add/update a milestone with milestone_or_date and notes), or 'report_slip' (record a delay with notes)."""
    if action == "get":
        return "Timeline: use set_milestone to record milestones and report_slip for delays. Current view is maintained by the flow state."
    if action == "set_milestone":
        return f"Milestone recorded: {milestone_or_date}. Notes: {notes}"
    if action == "report_slip":
        return f"Slip recorded: {notes}. Consider using blocker_resolution or human escalation if needed."
    return f"Unknown action '{action}'. Use 'get', 'set_milestone', or 'report_slip'."


@tool("Blocker resolution")
def blocker_resolution(
    blocker_description: str,
    attempted_fix: str = "",
    escalate_to_human: bool = False,
    human_question: str = "",
) -> str:
    """Record or resolve a blocker. If the blocker can be resolved by the team, describe it and attempted_fix. If a human decision or unblocking is needed, set escalate_to_human=True and provide human_question so the flow can pause for human input."""
    if escalate_to_human:
        return (
            f"ESCALATION: Blocker — {blocker_description}. "
            f"Question for human: {human_question or 'Please unblock or decide.'}"
        )
    return (
        f"Blocker recorded: {blocker_description}. "
        f"Attempted fix: {attempted_fix or 'None yet.'}"
    )


def get_manager_tools(**kwargs: Any) -> list:
    """Return CrewAI tools for the Manager agent (delegation, timeline, blocker resolution)."""
    return [task_delegation, timeline_management, blocker_resolution]
