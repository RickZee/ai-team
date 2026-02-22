# Ollama Setup

Local model configuration and recommended models (Qwen3, DeepSeek-R1, Qwen2.5-Coder).

**Single model for all agents (32 GB RAM)**  
Use one model for every role to avoid loading multiple models: set `OLLAMA_MEMORY_PRESET=32gb_single` or `OLLAMA_SINGLE_MODEL=qwen2.5-coder:7b`. Recommended model: **Qwen2.5-Coder 7B** (see `docs/HARDWARE.md`).

**Per-role models**  
Use `OLLAMA_MEMORY_PRESET=default` and optional `OLLAMA_*_MODEL` env vars (e.g. `OLLAMA_ARCHITECT_MODEL=deepseek-r1:14b`). For 32 GB with per-role 7B/8B models use `OLLAMA_MEMORY_PRESET=32gb`.

See `scripts/setup_ollama.sh` for automated setup and `.env.example` for all `OLLAMA_*` variables.
