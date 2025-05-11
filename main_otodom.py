#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

# --------- Configuration ---------
SEARCH_URL    = "https://www.otodom.pl/pl/oferty/wynajem/mieszkanie"
HEADERS       = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/113.0.0.0 Safari/537.36"}
MAX_LISTINGS  = 5
DELAY         = 2  # sekundy pomiędzy żądaniami
OUTPUT_CSV    = "otodom_wynajem.csv"

# --------- Helpers ---------
def fetch_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def get_listing_links():
    """Zwraca do MAX_LISTINGS unikatowych linków z listingu Otodom."""
    soup = fetch_soup(SEARCH_URL)
    seen = set()
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/pl/oferta/" in href:
            full = urljoin("https://www.otodom.pl", href)
            net = urlparse(full).netloc
            if "otodom.pl" in net and full not in seen:
                seen.add(full)
                links.append(full)
                if len(links) >= MAX_LISTINGS:
                    break
    return links

def parse_listing(url):
    """Parsuje szczegóły pojedynczego ogłoszenia Otodom."""
    soup = fetch_soup(url)
    data = {}

    # tytuł
    t = soup.select_one("h1")
    data["title"] = t.get_text(strip=True) if t else None

    # cena
    p = soup.find("strong")
    data["price"] = p.get_text(strip=True) if p else None

    # czynsz dodatkowy (jeśli jest tuż za ceną)
    fee = p.find_next_sibling(text=True) if p else ""
    data["rent_fee"] = fee.strip() if fee and "zł" in fee else None

    # lokalizacja
    loc = soup.select_one("span[data-cy*=location]")
    data["location"] = loc.get_text(strip=True) if loc else None

    # parametry: pokoje, powierzchnia, piętro, ogrzewanie
    params = {"rooms": None, "area": None, "floor": None, "heating": None}
    for li in soup.select("li"):
        txt = li.get_text(strip=True)
        if "pok" in txt:
            params["rooms"] = txt
        elif "m²" in txt:
            params["area"] = txt
        elif "piętro" in txt or "parter" in txt:
            params["floor"] = txt
        elif "ogrzew" in txt.lower():
            params["heating"] = txt
    data.update(params)

    # opis
    desc = soup.select_one("div[data-cy='adPageAdDescription']")
    data["description"] = desc.get_text(" ", strip=True) if desc else None

    # ID
    id_tag = soup.find(string=lambda t: isinstance(t, str) and "ID:" in t)
    data["id"] = id_tag.split("ID:")[-1].strip() if id_tag else url.rstrip("/").split("-")[-1]

    # meta
    data["url"]         = url
    data["scrape_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data

# --------- Main ---------
def main():
    print("▶ Pobieranie linków z Otodom...")
    links = get_listing_links()
    print(f"✔ Znaleziono {len(links)} ofert. Scrapuję szczegóły...\n")

    records = []
    for i, link in enumerate(links, 1):
        print(f"[{i}/{len(links)}] {link}")
        try:
            rec = parse_listing(link)
            records.append(rec)
        except Exception as e:
            print(f"⚠ Błąd przy {link}: {e}")
        time.sleep(DELAY)

    df = pd.DataFrame(records, columns=[
        "title", "price", "rent_fee", "location",
        "rooms", "area", "floor", "heating",
        "description", "id", "url", "scrape_date"
    ])
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ Zapisano dane do '{OUTPUT_CSV}'")

if __name__ == "__main__":
    main()
