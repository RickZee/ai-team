"""Pydantic models for Architect agent output (ArchitectureDocument)."""

from typing import List

from pydantic import BaseModel, Field


class Component(BaseModel):
    """A system component with name and responsibilities."""

    name: str = Field(..., description="Component identifier")
    responsibilities: str = Field(..., description="What this component is responsible for")


class TechnologyChoice(BaseModel):
    """A technology selection with justification."""

    name: str = Field(..., description="Technology or tool name")
    category: str = Field(..., description="e.g. backend, database, messaging, frontend")
    justification: str = Field(..., description="Why this choice was made")


class InterfaceContract(BaseModel):
    """API or interface contract between components."""

    provider: str = Field(..., description="Component providing the interface")
    consumer: str = Field(..., description="Component consuming the interface")
    contract_type: str = Field(..., description="e.g. REST API, message queue, event")
    description: str = Field(..., description="Summary of the contract or endpoints")


class ArchitectureDecisionRecord(BaseModel):
    """A single Architecture Decision Record (ADR)."""

    title: str = Field(..., description="Short decision title")
    status: str = Field(default="Accepted", description="e.g. Accepted, Deprecated, Superseded")
    context: str = Field(..., description="What is the issue we are facing?")
    decision: str = Field(..., description="What is the change we are proposing?")
    consequences: str = Field(..., description="What becomes easier or harder?")


class ArchitectureDocument(BaseModel):
    """Structured architecture document produced by the Architect agent."""

    system_overview: str = Field(..., description="High-level description of the system")
    components: List[Component] = Field(
        default_factory=list,
        description="Component list with responsibilities",
    )
    technology_stack: List[TechnologyChoice] = Field(
        default_factory=list,
        description="Technology stack with justification for each choice",
    )
    interface_contracts: List[InterfaceContract] = Field(
        default_factory=list,
        description="API/interface contracts between components",
    )
    data_model_outline: str = Field(
        default="",
        description="Data model or database schema outline",
    )
    ascii_diagram: str = Field(
        default="",
        description="ASCII architecture diagram",
    )
    adrs: List[ArchitectureDecisionRecord] = Field(
        default_factory=list,
        description="Architecture Decision Records",
    )
    deployment_topology: str = Field(
        default="",
        description="Deployment topology recommendation",
    )
