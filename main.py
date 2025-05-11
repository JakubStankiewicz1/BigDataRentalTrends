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
        # only internal OLX offers
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

    # 1) Title
    title_el = soup.find('h1')
    if title_el and title_el.text.strip():
        data['title'] = title_el.text.strip()
    else:
        og = soup.select_one('meta[property="og:title"]')
        data['title'] = og['content'].strip() if og and og.get('content') else None

    # 2) Price
    price_el = soup.find('h3')
    if price_el and price_el.text.strip():
        data['price'] = price_el.text.strip()
    else:
        pm = soup.select_one('meta[property="product:price:amount"]')
        if pm and pm.get('content'):
            currency = pm.get('data-currency', '').strip()
            data['price'] = pm['content'].strip() + (f" {currency}" if currency else "")
        else:
            data['price'] = None

    # 3) Location
    # OLX często używa a[data-testid="location-date"] lub p.css-p6wsjo-Text
    loc_el = soup.select_one('p[data-testid="location-date"]') \
             or soup.select_one('p.css-p6wsjo-Text')
    if loc_el:
        data['location'] = loc_el.get_text(strip=True)
    else:
        # fallback: og:site_name might contain region
        meta_loc = soup.select_one('meta[property="og:site_name"]')
        data['location'] = meta_loc['content'].strip() if meta_loc and meta_loc.get('content') else None

    # 4) Description
    desc_el = soup.find('div', {'data-cy': 'ad_description'}) \
              or soup.select_one('div.css-g5mtbi')
    data['description'] = desc_el.get_text(separator=' ', strip=True) if desc_el else None

    # 5) Seller
    seller_el = soup.find('div', class_='css-1rei56m') \
                or soup.select_one('div.css-1l83m9g') \
                or soup.select_one('div[data-testid="user-info"] span')
    data['seller'] = seller_el.get_text(strip=True) if seller_el else None

    # 6) Posted date
    date_el = soup.find('time')
    data['posted_date'] = date_el.get('datetime') if date_el and date_el.get('datetime') else None

    # 7) ID
    id_text = soup.find(string=lambda t: isinstance(t, str) and 'ID:' in t)
    if id_text:
        data['id'] = id_text.split('ID:')[-1].strip()
    else:
        # fallback from URL
        data['id'] = listing_url.rstrip('/').split('-')[-1]

    # 8) URL & scrape timestamp
    data['url'] = listing_url
    data['scrape_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return data

# --------- Main Workflow ---------
def main():
    print("▶ Pobieranie linków z OLX (page 1)...")
    links = get_listing_links(BASE_URL)
    print(f"✔ Znaleziono {len(links)} ofert. Pobieram szczegóły...\n")

    records = []
    for idx, url in enumerate(links, 1):
        print(f"[{idx}/{len(links)}] {url}")
        try:
            rec = parse_listing(url)
            records.append(rec)
        except Exception as e:
            print(f"✖ Błąd przy {url}: {e}")
        time.sleep(DELAY)

    # Save to CSV with specified columns
    df = pd.DataFrame(records, columns=[
        'title', 'price', 'location', 'description',
        'seller', 'posted_date', 'id', 'url', 'scrape_date'
    ])
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"\n✅ Zapisano dane do '{OUTPUT_CSV}'")

if __name__ == "__main__":
    main()
