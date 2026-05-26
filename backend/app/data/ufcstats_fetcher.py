from __future__ import annotations

import atexit
import os
import time
from typing import Any

import requests


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_playwright_manager: Any | None = None
_browser: Any | None = None
_context: Any | None = None


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def is_browser_check_html(html: str) -> bool:
    text = html.lower()

    return (
        "checking your browser" in text
        or "this site requires javascript" in text
        or "<title>loading" in text
    )


def fetch_html_with_requests(url: str, timeout: int = 30) -> str:
    response = requests.get(
        url,
        headers=REQUEST_HEADERS,
        timeout=timeout,
        allow_redirects=True,
    )

    response.raise_for_status()

    return response.text


def _get_playwright_context() -> Any:
    global _playwright_manager, _browser, _context

    if _context is not None:
        return _context

    from playwright.sync_api import sync_playwright

    headless = _env_flag("UFCSTATS_PLAYWRIGHT_HEADLESS", default=True)

    _playwright_manager = sync_playwright().start()
    _browser = _playwright_manager.chromium.launch(headless=headless)
    _context = _browser.new_context(
        user_agent=REQUEST_HEADERS["User-Agent"],
        locale="en-US",
        viewport={"width": 1365, "height": 900},
    )

    return _context


def close_playwright_context() -> None:
    global _playwright_manager, _browser, _context

    if _context is not None:
        try:
            _context.close()
        except Exception:
            pass
        _context = None

    if _browser is not None:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None

    if _playwright_manager is not None:
        try:
            _playwright_manager.stop()
        except Exception:
            pass
        _playwright_manager = None


atexit.register(close_playwright_context)


def fetch_html_with_playwright(
    url: str,
    timeout_ms: int = 60000,
    wait_ms: int | None = None,
) -> str:
    context = _get_playwright_context()
    page = context.new_page()

    if wait_ms is None:
        wait_ms = int(os.environ.get("UFCSTATS_PLAYWRIGHT_WAIT_MS", "8000"))

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )

        page.wait_for_timeout(wait_ms)

        html = page.content()

        return html

    finally:
        page.close()


def fetch_ufcstats_html(
    url: str,
    timeout: int = 30,
    use_playwright_fallback: bool = True,
) -> str:
    """
    Fetches UFCStats HTML.

    It tries requests first because requests is much faster. If UFCStats returns
    the JavaScript/browser-check page, it retries with Playwright so the browser
    can execute the check and return the real page HTML.
    """
    force_playwright = _env_flag("UFCSTATS_FORCE_PLAYWRIGHT", default=False)

    if not force_playwright:
        try:
            html = fetch_html_with_requests(url=url, timeout=timeout)

            if not use_playwright_fallback or not is_browser_check_html(html):
                return html

            print(
                "Requests received UFCStats browser-check page. "
                f"Retrying with Playwright: {url}"
            )

        except Exception as error:
            if not use_playwright_fallback:
                raise

            print(f"Requests failed for UFCStats page. Retrying with Playwright: {url}")
            print(f"    requests error: {error}")

    html = fetch_html_with_playwright(url=url)

    if is_browser_check_html(html):
        raise RuntimeError(
            "UFCStats still returned the browser-check page after Playwright fallback. "
            "Try running with UFCSTATS_PLAYWRIGHT_HEADLESS=false."
        )

    # Give UFCStats a tiny breather between browser-backed requests.
    time.sleep(float(os.environ.get("UFCSTATS_PLAYWRIGHT_DELAY_SECONDS", "0.05")))

    return html
