"""
src/collect.py - Rekolla dadus folin fos / Collect rice prices
==============================================================
Capstone Project DIT - Mining and Exploring - Topic 3

Collects REAL online rice prices for Timor-Leste (Fos Lokal and Fos
Importadu) and saves them to data/raw/agri_prices_raw.csv with a collection
timestamp on every row.

Sources (all online, no invented numbers)
-----------------------------------------
1. WFP Food Prices - Timor-Leste (HDX open data, CKAN API)
   "Rice (white, local)" -> Fos Lokal, "Rice (white, imported)" -> Fos
   Importadu. Markets are averaged per MUNISÍPIU (district): Dili, Baucau,
   Bobonaro, Oecussi, Atauro ... WFP publishes monthly, 1-2 months late.
2. Google Sheet typed by the student at Taibesi / Manleu market (daily).
   Only the two rice products are accepted; other rows are skipped.
   Stored with lokalizasaun = Dili (the district of Taibesi and Manleu).

lokalizasaun is always the municipality (district), never the market.

Polling interval: every 24 hours (GitHub Actions at 06:00 Dili time, or
`python src/collect.py --loop` on a laptop). Each run downloads the sources,
adds only NEW or REVISED rows to the raw file and writes one line per source
to data/raw/collection_log.csv.

If a website is down (or the internet in Dili is slow), the last good
download in data/raw/cache/ is used and the log says status=cache, so the
dashboard keeps working.

Usage
-----
    python src/collect.py              # collect once
    python src/collect.py --loop       # collect now and then every 24 h
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (  # noqa: E402
    CACHE_DIR, COLLECTION_LOG, GSHEET_ENV_CREDS, GSHEET_ENV_CSV, GSHEET_ENV_ID,
    HTTP_RETRIES, HTTP_TIMEOUT, LOCAL_MANUAL_FILE, MARKET_TO_MUNISIPIU,
    POLLING_INTERVAL_HOURS, PRODUTU, RAW_COLUMNS, RAW_DIR, RAW_FILE,
    SHEET_DEFAULT_MUNISIPIU, USER_AGENT, WFP_API_URL,
    WFP_COMMODITY_MAP, WFP_DATASET_PAGE,
)

KEY = ["data", "produto", "lokalizasaun", "fonte"]   # one price per key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get(url: str) -> requests.Response:
    """GET with retries (5 s, 10 s back-off). Raises the last error."""
    last = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT,
                             headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            if attempt < HTTP_RETRIES:
                time.sleep(5 * attempt)
    raise last


def save_cache(content: bytes, name: str, ext: str, ts: datetime) -> Path:
    """Keep a copy of the download; skip if identical to the last one."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    old = latest_cache(name, ext)
    if old and hashlib.sha256(old.read_bytes()).digest() == hashlib.sha256(content).digest():
        return old
    path = CACHE_DIR / f"{name}_{ts.strftime('%Y%m%dT%H%M%SZ')}.{ext}"
    path.write_bytes(content)
    return path


def latest_cache(name: str, ext: str) -> Path | None:
    files = sorted(CACHE_DIR.glob(f"{name}_*.{ext}"))
    return files[-1] if files else None


def cache_time(path: Path) -> datetime:
    """Download time is stored in the file name: wfp_20260928T190439Z.csv"""
    stamp = re.search(r"(\d{8}T\d{6}Z)", path.name).group(1)
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def log_run(rows: list[dict]) -> None:
    COLLECTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(COLLECTION_LOG, mode="a", index=False,
              header=not COLLECTION_LOG.exists())


# ---------------------------------------------------------------------------
# Source 1: WFP / HDX  ->  Fos Lokal, Fos Importadu
# ---------------------------------------------------------------------------
def download_wfp(ts: datetime) -> tuple[bytes, str, datetime, str]:
    """Return (csv bytes, source url, retrieval time, status)."""
    try:
        meta = http_get(WFP_API_URL).json()
        resources = [
            r for r in meta["result"]["resources"]
            if str(r.get("format", "")).upper() == "CSV"
            and "qc_" not in str(r.get("url", "")).lower()       # skip QuickCharts file
            and "quickchart" not in str(r.get("name", "")).lower()
        ]
        resources.sort(key=lambda r: r.get("last_modified") or "", reverse=True)
        url = resources[0]["url"]
        content = http_get(url).content
        save_cache(content, "wfp", "csv", ts)
        return content, url, ts, "ok"
    except Exception as e:
        cached = latest_cache("wfp", "csv")
        if cached is None:
            raise RuntimeError(f"WFP download failed and no cache: {e}") from e
        print(f"  [WFP] online download failed ({type(e).__name__}); using cache {cached.name}")
        return cached.read_bytes(), WFP_DATASET_PAGE, cache_time(cached), "cache"


def parse_wfp(content: bytes, source_url: str, retrieved: datetime) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(content), low_memory=False)
    # HDX files have an HXL tag row (#date, #adm1 ...) under the header
    if len(df) and str(df.iloc[0, 0]).startswith("#"):
        df = df.iloc[1:]
    df = df[df["commodity"].isin(WFP_COMMODITY_MAP) & (df["pricetype"] == "Retail")]
    df = df[df["unit"].str.upper() == "KG"]
    df = df.assign(
        data=pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"),
        produto=df["commodity"].map(WFP_COMMODITY_MAP),
        folin=pd.to_numeric(df["usdprice"], errors="coerce"),
        market=df["market"].str.strip(),
    )
    # market -> municipality (district); corrections from config
    munis = df["admin1"].str.strip()
    override = df["market"].map(MARKET_TO_MUNISIPIU)
    df["lokalizasaun"] = override.fillna(munis)
    unknown = df["lokalizasaun"].isna()
    if unknown.any():
        print(f"  [WFP] {unknown.sum()} rows without municipality dropped "
              f"(markets: {sorted(df.loc[unknown, 'market'].unique())})")
    df = df[~unknown]
    # one price per district, product and date = mean of its markets
    out = (df.groupby(["data", "produto", "lokalizasaun"])
             .agg(folin_kg_usd=("folin", "mean"), n_merkadu=("market", "nunique"))
             .reset_index())
    out["folin_kg_usd"] = out["folin_kg_usd"].round(4)
    out["timestamp"] = iso(retrieved)
    out["source_url"] = source_url
    out["fonte"] = "WFP/HDX"
    return out


# ---------------------------------------------------------------------------
# Source 2: Google Sheet (Taibesi / Manleu, typed daily) - rice rows only
# ---------------------------------------------------------------------------
def read_google_sheet() -> tuple[pd.DataFrame | None, str]:
    """Return (dataframe, url) or (None, reason) when no sheet is set up.

    Sheet columns (row 1): data | produto | folin_kg_usd | munisipiu
    munisipiu is optional (empty = Dili). Market names typed by mistake
    (Taibesi, Manleu) are also stored as Dili.
    Optional: timestamp (filled automatically if you use a Google Form).
    """
    csv_url = os.getenv(GSHEET_ENV_CSV)
    sheet_id = os.getenv(GSHEET_ENV_ID)
    if csv_url:
        return pd.read_csv(io.BytesIO(http_get(csv_url).content)), csv_url
    if sheet_id:
        import gspread  # only needed for this option
        gc = gspread.service_account(filename=os.getenv(GSHEET_ENV_CREDS))
        ws = gc.open_by_key(sheet_id).sheet1
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        return pd.DataFrame(ws.get_all_records()), url
    if LOCAL_MANUAL_FILE.exists():           # offline copy typed in Excel
        return pd.read_csv(LOCAL_MANUAL_FILE), str(LOCAL_MANUAL_FILE.name)
    return None, f"not configured (set {GSHEET_ENV_CSV} or {GSHEET_ENV_ID})"


def parse_sheet(df: pd.DataFrame, source_url: str, retrieved: datetime) -> pd.DataFrame:
    df = df.rename(columns=lambda c: str(c).strip().lower())
    names = {k.lower(): k for k in PRODUTU}
    produto = df["produto"].astype(str).str.strip().str.lower().map(names)
    bad = df.loc[produto.isna(), "produto"].unique()
    if len(bad):
        print(f"  [Sheet] not rice, rows skipped (only {list(PRODUTU)} accepted): {list(bad)}")
    col = "munisipiu" if "munisipiu" in df else ("lokalizasaun" if "lokalizasaun" in df else None)
    munisipiu = (df[col].fillna("").astype(str).str.strip() if col
                 else pd.Series("", index=df.index))
    markets_in_dili = {"", "taibesi", "manleu", "manleuana", "dili"}
    munisipiu = munisipiu.where(~munisipiu.str.lower().isin(markets_in_dili),
                                SHEET_DEFAULT_MUNISIPIU)
    ts = (pd.to_datetime(df["timestamp"], errors="coerce", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
          if "timestamp" in df else pd.Series(iso(retrieved), index=df.index))
    out = pd.DataFrame({
        "data": pd.to_datetime(df["data"], errors="coerce", dayfirst=True).dt.strftime("%Y-%m-%d"),
        "produto": produto,
        "folin_kg_usd": pd.to_numeric(df["folin_kg_usd"], errors="coerce").round(4),
        "lokalizasaun": munisipiu,
        "folin_ts": ts.fillna(iso(retrieved)),
        "source_url": source_url,
        "fonte": "Google Sheet (Taibesi)",
    }).dropna(subset=["data", "produto", "folin_kg_usd"])
    # several entries for the same day and district -> one mean price
    return (out.groupby(["data", "produto", "lokalizasaun", "source_url", "fonte"])
               .agg(folin_kg_usd=("folin_kg_usd", "mean"), timestamp=("folin_ts", "max"),
                    n_merkadu=("folin_kg_usd", "size"))
               .reset_index().round({"folin_kg_usd": 4}))


# ---------------------------------------------------------------------------
# Merge with the existing raw file
# ---------------------------------------------------------------------------
def merge_raw(new: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Append new rows. A row already stored keeps its original timestamp
    (= when we first saw it). If the source REVISED a price, the new value
    and the new timestamp replace the old row."""
    new = new[RAW_COLUMNS]
    old = pd.read_csv(RAW_FILE, dtype={"data": str}) if RAW_FILE.exists() else None
    if old is not None and list(old.columns) != RAW_COLUMNS:
        # file from an older version of this script (e.g. per market): keep a backup
        backup = RAW_FILE.with_name(f"agri_prices_raw_old_{now_utc():%Y%m%dT%H%M%SZ}.csv")
        RAW_FILE.rename(backup)
        print(f"  Old raw file has different columns -> moved to {backup.name}")
        old = None
    if old is not None:
        combined = pd.concat([old, new], ignore_index=True)
    else:
        old = pd.DataFrame(columns=RAW_COLUMNS)
        combined = new.copy()
    combined["_p"] = combined["folin_kg_usd"].round(4)
    combined = combined.drop_duplicates(KEY + ["_p"], keep="first")   # unchanged -> keep old
    combined = combined.drop_duplicates(KEY, keep="last")             # revised -> keep new
    combined = combined.drop(columns="_p").sort_values(["produto", "lokalizasaun", "data"])
    combined["n_merkadu"] = combined["n_merkadu"].astype(int)
    added = len(combined) - len(old.drop_duplicates(KEY))
    return combined, max(added, 0)


def collect_once() -> pd.DataFrame:
    ts = now_utc()
    print(f"Rekolla dadus / collecting at {iso(ts)} (Dili: "
          f"{ts.astimezone().strftime('%Y-%m-%d %H:%M')})")
    frames, log = [], []

    # (name, download function, parse function)
    jobs = [
        ("WFP/HDX", download_wfp, parse_wfp),
    ]
    for name, download, parse in jobs:
        try:
            content, url, retrieved, status = download(ts)
            df = parse(content, url, retrieved)
            frames.append(df)
            log.append(dict(run_utc=iso(ts), fonte=name, status=status, rows=len(df),
                            source_url=url, message=f"last data {df['data'].max()}"))
            print(f"  [{name}] {status}: {len(df)} rows, latest {df['data'].max()}")
        except Exception as e:
            log.append(dict(run_utc=iso(ts), fonte=name, status="error", rows=0,
                            source_url="", message=f"{type(e).__name__}: {e}"))
            print(f"  [{name}] ERROR {e}")

    try:
        sheet, url = read_google_sheet()
        if sheet is None:
            log.append(dict(run_utc=iso(ts), fonte="Google Sheet", status="skip",
                            rows=0, source_url="", message=url))
            print(f"  [Google Sheet] skipped: {url}")
        else:
            df = parse_sheet(sheet, url, ts)
            frames.append(df)
            log.append(dict(run_utc=iso(ts), fonte="Google Sheet", status="ok",
                            rows=len(df), source_url=url, message=""))
            print(f"  [Google Sheet] ok: {len(df)} rows")
    except Exception as e:
        log.append(dict(run_utc=iso(ts), fonte="Google Sheet", status="error", rows=0,
                        source_url="", message=f"{type(e).__name__}: {e}"))
        print(f"  [Google Sheet] ERROR {e}")

    if not frames:
        log_run(log)
        raise SystemExit("No source could be collected.")

    raw, added = merge_raw(pd.concat(frames, ignore_index=True))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw.to_csv(RAW_FILE, index=False)
    for row in log:
        row["new_rows_total"] = added
    log_run(log)
    print(f"Saved {RAW_FILE.relative_to(RAW_FILE.parents[2])}: {len(raw)} rows "
          f"({added} new). Products: {sorted(raw['produto'].unique())}")
    return raw


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--loop", action="store_true",
                    help=f"keep running and collect every {POLLING_INTERVAL_HOURS} h")
    args = ap.parse_args()
    collect_once()
    while args.loop:
        print(f"Next collection in {POLLING_INTERVAL_HOURS} h ...")
        time.sleep(POLLING_INTERVAL_HOURS * 3600)
        collect_once()


if __name__ == "__main__":
    main()
