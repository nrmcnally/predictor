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


class UfcStatsSession:
    """
    Fast bulk fetcher for UFCStats.

    UFCStats serves a JS browser-check that takes ~10s to resolve in headless
    Chromium, on *every* page — reusing the browser does not bypass it, so a pure
    Playwright loop is ~10s/page. But once the check is solved in a browser, the
    resulting cookies let plain `requests` fetch the real page in ~0.5s.

    So this session solves the check ONCE with Playwright, copies the cookies into
    a requests.Session, and serves everything else over requests (~20x faster). If
    a later request comes back as the check page (cookies went stale), it
    transparently re-warms with the browser and retries.

    Use as a context manager:

        with UfcStatsSession() as session:
            for url in urls:
                html = session.fetch(url)
    """

    def __init__(
        self,
        headless: bool | None = None,
        ready_token: str = "b-fight-details__table",
        selector_timeout_ms: int = 15000,
        settle_ms: int = 3000,
        request_timeout: int = 30,
    ) -> None:
        if headless is None:
            headless = env_bool("UFCSTATS_PLAYWRIGHT_HEADLESS", True)

        self.headless = headless
        self.ready_token = ready_token
        self.content_selector = f".{ready_token}"
        self.selector_timeout_ms = selector_timeout_ms
        self.settle_ms = settle_ms
        self.request_timeout = request_timeout

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._requests: requests.Session | None = None

    def __enter__(self) -> "UfcStatsSession":
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            user_agent=REQUEST_HEADERS["User-Agent"],
            locale="en-US",
            viewport={"width": 1366, "height": 768},
        )
        self._page = self._context.new_page()
        return self

    def _looks_ready(self, html: str) -> bool:
        return bool(html) and self.ready_token in html and not is_browser_check_html(html)

    def _warm_up(self, url: str, timeout_ms: int = 60000) -> str:
        """Solve the browser-check on `url` and refresh the requests cookies."""
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                self._page.wait_for_selector(self.content_selector, timeout=self.selector_timeout_ms)
            except Exception:
                self._page.wait_for_timeout(self.settle_ms)
        except Exception:
            self._page.wait_for_timeout(self.settle_ms)

        html = self._page.content()

        session = requests.Session()
        session.headers.update(REQUEST_HEADERS)
        for cookie in self._context.cookies():
            try:
                session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain"),
                    path=cookie.get("path", "/"),
                )
            except Exception:
                pass
        self._requests = session

        return html

    def fetch(self, url: str) -> str:
        # First call: warm up with the browser and return that page directly.
        if self._requests is None:
            return self._warm_up(url)

        try:
            html = self._requests.get(url, timeout=self.request_timeout).text
        except Exception:
            html = ""

        if self._looks_ready(html):
            return html

        # Cookies went stale / got blocked: re-solve with the browser and retry once.
        return self._warm_up(url)

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass

        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer is not None:
                    closer.close()
            except Exception:
                pass

        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass


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