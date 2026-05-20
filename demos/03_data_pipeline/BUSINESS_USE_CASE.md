# Business Use Case: ETL Data Pipeline

An analytics team receives **recurring CSV extracts** from partners or internal systems and spends hours in spreadsheets cleaning them. They need a dependable ingest → clean → load → report pipeline without hiring a data platform team to build it.

## Business need

Raw files arrive with inconsistent types, duplicates, and missing values. The existing one-off scripts break when schemas drift, create bus-factor risk, and produce no audit trail. Leadership lacks timely, trusted aggregates for planning and compliance.

## What matters

- Files dropped in a folder become queryable data
- Bad rows handled explicitly — not silently dropped
- CLI summary report shows what landed and what was rejected
- Process is testable and repeatable, not a fragile script

## Who asked for this

Data engineering and analytics teams. Finance and operations as consumers of the reports.

---

> **Note for the team:** Product Owner defines data quality rules, reporting requirements, and acceptance criteria. Architect decides pipeline stages, tooling (pandas/DuckDB/etc.), and storage. This document is the stakeholder brief — not the spec.
