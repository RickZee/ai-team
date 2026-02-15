#!/usr/bin/env python3
"""
Benchmark Ollama models for:
  1. Code generation quality (simple function generation)
  2. Reasoning capability (multi-step problem)
  3. Response latency
  4. Token throughput
Outputs JSON for comparison.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Load .env from project root when run from scripts/
try:
    import dotenv
    _root = Path(__file__).resolve().parent.parent
    dotenv.load_dotenv(_root / ".env")
except ImportError:
    pass

try:
    import httpx
except ImportError:
    print("error: httpx required. Run: uv add httpx", file=sys.stderr)
    sys.exit(1)

# --- Defaults ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODELS = [
    "qwen3:14b",
    "qwen2.5-coder:14b",
    "deepseek-r1:14b",
    "deepseek-coder-v2:16b",
]

CODE_PROMPT = """Write a Python function that takes a list of integers and returns the sum. Output only the function code, no explanation."""

REASONING_PROMPT = """I have 3 boxes. Each box contains 4 bags. Each bag contains 5 coins. How many coins do I have in total? Reply with the number on the first line, then one short sentence explaining the calculation."""


def generate(base_url: str, model: str, prompt: str, timeout: int = 120) -> dict:
    """Call Ollama /api/generate (non-streaming). Returns full response JSON."""
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


def run_benchmark(
    base_url: str,
    model: str,
    timeout: int,
) -> dict:
    """Run code-gen and reasoning benchmarks for one model. Return structured result."""
    result = {
        "model": model,
        "code_generation": None,
        "reasoning": None,
        "error": None,
    }

    # 1. Code generation
    try:
        wall_start = time.perf_counter()
        data = generate(base_url, model, CODE_PROMPT, timeout=timeout)
        wall_elapsed = time.perf_counter() - wall_start
        response_text = data.get("response", "")
        eval_count = data.get("eval_count") or 0
        eval_duration_ns = data.get("eval_duration") or 0
        eval_duration_s = eval_duration_ns / 1e9 if eval_duration_ns else 0
        tokens_per_sec = eval_count / eval_duration_s if eval_duration_s else 0
        # Simple quality heuristic: contains def and return
        has_def = "def " in response_text
        has_return = "return " in response_text
        result["code_generation"] = {
            "prompt": CODE_PROMPT,
            "response": response_text.strip(),
            "latency_seconds": round(wall_elapsed, 3),
            "latency_ms": round(wall_elapsed * 1000, 1),
            "tokens": eval_count,
            "tokens_per_second": round(tokens_per_sec, 2),
            "has_function": has_def and has_return,
        }
    except Exception as e:  # noqa: BLE001
        result["code_generation"] = {"error": str(e)}
        result["error"] = str(e)

    # 2. Reasoning
    try:
        wall_start = time.perf_counter()
        data = generate(base_url, model, REASONING_PROMPT, timeout=timeout)
        wall_elapsed = time.perf_counter() - wall_start
        response_text = data.get("response", "")
        eval_count = data.get("eval_count") or 0
        eval_duration_ns = data.get("eval_duration") or 0
        eval_duration_s = eval_duration_ns / 1e9 if eval_duration_ns else 0
        tokens_per_sec = eval_count / eval_duration_s if eval_duration_s else 0
        # Expected answer 60 (3*4*5). Heuristic: 60 appears in response
        has_correct_number = "60" in response_text
        result["reasoning"] = {
            "prompt": REASONING_PROMPT,
            "response": response_text.strip(),
            "latency_seconds": round(wall_elapsed, 3),
            "latency_ms": round(wall_elapsed * 1000, 1),
            "tokens": eval_count,
            "tokens_per_second": round(tokens_per_sec, 2),
            "answer_correct": has_correct_number,
        }
    except Exception as e:  # noqa: BLE001
        result["reasoning"] = {"error": str(e)}
        if not result.get("error"):
            result["error"] = str(e)

    return result


def check_ollama(base_url: str) -> bool:
    """Verify Ollama is reachable and return True."""
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Ollama models: code generation, reasoning, latency, throughput. Output JSON."
    )
    parser.add_argument(
        "models",
        nargs="*",
        default=DEFAULT_MODELS,
        help=f"Model names to benchmark (default: {DEFAULT_MODELS})",
    )
    parser.add_argument(
        "--base-url",
        default=OLLAMA_BASE_URL,
        help="Ollama API base URL",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write JSON to file (default: stdout)",
    )
    parser.add_argument(
        "--no-print",
        action="store_true",
        help="Do not print progress to stderr",
    )
    args = parser.parse_args()

    if not check_ollama(args.base_url):
        print("error: Ollama not reachable at", args.base_url, file=sys.stderr)
        print("Run: ollama serve", file=sys.stderr)
        return 1

    results = []
    for i, model in enumerate(args.models, 1):
        if not args.no_print:
            print(f"[{i}/{len(args.models)}] Benchmarking {model} ...", file=sys.stderr)
        results.append(run_benchmark(args.base_url, model, args.timeout))

    out = {
        "benchmark": "ollama_models",
        "base_url": args.base_url,
        "models": results,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    json_str = json.dumps(out, indent=2)

    if args.output:
        args.output.write_text(json_str, encoding="utf-8")
        if not args.no_print:
            print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(json_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
