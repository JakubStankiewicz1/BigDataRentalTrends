# analytics_otodom.py
import re
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

CSV_PATH = Path("otodom_wynajem.csv")   # zmień, jeśli plik jest gdzie indziej

# ─────────────────────────────────────────────────────────────
# ► 1. PRZYGOTOWANIE DANYCH
# ─────────────────────────────────────────────────────────────
def load_and_clean(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    """
    Wczytuje CSV z Otodom, czyści ceny, czynsz, kaucję i powierzchnię
    oraz dorzuca parę zmiennych pomocniczych.
    """
    df = pd.read_csv(csv_path)

    # Pomocnicza funkcja do "odPLN-owania" zapisu typu "3 200 zł"
    def to_number(x):
        if pd.isna(x):
            return np.nan
        x = re.sub(r"[^\d,.-]", "", str(x)).replace(",", ".")
        try:
            return float(x)
        except ValueError:
            return np.nan

    for col in ["miesięcznie", "czynsz", "kaucja", "powierzchnia"]:
        if col in df.columns:
            df[col + "_num"] = df[col].apply(to_number)

    # Cena za metr
    df["cena_m2"] = df["miesięcznie_num"] / df["powierzchnia_num"]

    # Liczba pokoi jako int
    if "liczba pokoi" in df.columns:
        df["pokoje_num"] = df["liczba pokoi"].str.extract(r"(\d+)").astype(float)

    # Czas w pandas-datetime
    df["data_pobrania"] = pd.to_datetime(df["data_pobrania"], errors="coerce")

    return df


# ─────────────────────────────────────────────────────────────
# ► 2. ANALIZY – KAŻDA JAKO ODDZIELNA FUNKCJA
# ─────────────────────────────────────────────────────────────
def hist_rent(df: pd.DataFrame, bins: int = 40, show: bool = True):
    """Histogram miesięcznych cen najmu."""
    fig, ax = plt.subplots()
    df["miesięcznie_num"].hist(bins=bins, ax=ax, edgecolor="black")
    ax.set_title("Rozkład miesięcznych cen najmu")
    ax.set_xlabel("Cena [PLN]")
    ax.set_ylabel("Liczba ofert")
    ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    if show:
        plt.show()
    return fig


def scatter_price_area(df: pd.DataFrame, show: bool = True):
    """Scatter: cena vs. powierzchnia, z prostą regresji OLS."""
    subset = df.dropna(subset=["miesięcznie_num", "powierzchnia_num"])
    x, y = subset["powierzchnia_num"], subset["miesięcznie_num"]

    fig, ax = plt.subplots()
    ax.scatter(x, y, alpha=0.4, s=20)
    # regresja liniowa
    coef = np.polyfit(x, y, 1)
    poly1d_fn = np.poly1d(coef)
    ax.plot(x, poly1d_fn(x), linewidth=2)
    ax.set_xlabel("Powierzchnia [m²]")
    ax.set_ylabel("Cena [PLN]")
    ax.set_title("Cena vs. powierzchnia")
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    if show:
        plt.show()
    return fig


def boxplot_city(df: pd.DataFrame, top_n: int = 10, show: bool = True):
    """Boxplot cen za m² dla najczęstszych miast."""
    if "miasto" not in df.columns:
        raise ValueError("Kolumna 'miasto' nie istnieje")

    city_counts = df["miasto"].value_counts().head(top_n).index
    subset = df[df["miasto"].isin(city_counts)]

    fig, ax = plt.subplots(figsize=(10, 6))
    subset.boxplot(column="cena_m2", by="miasto", ax=ax)
    ax.set_title(f"Cena za m² – top {top_n} miast")
    ax.set_xlabel("Miasto")
    ax.set_ylabel("Cena za m² [PLN]")
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    plt.suptitle("")
    if show:
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.show()
    return fig


def bar_price_by_rooms(df: pd.DataFrame, show: bool = True):
    """Średnia cena najmu vs. liczba pokoi."""
    grouped = df.groupby("pokoje_num")["miesięcznie_num"].mean().dropna()

    fig, ax = plt.subplots()
    grouped.plot(kind="bar", ax=ax)
    ax.set_title("Średnia cena a liczba pokoi")
    ax.set_xlabel("Liczba pokoi")
    ax.set_ylabel("Średnia cena [PLN]")
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    if show:
        plt.show()
    return fig


def pie_advertiser_type(df: pd.DataFrame, show: bool = True):
    """Udział typów ogłoszeniodawcy."""
    if "typ ogłoszeniodawcy" not in df.columns:
        raise ValueError("Brak kolumny 'typ ogłoszeniodawcy'")
    counts = df["typ ogłoszeniodawcy"].value_counts()

    fig, ax = plt.subplots()
    ax.pie(counts, labels=counts.index, autopct="%1.0f%%", startangle=90, textprops={'fontsize': 8})
    ax.set_title("Struktura typów ogłoszeniodawcy")
    if show:
        plt.show()
    return fig


# ─────────────────────────────────────────────────────────────
# ── NOWE FUNKCJE – MAPY / BAR CHART + HISTOGRAM  ─────────────
# ─────────────────────────────────────────────────────────────
import warnings

def _plot_or_map(grouped, value_label: str, cmap: str = "Blues", show: bool = True):
    """
    Jeżeli dostępne jest GeoPandas + shapefile PL (województwa), rysuje mapę choropleth.
    W przeciwnym razie – zwykły wykres słupkowy.
    """
    try:
        import geopandas as gpd
        shp = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
        # naturalearth nie ma PL województw – próbujemy user-supplied:
        voiv_path = Path("wojewodztwa.shp")
        if voiv_path.exists():
            shp = gpd.read_file(voiv_path)
        else:
            raise FileNotFoundError
        # Normalizujemy kolumnę z nazwą województwa
        name_col = next(c for c in shp.columns if "name" in c.lower())
        shp["wojewodztwo"] = (
            shp[name_col]
            .str.replace("województwo", "", case=False, regex=False)
            .str.strip()
            .str.capitalize()
        )

        g = shp.merge(grouped, how="left", on="wojewodztwo")
        fig, ax = plt.subplots(figsize=(7, 7))
        g.plot(column=value_label, ax=ax, legend=True,
               legend_kwds={"label": value_label, "orientation": "vertical"},
               edgecolor="black", linewidth=0.4, cmap=cmap, missing_kwds={
                   "color": "lightgrey",
                   "label": "Brak danych"})
        ax.set_axis_off()
        ax.set_title(f"{value_label} – mapa województw")
        if show:
            plt.show()
        return fig
    except Exception as e:
        # cicho przechodzimy na słupki
        warnings.warn(f"Mapa nie została wygenerowana ({e}). Pokazuję wykres słupkowy.")
        fig, ax = plt.subplots()
        grouped.sort_values(ascending=False).plot(kind="bar", ax=ax, color="#4a90e2")
        ax.set_ylabel(value_label)
        ax.set_xlabel("Województwo")
        ax.set_title(value_label)
        ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        if show:
            plt.show()
        return fig


def map_or_bar_avg_price(df: pd.DataFrame, show: bool = True):
    """Średnia *cena* najmu w województwach (mapa lub bar)."""
    grouped = df.groupby("województwo")["miesięcznie_num"].mean().round(0).dropna()
    grouped.name = "Średnia cena [PLN]"
    return _plot_or_map(grouped, grouped.name, cmap="Reds", show=show)


def map_or_bar_avg_price_m2(df: pd.DataFrame, show: bool = True):
    """Średnia *cena za m²* w województwach (mapa lub bar)."""
    grouped = df.groupby("województwo")["cena_m2"].mean().round(0).dropna()
    grouped.name = "Średnia cena za m² [PLN]"
    return _plot_or_map(grouped, grouped.name, cmap="Oranges", show=show)


def hist_rent_city(df: pd.DataFrame, city: str, bins: int = 40, show: bool = True):
    """
    Histogram cen dla wskazanego miasta (argument *city* – np. 'Warszawa').
    Jeśli miasto nie występuje, zgłasza wyjątek.
    """
    subset = df[df["miasto"].str.lower() == city.lower()]
    if subset.empty:
        raise ValueError(f"Brak ogłoszeń dla miasta: {city}")
    fig, ax = plt.subplots()
    subset["miesięcznie_num"].hist(bins=bins, ax=ax, edgecolor="black")
    ax.set_title(f"Rozkład cen najmu – {city.capitalize()}")
    ax.set_xlabel("Cena [PLN]")
    ax.set_ylabel("Liczba ofert")
    ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    if show:
        plt.show()
    return fig
# ─────────────────────────────────────────────────────────────
# ── KONIEC NOWYCH FUNKCJI ────────────────────────────────────


# ─────────────────────────────────────────────────────────────
# ► 3. SZYBKA DEMO-ŚCIEŻKA
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    df = load_and_clean()

    # Odkomentuj, aby wygenerować interesujące Cię wykresy:
    hist_rent(df)
    scatter_price_area(df)
    boxplot_city(df, top_n=10)
    bar_price_by_rooms(df)
    pie_advertiser_type(df)

    map_or_bar_avg_price(df)
    map_or_bar_avg_price_m2(df)
    hist_rent_city(df, "Poznań")
