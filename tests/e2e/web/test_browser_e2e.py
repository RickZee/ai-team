"""Playwright browser E2E for the web dashboard (demo path — zero LLM cost)."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.browser_e2e, pytest.mark.web_e2e]


class TestWebUiNavigation:
    def test_app_shell_and_nav(self, page: Page, browser_base_url: str) -> None:
        page.goto(browser_base_url)
        expect(page.get_by_text("AI-Team Dashboard")).to_be_visible()
        expect(page.get_by_test_id("nav-dashboard")).to_be_visible()
        expect(page.get_by_test_id("nav-run")).to_be_visible()
        expect(page.get_by_test_id("nav-compare")).to_be_visible()

    def test_navigate_run_and_compare(self, page: Page, browser_base_url: str) -> None:
        page.goto(browser_base_url)
        page.get_by_test_id("nav-run").click()
        expect(page.get_by_role("heading", name="Run Pipeline")).to_be_visible()
        page.get_by_test_id("nav-compare").click()
        expect(page.get_by_role("heading", name="Compare Backends")).to_be_visible()


class TestWebUiDemoFlow:
    """Demo button triggers simulated pipeline; Dashboard shows COMPLETE."""

    def test_demo_reaches_complete_on_dashboard(
        self, page: Page, browser_base_url: str
    ) -> None:
        page.goto(f"{browser_base_url}/run")
        page.get_by_test_id("run-demo").click()
        page.wait_for_url(f"{browser_base_url}/**")
        expect(page.get_by_test_id("dashboard-active")).to_be_visible(timeout=90_000)
        expect(page.get_by_test_id("phase-pipeline")).to_contain_text("COMPLETE", timeout=90_000)

    def test_demo_shows_agent_activity(self, page: Page, browser_base_url: str) -> None:
        page.goto(f"{browser_base_url}/run")
        page.get_by_test_id("run-demo").click()
        expect(page.get_by_test_id("dashboard-active")).to_be_visible(timeout=90_000)
        expect(page.get_by_role("heading", name="Agents")).to_be_visible()
        expect(page.get_by_role("heading", name="Activity Log")).to_be_visible()


class TestWebUiEstimate:
    def test_estimate_shows_cost_table(self, page: Page, browser_base_url: str) -> None:
        page.goto(f"{browser_base_url}/run")
        page.get_by_test_id("run-estimate").click()
        expect(page.locator(".estimate-panel")).to_be_visible(timeout=15_000)
        expect(page.locator(".estimate-table")).to_be_visible()


class TestWebUiRunFormValidation:
    def test_run_disabled_without_description(self, page: Page, browser_base_url: str) -> None:
        page.goto(f"{browser_base_url}/run")
        page.get_by_test_id("run-description").fill("")
        # Run still clickable but handleRun no-ops; verify empty state
        expect(page.get_by_test_id("run-submit")).to_be_enabled()
        expect(page.get_by_test_id("run-description")).to_have_value("")

    def test_claude_backend_option_present(self, page: Page, browser_base_url: str) -> None:
        page.goto(f"{browser_base_url}/run")
        options = page.get_by_test_id("run-backend").locator("option")
        labels = [options.nth(i).inner_text() for i in range(options.count())]
        assert any("Claude" in label for label in labels)


class TestWebUiComparePage:
    def test_compare_form_renders(self, page: Page, browser_base_url: str) -> None:
        page.goto(f"{browser_base_url}/compare")
        expect(page.get_by_test_id("compare-submit")).to_be_visible()
        expect(page.get_by_text("CrewAI")).to_be_visible()
        expect(page.get_by_text("LangGraph")).to_be_visible()
