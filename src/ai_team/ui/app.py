"""
Gradio UI for AI-Team (Phase 8).

LangGraph: streams ``updates`` to a live log; supports resume with ``Command(resume=...)``.
CrewAI: synchronous run with JSON result.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import gradio as gr
import structlog
from ai_team.backends.registry import get_backend
from ai_team.core.team_profile import load_team_profile

logger = structlog.get_logger(__name__)


def _run_langgraph_stream(
    description: str,
    team: str,
    thread_id: str,
) -> Iterator[str]:
    """Yield text log lines for LangGraph ``iter_stream_events``."""
    try:
        profile = load_team_profile((team or "full").strip())
    except KeyError as e:
        yield f"Error: {e}"
        return
    from ai_team.backends.langgraph_backend.backend import LangGraphBackend

    backend = get_backend("langgraph")
    if not isinstance(backend, LangGraphBackend):
        yield "Internal error: expected LangGraph backend."
        return
    kw: dict[str, Any] = {}
    if thread_id.strip():
        kw["thread_id"] = thread_id.strip()
    lines: list[str] = []
    for ev in backend.iter_stream_events(description.strip(), profile, **kw):
        lines.append(json.dumps(ev, default=str, indent=2))
        yield "\n\n".join(lines[-40:])

    yield "\n\n--- done ---"


def _run_langgraph_resume(thread_id: str, resume_input: str, team: str) -> str:
    try:
        profile = load_team_profile((team or "full").strip())
    except KeyError as e:
        return f"Error: {e}"
    from ai_team.backends.langgraph_backend.backend import LangGraphBackend

    backend = get_backend("langgraph")
    if not isinstance(backend, LangGraphBackend):
        return "Internal error: expected LangGraph backend."
    pr = backend.resume(thread_id.strip(), resume_input, profile)
    return json.dumps(pr.model_dump(), indent=2, default=str)


def _run_crewai(description: str, team: str) -> str:
    try:
        profile = load_team_profile((team or "full").strip())
    except KeyError as e:
        return f"Error: {e}"
    backend = get_backend("crewai")
    pr = backend.run(description.strip(), profile, env=None)
    return json.dumps(pr.model_dump(), indent=2, default=str)


def build_demo() -> gr.Blocks:
    """Build Gradio Blocks (call ``.launch()`` from ``if __name__``)."""
    with gr.Blocks(title="AI Team") as demo:
        gr.Markdown("# AI Team")
        gr.Markdown(
            "Use **LangGraph** for streamed graph updates and **resume** after HITL interrupts. "
            "Set `OPENROUTER_API_KEY` and `RAG_ENABLED` as needed."
        )
        with gr.Row():
            backend = gr.Dropdown(
                choices=["crewai", "langgraph"],
                value="langgraph",
                label="Backend",
            )
        team = gr.Textbox(label="Team profile", value="full")
        description = gr.Textbox(
            label="Project description",
            lines=4,
            placeholder="Describe what to build…",
        )
        thread_id = gr.Textbox(
            label="Thread id (optional; leave empty for new run)",
            value="",
        )
        run_btn = gr.Button("Run")
        output = gr.Textbox(label="Output", lines=24, max_lines=40)

        gr.Markdown("### Resume interrupted LangGraph run (HITL)")
        resume_tid = gr.Textbox(label="Thread id to resume")
        resume_in = gr.Textbox(label="Resume value (feedback for interrupt)", lines=2)
        resume_btn = gr.Button("Resume")

        def run_click(
            desc: str,
            tm: str,
            tid: str,
            be: str,
        ) -> Any:
            if be == "langgraph":
                return _run_langgraph_stream(desc, tm, tid)
            return _run_crewai(desc, tm)

        run_btn.click(
            fn=run_click,
            inputs=[description, team, thread_id, backend],
            outputs=output,
        )
        resume_btn.click(
            fn=_run_langgraph_resume,
            inputs=[resume_tid, resume_in, team],
            outputs=output,
        )
    return demo  # type: ignore[no-any-return]


# Pre-built Blocks for ``ai_team.ui.main`` and ``python -m ai_team.ui.app``.
demo = build_demo()

if __name__ == "__main__":
    demo.launch()
