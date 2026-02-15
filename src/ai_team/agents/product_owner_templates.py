"""Templates for common project types used by the Product Owner agent."""

from typing import Dict, List

# Project type key -> list of prompt snippets or section hints for requirements
PROJECT_TYPE_TEMPLATES: Dict[str, List[str]] = {
    "api": [
        "REST or GraphQL API",
        "Target users: integrators, frontend apps, mobile apps, third-party developers",
        "User stories: authentication, CRUD resources, versioning, rate limits, error responses",
        "NFRs: latency (p95/p99), availability (SLA), rate limiting, API documentation (OpenAPI)",
        "Constraints: stateless design, idempotency for writes where applicable",
    ],
    "web_app": [
        "Web application (SPA or server-rendered)",
        "Target users: end users (roles: guest, authenticated, admin)",
        "User stories: sign-up/sign-in, main workflows, dashboard, settings, notifications",
        "NFRs: responsiveness, accessibility (WCAG), browser support, SEO if public",
        "Constraints: responsive design, session handling, CSRF/XSS mitigation",
    ],
    "cli_tool": [
        "Command-line interface tool",
        "Target users: developers, ops, power users",
        "User stories: main command(s), subcommands, flags, config file/env, exit codes",
        "NFRs: help text, shell completion, performance for large inputs",
        "Constraints: no interactive prompts unless required; scriptable by default",
    ],
    "data_pipeline": [
        "Data pipeline (ETL, batch, or streaming)",
        "Target users: data engineers, analysts, downstream systems",
        "User stories: ingest sources, transform rules, output sinks, monitoring, backfill",
        "NFRs: throughput, idempotency, exactly-once or at-least-once semantics, observability",
        "Constraints: config-driven where possible; replay and failure handling",
    ],
}


def get_template_for_project_type(project_type: str) -> str:
    """Return a single string of template guidance for the given project type."""
    key = project_type.lower().strip() if project_type else ""
    if key not in PROJECT_TYPE_TEMPLATES:
        return (
            "No specific template. Use generic requirements: identify target users, "
            "main features, and non-functional needs (performance, security, scalability)."
        )
    lines = PROJECT_TYPE_TEMPLATES[key]
    return "Template guidance:\n" + "\n".join(f"- {line}" for line in lines)
