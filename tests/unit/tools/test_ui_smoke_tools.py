"""UI smoke: skip, foreign refuse, console-error fail, no model call (R13)."""

from __future__ import annotations

from pathlib import Path

from ai_team.tools.ui_smoke_tools import run_ui_smoke


def test_ui_less_scenario_skipped(tmp_path: Path) -> None:
    result = run_ui_smoke(tmp_path, scenario={"id": "plain"})
    assert result.status == "skipped"
    assert result.skip_reason
    assert (tmp_path / "docs" / "ui_smoke_results.json").is_file()


def test_foreign_url_refused(tmp_path: Path) -> None:
    result = run_ui_smoke(
        tmp_path,
        scenario={"ui": {"base_url": "https://example.com/"}},
    )
    assert result.status == "fail"
    assert result.skip_reason == "refused foreign service"


def test_console_error_fails_without_model(tmp_path: Path) -> None:
    def factory(base_url, steps, workspace, item_id, viewport):  # noqa: ANN001
        del base_url, steps, viewport
        from ai_team.tools.ui_smoke_tools import UiStepResult

        shot = workspace / "docs" / "verification" / item_id / "step-00.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        shot.write_bytes(b"png")
        return [
            UiStepResult(
                action="navigate",
                outcome="fail",
                console_errors=["error: boom"],
                screenshot_path=str(shot.relative_to(workspace)),
            )
        ]

    result = run_ui_smoke(
        tmp_path,
        scenario={"ui": {"base_url": "http://127.0.0.1:9"}},
        playwright_factory=factory,
    )
    assert result.status == "fail"
    assert result.steps[0].console_errors
