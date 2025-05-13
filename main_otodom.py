#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

# --------- Configuration ---------
SEARCH_URL   = "https://www.otodom.pl/pl/oferty/wynajem/mieszkanie"
HEADERS      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/113.0.0.0 Safari/537.36"}
MAX_LISTINGS = 5
DELAY        = 2    # seconds between requests
OUTPUT_CSV   = "otodom_wynajem.csv"

# --------- Helpers ---------
def fetch_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def get_listing_links():
    """Zwraca unikalne linki do MAX_LISTINGS ofert z listingu."""
    soup = fetch_soup(SEARCH_URL)
    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/pl/oferta/" in href:
            full = urljoin("https://www.otodom.pl", href)
            if urlparse(full).netloc.endswith("otodom.pl") and full not in seen:
                seen.add(full)
                links.append(full)
                if len(links) >= MAX_LISTINGS:
                    break
    return links

def parse_listing(url):
    """Parsuje szczegóły pojedynczego ogłoszenia Otodom."""
    soup = fetch_soup(url)
    data = {}

    # Title
    h1 = soup.select_one("h1[data-cy='adPageAdTitle']")
    data["title"] = h1.get_text(strip=True) if h1 else None

    # Price
    price_el = soup.select_one("strong[data-cy='adPageHeaderPrice']")
    data["price"] = price_el.get_text(strip=True) if price_el else None

    # Rent Fee (Additional Price)
    fee_el = soup.select_one("div[data-sentry-element='AdditionalPriceWrapper']")
    data["rent_fee"] = fee_el.get_text(strip=True) if fee_el else None

    # Location
    loc_el = soup.select_one("div[data-sentry-element='Container'] a[data-sentry-element='StyledLink']")
    data["location"] = loc_el.get_text(strip=True) if loc_el else None

    # Number of Rooms
    rooms_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Liczba pokoi:') + p")
    data["rooms"] = rooms_el.get_text(strip=True) if rooms_el else None

    # Advertiser Type
    advertiser_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Typ ogłoszeniodawcy:') + p")
    data["advertiser_type"] = advertiser_el.get_text(strip=True) if advertiser_el else None

    # ID (unchanged)
    id_tag = soup.find(string=lambda t: isinstance(t, str) and "ID:" in t)
    data["id"] = id_tag.split("ID:")[-1].strip() if id_tag else url.rstrip("/").split("-")[-1]

    # URL & timestamp (unchanged)
    data["url"] = url
    data["scrape_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data

# --------- Main ---------
def main():
    print("▶ Pobieranie linków z Otodom...")
    links = get_listing_links()
    print(f"✔ Znaleziono {len(links)} ofert. Scrapuję szczegóły...\n")

    rows = []
    for idx, link in enumerate(links,1):
        print(f"[{idx}/{len(links)}] {link}")
        try:
            rows.append(parse_listing(link))
        except Exception as e:
            print(f"⚠ Błąd przy {link}: {e}")
        time.sleep(DELAY)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ Zapisano dane do '{OUTPUT_CSV}'")

if __name__=="__main__":
    main()
