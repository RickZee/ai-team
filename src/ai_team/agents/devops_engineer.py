"""
DevOps / SRE Engineer agent.

Designs CI/CD pipelines, Docker configs, K8s manifests, and monitoring.
Uses tools: dockerfile_generator, compose_generator, ci_pipeline_generator,
k8s_manifest_generator, monitoring_config_generator.
Generated IaC is validated for security best practices (multi-stage builds,
non-root users, health checks, resource limits).
"""

from ai_team.agents.base import BaseAgent, create_agent
from ai_team.tools.infrastructure import (
    DEVOPS_TOOLS,
)

__all__ = ["DevOpsEngineer", "create_devops_engineer"]


def create_devops_engineer(**kwargs) -> BaseAgent:
    """
    Create the DevOps Engineer agent from config with infrastructure tools.

    Uses agents.yaml key 'devops_engineer' (Role "DevOps / SRE Engineer",
    allow_delegation: false, max_iter: 10). Tools generate Dockerfile,
    docker-compose.yml, .github/workflows/ci.yml, K8s manifests, and
    monitoring config; all outputs are validated for security best practices.
    """
    return create_agent("devops_engineer", tools=DEVOPS_TOOLS, **kwargs)


# Alias for direct use
DevOpsEngineer = create_devops_engineer
