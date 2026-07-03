"""Regression tests for CrewAI Flow event wiring in ``AITeamFlow``.

Root cause these tests guard against (found 2026-07-01, live evidence:
93,284 retry iterations in 15 minutes): in CrewAI Flow, a method's completion
emits the *method's own name* as the next trigger, and completed listeners are
deliberately cleared to allow cycles. A method that ``@listen``s to its own
name therefore re-triggers itself unbounded. Separately, a plain ``@listen``'s
return value is discarded — only ``@router`` returns route — so a retry cap
implemented as ``return "escalate_to_human"`` from a listener never routed.
"""

from __future__ import annotations

from typing import Any

from ai_team.flows.main_flow import AITeamFlow


def _trigger_map() -> dict[str, tuple[list[str], bool]]:
    """Map method name -> (trigger names, is_router) for all Flow-decorated methods."""
    out: dict[str, tuple[list[str], bool]] = {}
    for name in dir(AITeamFlow):
        attr = getattr(AITeamFlow, name, None)
        triggers = getattr(attr, "__trigger_methods__", None)
        if triggers is None:
            continue
        is_router = bool(getattr(attr, "__is_router__", False))
        out[name] = ([str(t) for t in triggers], is_router)
    return out


class TestNoSelfTriggeringListeners:
    def test_no_method_listens_to_its_own_name(self) -> None:
        """A method whose name appears in its own trigger set self-loops forever."""
        offenders = [name for name, (triggers, _) in _trigger_map().items() if name in triggers]
        assert offenders == [], (
            f"Flow methods listening to their own name (infinite self-trigger): {offenders}. "
            "Rename the method (on_<trigger> convention) — CrewAI emits the completed "
            "method's name as the next trigger and allows cyclic re-execution."
        )

    def test_retry_listeners_have_routers(self) -> None:
        """Retry-cap decisions must flow through @router — plain @listen returns are discarded."""
        tmap = _trigger_map()
        routed_sources: set[str] = set()
        for _name, (triggers, is_router) in tmap.items():
            if is_router:
                routed_sources.update(triggers)
        for listener in ("on_retry_development", "on_retry_planning"):
            assert listener in tmap, f"{listener} missing from flow"
            assert listener in routed_sources, (
                f"{listener} has no @router attached — its return value routes nowhere "
                "and the retry cap is dead code."
            )


class TestDevRetryCap:
    def _make_flow_with_state(self) -> AITeamFlow:
        """Flow instance with a stub state, skipping kickoff machinery.

        crewai's ``Flow.state`` is a property, so it's overridden on a
        throwaway subclass rather than the instance ``__dict__``.
        """
        import structlog

        class _State:
            def __init__(self) -> None:
                self.metadata: dict[str, Any] = {}
                self.project_id = "test-project"

        state = _State()
        cls = type("_FlowForTest", (AITeamFlow,), {"state": property(lambda self: state)})
        f = cls.__new__(cls)
        f.__dict__["logger"] = structlog.get_logger("test")
        return f

    def test_cap_escalates_after_max_retries(self) -> None:
        flow = self._make_flow_with_state()
        results = []
        for _ in range(AITeamFlow.MAX_DEV_RETRIES + 2):
            r = flow.on_retry_development()
            results.append(flow.route_after_retry_development(r))
        under_cap = results[: AITeamFlow.MAX_DEV_RETRIES]
        over_cap = results[AITeamFlow.MAX_DEV_RETRIES :]
        assert all(r == "run_development" for r in under_cap)
        assert all(
            r == "escalate_to_human" for r in over_cap
        ), f"retry cap did not escalate: {results}"

    def test_retry_planning_routes_to_run_planning(self) -> None:
        flow = self._make_flow_with_state()
        r = flow.on_retry_planning()
        assert flow.route_after_retry_planning(r) == "run_planning"
