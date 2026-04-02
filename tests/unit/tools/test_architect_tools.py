"""Unit tests for ``architect_tools`` (CrewAI tools + ``get_architect_tools``)."""

from __future__ import annotations

from ai_team.tools.architect_tools import (
    architecture_designer,
    diagram_generator,
    get_architect_tools,
    interface_definer,
    technology_selector,
)


class TestArchitectureDesigner:
    def test_run_returns_guidance_string(self) -> None:
        out = architecture_designer.run(
            system_overview="Three-tier web app",
            components_description="API, worker, DB",
        )
        assert isinstance(out, str)
        assert "ArchitectureDocument" in out
        assert "system_overview" in out.lower() or "components" in out.lower()


class TestTechnologySelector:
    def test_run_returns_guidance_string(self) -> None:
        out = technology_selector.run(choices_description="Postgres for OLTP; Redis for cache")
        assert isinstance(out, str)
        assert "technology_stack" in out.lower()


class TestInterfaceDefiner:
    def test_run_returns_guidance_string(self) -> None:
        out = interface_definer.run(
            contracts_description="API exposes /users; worker consumes events",
        )
        assert isinstance(out, str)
        assert "interface_contracts" in out.lower()


class TestDiagramGenerator:
    def test_run_returns_guidance_string(self) -> None:
        out = diagram_generator.run(
            diagram_type="component",
            ascii_content="[Web] --> [API]",
        )
        assert isinstance(out, str)
        assert "ascii_diagram" in out.lower()


class TestGetArchitectTools:
    def test_returns_four_tools(self) -> None:
        tools = get_architect_tools()
        assert len(tools) == 4
        names = [t.name for t in tools]
        assert "Architecture designer" in names
        assert "Technology selector" in names
        assert "Interface definer" in names
        assert "Diagram generator" in names

    def test_each_tool_is_runnable(self) -> None:
        tools = get_architect_tools()
        for t in tools:
            assert callable(getattr(t, "run", None))
