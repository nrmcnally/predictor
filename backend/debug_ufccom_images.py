from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = "https://www.ufc.com/athletes/all"

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
    page.wait_for_timeout(8000)

    html = page.content()
    browser.close()

Path("debug_ufccom_athletes.html").write_text(html, encoding="utf-8")

soup = BeautifulSoup(html, "html.parser")

print("title:", soup.title.get_text(" ", strip=True) if soup.title else "NO TITLE")
print("length:", len(html))
print("links:", len(soup.find_all("a", href=True)))
print("images:", len(soup.find_all("img")))

print()
print("First 20 images:")
for img in soup.find_all("img")[:20]:
    print("src:", img.get("src"))
    print("alt:", img.get("alt"))
    print()

print("saved: debug_ufccom_athletes.html")