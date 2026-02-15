"""Gradio launcher entry point for ai-team-ui."""

from ai_team.ui.app import demo


def run() -> None:
    """Run the Gradio UI app."""
    demo.launch()


if __name__ == "__main__":
    run()
