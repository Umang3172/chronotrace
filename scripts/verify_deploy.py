#!/usr/bin/env python3
"""Verify the deployed dashboard against its live Amplify URL, not localhost.

A deploy job reporting SUCCEED only proves bytes were copied. This script is the
evidence that the site a judge will click actually works: it loads the live
origin, asserts the incident data arrived and rendered as rows, fails on any
console error or uncaught exception, and captures the two screenshots referenced
by the README.

The empty state ("No incidents yet") and the Next.js error boundary both return
HTTP 200, so status alone cannot distinguish a working dashboard from a broken
one. The row assertion is what separates them.

Usage:
    uv run python scripts/verify_deploy.py [URL]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import sync_playwright

if TYPE_CHECKING:
    from playwright.sync_api import ConsoleMessage, Page

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "assets" / "deploy"

DEFAULT_URL = "https://main.d3k7wvrz5f9b6h.amplifyapp.com"

VIEWPORT = {"width": 1440, "height": 900}

# The dashboard renders this heading when incidents.json is missing or empty. It
# returns 200 like any other page, so it has to be asserted against by name.
EMPTY_STATE = "No incidents yet"

# incidents.json ships 15 incidents. Asserting a floor rather than equality keeps
# the check meaningful if the corpus grows, while still failing on a partial load.
MIN_INCIDENTS = 10


class VerificationError(Exception):
    """Raised when the live site fails one of the deployment assertions."""


def _check(condition: bool, message: str) -> None:
    """Record an assertion, raising with `message` when it does not hold."""
    if condition:
        print(f"  PASS  {message}")
    else:
        raise VerificationError(message)


def verify(url: str) -> None:
    """Load `url`, assert the dashboard really rendered, and write screenshots."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        def on_console(message: ConsoleMessage) -> None:
            if message.type == "error":
                console_errors.append(message.text)

        page.on("console", on_console)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        print(f"\nlist view — {url}/")
        response = page.goto(f"{url}/", wait_until="networkidle")
        _check(response is not None and response.status == 200, "HTTP 200")
        _check(page.title().strip() != "", f"document title renders ({page.title()!r})")

        body = page.inner_text("body")
        _check(EMPTY_STATE not in body, "not the empty state")

        rows = page.locator("main a[href*='/incident/']")
        count = rows.count()
        _check(count >= MIN_INCIDENTS, f"{count} incident rows rendered (>= {MIN_INCIDENTS})")

        first_row_text = rows.first.inner_text()
        _check("::" in first_row_text or "test_" in first_row_text,
               "first row names a real test")

        list_shot = OUT_DIR / "amplify-live.png"
        _settle(page)
        page.screenshot(path=list_shot)
        print(f"  SHOT  {list_shot.relative_to(REPO_ROOT)}")

        print("\ndetail view — first incident")
        rows.first.click()
        page.wait_for_load_state("networkidle")
        _check("/incident/" in page.url, f"navigated to {page.url}")

        detail = page.inner_text("body")
        _check(len(detail) > 500, f"detail view rendered {len(detail)} chars of content")
        _check(EMPTY_STATE not in detail, "detail view is not the empty state")

        detail_shot = OUT_DIR / "amplify-incident.png"
        _settle(page)
        page.screenshot(path=detail_shot, full_page=True)
        print(f"  SHOT  {detail_shot.relative_to(REPO_ROOT)}")

        context.close()
        browser.close()

    print("\nconsole")
    _check(not console_errors, f"no console errors (found {len(console_errors)})")
    _check(not page_errors, f"no uncaught exceptions (found {len(page_errors)})")
    for line in console_errors + page_errors:
        print(f"        {line}")


def _settle(page: Page) -> None:
    """Wait out the entrance animations before capturing.

    The dashboard staggers section reveals with framer-motion, which `networkidle`
    knows nothing about — screenshotting on load alone catches half-faded panels.
    This also gives late console errors a window in which to surface.
    """
    page.wait_for_timeout(2500)


def main() -> int:
    """Run the verification, returning a process exit code."""
    url = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL).rstrip("/")
    try:
        verify(url)
    except VerificationError as exc:
        print(f"\nFAIL: {exc}", file=sys.stderr)
        return 1
    print("\nall assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
