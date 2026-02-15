"""Tools for the Architect agent: design, technology selection, interfaces, diagrams."""

from crewai.tools import tool


@tool("Architecture designer")
def architecture_designer(system_overview: str, components_description: str) -> str:
    """Record or refine the system overview and component list with responsibilities.
    Use this when drafting or updating the high-level architecture: describe the system
    in a few sentences, then list each component and its responsibilities (name and
    what it does). Inputs are free-form text; the agent should structure the final
    output into ArchitectureDocument format."""
    return (
        "Architecture design recorded. System overview and components captured. "
        "Include these in your final ArchitectureDocument: system_overview, components "
        "(list of name + responsibilities)."
    )


@tool("Technology selector")
def technology_selector(choices_description: str) -> str:
    """Record technology stack choices with justification for each.
    Use this when selecting technologies (frameworks, databases, messaging, infra):
    for each choice provide the name, category (e.g. backend, database), and why it was
    chosen. The final output should populate ArchitectureDocument.technology_stack."""
    return (
        "Technology stack recorded. Include technology_stack in your ArchitectureDocument "
        "with name, category, and justification for each choice."
    )


@tool("Interface definer")
def interface_definer(contracts_description: str) -> str:
    """Record API or interface contracts between components.
    Use this when defining how components communicate: for each contract specify provider,
    consumer, type (e.g. REST API, event), and a short description. Populate
    ArchitectureDocument.interface_contracts in the final output."""
    return (
        "Interface contracts recorded. Include interface_contracts in your "
        "ArchitectureDocument (provider, consumer, contract_type, description)."
    )


@tool("Diagram generator")
def diagram_generator(diagram_type: str, ascii_content: str) -> str:
    """Record an ASCII architecture diagram.
    Use this when producing a diagram: specify the type (e.g. component, deployment,
    data flow) and the ASCII art content. The final ArchitectureDocument.ascii_diagram
    should contain the diagram; deployment_topology can hold deployment-specific notes."""
    return (
        "Diagram recorded. Include ascii_diagram (and deployment_topology if relevant) "
        "in your final ArchitectureDocument."
    )


def get_architect_tools():
    """Return the list of tools for the Architect agent."""
    return [
        architecture_designer,
        technology_selector,
        interface_definer,
        diagram_generator,
    ]
