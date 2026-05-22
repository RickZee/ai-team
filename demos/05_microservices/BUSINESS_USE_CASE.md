# Business Use Case: Microservices Platform (Gateway, Users, Notifications)

A growing product is hitting the limits of its monolith — teams can't ship user features without coordinating a huge codebase, and notification logic tightly coupled to user CRUD creates constant change risk. The business wants to **split into independently deployable services** while keeping one entry point for clients.

## Business need

Mistakes in gateway routing or service contracts cause production outages. Greenfield service generation is expensive and often undocumented for local dev. We want to prove agents can produce a coherent multi-service layout — not just a single API.

## What matters

- One public port (gateway) hiding internal topology
- User service owns user data independently
- Notification service can be changed without touching user code
- A developer can run the full stack locally with one command

## Who asked for this

Platform architecture and backend chapter leads. This is the highest-complexity demo in the catalog — it tests agent coordination across domain boundaries.

---

> **Note for the team:** Product Owner defines service responsibilities, API contracts, and user journeys. Architect designs service boundaries, inter-service communication, and compose topology. This document is the stakeholder brief — not the spec.
