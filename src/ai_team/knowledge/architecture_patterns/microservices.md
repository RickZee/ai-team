# Microservices pattern

- Bound contexts: each service owns its data store; avoid shared databases across teams.
- Prefer async messaging or HTTP APIs with explicit schemas (OpenAPI) between services.
- Deploy independently; use health checks and graceful shutdown for orchestrators.
- Centralize observability: correlation IDs across service calls.
