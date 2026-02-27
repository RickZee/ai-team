#!/usr/bin/env python3
"""
Verify OpenRouter connectivity and list active env / model.

Makes one chat completion request to confirm OPENROUTER_API_KEY works.
No local LLM required; ai-team uses OpenRouter only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __name__ == "__main__" and str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: poetry install", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("OPENROUTER_API_KEY is not set. Add it to .env (see .env.example).", file=sys.stderr)
        sys.exit(1)

    env = os.environ.get("AI_TEAM_ENV", "dev")
    base = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1").rstrip("/")
    # Use a cheap model for connectivity check
    model = "openrouter/openai/gpt-3.5-turbo"
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 10,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices", [])
            if not choices:
                print("OpenRouter returned no choices.", file=sys.stderr)
                sys.exit(1)
            content = (choices[0].get("message", {}).get("content", "") or "").strip()
            print(f"OpenRouter OK (env={env}, model={model})")
            print(f"Response: {content[:80]}")
    except httpx.HTTPStatusError as e:
        print(f"OpenRouter request failed: {e.response.status_code} {e.response.text[:200]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
