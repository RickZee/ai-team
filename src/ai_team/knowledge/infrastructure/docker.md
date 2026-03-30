# Docker

- Use multi-stage builds to keep runtime images small; copy only artifacts into final stage.
- Run as non-root (`USER` directive) when the base image allows it.
- Prefer `HEALTHCHECK` for long-running services behind orchestrators.
- Pin base image digests or minor tags for reproducible builds.
