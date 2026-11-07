"""
Konfigurasaun projetu / Project configuration
=============================================
Monitorizasaun no Predisaun Folin Fos Timor-Leste (rice prices only)
Capstone Project - Mining and Exploring - Dili Institute of Technology (DIT)

All paths, source URLs, product names and the polling interval live here,
so no other file has to hard-code them.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to the repository root, works on Windows / Mac / Linux)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CACHE_DIR = RAW_DIR / "cache"               # last good download of each source
PROCESSED_DIR = ROOT / "data" / "processed"
MANUAL_DIR = ROOT / "data" / "manual"       # Taibesi / Manleu prices typed by hand
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
MODELS_DIR = ROOT / "models"

RAW_FILE = RAW_DIR / "agri_prices_raw.csv"
COLLECTION_LOG = RAW_DIR / "collection_log.csv"
CLEAN_FILE = PROCESSED_DIR / "agri_prices_clean.csv"
FORECAST_FILE = PROCESSED_DIR / "forecast_7.csv"
TEST_PRED_FILE = PROCESSED_DIR / "test_predictions.csv"
METRICS_FILE = REPORTS_DIR / "model_comparison.csv"
DICTIONARY_FILE = REPORTS_DIR / "data_dictionary.md"
LOCAL_MANUAL_FILE = MANUAL_DIR / "taibesi_prices.csv"   # optional offline copy of the sheet

# ---------------------------------------------------------------------------
# Polling interval (manual requirement: near-real-time, documented interval)
# ---------------------------------------------------------------------------
POLLING_INTERVAL_HOURS = 24
# GitHub Actions cron is in UTC. 21:00 UTC = 06:00 in Dili (UTC+9).
POLLING_CRON_UTC = "0 21 * * *"

# ---------------------------------------------------------------------------
# Online sources
# ---------------------------------------------------------------------------
# 1) WFP Food Prices for Timor-Leste, published on HDX (Humanitarian Data
#    Exchange). We ask the CKAN API for the dataset metadata and read the
#    CSV link from it, so the code keeps working if HDX moves the file.
WFP_DATASET_ID = "wfp-food-prices-for-timor-leste"
WFP_API_URL = f"https://data.humdata.org/api/3/action/package_show?id={WFP_DATASET_ID}"
WFP_DATASET_PAGE = f"https://data.humdata.org/dataset/{WFP_DATASET_ID}"

# 2) Google Sheet where the student types daily prices from Taibesi /
#    Manleu market. Two ways to connect (set ONE as an environment variable):
#      GSHEET_CSV_URL  - "File > Share > Publish to web > CSV" link (no login)
#      GSHEET_ID       - sheet id, read with gspread + a service account JSON
#                        in GOOGLE_APPLICATION_CREDENTIALS
GSHEET_ENV_CSV = "GSHEET_CSV_URL"
GSHEET_ENV_ID = "GSHEET_ID"
GSHEET_ENV_CREDS = "GOOGLE_APPLICATION_CREDENTIALS"

HTTP_TIMEOUT = 60
HTTP_RETRIES = 3
USER_AGENT = "DIT-Capstone-TL-FolinFos/1.0 (student project, Dili)"

# ---------------------------------------------------------------------------
# Produtu / products
# ---------------------------------------------------------------------------
# Rice only. Tetun name -> English name.
# Fos Lokal = rice grown in Timor-Leste (Baucau, Viqueque, Bobonaro ...);
# Fos Importadu = imported rice, most of the rice eaten in Timor-Leste.
PRODUTU = {
    "Fos Lokal": "Local rice",
    "Fos Importadu": "Imported rice",
}

# WFP commodity name -> Tetun product name. Only these rows are kept.
WFP_COMMODITY_MAP = {
    "Rice (white, local)": "Fos Lokal",
    "Rice (white, imported)": "Fos Importadu",
}

# lokalizasaun = MUNISÍPIU (district), not the individual market.
# WFP reports several markets per municipality (e.g. Baucau, Laga, Venilale
# in Baucau); collect.py averages them into ONE district price per date.
# Corrections to the WFP "admin1" field:
#   - Becora rows (2011-13) have no admin1; Becora is in Dili.
#   - Atauro market: WFP lists it under Dili, but Ataúro is its own
#     municipality since 2022 and island prices are higher, so it is kept
#     separate (otherwise "Dili" would jump whenever only Atauro reports).
MARKET_TO_MUNISIPIU = {"Becora": "Dili", "Atauro": "Atauro"}
SHEET_DEFAULT_MUNISIPIU = "Dili"    # Taibesi and Manleu markets are in Dili

# Raw file columns. The first six are required by the project brief;
# fonte = which source; n_merkadu = how many markets were averaged.
RAW_COLUMNS = [
    "data", "produto", "folin_kg_usd", "lokalizasaun", "timestamp",
    "source_url", "fonte", "n_merkadu",
]

FORECAST_HORIZON = 7      # steps ahead (days for daily data, months for monthly)
TEST_SIZE = 0.20          # 80 / 20 chronological split
RANDOM_STATE = 42
