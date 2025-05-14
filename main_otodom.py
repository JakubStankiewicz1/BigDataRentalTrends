import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re 
import os  # Added for file existence check
import sys

# --------- Configuration ---------
SEARCH_URL   = "https://www.otodom.pl/pl/oferty/wynajem/mieszkanie"
HEADERS      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/113.0.0.0 Safari/537.36"}
DELAY        = 0    # seconds between requests
OUTPUT_CSV   = "otodom_wynajem.csv"

# Zapytaj użytkownika o limit ogłoszeń
limit_input = input("Ile ogłoszeń pobrać? (wpisz liczbę lub Enter dla wszystkich): ").strip()
if limit_input == '' or limit_input.lower() == 'wszystkie':
    MAX_LISTINGS = None
else:
    try:
        MAX_LISTINGS = int(limit_input)
        if MAX_LISTINGS <= 0:
            MAX_LISTINGS = None
    except ValueError:
        MAX_LISTINGS = None

# Check if the output file already exists
if os.path.exists(OUTPUT_CSV):
    new_name = input(f"Plik '{OUTPUT_CSV}' już istnieje. Podaj nową nazwę pliku (lub naciśnij Enter, aby nadpisać): ").strip()
    if new_name:
        OUTPUT_CSV = new_name

# --------- Helpers ---------
def fetch_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def parse_location(location_str):
    """Parse location string into components: województwo, powiat, miasto, dzielnica, ulica"""
    if not location_str:
        return {
            'wojewodztwo': None,
            'powiat': None,
            'miasto': None,
            'dzielnica': None,
            'ulica': None
        }
    parts = [part.strip() for part in location_str.split(',')]
    n = len(parts)
    result = {
        'wojewodztwo': None,
        'powiat': None,
        'miasto': None,
        'dzielnica': None,
        'ulica': None
    }
    if n == 0:
        return result
    # Województwo
    result['wojewodztwo'] = parts[-1]
    # Powiat (jeśli drugi od końca jest z małej litery)
    powiat_idx = None
    if n > 1 and parts[-2].islower():
        result['powiat'] = parts[-2]
        powiat_idx = n - 2
    # Miasto
    if powiat_idx is not None and n > 2:
        result['miasto'] = parts[-3]
        miasto_idx = n - 3
    elif n > 1:
        result['miasto'] = parts[-2]
        miasto_idx = n - 2
    else:
        miasto_idx = None
    # Ulica
    ulica_idx = None
    for i, part in enumerate(parts):
        if part.startswith('ul.'):
            result['ulica'] = part
            ulica_idx = i
            break
    # Dzielnica
    if result['ulica']:
        # Jeśli ulica jest pierwszym elementem, dzielnica = brak informacji
        if ulica_idx == 0:
            result['dzielnica'] = None
        # Jeśli jest coś przed ulicą i nie jest to miasto ani powiat, to to jest dzielnica
        elif ulica_idx > 0:
            # Sprawdzamy, czy element przed ulicą nie jest miastem ani powiatem
            dzielnica_candidate = parts[ulica_idx - 1]
            if (miasto_idx is not None and ulica_idx - 1 == miasto_idx) or (powiat_idx is not None and ulica_idx - 1 == powiat_idx):
                result['dzielnica'] = None
            elif not dzielnica_candidate.startswith('ul.'):
                result['dzielnica'] = dzielnica_candidate
            else:
                result['dzielnica'] = None
    elif miasto_idx is not None and miasto_idx > 0:
        # Jeśli nie ma ulicy, a są co najmniej 3 elementy, dzielnica to element przed miastem, jeśli nie jest ulicą
        dzielnica_candidate = parts[miasto_idx - 1]
        if not dzielnica_candidate.startswith('ul.'):
            result['dzielnica'] = dzielnica_candidate
        else:
            result['dzielnica'] = None
    # Jeśli nie znaleziono dzielnicy, zostaje None
    return result

def get_listing_links(max_listings=None):
    """Zwraca unikalne linki do wszystkich ofert z listingu (wszystkie strony lub do limitu)."""
    seen, links = set(), []
    page = 1
    while True:
        url = SEARCH_URL if page == 1 else f"{SEARCH_URL}?page={page}"
        soup = fetch_soup(url)
        found_on_page = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/pl/oferta/" in href:
                full = urljoin("https://www.otodom.pl", href)
                if urlparse(full).netloc.endswith("otodom.pl") and full not in seen:
                    seen.add(full)
                    links.append(full)
                    found_on_page += 1
                    if max_listings is not None and len(links) >= max_listings:
                        print(f"Zebrano {len(links)} ogłoszeń (limit osiągnięty)")
                        return links
        if found_on_page == 0:
            break  # Brak nowych ogłoszeń na stronie, kończymy
        print(f"Zebrano {len(links)} ogłoszeń (strona {page})")
        page += 1
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

    # Kaucja (Deposit)
    deposit_el = soup.select_one("div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Kaucja:') + p")
    data["deposit"] = deposit_el.get_text(strip=True) if deposit_el else None

    # Location
    loc_el = soup.select_one("div[data-sentry-element='Container'] a[data-sentry-element='StyledLink']")
    location_str = loc_el.get_text(strip=True) if loc_el else None
    
    # Parse location components
    location_components = parse_location(location_str)
    data.update(location_components)
    data["location"] = location_str  # Keep the original location string

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

def print_progress_bar(iteration, total, start_time, length=30):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    elapsed = time.time() - start_time
    avg_time = elapsed / iteration if iteration > 0 else 0
    remaining = int(avg_time * (total - iteration))
    mins, secs = divmod(remaining, 60)
    eta = f"ETA: {mins:02d}:{secs:02d}"
    sys.stdout.write(f'\rPostęp: |{bar}| {iteration}/{total} ({percent}%) {eta}')
    sys.stdout.flush()
    if iteration == total:
        print()  # Nowa linia na końcu

# --------- Main ---------
def main():
    print("▶ Pobieranie linków z Otodom...")
    links = get_listing_links(MAX_LISTINGS)
    print(f"✔ Znaleziono {len(links)} ofert. Scrapuję szczegóły...\n")

    rows = []
    total = len(links)
    start_time = time.time()
    for idx, link in enumerate(links, 1):
        print_progress_bar(idx, total, start_time)
        try:
            row = parse_listing(link)
            # Uzupełnij brakujące dane domyślną wartością
            for k, v in row.items():
                if v is None or (isinstance(v, str) and not v.strip()):
                    row[k] = "brak informacji"
            rows.append(row)
        except Exception as e:
            print(f"\n⚠ Błąd przy {link}: {e}")
        time.sleep(DELAY)

    df = pd.DataFrame(rows)
    # Mapowanie nazw kolumn na polskie
    polish_columns = {
        'title': 'tytuł',
        'price': 'miesięcznie',
        'rent_fee': 'czynsz',
        'deposit': 'kaucja',
        'wojewodztwo': 'województwo',
        'powiat': 'powiat',
        'miasto': 'miasto',
        'dzielnica': 'dzielnica',
        'ulica': 'ulica',
        'location': 'lokalizacja',
        'rooms': 'liczba pokoi',
        'advertiser_type': 'typ ogłoszeniodawcy',
        'heating': 'ogrzewanie',
        'floor': 'piętro',
        'finishing_state': 'stan wykończenia',
        'available_from': 'dostępne od',
        'additional_info': 'informacje dodatkowe',
        'building_year': 'rok budowy',
        'elevator': 'winda',
        'building_type': 'rodzaj zabudowy',
        'building_material': 'materiał budynku',
        'windows': 'okna',
        'safety': 'bezpieczeństwo',
        'equipment': 'wyposażenie',
        'security': 'zabezpieczenia',
        'media': 'media',
        'url': 'url',
        'scrape_date': 'data_pobrania'
    }
    df = df.rename(columns=polish_columns)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n✅ Zapisano dane do '{OUTPUT_CSV}'")

if __name__=="__main__":
    main()
