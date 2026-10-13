import os
import urllib.request
import uuid

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

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


@pytest.fixture
def e2e_page(e2e_browser):
    context = e2e_browser.new_context(base_url=BASE_URL)
    page = context.new_page()
    yield page
    context.close()


def unique_title(prefix="Task"):
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def add_task(page, title):
    page.goto("/tasks")
    page.fill("#title", title)
    page.click("#add-task")


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