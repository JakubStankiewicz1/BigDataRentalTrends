from requests import get
from bs4 import BeautifulSoup
from pandas import DataFrame
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re 
from os import path  # Added for file existence check
from sys import stdout

# --------- Configuration ---------
SEARCH_URL   = "https://www.otodom.pl/pl/oferty/wynajem/mieszkanie"
HEADERS      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/113.0.0.0 Safari/537.36"}
DELAY        = 0    # seconds between requests
OUTPUT_CSV   = "otodom_wynajem.csv"

# Zapytaj użytkownika o limit ogłoszeń
while True:
    limit_input = input("Ile ogłoszeń pobrać? (wpisz liczbę lub Enter dla wszystkich): ").strip()
    if limit_input == '' or limit_input.lower() == 'wszystkie':
        MAX_LISTINGS = None
        break
    else:
        try:
            MAX_LISTINGS = int(limit_input)
            if MAX_LISTINGS <= 0:
                raise ValueError
            break
        except ValueError:
            MAX_LISTINGS = None
            print("Nieprawidłowa liczba")

# Check if the output file already exists
if path.exists(OUTPUT_CSV):
    new_name = input(f"Plik '{OUTPUT_CSV}' już istnieje. Podaj nową nazwę pliku (lub naciśnij Enter, aby nadpisać): ").strip()
    if new_name:
        OUTPUT_CSV = new_name

# --------- Helpers ---------
def fetch_soup(url: str) -> BeautifulSoup:
    r = get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def parse_location(location_str: str) -> dict[str, str | None]:
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

def get_listing_links(max_listings: int | None = None) -> set[str]:
    """Zwraca unikalne linki do wszystkich ofert z listingu (wszystkie strony lub do limitu)."""
    links = set()
    page = 1
    while True:
        url = SEARCH_URL if page == 1 else f"{SEARCH_URL}?page={page}"
        soup = fetch_soup(url)
        found_on_page = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/pl/oferta/" in href:
                full = urljoin("https://www.otodom.pl", href)
                if urlparse(full).netloc.endswith("otodom.pl") and full not in links:
                    links.add(full)
                    found_on_page += 1
                    if max_listings is not None and len(links) >= max_listings:
                        print(f"Zebrano {len(links)} ogłoszeń (limit osiągnięty)")
                        return links
        if found_on_page == 0:
            break  # Brak nowych ogłoszeń na stronie, kończymy
        print(f"Zebrano {len(links)} ogłoszeń (strona {page})")
        page += 1
    return links

def parse_listing(url: str) -> dict[str, str | None]:
    """Parsuje szczegóły pojedynczego ogłoszenia Otodom."""
    soup = fetch_soup(url)
    data: dict[str, str | None] = {}

    datakeys_to_single_selectors = {
        "title" : "h1[data-cy='adPageAdTitle']",
        "price" : "strong[data-cy='adPageHeaderPrice']",
        "deposit" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Kaucja:') + p",
        "rooms" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Liczba pokoi:') + p",
        "advertiser_type" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Typ ogłoszeniodawcy:') + p",
        "heating" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Ogrzewanie:') + p",
        "floor" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Piętro:') + p",
        "finishing_state" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Stan wykończenia:') + p",
        "available_from" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Dostępne od:') + p",
        "building_year" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Rok budowy:') + p",
        "elevator" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Winda:') + p",
        "building_type" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Rodzaj zabudowy:') + p",
        "building_material" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Materiał budynku:') + p",
        "windows" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Okna:') + p",
        "safety" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Bezpieczeństwo:') + p",
        "location" : "div[data-sentry-element='Container'] a[data-sentry-element='StyledLink']",
        "area": "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Powierzchnia:') + p",
    }

    datakeys_to_multi_selectors = {
        "equipment" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Wyposażenie:') + p span",
        "security" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Zabezpieczenia:') + p span",
        "media" : "div[data-sentry-element='ItemGridContainer'] p:-soup-contains('Media:') + p span",
    }

    for key, selector in datakeys_to_single_selectors.items():
        element = soup.select_one(selector)
        if key == "area" and element:
            # Wyciągnij tylko liczbę (może być float) z tekstu np. "27.4 m²"
            match = re.search(r"[\d,.]+", element.get_text(strip=True).replace(",", "."))
            data[key] = float(match.group()) if match else None
        else:
            data[key] = element.get_text(strip=True) if element else None

    for key, selector in datakeys_to_multi_selectors.items():
        elements = soup.select(selector)
        data[key] = ", ".join(element.get_text(strip=True) for element in elements) if elements else None

    # Rent Fee (Additional Price)
    fee_el = soup.select_one("div[data-sentry-element='AdditionalPriceWrapper']")
    if fee_el:
        fee_text = fee_el.get_text(strip=True)
        match = re.search(r'\d+', fee_text)  # Extract only the numeric value
        data["rent_fee"] = int(match.group()) if match else None
    else:
        data["rent_fee"] = None

    # Parse location components
    location_components = parse_location(data["location"])
    data.update(location_components)

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

    # URL & timestamp (unchanged)
    data["url"] = url
    data["scrape_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return data

def print_progress_bar(iteration: int, total: int, start_time: float, length: int = 30):
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    elapsed = time.time() - start_time
    avg_time = elapsed / iteration if iteration > 0 else 0
    remaining = int(avg_time * (total - iteration))
    mins, secs = divmod(remaining, 60)
    eta = f"ETA: {mins:02d}:{secs:02d}"
    stdout.write(f'\rPostęp: |{bar}| {iteration}/{total} ({percent}%) {eta}')
    stdout.flush()
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

    df = DataFrame(rows)
    # Mapowanie nazw kolumn na polskie
    polish_columns = {
        'title': 'tytuł',
        'price': 'miesięcznie',
        'rent_fee': 'czynsz',
        'deposit': 'kaucja',
        'area': 'powierzchnia',  # Dodano powierzchnię
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
