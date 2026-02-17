"""Crew definitions for planning, development, testing, and deployment phases."""

from ai_team.crews.planning_crew import create_planning_crew, kickoff as planning_crew_kickoff

__all__ = [
    "create_planning_crew",
    "planning_crew_kickoff",
]

from ai_team.crews.testing_crew import (
    TestingCrewOutput,
    create_testing_crew,
    get_feedback,
    kickoff as testing_crew_kickoff,
)

__all__ = [
    "TestingCrewOutput",
    "create_testing_crew",
    "get_feedback",
    "testing_crew_kickoff",
]

from ai_team.crews.deployment_crew import DeploymentCrew, package_output
from ai_team.crews.planning_crew import create_planning_crew, kickoff as planning_kickoff

__all__ = [
    "DeploymentCrew",
    "create_planning_crew",
    "package_output",
    "planning_kickoff",
]

from ai_team.crews.development_crew import (
    kickoff as development_crew_kickoff,
    create_development_crew,
)

__all__ = [
    "development_crew_kickoff",
    "create_development_crew",
]
