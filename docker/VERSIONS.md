# Pinned 2026-09-28. Do not use latest.
#
# Checked against the public registries that day:
# - otel/opentelemetry-collector-contrib 0.160.0 (contrib GitHub releases)
# - mcr.microsoft.com/dotnet/aspire-dashboard 13.4.2 (MCR, published 2026-08-12)
# - Ollama model llama3.2 (already on this Mac, tool-calling, 2 GB, fits 16 GB)

otel_collector: otel/opentelemetry-collector-contrib:0.160.0
aspire_dashboard: mcr.microsoft.com/dotnet/aspire-dashboard:13.4.2
ollama_model: llama3.2
