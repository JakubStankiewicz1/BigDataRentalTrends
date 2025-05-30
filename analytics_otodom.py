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


def trend_over_time(df: pd.DataFrame, freq: str = "W", show: bool = True):
    """Trend średniej ceny w czasie; domyślnie tygodniowo (freq='W'), można 'M'."""
    if df["data_pobrania"].isna().all():
        raise ValueError("Kolumna 'data_pobrania' pusta lub niepoprawna")
    ts = df.set_index("data_pobrania")["miesięcznie_num"].resample(freq).mean()

    fig, ax = plt.subplots()
    ts.plot(ax=ax, marker="o")
    ax.set_title(f"Średnia cena najmu w czasie ({freq})")
    ax.set_xlabel("Data")
    ax.set_ylabel("Cena [PLN]")
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    if show:
        plt.show()
    return fig


def corr_heatmap(df: pd.DataFrame, show: bool = True):
    """Heat-mapa korelacji dla wybranych numerycznych kolumn."""
    num_cols = ["miesięcznie_num", "czynsz_num", "kaucja_num",
                "powierzchnia_num", "cena_m2", "pokoje_num"]
    existing = [c for c in num_cols if c in df.columns]
    corr = df[existing].corr()

    fig, ax = plt.subplots()
    im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(existing)), labels=existing, rotation=45, ha="right")
    ax.set_yticks(range(len(existing)), labels=existing)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Macierz korelacji")
    if show:
        plt.tight_layout()
        plt.show()
    return fig


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
    #trend_over_time(df, freq="W")
    #corr_heatmap(df)
