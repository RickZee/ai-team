# Prompt 0.2: Generate Ollama setup script

**Source:** PROJECT_PLAN_OPUS_4_5.md — Phase 0 (Preparation & Research)

---

Create a bash script that:
1. Checks if Ollama is installed, installs if not
2. Pulls these models with progress indication:
   - qwen3:32b (or :14b for lower VRAM)
   - qwen2.5-coder:32b (or :14b)
   - deepseek-r1:32b (or :14b)
   - deepseek-coder-v2:16b
3. Verifies each model works with a simple test
4. Reports VRAM usage estimates
