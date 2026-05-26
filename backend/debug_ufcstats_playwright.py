from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = "http://ufcstats.com/statistics/events/completed?page=all"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        )
    )

    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)

    html = page.content()
    browser.close()

Path("debug_ufcstats_playwright.html").write_text(html, encoding="utf-8")

soup = BeautifulSoup(html, "html.parser")

title = soup.title.get_text(" ", strip=True) if soup.title else "NO TITLE"

print("title:", title)
print("length:", len(html))
print("event_links:", len(soup.select("a.b-link.b-link_style_black")))
print("table_rows:", len(soup.select("tr.b-statistics__table-row")))
print("text_sample:", soup.get_text(" ", strip=True)[:300])
print("saved: debug_ufcstats_playwright.html")