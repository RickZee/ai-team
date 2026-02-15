"""
Gradio application for AI Team.

Provides a web UI for project input and monitoring.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path when running from repo root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def create_app():
    """Create and return the Gradio Interface."""
    import gradio as gr
    from ai_team.flows.main_flow import run_ai_team

    def run_request(request: str) -> str:
        if not request or not request.strip():
            return "Please enter a project request."
        result = run_ai_team(request)
        state = result.get("state", {})
        phase = state.get("current_phase", "unknown")
        return f"Phase: {phase}\n\nResult: {result.get('result', '')}"

    with gr.Blocks(title="AI Team") as app:
        gr.Markdown("# AI Team — Autonomous Development")
        inp = gr.Textbox(
            label="Project request",
            placeholder="e.g. Create a REST API for a todo list",
            lines=3,
        )
        out = gr.Textbox(label="Output", lines=10)
        btn = gr.Button("Run")
        btn.click(fn=run_request, inputs=inp, outputs=out)
    return app


def main() -> None:
    app = create_app()
    # Bind to 0.0.0.0 and port 8501 for Docker/container usage
    app.launch(server_name="0.0.0.0", server_port=8501)


if __name__ == "__main__":
    main()
