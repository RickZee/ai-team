#!/usr/bin/env python3
"""
Benchmark Ollama models for agent role suitability.

Measures: code generation, reasoning, instruction following, latency, throughput.
Outputs JSON, formatted table, and role recommendations.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

# Add project root for imports if needed
if __name__ == "__main__" and str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from langchain_ollama import ChatOllama
except ImportError:
    print("Error: langchain-ollama is required. Install with: poetry install", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODELS = [
    "qwen3:32b",
    "qwen2.5-coder:32b",
    "deepseek-r1:32b",
    "deepseek-coder-v2:16b",
]

CODE_GEN_PROMPT = """Generate a single Python function that:
1. Has a docstring (triple-quoted) describing what it does and its args/returns.
2. Uses type hints for parameters and return type.
3. Includes a try/except block for error handling.

Function: parse_config_file(path: str) -> dict. It should read a JSON file and return the parsed dict; on failure return an empty dict and handle FileNotFoundError and json.JSONDecodeError."""

REASONING_PROMPT = """You are an architect. In 4 clear steps, design how to add a rate-limiting layer in front of an existing REST API (assume the API already exists). For each step, give a one-sentence description. Output format:

Step 1: ...
Step 2: ...
Step 3: ...
Step 4: ..."""

JSON_SCHEMA_PROMPT = """Respond with only a single JSON object (no markdown, no explanation) that has exactly these keys: "task", "priority", "estimate_hours". Use this example shape: {"task": "Implement auth", "priority": "high", "estimate_hours": 8}. Choose any valid values for task, priority, and estimate_hours."""

EXPECTED_JSON_KEYS = {"task", "priority", "estimate_hours"}

# Latency/throughput scoring bands (time in seconds, tokens_per_sec)
LATENCY_BANDS = [(0.5, 10), (1.0, 9), (2.0, 8), (4.0, 7), (6.0, 6), (10.0, 5), (20.0, 4), (45.0, 3), (90.0, 2), (float("inf"), 1)]
THROUGHPUT_BANDS = [(5, 1), (10, 2), (15, 3), (25, 4), (40, 5), (60, 6), (80, 7), (100, 8), (150, 9), (float("inf"), 10)]


def _score_latency(ttft_seconds: float) -> int:
    for bound, score in LATENCY_BANDS:
        if ttft_seconds <= bound:
            return score
    return 1


def _score_throughput(tokens_per_sec: float) -> int:
    for bound, score in THROUGHPUT_BANDS:
        if tokens_per_sec <= bound:
            return score
    return 10


def _score_code_generation(response: str) -> int:
    """Score 1-10 based on docstring, type hints, and error handling."""
    score = 0
    if '"""' in response or "'''" in response:
        score += 3
    if "->" in response or re.search(r":\s*(str|int|dict|list|Optional|bool)\s*[\),]", response):
        score += 3
    if "try:" in response and "except" in response:
        score += 4
    return min(10, score) if score else 1


def _score_reasoning(response: str) -> int:
    """Score 1-10 based on multi-step structure and clarity."""
    steps = re.findall(r"(?i)step\s*\d+\s*[:.]", response)
    if len(steps) >= 4:
        base = 8
    elif len(steps) >= 2:
        base = 6
    elif "step" in response.lower():
        base = 4
    else:
        base = 2
    if any(w in response.lower() for w in ("rate", "limit", "api", "layer")):
        base = min(10, base + 2)
    return min(10, base)


def _score_instruction_following(response: str) -> int:
    """Score 1-10 based on valid JSON with required keys."""
    stripped = response.strip()
    # Remove possible markdown code fence
    if stripped.startswith("```"):
        stripped = re.sub(r"^```\w*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return 1
    if not isinstance(data, dict):
        return 2
    keys = set(data.keys())
    if keys == EXPECTED_JSON_KEYS:
        return 10
    if keys & EXPECTED_JSON_KEYS:
        return 4 + 2 * len(keys & EXPECTED_JSON_KEYS)
    return 2


def run_streaming(llm: ChatOllama, prompt: str) -> tuple[str, float, float, int]:
    """Invoke model with streaming; return (full_text, time_to_first_token, total_seconds, token_count)."""
    full_text = ""
    ttft: float | None = None
    start = time.perf_counter()
    token_count = 0
    try:
        for chunk in llm.stream(prompt):
            if ttft is None:
                ttft = time.perf_counter() - start
            if hasattr(chunk, "content") and chunk.content:
                full_text += chunk.content
                token_count += 1
    except Exception as e:
        full_text = f"[Error: {e}]"
        ttft = ttft if ttft is not None else time.perf_counter() - start
    total = time.perf_counter() - start
    return full_text, ttft or total, total, max(1, token_count)


def run_benchmark(model: str) -> dict:
    """Run all five benchmarks for one model."""
    llm = ChatOllama(model=model, temperature=0.2)
    results: dict = {
        "model": model,
        "code_generation": {"score": 0, "raw": ""},
        "reasoning": {"score": 0, "raw": ""},
        "instruction_following": {"score": 0, "raw": ""},
        "latency": {"ttft_seconds": 0.0, "total_seconds": 0.0, "score": 0},
        "throughput": {"tokens_per_second": 0.0, "score": 0},
    }

    # 1. Code generation
    text, _, _, _ = run_streaming(llm, CODE_GEN_PROMPT)
    results["code_generation"]["raw"] = text[:2000]
    results["code_generation"]["score"] = _score_code_generation(text)

    # 2. Reasoning
    text, _, _, _ = run_streaming(llm, REASONING_PROMPT)
    results["reasoning"]["raw"] = text[:2000]
    results["reasoning"]["score"] = _score_reasoning(text)

    # 3. Instruction following (JSON)
    text, _, _, _ = run_streaming(llm, JSON_SCHEMA_PROMPT)
    results["instruction_following"]["raw"] = text[:500]
    results["instruction_following"]["score"] = _score_instruction_following(text)

    # 4 & 5. Latency and throughput (one run, medium prompt)
    prompt_perf = "List the numbers 1 to 20, one per line, then say 'Done'."
    _, ttft, total, tokens = run_streaming(llm, prompt_perf)
    results["latency"]["ttft_seconds"] = round(ttft, 3)
    results["latency"]["total_seconds"] = round(total, 3)
    results["latency"]["score"] = _score_latency(ttft)
    tps = tokens / total if total > 0 else 0
    results["throughput"]["tokens_per_second"] = round(tps, 2)
    results["throughput"]["score"] = _score_throughput(tps)

    return results


def build_recommendations(all_results: list[dict]) -> dict[str, str]:
    """Map agent roles to best model by category."""
    def best_for(key: str, score_key: str = "score") -> str:
        by_score: list[tuple[str, int]] = []
        for r in all_results:
            if key in r and isinstance(r[key], dict) and score_key in r[key]:
                by_score.append((r["model"], r[key][score_key]))
        if not by_score:
            return "—"
        by_score.sort(key=lambda x: -x[1])
        return by_score[0][0]

    return {
        "code_generation_agent": best_for("code_generation"),
        "reasoning_architect_agent": best_for("reasoning"),
        "structured_output_agent": best_for("instruction_following"),
        "low_latency_agent": best_for("latency", "score"),
        "high_throughput_agent": best_for("throughput", "score"),
    }


def main() -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        Console = None  # type: ignore
        Table = None     # type: ignore

    out_dir = Path(__file__).resolve().parent.parent
    json_path = out_dir / "benchmark_results.json"

    all_results: list[dict] = []
    for i, model in enumerate(MODELS):
        print(f"\nBenchmarking ({i+1}/{len(MODELS)}): {model}")
        try:
            all_results.append(run_benchmark(model))
        except Exception as e:
            print(f"  Error: {e}")
            all_results.append({
                "model": model,
                "error": str(e),
                "code_generation": {"score": 0, "raw": ""},
                "reasoning": {"score": 0, "raw": ""},
                "instruction_following": {"score": 0, "raw": ""},
                "latency": {"ttft_seconds": 0, "total_seconds": 0, "score": 0},
                "throughput": {"tokens_per_second": 0, "score": 0},
            })

    recommendations = build_recommendations(all_results)
    payload = {
        "models": all_results,
        "recommendations": recommendations,
    }

    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\nJSON written to: {json_path}")

    # Formatted table
    if Table and Console:
        console = Console()
        t = Table(title="Ollama model benchmark (1–10 per category)")
        t.add_column("Model", style="cyan")
        t.add_column("Code", justify="center")
        t.add_column("Reason", justify="center")
        t.add_column("Instr", justify="center")
        t.add_column("Latency", justify="center")
        t.add_column("Throughput", justify="center")
        t.add_column("TTFT (s)", justify="right")
        t.add_column("T/s", justify="right")
        for r in all_results:
            if "error" in r:
                t.add_row(r["model"], "—", "—", "—", "—", "—", "—", "—")
                continue
            cg = r.get("code_generation", {})
            reas = r.get("reasoning", {})
            inst = r.get("instruction_following", {})
            lat = r.get("latency", {})
            thr = r.get("throughput", {})
            t.add_row(
                r["model"],
                str(cg.get("score", "—")),
                str(reas.get("score", "—")),
                str(inst.get("score", "—")),
                str(lat.get("score", "—")),
                str(thr.get("score", "—")),
                str(lat.get("ttft_seconds", "—")),
                str(thr.get("tokens_per_second", "—")),
            )
        console.print(t)
        rec_table = Table(title="Recommendation: best model per agent role")
        rec_table.add_column("Role", style="green")
        rec_table.add_column("Model", style="yellow")
        for role, model in recommendations.items():
            rec_table.add_row(role, model)
        console.print(rec_table)
    else:
        print("\n--- Summary table (install 'rich' for pretty output) ---")
        for r in all_results:
            if "error" in r:
                print(r["model"], "ERROR:", r["error"])
                continue
            print(
                r["model"],
                "| code:", r["code_generation"]["score"],
                "| reason:", r["reasoning"]["score"],
                "| instr:", r["instruction_following"]["score"],
                "| lat:", r["latency"]["score"],
                "| tput:", r["throughput"]["score"],
                "| ttft:", r["latency"]["ttft_seconds"],
                "| t/s:", r["throughput"]["tokens_per_second"],
            )
        print("\nRecommendations:")
        for role, model in recommendations.items():
            print(f"  {role}: {model}")


if __name__ == "__main__":
    main()
