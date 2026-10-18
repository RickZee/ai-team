# Pinned 2026-09-28. Do not use latest.
#
# Checked against the public registries that day:
# - otel/opentelemetry-collector-contrib 0.160.0 (contrib GitHub releases)
# - mcr.microsoft.com/dotnet/aspire-dashboard 13.4.2 (MCR, published 2026-08-12)
# - Ollama model llama3.2 (already on this Mac, tool-calling, 2 GB, fits 16 GB)

otel_collector: otel/opentelemetry-collector-contrib:0.160.0
aspire_dashboard: mcr.microsoft.com/dotnet/aspire-dashboard:13.4.2
ollama_model: llama3.2

# Added 2026-10-18 for .kiro/specs/otel-observability (task 0.2):
# - arizephoenix/phoenix 20.5.0: newest server version in the Phoenix release notes
#   (2026-09-01). Tags are plain MAJOR.MINOR.PATCH. Not yet pulled on Rick's Mac.
#   Licence: Elastic License 2.0; self-hosting is free (arize.com/docs/phoenix/self-hosting/license).
#   OTLP/HTTP at :6006/v1/traces, OTLP/gRPC at :4317, data in PHOENIX_WORKING_DIR (SQLite).
#   Query API: GET /v1/projects/{project}/spans/otlpv1 (filters: trace_id, span_id, attribute).
#   Converts gen_ai.* to OpenInference at ingest since 15.10.0; existing OpenInference
#   attributes take precedence.
#   Still to check on a running stack: what Phoenix does with a re-sent span id.
# - OpenTelemetry GenAI semantic conventions 1.42.0 (2026-06-12, status "development").
#   No published schema URL for the GenAI repo yet; export uses
#   https://opentelemetry.io/schemas/1.42.0 until one exists.
# - OpenInference semantic conventions: no version number published; names taken from the
#   spec on 2026-10-18 (openinference.span.kind, llm.model_name, llm.token_count.*, tool.name,
#   input.value, output.value, session.id, metadata).

phoenix: arizephoenix/phoenix:20.5.0
genai_semconv: "1.42.0"
