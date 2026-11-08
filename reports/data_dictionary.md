# Data Dictionary - Folin Fos Timor-Leste

Generated automatically by `src/preprocessing.py` on 2026-11-08 09:16 (Dili time).

## 1. Raw file `data/raw/agri_prices_raw.csv`

1587 rows. One row = one price for one product, in one district (munisípiu), on one date, from one source.
WFP prices of several markets in the same district are averaged (`n_merkadu`).

| Kolúna / Column | Tipu / Type | Deskrisaun / Description | Unidade / Unit | Missing |
|---|---|---|---|---|
| `data` | datetime64[us] | Data folin nian / date of the price observation (WFP: 15th of the month) | YYYY-MM-DD | 0 (0.0%) |
| `produto` | str | Naran produtu / product: Fos Lokal (local rice), Fos Importadu (imported rice) | text | 0 (0.0%) |
| `folin_kg_usd` | float64 | Folin retalhu ba kg ida / retail price per kg | USD/kg | 0 (0.0%) |
| `lokalizasaun` | str | Munisípiu / district (Dili, Baucau, Bobonaro, Atauro ...) | text | 0 (0.0%) |
| `timestamp` | datetime64[us, UTC] | Tempu ne'ebé dadus rekolla / UTC time the row was collected | ISO 8601 UTC | 0 (0.0%) |
| `source_url` | str | Ligasaun fonte / URL of the online source | URL | 0 (0.0%) |
| `fonte` | str | Fonte / source: WFP/HDX or Google Sheet (Taibesi) | text | 0 (0.0%) |
| `n_merkadu` | int64 | Numeru merkadu iha munisípiu ne'ebé halo media / markets averaged | count | 0 (0.0%) |

## 2. Clean file `data/processed/agri_prices_clean.csv`

1587 rows.

| Kolúna / Column | Tipu / Type | Deskrisaun / Description | Unidade / Unit | Missing |
|---|---|---|---|---|
| `data` | datetime64[us] | Data folin nian / date of the price observation (WFP: 15th of the month) | YYYY-MM-DD | 0 (0.0%) |
| `produto` | str | Naran produtu / product: Fos Lokal (local rice), Fos Importadu (imported rice) | text | 0 (0.0%) |
| `folin_kg_usd` | float64 | Folin retalhu ba kg ida / retail price per kg | USD/kg | 0 (0.0%) |
| `lokalizasaun` | str | Munisípiu / district (Dili, Baucau, Bobonaro, Atauro ...) | text | 0 (0.0%) |
| `timestamp` | datetime64[us, UTC] | Tempu ne'ebé dadus rekolla / UTC time the row was collected | ISO 8601 UTC | 0 (0.0%) |
| `source_url` | str | Ligasaun fonte / URL of the online source | URL | 0 (0.0%) |
| `fonte` | str | Fonte / source: WFP/HDX or Google Sheet (Taibesi) | text | 0 (0.0%) |
| `n_merkadu` | int64 | Numeru merkadu iha munisípiu ne'ebé halo media / markets averaged | count | 0 (0.0%) |
| `folin_imputadu` | bool | True if the price was missing and filled (ffill / mean) | bool | 0 (0.0%) |
| `folin_kotuk` | float64 | Folin observasaun anterior / previous observation of the series | USD/kg | 28 (1.8%) |
| `folin_media_7_dias` | float64 | Media folin 7 observasaun anterior / mean of 7 previous observations | USD/kg | 28 (1.8%) |
| `folin_7_loron_kotuk` | float64 | Folin ikus husi loron 7 ka liu kotuk / last price >= 7 days before | USD/kg | 28 (1.8%) |
| `frekuensia` | str | Frekuénsia serie / 'loron' = daily, 'fulan' = monthly | text | 0 (0.0%) |
| `tinan` | int32 | Tinan / year | year | 0 (0.0%) |
| `fulan` | int32 | Fulan / month 1-12 | month | 0 (0.0%) |
| `dia_semana` | int32 | Loron semana / day of week 0=Segunda ... 6=Domingu | 0-6 | 0 (0.0%) |
| `dia_semana_naran` | str | Naran loron semana / day name in Tetun | text | 0 (0.0%) |
| `is_dili` | int64 | 1 se munisípiu Dili / 1 if the district is Dili | 0/1 | 0 (0.0%) |

Missing values in `folin_kotuk`, `folin_7_loron_kotuk` and `folin_media_7_dias` are expected:
they are the first observation(s) of each series, where no earlier price exists.
The models drop those rows.

## 3. Cleaning report

| Step | Rows |
|---|---|
| Raw rows | 1587 |
| Exact duplicates removed | 0 |
| Same date/product/market duplicates removed | 0 |
| Invalid prices (<= 0 or > 50 USD/kg) set to missing | 0 |
| Missing prices before filling | 0 |
| Missing prices after filling | 0 |

## 4. Coverage per source and product

| Fonte | Produto | Rows | First | Last |
|---|---|---|---|---|
| WFP/HDX | Fos Importadu | 843 | 2011-10-15 | 2026-09-15 |
| WFP/HDX | Fos Lokal | 744 | 2008-04-15 | 2026-09-15 |
