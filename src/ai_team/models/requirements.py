"""Pydantic models for Product Owner requirements output."""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class MoSCoW(str, Enum):
    """MoSCoW priority levels."""

    MUST = "Must have"
    SHOULD = "Should have"
    COULD = "Could have"
    WONT = "Won't have (this time)"


class AcceptanceCriterion(BaseModel):
    """A single testable acceptance criterion for a user story."""

    description: str = Field(..., description="Testable criterion in Given/When/Then or checklist form")
    testable: bool = Field(default=True, description="Whether the criterion is verifiable")


class UserStory(BaseModel):
    """User story in 'As a... I want... So that...' format."""

    as_a: str = Field(..., description="Role or type of user")
    i_want: str = Field(..., description="Capability or feature desired")
    so_that: str = Field(..., description="Benefit or outcome")
    acceptance_criteria: List[AcceptanceCriterion] = Field(
        default_factory=list,
        description="Testable acceptance criteria",
    )
    priority: MoSCoW = Field(..., description="MoSCoW priority")
    story_id: str = Field(default="", description="Optional story identifier (e.g. US-1)")


class NonFunctionalRequirement(BaseModel):
    """Non-functional requirement (performance, security, scalability, etc.)."""

    category: str = Field(..., description="e.g. performance, security, scalability, usability")
    description: str = Field(..., description="Requirement description")
    measurable: bool = Field(default=True, description="Whether it can be measured or verified")


class RequirementsDocument(BaseModel):
    """Structured requirements document produced by the Product Owner agent."""

    project_name: str = Field(..., description="Name of the project")
    description: str = Field(default="", description="Brief project description")
    target_users: List[str] = Field(default_factory=list, description="Primary user personas or roles")
    user_stories: List[UserStory] = Field(default_factory=list, description="User stories with acceptance criteria")
    non_functional_requirements: List[NonFunctionalRequirement] = Field(
        default_factory=list,
        description="NFRs for performance, security, scalability",
    )
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made")
    constraints: List[str] = Field(default_factory=list, description="Constraints (time, tech, scope)")
