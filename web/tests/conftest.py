"""Shared fixtures for CrateDigger web UI tests (pytest-playwright)."""

import os

import pytest
from playwright.sync_api import Page

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:3001")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8899")

# Directory for failure screenshots
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Override default browser context — bigger viewport, no animations."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 900},
        "ignore_https_errors": True,
    }


@pytest.fixture
def app(page: Page):
    """Navigate to the frontend root and wait for it to be ready."""
    page.goto(FRONTEND_URL, wait_until="networkidle", timeout=15_000)
    # Wait for the app layout to render (sidebar or mobile tabs)
    page.wait_for_selector(".app-layout", timeout=10_000)
    return page


@pytest.fixture(autouse=True)
def screenshot_on_failure(request, page: Page):
    """Capture a screenshot when a test fails."""
    yield
    if request.node.rep_call and request.node.rep_call.failed:
        name = request.node.name.replace("[", "_").replace("]", "_")
        path = os.path.join(SCREENSHOT_DIR, f"FAIL_{name}.png")
        page.screenshot(path=path, full_page=True)
        print(f"\n  Screenshot saved: {path}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach call report to the request node so the screenshot fixture can read it."""
    import pluggy

    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
