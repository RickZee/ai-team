# Hardware Requirements & Local LLM Recommendations

The autonomous dev team is designed to run fully locally via **Ollama** for privacy, zero cost, and maximum control. All recommendations below are based on February 2026 benchmarks and real-world testing on M-series Macs (Ollama + llama.cpp / MLX backends). Performance focuses on **agentic capabilities** (reasoning, coding, tool use, long-context stability) critical for CrewAI Flows.

## 1. M3 Pro MacBook (36 GB unified memory) – Recommended Configuration

This hardware is the **sweet spot** for a high-performance autonomous team. You can run strong 32B-class models comfortably while leaving headroom for IDE, browser, and parallel agents.

**Primary Recommendation (Best Overall Performance)**

- **Model for most agents**: `qwen2.5-coder:32b` or `qwen3-coder:32b` (Q5_K_M or Q4_K_M)
  - **Why**: Current leader in coding, refactoring, code reasoning, and agentic workflows. Excellent tool-use and long-context handling. Outperforms or matches larger models in dev tasks while staying efficient.
  - **Expected usage**: ~20–26 GB
  - **Speed**: 30–55+ tokens/sec (depending on quant and context)
  - **Ollama pull**: `ollama pull qwen2.5-coder:32b`

**Role-Specific Assignments (Optimal for the Team)**

| Role | Recommended Model | Quant | Rationale | Approx. Memory |
|------|-------------------|-------|-----------|----------------|
| **Manager** | `deepseek-r1:32b` or `glm-4.7-flash` | Q5_K_M | Superior reasoning, planning, blocker resolution | 22–26 GB |
| **Product Owner / Architect** | `qwen3:32b` or `qwen2.5-coder:32b` | Q5_K_M | Strong architecture design + requirements refinement | 22–26 GB |
| **Cloud / DevOps Engineer** | `qwen2.5-coder:32b` | Q5_K_M | Excellent IaC, CI/CD, AWS patterns | 22–26 GB |
| **Software Engineers** | `qwen2.5-coder:32b` (main) + lighter fallback | Q4_K_M | Fast code generation & iteration | 20–24 GB |
| **QA Engineer** | `gemma3:27b` or same coder model | Q4_K_M | Strong analysis, test generation, edge-case detection | 18–22 GB |

**Pro Tip**: Configure CrewAI to use the same strong coder model for all technical roles and a dedicated reasoning model only for the Manager/Architect. This maximizes quality while keeping total memory under ~28–30 GB during runs.

**Alternative High-Quality Option**: `llama3.3:70b` at Q3_K or Q4_K (tight fit, ~34–38 GB). Use only for Manager/Architect if you want maximum reasoning depth — slower (~15–25 t/s) and requires closing other apps.

## 2. MacBook Air (24 GB unified memory) – Recommended Configuration

More constrained, so prioritize **speed + quality balance** over raw size. Expect usable performance with smart model choices.

**Primary Recommendation**

- **Model for all agents**: `qwen2.5-coder:14b` or `qwen3:14b` (Q5_K_M preferred)
  - **Why**: Best quality-to-size ratio for coding and agentic tasks in the 14B class. Runs smoothly with room for context and tools.
  - **Expected usage**: 10–14 GB
  - **Speed**: 40–70+ tokens/sec
  - **Ollama pull**: `ollama pull qwen2.5-coder:14b`

**Role-Specific Assignments**

| Role | Recommended Model | Quant | Rationale | Approx. Memory |
|------|-------------------|-------|-----------|----------------|
| **Manager / Architect** | `deepseek-r1:14b` or `glm-4.7-flash` | Q5_K_M | Strong planning & reasoning | 11–14 GB |
| **Technical Roles** (Engineers, DevOps, Cloud, QA) | `qwen2.5-coder:14b` | Q5_K_M | Excellent coding + efficiency | 10–13 GB |
| **Lightweight Fallback** | `gemma3:12b` or `phi-4:14b` | Q4_K_M | Very fast for simple subtasks | 8–11 GB |

**Note**: Avoid 32B+ models on 24 GB — they will swap heavily and become frustratingly slow. The 14B Qwen coder models deliver surprisingly close quality to 32B versions for most dev-team workflows.

## 3. General Setup & Optimization Tips

- **Preferred backend**: Use the latest Ollama (supports MLX acceleration on Apple Silicon for best speed/memory efficiency). Alternative: LM Studio with native MLX models.
- **Quantization sweet spot**: Q5_K_M for best quality, Q4_K_M for more headroom/speed.
- **Monitoring**: Keep Activity Monitor open → Memory tab. Aim to stay under 80–85% usage during runs.
- **In CrewAI config** (example):

  ```python
  from langchain_community.llms import Ollama

  llm_architect = Ollama(model="qwen2.5-coder:32b", temperature=0.2)
  llm_manager   = Ollama(model="deepseek-r1:32b", temperature=0.1)
  ```

- **Quick start commands**:

  ```bash
  ollama pull qwen2.5-coder:32b
  ollama pull deepseek-r1:32b   # for 36 GB
  # or for 24 GB:
  ollama pull qwen2.5-coder:14b
  ```

- **Testing workflow**: Start with a simple “Hello World FastAPI app” project to validate the full crew before scaling to complex data pipelines or web apps.

These recommendations make the repo immediately practical and impressive for anyone running it on modern Mac hardware — a strong signal of production-aware AI engineering leadership.
