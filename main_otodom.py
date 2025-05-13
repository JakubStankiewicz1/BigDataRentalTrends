import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re 

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
    if fee_el:
        fee_text = fee_el.get_text(strip=True)
        match = re.search(r'\d+', fee_text)  # Extract only the numeric value
        data["rent_fee"] = int(match.group()) if match else None
    else:
        data["rent_fee"] = None

    # Location
    loc_el = soup.select_one("div[data-sentry-element='Container'] a[data-sentry-element='StyledLink']")
    data["location"] = loc_el.get_text(strip=True) if loc_el else None

    # Number of Rooms
    rooms_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Liczba pokoi:') + p")
    data["rooms"] = rooms_el.get_text(strip=True) if rooms_el else None

    # Advertiser Type
    advertiser_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Typ ogłoszeniodawcy:') + p")
    data["advertiser_type"] = advertiser_el.get_text(strip=True) if advertiser_el else None

    # Heating
    heating_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Ogrzewanie:') + p")
    data["heating"] = heating_el.get_text(strip=True) if heating_el else None

    # Floor
    floor_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Piętro:') + p")
    data["floor"] = floor_el.get_text(strip=True) if floor_el else None

    # Finishing State
    finishing_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Stan wykończenia:') + p")
    data["finishing_state"] = finishing_el.get_text(strip=True) if finishing_el else None

    # Availability Date
    availability_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Dostępne od:') + p")
    data["available_from"] = availability_el.get_text(strip=True) if availability_el else None

    # Additional Information (lepsze rozdzielanie)
    additional_info_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Informacje dodatkowe:') + p")
    if additional_info_el:
        spans = additional_info_el.find_all("span")
        if spans:
            data["additional_info"] = ", ".join(span.get_text(strip=True) for span in spans)
        else:
            text = additional_info_el.get_text(strip=True)
            items = re.split(r'[;,•·\u2022\u2023\u25E6\u2043\u2219]', text)
            data["additional_info"] = ", ".join(item.strip() for item in items if item.strip())
    else:
        data["additional_info"] = None

    # Building Year
    building_year_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Rok budowy:') + p")
    data["building_year"] = building_year_el.get_text(strip=True) if building_year_el else None

    # Elevator
    elevator_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Winda:') + p")
    data["elevator"] = elevator_el.get_text(strip=True) if elevator_el else None

    # Building Type
    building_type_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Rodzaj zabudowy:') + p")
    data["building_type"] = building_type_el.get_text(strip=True) if building_type_el else None

    # Building Material
    building_material_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Materiał budynku:') + p")
    data["building_material"] = building_material_el.get_text(strip=True) if building_material_el else None

    # Windows
    windows_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Okna:') + p")
    data["windows"] = windows_el.get_text(strip=True) if windows_el else None

    # Safety
    safety_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Bezpieczeństwo:') + p")
    data["safety"] = safety_el.get_text(strip=True) if safety_el else None

    # Equipment
    equipment_el = soup.select("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Wyposażenie:') + p span")
    data["equipment"] = ", ".join(equip.get_text(strip=True) for equip in equipment_el) if equipment_el else None

    # Security
    security_el = soup.select("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Zabezpieczenia:') + p span")
    data["security"] = ", ".join(sec.get_text(strip=True) for sec in security_el) if security_el else None

    # Media
    media_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Media:') + p")
    data["media"] = media_el.get_text(strip=True) if media_el else None

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
            row = parse_listing(link)
            # Uzupełnij brakujące dane domyślną wartością
            for k, v in row.items():
                if v is None or (isinstance(v, str) and not v.strip()):
                    row[k] = "brak informacji"
            rows.append(row)
        except Exception as e:
            print(f"⚠ Błąd przy {link}: {e}")
        time.sleep(DELAY)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ Zapisano dane do '{OUTPUT_CSV}'")

if __name__=="__main__":
    main()
