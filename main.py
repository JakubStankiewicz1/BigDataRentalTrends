#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

# --------- Configuration ---------
BASE_URL = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/113.0.0.0 Safari/537.36"
    )
}
DELAY = 2              # seconds between requests
MAX_LISTINGS = 5       # limit to scrape only 5 listings
OUTPUT_CSV = "olx_wynajem_5.csv"


# --------- Helper Functions ---------
def fetch_soup(url):
    """Fetches content and returns BeautifulSoup object."""
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "html.parser")


def get_listing_links(page_url):
    """Extracts up to MAX_LISTINGS unique OLX listing URLs from the page."""
    soup = fetch_soup(page_url)
    seen = set()
    links = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        if "/d/oferta/" in href:
            full = urljoin("https://www.olx.pl", href)
            parsed = urlparse(full)
            if "olx.pl" in parsed.netloc and full not in seen:
                seen.add(full)
                links.append(full)
                if len(links) >= MAX_LISTINGS:
                    break
    return links


def parse_listing(listing_url):
    """Fetches and parses all required fields from a single OLX listing."""
    soup = fetch_soup(listing_url)
    data = {}

    # 1) Title: from <title>, strip suffix ". OLX.pl"
    title_tag = soup.find('title')
    data['title'] = title_tag.text.strip().rsplit('.', 1)[0] if title_tag and title_tag.text else None

    # 2) Price: first <h3>
    price_el = soup.find('h3')
    data['price'] = price_el.get_text(strip=True) if price_el and price_el.text.strip() else None

    # 3) Location: p.css-7wnksb and optional span.css-1ufkhqf
    loc_main = soup.select_one('p.css-7wnksb')
    if loc_main:
        main = loc_main.contents[0].strip()
        sub = loc_main.select_one('span.css-1ufkhqf')
        data['location'] = f"{main}, {sub.text.strip()}" if sub else main
    else:
        data['location'] = None

    # 4) Description: data-cy or generic container
    desc_el = soup.find('div', {'data-cy': 'ad_description'}) or soup.select_one('div.css-g5mtbi')
    data['description'] = desc_el.get_text(separator=' ', strip=True) if desc_el else None

    # 5) Seller name
    seller_el = soup.select_one('h4[data-testid="user-profile-user-name"]')
    data['seller'] = seller_el.get_text(strip=True) if seller_el else None

    # 5b) Trader type
    trader_el = soup.select_one('p[data-testid="trader-title"]')
    data['trader_type'] = trader_el.get_text(strip=True) if trader_el else None

    # 6) Posted date
    date_el = soup.find('time')
    data['posted_date'] = date_el.get('datetime') if date_el and date_el.get('datetime') else None

    # 7) Phone number
    phone_a = soup.select_one('a[href^="tel:"]')
    if phone_a:
        data['phone'] = "".join(ch for ch in phone_a['href'].replace("tel:", "") if ch.isdigit() or ch == '+')
    else:
        data['phone'] = None

    # 8) Technical parameters (floor, furnished, building type, area, rooms…)
    params = {'floor': None, 'furnished': None, 'building_type': None, 'area': None, 'rooms': None}
    for p in soup.select('div[data-testid="ad-parameters-container"] p.css-1los5bp'):
        text = p.get_text(strip=True)
        if text.startswith("Poziom:"):
            params['floor'] = text.replace("Poziom:", "").strip()
        elif text.startswith("Umeblowane:"):
            params['furnished'] = text.replace("Umeblowane:", "").strip()
        elif text.startswith("Rodzaj zabudowy:"):
            params['building_type'] = text.replace("Rodzaj zabudowy:", "").strip()
        elif text.startswith("Powierzchnia:"):
            params['area'] = text.replace("Powierzchnia:", "").strip()
        elif text.startswith("Liczba pokoi:"):
            params['rooms'] = text.replace("Liczba pokoi:", "").strip()

    data.update(params)

    # 9) ID
    id_text = soup.find(string=lambda t: isinstance(t, str) and 'ID:' in t)
    if id_text:
        data['id'] = id_text.split('ID:')[-1].strip()
    else:
        data['id'] = listing_url.rstrip('/').split('-')[-1]

    # 10) URL & scrape timestamp
    data['url'] = listing_url
    data['scrape_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return data


# --------- Main Workflow ---------
def main():
    print("▶ Pobieranie linków z OLX (page 1)…")
    links = get_listing_links(BASE_URL)
    print(f"✔ Znaleziono {len(links)} ofert. Pobieram szczegóły…\n")

    records = []
    for idx, url in enumerate(links, 1):
        print(f"[{idx}/{len(links)}] {url}")
        try:
            rec = parse_listing(url)
            records.append(rec)
        except Exception as e:
            print(f"✖ Błąd przy {url}: {e}")
        time.sleep(DELAY)

    df = pd.DataFrame(records, columns=[
        'title', 'price', 'location', 'description',
        'seller', 'trader_type', 'posted_date', 'phone',
        'floor', 'furnished', 'building_type', 'area', 'rooms',
        'id', 'url', 'scrape_date'
    ])
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"\n✅ Zapisano dane do '{OUTPUT_CSV}'")


if __name__ == "__main__":
    main()
