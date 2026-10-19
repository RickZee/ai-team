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
#   (2026-09-01). Tags are plain MAJOR.MINOR.PATCH. Pulled on Rick's Mac 2026-10-18,
#   digest sha256:39374ee6ad0c69c0a5e713e42e869f70ae99f681e0dbad374721a5ccecd0d54d.
#   Licence: Elastic License 2.0; self-hosting is free (arize.com/docs/phoenix/self-hosting/license).
#   OTLP/HTTP at :6006/v1/traces, OTLP/gRPC at :4317, data in PHOENIX_WORKING_DIR (SQLite).
#   Query API: GET /v1/projects/{project}/spans/otlpv1 (filters: trace_id, span_id, attribute).
#   Converts gen_ai.* to OpenInference at ingest since 15.10.0; existing OpenInference
#   attributes take precedence.
#   Re-sent span ids (checked 2026-10-18, running stack): sending the same 19-span run twice
#   leaves 19 spans, so a re-export replaces rather than duplicates. Kept across a restart.
#
# Checked on the running stack 2026-10-18 (Aspire 13.4.2, collector 0.160.0):
# - Aspire's OTLP/HTTP endpoint (:18890) doesn't accept gzip; the collector's otlphttp default.
#   It returns HTTP 500 and the collector drops the batch. otel-collector.yaml sets
#   compression: none for Aspire only.
# - Aspire's UI asks for a browser token unless DASHBOARD__FRONTEND__AUTHMODE=Unsecured; set
#   in compose, like Phoenix, because the port is on 127.0.0.1.
# - The collector warns that the "otlphttp" alias is deprecated in favour of "otlp_http".
#   Still accepted in 0.160.0; rename with the next collector bump.
# - OpenTelemetry GenAI semantic conventions 1.42.0 (2026-06-12, status "development").
#   No published schema URL for the GenAI repo yet; export uses
#   https://opentelemetry.io/schemas/1.42.0 until one exists.
# - OpenInference semantic conventions: no version number published; names taken from the
#   spec on 2026-10-18 (openinference.span.kind, llm.model_name, llm.token_count.*, tool.name,
#   input.value, output.value, session.id, metadata).

phoenix: arizephoenix/phoenix:20.5.0
genai_semconv: "1.42.0"
