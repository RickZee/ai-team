# Monolith pattern

- Start with modular packages inside one deployable unit to reduce operational overhead.
- Enforce clear module boundaries (dependency direction: utils → domain → API).
- Extract a service only when scaling or team boundaries require independent deployment.
- Use feature flags for risky changes within the monolith.
