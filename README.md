# 🌾 Monitorizasaun no Predisaun Folin Fos Timor-Leste
### Rice Price Monitoring and Prediction for Timor-Leste

Capstone Project · **Mining and Exploring** · Siensia Komputadór · **Dili Institute of Technology (DIT)** · 2026
Topic No. 3 (Monitorizasaun no Predisaun Folin Agrikultura), focused on rice

| | |
|---|---|
| **Autor / Author** | _Naran / Name_ - _NIM_ |
| **Supervizór** | _Naran supervizór_ |
| **Dashboard** | `streamlit run dashboard/app.py` · online: _Streamlit Cloud link_ |
| **Vídeo demo** | _YouTube link_ |
| **Relatóriu** | `reports/` |

---

## 1. Deskrisaun projetu / Project description

A Python system that **collects real rice prices online every 24 hours**, cleans them, explores them
(EDA), predicts the next price with three data-mining models (Linear Regression, Random Forest, ARIMA)
and shows everything in a bilingual (Tetun + English) Streamlit dashboard.

Produtu: **Fos Lokal** (local rice) and **Fos Importadu** (imported rice). Currency: **USD/kg**.
Location: **municipality (district)**, 14 districts.

## 2. Problema / Problem statement (Timor-Leste context)

- Rice is the staple food in Timor-Leste. When the price at **Taibesi** or **Manleu** market jumps, poor
  households feel it first.
- Most rice eaten in Timor-Leste is imported, so its price follows world supply shocks (for example the
  India rice export restrictions of 2023). Local rice is grown in Baucau, Viqueque, Bobonaro and other
  districts and costs about 2.5 times more.
- Official price data exist (WFP) but are monthly, published late and scattered by market, and there is
  **no daily rice price feed for Taibesi**.

**Objetivu:** (1) monitor rice prices automatically from online sources, (2) find patterns (trend,
volatility, Dili vs other districts, local vs imported, seasonality), (3) predict the next price and the
next 7 periods, (4) present it in a dashboard that a student, trader or policy maker can use.

## 3. Arkitetura / Architecture

```
            ONLINE SOURCES (polled every 24 h)
 ┌─────────────────────────────────┐   ┌──────────────────────────────────┐
 │ WFP Food Prices Timor-Leste     │   │ Google Sheet Taibesi / Manleu    │
 │ HDX CKAN API (CSV), monthly     │   │ (typed daily, rice rows only)    │
 │ Fos Lokal, Fos Importadu        │   │ Fos Lokal, Fos Importadu (Dili)  │
 └───────────────┬─────────────────┘   └─────────────────┬────────────────┘
                 └──────────────────┬────────────────────┘
                                    ▼
  1. src/collect.py ──► data/raw/agri_prices_raw.csv   (+ timestamp, source_url)
                        data/raw/collection_log.csv     (one line per source per run)
                        data/raw/cache/                 (last good download = fallback)
                                    ▼
  2. src/preprocessing.py ──► data/processed/agri_prices_clean.csv
                              reports/data_dictionary.md
                                    ▼
  3. notebooks/eda.ipynb ──► reports/figures/eda_*.png|html
                                    ▼
  4. src/model.py ──► Linear Regression · Random Forest · ARIMA
                      reports/model_comparison.csv, figures/actual_vs_predicted
                      data/processed/forecast_7.csv, models/*.joblib
                                    ▼
  5. dashboard/app.py (Streamlit + Plotly) ──► KPI, filters, trend, forecast, models, data

  Automation: .github/workflows/collect_daily.yml runs 1 → 2 → 4 every day 06:00 Dili
```

## 4. Fonte dadus / Data sources & update interval

| Source | URL / API | Products | Source publishes | We poll |
|---|---|---|---|---|
| WFP Food Prices - Timor-Leste (HDX) | API: `https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-timor-leste` → CSV link read from the response | "Rice (white, local)" → Fos Lokal, "Rice (white, imported)" → Fos Importadu, **averaged per district** (14 districts) | monthly, 1-2 months late | **every 24 h** |
| Google Sheet Taibesi / Manleu | your published CSV link (`GSHEET_CSV_URL`) or `GSHEET_ID` + gspread | Fos Lokal, Fos Importadu (Dili) | daily (you type it) | **every 24 h** |

- **Polling interval: 24 hours**, at **06:00 Dili time** (cron `0 21 * * *` UTC) in GitHub Actions,
  or `python src/collect.py --loop` on a laptop. Defined in `src/config.py` (`POLLING_INTERVAL_HOURS`).
- **Timestamp:** every row has `timestamp` = UTC time the row was first collected. A price that the
  source later revises gets a new timestamp. Every run is logged in `data/raw/collection_log.csv`.
- **Lokalizasaun = munisípiu (district), not market.** WFP reports several markets in some districts
  (e.g. Baucau, Laga, Venilale in Baucau); `collect.py` averages them into one price per district and
  date (`n_merkadu` = how many markets were averaged). Taibesi/Manleu sheet prices are stored as **Dili**.
  Two corrections to the WFP district field (in `src/config.py`): Becora → Dili, and **Ataúro** is kept as
  its own municipality (since 2022) instead of inside Dili, because island prices are much higher.
  Numbey market (44 rice rows, 2011-13) has no district in the WFP file and is dropped (logged).
- If a website cannot be reached, the last good download in `data/raw/cache/` is used and the log
  says `status=cache` (the dashboard shows a warning).

### Set up the Taibesi Google Sheet (daily data)

1. Create a Google Sheet with row 1: `data | produto | folin_kg_usd | munisipiu | nota`
   (template: `data/manual/taibesi_template.csv`). Example row: `15/10/2026 | Fos Importadu | 0.55 | Dili | Taibesi`.
   `munisipiu` may be left empty (= Dili); the market name can go in `nota`. Several prices for the same day
   and district are averaged.
   Product names must be `Fos Lokal` or `Fos Importadu` (upper/lower case does not matter); other rows are
   skipped with a message. Tip: use a **Google Form** linked to the sheet - it adds a `Timestamp` column.
2. **Easy option (no password):** File → Share → *Publish to web* → sheet → **CSV** → copy link, then
   ```bash
   export GSHEET_CSV_URL="https://docs.google.com/spreadsheets/d/e/.../pub?output=csv"   # Windows: set GSHEET_CSV_URL=...
   ```
3. **gspread option:** create a Google Cloud service account, share the sheet with its e-mail,
   `pip install gspread`, then set `GSHEET_ID=<sheet id>` and
   `GOOGLE_APPLICATION_CREDENTIALS=path/to/service_account.json`.
4. Offline: save the sheet as `data/manual/taibesi_prices.csv`; `collect.py` reads it if no sheet is set.
5. On GitHub: add `GSHEET_CSV_URL` under *Settings → Secrets and variables → Actions*.

With **≥ 60 days** of Taibesi data, ARIMA automatically switches to that daily series, so the dashboard
forecast becomes **the next 7 days** (with only WFP data, one step = one month).

## 5. Struktura repositóriu / Folder structure

```
tl-agri-folin/
├── data/
│   ├── raw/            agri_prices_raw.csv, collection_log.csv, cache/ (WFP)
│   ├── processed/      agri_prices_clean.csv, forecast_7.csv, test_predictions.csv
│   └── manual/         taibesi_template.csv (Google Sheet columns)
├── src/
│   ├── config.py       URLs, rice products, paths, polling interval
│   ├── collect.py      1. data collection
│   ├── preprocessing.py 2. cleaning + features + data dictionary
│   └── model.py        4-5. models + evaluation + 7-step forecast
├── notebooks/eda.ipynb 3. exploratory data analysis (rice)
├── dashboard/
│   ├── app.py          6. Streamlit dashboard
│   └── style.py        visual identity: colours, fonts, chart template, price cards
├── .streamlit/config.toml  theme (light page, dark green sidebar)
├── reports/            data_dictionary.md, model_comparison*.csv, rf_feature_importance.csv, figures/
├── models/             saved Linear Regression and Random Forest
├── .github/workflows/collect_daily.yml
└── requirements.txt
```

## 6. Instalasaun / Installation

Python **3.10 or newer**.

```bash
git clone https://github.com/<your-user>/tl-agri-folin.git
cd tl-agri-folin
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 7. Oinsá halai / How to run

```bash
python src/collect.py              # 1. collect online data (once)
python src/collect.py --loop       #    ...or keep running, every 24 h
python src/preprocessing.py        # 2. clean + features + data dictionary
jupyter notebook notebooks/eda.ipynb   # 3. EDA
python src/model.py                # 4-5. train, evaluate, forecast
streamlit run dashboard/app.py     # 6. dashboard → http://localhost:8501
```
The dashboard button **"Rekolla dadus agora / Collect now"** runs steps 1, 2 and 4 again.

**Deploy free:** push to GitHub → [share.streamlit.io](https://share.streamlit.io) → main file
`dashboard/app.py`. GitHub Actions updates the data every day, Streamlit Cloud redeploys automatically.

## 8. Preprocessing

Parse dates · remove duplicates (same date + rice type + district + source) · invalid prices (≤ 0 or > 50 USD/kg)
→ missing · missing values: **forward fill** per series, then **product mean** · features:

| Feature | Meaning |
|---|---|
| `folin_kotuk` | previous observation of the same series |
| `folin_7_loron_kotuk` | last known price **at least 7 days earlier** |
| `folin_media_7_dias` | mean of the **7 previous observations** (7 days for Taibesi, 7 months for WFP) |
| `fulan`, `dia_semana`, `tinan` | month, day of week (0 = Segunda), year |

Full dictionary with types, units and missing counts: [`reports/data_dictionary.md`](reports/data_dictionary.md).
Current dataset: **1,574 rows** (Fos Lokal 739, Fos Importadu 835), 14 districts, 2008-04 → 2026-07.

## 9. Modelu / Data mining

Target: **the next rice price** of each series (next day for Taibesi, next month for WFP).
Split: **chronological 80 / 20** (cut-off 2024-10-15: 1,068 training rows, 279 test rows; no shuffling,
no future data in training).

1. **Linear Regression** - simple, explainable model.
2. **Random Forest Regressor** - *why:* rice prices in Timor-Leste are **non-linear**: a price far above
   its recent average tends to fall back, local rice depends on the harvest, imported rice reacts to world
   supply shocks, and these effects differ by rice type, month and district. A forest of decision trees
   learns these thresholds and interactions automatically, is robust to outliers (Ataúro, single spike
   months in Ermera) and gives feature importance for the report.
3. **ARIMA** (statsmodels, order chosen by AIC, p,q ∈ 0..2, d ∈ 0..1) - one series per rice type
   (Dili: daily Taibesi sheet if ≥ 60 days, else WFP monthly). Forecasts the **next 7 steps with a 95%
   interval** for the dashboard. Missing months are handled by the Kalman filter.

LR and RF learn the **% change** to the next price (log return), then convert back to USD/kg, because
price levels differ a lot between districts and rice types and trees cannot predict above the range they
saw in training.

## 10. Evaluasaun / Results (WFP data up to 2026-07)

| Model | MAE | RMSE | R² | Test set |
|---|---|---|---|---|
| **Linear Regression** | 0.118 | **0.221** | **0.897** | all districts, 279 obs |
| Random Forest | **0.117** | 0.223 | 0.895 | all districts, 279 obs |
| **Linear Regression** | **0.159** | **0.275** | **0.874** | Dili, 1 series per rice type, 30 obs |
| Random Forest | 0.180 | 0.312 | 0.837 | same |
| ARIMA | 0.206 | 0.314 | 0.835 | same |

Per rice type (Dili, 15 test months each):

| Rice type | Model | MAE | RMSE | R² |
|---|---|---|---|---|
| Fos Importadu | Linear Regression | 0.036 | **0.043** | **0.775** |
| Fos Importadu | Random Forest | 0.036 | 0.045 | 0.756 |
| Fos Importadu | ARIMA | 0.065 | 0.079 | 0.231 |
| Fos Lokal | Linear Regression | **0.282** | **0.386** | −0.045 |
| Fos Lokal | Random Forest | 0.326 | 0.439 | −0.352 |
| Fos Lokal | ARIMA | 0.348 | 0.437 | −0.341 |

Files: `reports/model_comparison.csv`, `reports/model_comparison_per_produto.csv`,
`reports/figures/actual_vs_predicted.png`.

**Interpretation**
- **Linear Regression is the best model for rice** on both test sets (lowest RMSE). Random Forest is almost
  equal across all districts (RMSE 0.223 vs 0.221, and a slightly lower MAE) but worse on Dili. With rice,
  the main pattern is simple mean reversion, which a linear model captures well.
- **Imported rice is predictable:** errors are about 4 cents/kg and R² ≈ 0.78, because the price moves
  slowly and smoothly.
- **Local rice is hard to predict one month ahead:** errors are about 30-40 cents/kg and R² is near zero or
  negative, so no model explains its month-to-month jumps well. Its price is volatile (CV 34%) and Dili
  has missing months.
- The pooled R² (0.84-0.90) is higher than the per-type R² because local rice (≈ 1.6 USD/kg) and imported
  rice (≈ 0.6 USD/kg) have very different price levels; read the per-type table for the honest picture.
- Most important RF features: distance from the 7-period mean (0.39), last change (0.27), 7-period change
  (0.26), month (0.07).

**ARIMA forecast (Dili):** Fos Importadu 0.53 USD/kg in Aug 2026 (95%: 0.47-0.59) → 0.55 in Feb 2027
(95%: 0.42-0.68); Fos Lokal stays at 1.80 USD/kg (95% in Feb 2027: 1.01-2.59).

## 11. Limitasaun / Limitations

- WFP is **monthly** and published 1-2 months late; in 2026 only 2-6 districts report rice prices per month,
  and Dili has no rice data Oct 2025 - Feb 2026. Daily Taibesi data from the Google Sheet fixes this.
- Short test period (about 2 years, 15 months per rice type in Dili); results may change as data are added.
- Local rice has a few extreme months (e.g. Ermera 4.6 and 5.3 USD/kg); they are kept as real data.

## 12. Deliverables checklist (Manual)

- [x] Online data via API / open data (WFP HDX) + Google Sheet
- [x] Polling interval documented (24 h) + timestamp on every row + collection log
- [x] Data dictionary (`reports/data_dictionary.md`)
- [x] Preprocessing (`src/preprocessing.py`)
- [x] EDA notebook (`notebooks/eda.ipynb`, figures in `reports/figures/`)
- [x] 3 models + evaluation MAE/RMSE/R² (`src/model.py`)
- [x] Dashboard (`dashboard/app.py`)
- [ ] GitHub repo public + Actions enabled
- [ ] Dashboard deployed (Streamlit Cloud link above)
- [ ] Relatóriu final (report) + PowerPoint
- [ ] Vídeo demo YouTube (link above)

## 13. Lisensa / Credits

Code: MIT. Data: World Food Programme via HDX (CC BY-IGO). Check the current licence on the source page
before publishing.
