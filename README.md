# BigDataRentalTrends
Projekt analizy danych dotyczących cen wynajmu mieszkań w Polsce. Zawiera web scraping, czyszczenie danych, analizę statystyczną oraz wizualizację trendów na rynku najmu.

## Instrukcja obsługi

### 1. Wymagania
- Python 3.8 lub nowszy
- System operacyjny: Windows, Linux lub MacOS

### 2. Instalacja zależności
Zainstaluj wymagane biblioteki poleceniem:
```bash
pip install -r requirements.txt
```

### 3. Uruchomienie skryptu
Aby uruchomić pobieranie danych z Otodom, wpisz w terminalu:
```bash
python main_otodom.py
```

Podczas uruchamiania zostaniesz zapytany, ile ogłoszeń pobrać (możesz podać liczbę lub nacisnąć Enter, aby pobrać wszystkie dostępne ogłoszenia).

### 4. Wynik
Dane zostaną zapisane do pliku CSV (domyślnie `otodom_wynajem.csv`). Jeśli plik już istnieje, możesz podać nową nazwę.

### 5. Otwieranie pliku CSV
Plik CSV możesz otworzyć w Excelu lub edytorze tekstu (np. VS Code). **Uwaga:** Excel może błędnie interpretować niektóre dane (np. piętro `1/8` jako datę). Zalecamy otwieranie pliku najpierw w edytorze tekstu.

### 6. Aktualizacja requirements.txt
Jeśli dodasz nowe biblioteki do projektu, zaktualizuj plik requirements.txt poleceniem:
```bash
pip freeze > requirements.txt
```

### 7. Najczęstsze problemy
- Jeśli pojawią się błędy związane z brakiem bibliotek, upewnij się, że wykonałeś instalację z requirements.txt.
- Jeśli strona Otodom zmieni układ, skrypt może wymagać aktualizacji selektorów.

### 8. Kontakt
W razie problemów lub pytań zgłoś issue na repozytorium lub skontaktuj się z autorem projektu.