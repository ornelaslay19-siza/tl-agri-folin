"""
src/preprocessing.py - Prepara dadus / Clean the raw rice prices and build features
==============================================================================
Input : data/raw/agri_prices_raw.csv          (from src/collect.py)
Output: data/processed/agri_prices_clean.csv
        reports/data_dictionary.md             (columns, types, units, missing)

Steps
-----
1. Parse the `data` column to a real date.
2. Remove duplicates (same date + product + district + source).
3. Invalid prices (<= 0 or above 50 USD/kg) become missing.
4. Missing values: forward fill inside each series (the last known market
   price is the best guess in Taibesi too), then the product mean.
5. Features
   - folin_kotuk          : previous observation of the same series
   - folin_7_loron_kotuk  : last known price at least 7 days earlier
   - folin_media_7_dias   : mean of the 7 previous observations
   - fulan, dia_semana, tinan
   A "series" = one product in one district from one source
   (e.g. Fos Lokal in Bobonaro from WFP). lokalizasaun = munisípiu (district).
   For the Taibesi sheet (daily) the 7-observation window is 7 days; for the
   WFP data (monthly) it is 7 months. The column `frekuensia` says which.

Usage:  python src/preprocessing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import CLEAN_FILE, DICTIONARY_FILE, PROCESSED_DIR, RAW_FILE  # noqa: E402

SERIES = ["produto", "lokalizasaun", "fonte"]
MAX_VALID_PRICE = 50.0   # USD/kg; nothing in Taibesi costs more than this

DIAS = ["Segunda", "Tersa", "Kuarta", "Kinta", "Sesta", "Sábadu", "Domingu"]


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_FILE)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    return df


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report = {"rows_raw": len(df)}

    # 1-2. dates and duplicates
    df = df.dropna(subset=["data", "produto"])
    report["duplicates_exact"] = int(df.duplicated().sum())
    df = df.drop_duplicates()
    report["duplicates_key"] = int(df.duplicated(["data"] + SERIES).sum())
    df = df.sort_values("timestamp").drop_duplicates(["data"] + SERIES, keep="last")

    # 3. invalid prices -> NaN
    bad = (df["folin_kg_usd"] <= 0) | (df["folin_kg_usd"] > MAX_VALID_PRICE)
    report["invalid_prices"] = int(bad.sum())
    df.loc[bad, "folin_kg_usd"] = np.nan

    # 4. missing values: forward fill per series, then product mean
    df = df.sort_values(SERIES + ["data"]).reset_index(drop=True)
    report["missing_before"] = int(df["folin_kg_usd"].isna().sum())
    df["folin_imputadu"] = df["folin_kg_usd"].isna()
    df["folin_kg_usd"] = df.groupby(SERIES)["folin_kg_usd"].ffill()
    df["folin_kg_usd"] = df["folin_kg_usd"].fillna(
        df.groupby("produto")["folin_kg_usd"].transform("mean"))
    report["missing_after"] = int(df["folin_kg_usd"].isna().sum())
    return df, report


def price_days_before(dates: pd.Series, prices: pd.Series, days: int) -> np.ndarray:
    """For each date d: last price observed on or before d - `days`."""
    t = dates.values
    idx = np.searchsorted(t, t - np.timedelta64(days, "D"), side="right") - 1
    out = prices.values[np.clip(idx, 0, None)].astype(float)
    out[idx < 0] = np.nan
    return out


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(SERIES, sort=False)
    df["folin_kotuk"] = g["folin_kg_usd"].shift(1)
    df["folin_media_7_dias"] = g["folin_kg_usd"].transform(
        lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    df["folin_7_loron_kotuk"] = np.nan
    for _, ix in g.groups.items():
        sub = df.loc[ix]
        df.loc[ix, "folin_7_loron_kotuk"] = price_days_before(sub["data"], sub["folin_kg_usd"], 7)

    # Is this series daily (Taibesi sheet) or monthly (WFP)?
    gap = g["data"].transform(lambda s: s.diff().dt.days.median())
    df["frekuensia"] = np.where(gap <= 2, "loron", "fulan")

    df["tinan"] = df["data"].dt.year
    df["fulan"] = df["data"].dt.month
    df["dia_semana"] = df["data"].dt.dayofweek          # 0 = Segunda (Monday)
    df["dia_semana_naran"] = df["dia_semana"].map(dict(enumerate(DIAS)))
    df["is_dili"] = (df["lokalizasaun"] == "Dili").astype(int)

    for c in ["folin_kotuk", "folin_7_loron_kotuk", "folin_media_7_dias"]:
        df[c] = df[c].round(4)
    return df


# ---------------------------------------------------------------------------
# Data dictionary (generated, so the missing counts are always current)
# ---------------------------------------------------------------------------
DICTIONARY = {
    # column: (description Tetun / English, unit)
    "data": ("Data folin nian / date of the price observation (WFP: 15th of the month)", "YYYY-MM-DD"),
    "produto": ("Naran produtu / product: Fos Lokal (local rice), Fos Importadu (imported rice)", "text"),
    "folin_kg_usd": ("Folin retalhu ba kg ida / retail price per kg", "USD/kg"),
    "lokalizasaun": ("Munisípiu / district (Dili, Baucau, Bobonaro, Atauro ...)", "text"),
    "timestamp": ("Tempu ne'ebé dadus rekolla / UTC time the row was collected", "ISO 8601 UTC"),
    "source_url": ("Ligasaun fonte / URL of the online source", "URL"),
    "n_merkadu": ("Numeru merkadu iha munisípiu ne'ebé halo media / markets averaged", "count"),
    "fonte": ("Fonte / source: WFP/HDX or Google Sheet (Taibesi)", "text"),
    "folin_imputadu": ("True if the price was missing and filled (ffill / mean)", "bool"),
    "folin_kotuk": ("Folin observasaun anterior / previous observation of the series", "USD/kg"),
    "folin_7_loron_kotuk": ("Folin ikus husi loron 7 ka liu kotuk / last price >= 7 days before", "USD/kg"),
    "folin_media_7_dias": ("Media folin 7 observasaun anterior / mean of 7 previous observations", "USD/kg"),
    "frekuensia": ("Frekuénsia serie / 'loron' = daily, 'fulan' = monthly", "text"),
    "tinan": ("Tinan / year", "year"),
    "fulan": ("Fulan / month 1-12", "month"),
    "dia_semana": ("Loron semana / day of week 0=Segunda ... 6=Domingu", "0-6"),
    "dia_semana_naran": ("Naran loron semana / day name in Tetun", "text"),
    "is_dili": ("1 se munisípiu Dili / 1 if the district is Dili", "0/1"),
}


def write_dictionary(raw: pd.DataFrame, clean_df: pd.DataFrame, report: dict) -> None:
    def table(df: pd.DataFrame) -> str:
        lines = ["| Kolúna / Column | Tipu / Type | Deskrisaun / Description | Unidade / Unit | Missing |",
                 "|---|---|---|---|---|"]
        for c in df.columns:
            desc, unit = DICTIONARY.get(c, ("", ""))
            n = int(df[c].isna().sum())
            lines.append(f"| `{c}` | {df[c].dtype} | {desc} | {unit} | {n} ({n / len(df):.1%}) |")
        return "\n".join(lines)

    counts = (clean_df.groupby(["fonte", "produto"])
              .agg(rows=("data", "size"), first=("data", "min"), last=("data", "max"))
              .reset_index())
    counts["first"] = counts["first"].dt.date
    counts["last"] = counts["last"].dt.date
    cov = ["| Fonte | Produto | Rows | First | Last |", "|---|---|---|---|---|"] + [
        f"| {r.fonte} | {r.produto} | {r.rows} | {r.first} | {r.last} |" for r in counts.itertuples()]

    text = f"""# Data Dictionary - Folin Fos Timor-Leste

Generated automatically by `src/preprocessing.py` on {pd.Timestamp.now(tz='Asia/Dili'):%Y-%m-%d %H:%M} (Dili time).

## 1. Raw file `data/raw/agri_prices_raw.csv`

{len(raw)} rows. One row = one price for one product, in one district (munisípiu), on one date, from one source.
WFP prices of several markets in the same district are averaged (`n_merkadu`).

{table(raw)}

## 2. Clean file `data/processed/agri_prices_clean.csv`

{len(clean_df)} rows.

{table(clean_df)}

Missing values in `folin_kotuk`, `folin_7_loron_kotuk` and `folin_media_7_dias` are expected:
they are the first observation(s) of each series, where no earlier price exists.
The models drop those rows.

## 3. Cleaning report

| Step | Rows |
|---|---|
| Raw rows | {report['rows_raw']} |
| Exact duplicates removed | {report['duplicates_exact']} |
| Same date/product/market duplicates removed | {report['duplicates_key']} |
| Invalid prices (<= 0 or > {MAX_VALID_PRICE:.0f} USD/kg) set to missing | {report['invalid_prices']} |
| Missing prices before filling | {report['missing_before']} |
| Missing prices after filling | {report['missing_after']} |

## 4. Coverage per source and product

{chr(10).join(cov)}
"""
    DICTIONARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    DICTIONARY_FILE.write_text(text, encoding="utf-8")


def main() -> pd.DataFrame:
    raw = load_raw()
    df, report = clean(raw.copy())
    df = add_features(df)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["data"] = out["data"].dt.strftime("%Y-%m-%d")
    out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out.to_csv(CLEAN_FILE, index=False)
    raw_out = raw.copy()
    write_dictionary(raw_out, df, report)
    print("Cleaning report:", report)
    print(f"Saved {CLEAN_FILE.name}: {len(df)} rows, {df.shape[1]} columns")
    print(f"Saved {DICTIONARY_FILE.name}")
    return df


if __name__ == "__main__":
    main()
