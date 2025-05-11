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
    price_wr = soup.select_one("div[data-sentry-element='MainPricewrapper']")
    data["price"] = price_wr.get_text(strip=True) if price_wr else None
    fee_wr = soup.select_one("div[data-sentry-element='AdditionalPriceWrapper']")
    data["rent_fee"] = fee_wr.get_text(strip=True) if fee_wr else None

    # Location
    loc = soup.select_one("div[data-sentry-element='MapLink'] + div p")
    data["location"] = loc.get_text(strip=True) if loc else None

    # Detail items (grid)
    params = {
        "rooms": None, "area": None, "floor": None, "heating": None,
        "condition": None, "available_from": None, "deposit": None,
        "advertiser_type": None
    }
    for item in soup.select("div.css-1xw0jqp.esen0m91"):
        lbl = item.select_one("p.css-1airkmu")
        val = item.select("p.css-1airkmu")
        if not lbl or len(val)<2: continue
        key, value = lbl.get_text(strip=True).lower(), val[1].get_text(strip=True)
        if "liczba pokoi" in key:       params["rooms"] = value
        elif "powierzchnia" in key:     params["area"] = value
        elif "piętro" in key:           params["floor"] = value
        elif "ogrzewanie" in key:       params["heating"] = value
        elif "stan wykończenia" in key: params["condition"] = value
        elif "dostępne od" in key:      params["available_from"] = value
        elif "czynsz" in key:           params["rent_fee"] = value  # override if needed
        elif "kaucja" in key:           params["deposit"] = value
        elif "typ ogłoszeniodawcy" in key: params["advertiser_type"] = value

    data.update(params)

    # Extras (garaż/piwnica etc)
    extras_el = soup.select_one("div.css-1xw0jqp.esen0m91 p span.css-axw7ok")
    if extras_el:
        data["extras"] = ", ".join(sp.get_text(strip=True) for sp in 
                                   soup.select("div.css-1xw0jqp.esen0m91 p span.css-axw7ok"))
    else:
        data["extras"] = None

    # Building & Materials / Elevator / Security
    extras2 = {"building_type": None, "elevator": None, "security": None}
    # these appear under the accordion first section
    for block in soup.select("button.css-12wre93 + div.css-t6wh4q div.css-1xw0jqp"):
        lbl = block.select_one("p.css-1airkmu")
        val = block.select_one("p.css-1airkmu + p")
        if not lbl or not val: continue
        key, value = lbl.get_text(strip=True).lower(), val.get_text(strip=True)
        if "rodzaj zabudowy" in key:    extras2["building_type"] = value
        elif "winda" in key:            extras2["elevator"] = value
        elif "bezpieczeństwo" in key:   extras2["security"] = value

    data.update(extras2)

    # Equipment & Media (second accordion)
    equip = soup.select("div.css-1svn882 p.css-1airkmu span.css-axw7ok")
    if equip:
        # group media vs equipment by header context
        # for simplicity lump all into one comma list
        data["equipment_media"] = ", ".join(sp.get_text(strip=True) for sp in equip)
    else:
        data["equipment_media"] = None

    # Description (full accordion)
    desc = soup.select_one("div[data-cy='adPageAdDescription']")
    data["description"] = desc.get_text(" ", strip=True) if desc else None

    # ID
    id_tag = soup.find(string=lambda t: isinstance(t,str) and "ID:" in t)
    data["id"] = id_tag.split("ID:")[-1].strip() if id_tag else url.rstrip("/").split("-")[-1]

    # URL & timestamp
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
