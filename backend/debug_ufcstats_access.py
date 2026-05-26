import requests
from bs4 import BeautifulSoup

URLS = [
    "http://ufcstats.com/statistics/events/completed?page=all",
    "https://ufcstats.com/statistics/events/completed?page=all",
    "http://www.ufcstats.com/statistics/events/completed?page=all",
    "https://www.ufcstats.com/statistics/events/completed?page=all",
    "http://ufcstats.com/statistics/events/upcoming",
    "https://www.ufcstats.com/statistics/events/upcoming",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

for url in URLS:
    print()
    print("=" * 80)
    print("URL:", url)

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True,
        )

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else "NO TITLE"
        text_sample = soup.get_text(" ", strip=True)[:300]

        print("status:", response.status_code)
        print("final_url:", response.url)
        print("length:", len(response.text))
        print("title:", title)
        print("event_links:", len(soup.select("a.b-link.b-link_style_black")))
        print("table_rows:", len(soup.select("tr.b-statistics__table-row")))
        print("text_sample:", text_sample)

    except Exception as error:
        print("ERROR:", repr(error))