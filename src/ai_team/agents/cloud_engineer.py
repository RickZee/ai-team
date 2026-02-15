"""
Cloud Infrastructure Engineer agent.

Designs cloud infrastructure using IaC, optimizes cost/performance/security.
Uses tools: terraform_generator, cloudformation_generator, iam_policy_generator,
cost_estimator, network_designer.
Generated IaC is validated for security best practices (state management,
module reuse, security groups, tagging, least privilege).
"""

from ai_team.agents.base import BaseAgent, create_agent
from ai_team.tools.infrastructure import (
    CLOUD_TOOLS,
)

__all__ = ["CloudEngineer", "create_cloud_engineer"]


def create_cloud_engineer(**kwargs) -> BaseAgent:
    """
    Create the Cloud Engineer agent from config with infrastructure tools.

    Uses agents.yaml key 'cloud_engineer' (Role "Cloud Infrastructure Engineer",
    allow_delegation: false, max_iter: 10). Tools generate Terraform modules,
    CloudFormation templates, IAM policies, cost estimates, and network design;
    all outputs are validated for security best practices.
    """
    return create_agent("cloud_engineer", tools=CLOUD_TOOLS, **kwargs)


# Alias for direct use
CloudEngineer = create_cloud_engineer
