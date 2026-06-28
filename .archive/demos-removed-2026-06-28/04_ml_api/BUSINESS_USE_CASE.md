# Business Use Case: ML Inference API

A data science team has a trained model (churn, fraud score, demand forecast — pick one) sitting in a notebook. Product engineering needs it exposed as a **stable HTTP API** so features can call it. SRE needs health checks and metrics. Nobody has time to hand-wire this glue for every model.

## Business need

Models stuck in notebooks can't drive customer-facing features. Building the serving layer manually delays launches and duplicates effort across teams. There's no standard pattern today, so each model gets its own bespoke integration that nobody else can maintain.

## What matters

- `POST /predict` returns a prediction from a feature vector
- Health endpoint reports model load status — Kubernetes can probe it
- Metrics endpoint exposes request counts and latency for on-call
- CI tests work without loading real model weights

## Who asked for this

ML engineering (owns the model) and product engineering (calls the API). SRE cares about operability.

---

> **Note for the team:** Product Owner defines the API contract, latency expectations, and acceptance criteria. Architect decides serving framework, model packaging, and observability approach. This document is the stakeholder brief — not the spec.
