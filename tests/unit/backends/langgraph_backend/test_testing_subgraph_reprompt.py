"""Regression: testing_subgraph_node re-prompts once on no-tests-collected.

QA degeneration on deepseek (2026-06-28 handoff, lever #3): the model can
finish a testing turn without ever calling file_writer, leaving pytest with
zero tests to collect (exit code 5). A full retry_development cycle re-runs
dev+test end to end and costs several LLM calls; testing_subgraph_node now
does one cheap, bounded in-node re-prompt first — call the subgraph again
with a blunt "you wrote nothing, call file_writer now" instruction — before
falling back to the normal graph-level retry loop.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_team.backends.langgraph_backend.graphs import subgraph_runners as sr
from langchain_core.messages import AIMessage


def _state(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "project_description": "x" * 20,
        "generated_files": [],
        "messages": [],
        "metadata": {},
    }
    base.update(extra)
    return base


class TestTestingSubgraphReprompt:
    def test_reprompts_once_when_no_tests_collected_then_recovers(self) -> None:
        """First invoke writes nothing; the re-prompt invoke writes a test file
        (simulated via _workspace_has_tests flipping true after the 2nd call).
        The gate must be re-run after the re-prompt and the final result must
        reflect the recovered (passing) state, not the first failure.
        """
        sub = MagicMock()
        sub.invoke.side_effect = [
            {"messages": [AIMessage(content="the test. the test. the test.")]},
            {"messages": [AIMessage(content="Wrote tests/test_main.py via file_writer.")]},
        ]

        gate_results = iter(
            [
                {"passed": False, "no_tests_collected": True, "reason": "no tests"},
                {"passed": True, "tests": {"ok": True}},
            ]
        )
        has_tests_results = iter([False, False, True])  # pre-gate1, pre-reprompt, pre-gate2

        with (
            patch.object(sr, "_cached_testing", return_value=sub),
            patch.object(sr, "_extract_profile_from_state", return_value=([], {})),
            patch.object(sr, "_guardrail_error_dict", return_value=None),
            patch.object(sr, "_extract_and_write_code_blocks", return_value=[]),
            patch.object(sr, "_run_real_quality_gate", side_effect=lambda: next(gate_results)),
            patch.object(sr, "_workspace_has_tests", side_effect=lambda: next(has_tests_results)),
        ):
            result = sr.testing_subgraph_node(_state(), {})

        assert sub.invoke.call_count == 2, "must re-invoke the subgraph exactly once on failure"
        assert result["test_results"]["passed"] is True
        assert result["phase_history"][0]["passed"] is True

    def test_no_reprompt_when_tests_pass_first_try(self) -> None:
        sub = MagicMock()
        sub.invoke.return_value = {
            "messages": [AIMessage(content="Wrote tests/test_main.py via file_writer.")]
        }

        with (
            patch.object(sr, "_cached_testing", return_value=sub),
            patch.object(sr, "_extract_profile_from_state", return_value=([], {})),
            patch.object(sr, "_guardrail_error_dict", return_value=None),
            patch.object(sr, "_extract_and_write_code_blocks", return_value=[]),
            patch.object(
                sr, "_run_real_quality_gate", return_value={"passed": True, "tests": {"ok": True}}
            ),
            patch.object(sr, "_workspace_has_tests", return_value=True),
        ):
            result = sr.testing_subgraph_node(_state(), {})

        assert sub.invoke.call_count == 1, "must not re-prompt when the gate already passed"
        assert result["test_results"]["passed"] is True

    def test_no_reprompt_when_salvage_recovers_tests(self) -> None:
        """If fenced-code salvage already produced a test file after the first
        invoke, the gate result stands even if it reports no_tests_collected
        from a stale pre-salvage check — the node must not waste a second
        subgraph call once _workspace_has_tests() is true.
        """
        sub = MagicMock()
        sub.invoke.return_value = {
            "messages": [AIMessage(content="```python\ndef test_x(): assert True\n```")]
        }

        with (
            patch.object(sr, "_cached_testing", return_value=sub),
            patch.object(sr, "_extract_profile_from_state", return_value=([], {})),
            patch.object(sr, "_guardrail_error_dict", return_value=None),
            patch.object(sr, "_extract_and_write_code_blocks", return_value=[{"path": "x"}]),
            patch.object(
                sr, "_run_real_quality_gate", return_value={"passed": True, "tests": {"ok": True}}
            ),
            patch.object(sr, "_workspace_has_tests", side_effect=[False, True]),
        ):
            result = sr.testing_subgraph_node(_state(), {})

        assert sub.invoke.call_count == 1
        assert result["test_results"]["passed"] is True

    def test_reprompt_exception_falls_back_to_first_gate_result(self) -> None:
        """If the re-prompt invoke itself raises, the node must not crash —
        it falls back to the (failing) first gate result so the graph-level
        retry_development loop still gets a clear signal to act on.
        """
        sub = MagicMock()
        sub.invoke.side_effect = [
            {"messages": [AIMessage(content="the test. the test.")]},
            RuntimeError("boom"),
        ]

        with (
            patch.object(sr, "_cached_testing", return_value=sub),
            patch.object(sr, "_extract_profile_from_state", return_value=([], {})),
            patch.object(sr, "_guardrail_error_dict", return_value=None),
            patch.object(sr, "_extract_and_write_code_blocks", return_value=[]),
            patch.object(
                sr,
                "_run_real_quality_gate",
                return_value={"passed": False, "no_tests_collected": True},
            ),
            patch.object(sr, "_workspace_has_tests", return_value=False),
        ):
            result = sr.testing_subgraph_node(_state(), {})

        assert sub.invoke.call_count == 2
        assert result["test_results"]["passed"] is False
        assert result["test_results"]["no_tests_collected"] is True
