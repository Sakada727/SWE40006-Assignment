import os
import urllib.request
import uuid

import pytest

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:
    if os.environ.get("CI"):
        # In the pipeline a skipped browser suite would look like a pass
        raise
    pytest.skip("Playwright is not installed.", allow_module_level=True)

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="module", autouse=True)
def server_is_running():
    try:
        urllib.request.urlopen(f"{BASE_URL}/health", timeout=3)
    except Exception:
        pytest.fail(f"The app is not reachable at {BASE_URL}. Start it first.")


@pytest.fixture(scope="module")
def e2e_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


def register_and_login(page):
    """Create a brand-new account (unique name, because the database keeps data between runs)."""
    page.goto("/register")
    page.fill("#username", "user" + uuid.uuid4().hex[:8])
    page.fill("#password", "password123")
    page.click("#register-button")
    page.wait_for_selector("#logout-button")       # only shown once we are logged in


@pytest.fixture
def e2e_page(e2e_browser):
    """A browser page that is already logged in as a fresh user."""
    context = e2e_browser.new_context(base_url=BASE_URL)
    page = context.new_page()
    register_and_login(page)
    yield page
    context.close()


def unique_title(prefix="Task"):
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def add_task(page, title):
    page.goto("/tasks")
    page.fill("#title", title)
    page.click("#add-task")


# ---- task tracker ----

def test_add_task_appears_in_list(e2e_page):
    title = unique_title("Write report")
    add_task(e2e_page, title)
    assert title in e2e_page.inner_text("#task-list")


def test_mark_task_complete(e2e_page):
    title = unique_title("Deploy")
    add_task(e2e_page, title)
    item = e2e_page.locator("#task-list li", has_text=title)
    item.locator(".complete-btn").click()
    assert "Completed" in e2e_page.locator(
        "#task-list li", has_text=title
    ).inner_text()


def test_blank_title_shows_error(e2e_page):
    add_task(e2e_page, "   ")
    assert "must not be blank" in e2e_page.inner_text("#error")


# ---- login ----

def test_tasks_page_requires_login(e2e_browser):
    context = e2e_browser.new_context(base_url=BASE_URL)     # a visitor who is not logged in
    page = context.new_page()
    page.goto("/tasks")
    assert "/login" in page.url
    context.close()


# ---- URL shortener ----

def test_user_can_shorten_a_link_and_follow_it(e2e_page):
    e2e_page.goto("/links")
    e2e_page.fill("#url", BASE_URL + "/health")            # the app's own health page, so no outside website is needed
    e2e_page.click("#add-link")

    short_url = e2e_page.locator(".short-url").first.inner_text()
    e2e_page.goto(short_url)                                # follow the short link
    expect(e2e_page.locator("body")).to_contain_text("ok")  # it landed on /health

    e2e_page.goto("/links")


def test_home_page_shows_the_deployed_version(e2e_browser):
    context = e2e_browser.new_context(base_url=BASE_URL)
    page = context.new_page()
    page.goto("/")
    expect(page.locator("#go-login")).to_be_visible()
    expected = os.environ.get("E2E_EXPECTED_VERSION")    # set by the pipeline to the commit SHA
    if expected:
        expect(page.locator("#app-version")).to_have_text(expected[:7])
    context.close()


def test_dangerous_link_is_rejected(e2e_page):
    e2e_page.goto("/links")
    e2e_page.fill("#url", "javascript:alert(1)")
    e2e_page.click("#add-link")
    expect(e2e_page.locator("#error")).to_contain_text("must start with http")