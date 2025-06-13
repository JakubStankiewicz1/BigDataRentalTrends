import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.ticker as ticker
from analytics_otodom import load_and_clean  # Zakładam, że masz funkcję load_and_clean w osobnym pliku
import os

df = load_and_clean()  # Wczytaj i oczyść dane

# Utwórz katalog na wykresy jeśli nie istnieje
os.makedirs("plots", exist_ok=True)

# Konwersja cen i powierzchni
def parse_price(price_str):
    try:
        return float(price_str.replace("zł", "").replace(" ", "").replace(",", "."))
    except:
        return np.nan

df["cena_miesięczna"] = df["miesięcznie"].apply(parse_price)
df["powierzchnia_m2"] = pd.to_numeric(df["powierzchnia"], errors='coerce')

# Cena za metr kwadratowy
df["cena_za_m2"] = df["cena_miesięczna"] / df["powierzchnia_m2"]
df = df[df["cena_za_m2"].notna()]

# Grupowanie: mediany cen za m2 dla miast
top_cities = (
    df.groupby("miasto")
    .agg(
        liczba_ogłoszeń=("cena_za_m2", "count"),
        mediana_cena_za_m2=("cena_za_m2", "median")
    )
    .sort_values(by="liczba_ogłoszeń", ascending=False)
    .head(20)
    .sort_values("mediana_cena_za_m2", ascending=False)
    .reset_index()
)

# Wykres główny - miasta
plt.figure(figsize=(10, 10))
sns.set(style="whitegrid")

palette = sns.color_palette("Spectral", len(top_cities))

barplot = sns.barplot(
    data=top_cities,
    y="miasto",
    x="mediana_cena_za_m2",
    palette=palette
)

# Dodanie wartości na słupkach
for i, row in top_cities.iterrows():
    barplot.text(
        row["mediana_cena_za_m2"] + 0.1,
        i,
        f'{row["mediana_cena_za_m2"]:.1f}',
        color='black',
        va='center'
    )
    barplot.text(
        0.5,
        i,
        f'{int(row["liczba_ogłoszeń"])}',
        color='black',
        va='center',
        ha='left'
    )

plt.title("20 miast z najwyższą medianą ceny wynajmu za m²", fontsize=16)
plt.xlabel("Cena za metr kwadratowy (zł/m²)")
plt.ylabel("Miasto")
plt.axvline(40, color="black", linestyle="--", alpha=0.7)
plt.tight_layout()
plt.gca().xaxis.set_major_locator(ticker.MultipleLocator(5))
# Zapisz wykres do pliku PNG
plt.savefig("plots/miasta_top20.png", dpi=200, bbox_inches="tight")
plt.show()

# Lista 20 miast do analizy dzielnic (w tej samej kolejności co na wykresie)
cities_for_districts = top_cities["miasto"].tolist()

# Ustaw styl wykresów
sns.set(style="whitegrid")
plt.rcParams.update({'figure.max_open_warning': 0})

for city in cities_for_districts:
    city_df = df[df["miasto"] == city]
    # Grupowanie po dzielnicy
    dzielnice = (
        city_df.groupby("dzielnica")
        .agg(
            liczba_ogłoszeń=("cena_za_m2", "count"),
            mediana_cena_za_m2=("cena_za_m2", "median")
        )
        .sort_values("mediana_cena_za_m2", ascending=False)
        .reset_index()
    )
    # Pomijaj miasta bez dzielnic
    if dzielnice.shape[0] < 2:
        continue

    # Mediana dla całego miasta
    city_median = city_df["cena_za_m2"].median()

    plt.figure(figsize=(8, 6))
    bar = sns.barplot(
        data=dzielnice,
        y="dzielnica",
        x="mediana_cena_za_m2",
        palette="Spectral",
        orient="h"
    )
    # Dodaj wartości na słupkach
    for i, (cnt, val) in enumerate(zip(dzielnice["liczba_ogłoszeń"], dzielnice["mediana_cena_za_m2"])):
        bar.text(val + 0.2, i, f"{val:.1f}", va='center', fontsize=9)
        bar.text(0, i, f"{cnt}", va='center', fontsize=8, color='black')

    # Dodaj pionową linię z medianą miasta
    plt.axvline(city_median, color="black", linestyle="--", alpha=0.7, label=f"Mediana miasta: {city_median:.1f} zł/m²")
    plt.legend(loc="lower right", fontsize=9)

    plt.title(f"{city} – dzielnice i ceny za m² (mediana miasta: {city_median:.1f} zł/m²)")
    plt.xlabel("Cena za metr kwadratowy (mediana dla dzielnicy)")
    plt.ylabel("Dzielnica")
    plt.tight_layout()
    # Zapisz wykres do pliku PNG
    plt.savefig(f"plots/{city}_dzielnice.png", dpi=200, bbox_inches="tight")
    plt.show()
    # Jeśli chcesz zapisywać wykresy do plików, odkomentuj poniższą linię:
    # plt.savefig(f"{city}_dzielnice_cena_m2.png")
