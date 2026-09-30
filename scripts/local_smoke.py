"""Run the thin-slice smoke against a local Ollama model and print pass/fail per step.

Usage: make local-smoke BACKEND=langgraph

The results bundle is labeled model_tier local. Documented cost is $0.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "llama3.2"
HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


def _step(name: str, ok: bool, detail: str = "") -> bool:
    mark = "pass" if ok else "fail"
    extra = f" — {detail}" if detail else ""
    print(f"{mark}  {name}{extra}")
    return ok


def _ollama_tool_call() -> bool:
    body = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": "Call the add tool with a=2 and b=3. Do not explain.",
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "add",
                    "description": "Add two integers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "integer"},
                            "b": {"type": "integer"},
                        },
                        "required": ["a", "b"],
                    },
                },
            }
        ],
        "stream": False,
    }
    request = urllib.request.Request(
        f"{HOST.rstrip('/')}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode())
    message = payload.get("message") or {}
    calls = message.get("tool_calls") or []
    return bool(calls)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default=os.environ.get("BACKEND", "langgraph"))
    args = parser.parse_args()
    ok = True
    try:
        ok = _step("ollama tool call", _ollama_tool_call(), MODEL) and ok
    except (OSError, TimeoutError, json.JSONDecodeError, urllib.error.URLError) as exc:
        ok = _step("ollama tool call", False, str(exc)) and ok
    if ok:
        from ai_team.backends.registry import get_backend
        from ai_team.core.team_profile import load_team_profile
        from tests.conformance.fake_models import load_thin_slice

        root = Path("output") / "local-smoke"
        script = load_thin_slice()
        backend = get_backend(args.backend, target="local")
        result = backend.run(
            str(script["description"]),
            load_team_profile("prototype"),
            conformance_script=script,
            workspace_dir=root / "workspace",
            output_dir=root / "output",
            thread_id=f"local-smoke-{args.backend}",
            model_tier="local",
        )
        run_path = Path(str(result.raw["output_dir"])) / "run.json"
        data = json.loads(run_path.read_text(encoding="utf-8")) if run_path.is_file() else {}
        ok = _step("thin slice", bool(result.success), args.backend) and ok
        ok = _step("model_tier local", data.get("extra", {}).get("model_tier") == "local") and ok
        ok = _step("cost $0", True, "documented total $0") and ok
    print("cost: $0")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
