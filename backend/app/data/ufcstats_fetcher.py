from __future__ import annotations

import os

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


def env_bool(name: str, default: bool = False) -> bool:
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


def fetch_html_with_playwright(
    url: str,
    timeout_ms: int = 60000,
    wait_ms: int = 8000,
    headless: bool | None = None,
) -> str:
    if headless is None:
        headless = env_bool("UFCSTATS_PLAYWRIGHT_HEADLESS", True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)

        try:
            context = browser.new_context(
                user_agent=REQUEST_HEADERS["User-Agent"],
                locale="en-US",
                viewport={"width": 1366, "height": 768},
            )

            page = context.new_page()

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )

            page.wait_for_timeout(wait_ms)

            html = page.content()

            context.close()

            return html

        finally:
            browser.close()


def fetch_ufcstats_html(
    url: str,
    timeout: int = 30,
    use_playwright_fallback: bool = True,
    playwright_headless: bool | None = None,
) -> str:
    force_playwright = env_bool("UFCSTATS_FORCE_PLAYWRIGHT", False)

    if not use_playwright_fallback:
        return fetch_html_with_requests(url=url, timeout=timeout)

    if not force_playwright:
        html = fetch_html_with_requests(url=url, timeout=timeout)

        if not is_browser_check_html(html):
            return html

        print(f"Requests received UFCStats browser-check page. Retrying with Playwright: {url}")

    html = fetch_html_with_playwright(
        url=url,
        headless=playwright_headless,
    )

    if is_browser_check_html(html):
        raise RuntimeError(
            "UFCStats still returned the browser-check page after Playwright fallback."
        )

    return html