"""
src/model.py - Data Mining: predisaun folin fos / rice price prediction
==============================================================
Input : data/processed/agri_prices_clean.csv
Output: reports/model_comparison.csv          (Model | MAE | RMSE | R2)
        reports/model_comparison_per_produto.csv
        reports/figures/actual_vs_predicted.html (+ .png if kaleido works)
        data/processed/test_predictions.csv
        data/processed/forecast_7.csv          (ARIMA, next 7 steps)
        models/*.joblib

Three models (Manual, Topic 3)
------------------------------
1. Linear Regression - predicts the NEXT price of a series from today's price,
   the lag features and the month. Simple, explainable baseline: "tomorrow's
   price = a * today's price + b * 7-day mean + ...".
2. Random Forest Regressor - same features. WHY Random Forest:
   * rice prices in Timor-Leste do not move linearly: a price far above its
     recent average tends to fall back, local rice depends on the harvest
     months, and imported rice reacts to world supply shocks; a forest of
     decision trees learns these non-linear, month-dependent rules and
     interactions (rice type x month x district) without us writing them;
   * robust to outliers (e.g. one expensive month in Atauro) and needs no
     scaling;
   * gives feature importance, which we can explain in the report.
3. ARIMA - classic time-series model for ONE series per rice type: Dili
   district (daily Taibesi sheet if it has enough data, else WFP monthly).
   Used to forecast the next 7 steps with a 95% interval for the dashboard.

Train / test: chronological 80 / 20. The cut-off date is the date where 80%
of all observations are before it. Nothing after the cut-off is used to
train (no data leakage). ARIMA test predictions are one-step-ahead: at each
test date the model only knows the prices before that date.

Usage:  python src/model.py
"""

from __future__ import annotations

import sys
import warnings
from itertools import product as iproduct
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (  # noqa: E402
    CLEAN_FILE, FIGURES_DIR, FORECAST_FILE, FORECAST_HORIZON, METRICS_FILE,
    MODELS_DIR, RANDOM_STATE, TEST_PRED_FILE, TEST_SIZE,
)

warnings.filterwarnings("ignore")   # statsmodels convergence chatter

SERIES = ["produto", "lokalizasaun", "fonte"]
NUM_FEATURES = ["folin_kg_usd", "folin_kotuk", "folin_7_loron_kotuk",
                "folin_media_7_dias", "fulan", "dia_semana", "is_dili"]
MODEL_FEATURES = ["muda_kotuk", "muda_7", "dist_media_7", "fulan", "dia_semana_diariu", "is_dili"]
MIN_DAILY_FOR_ARIMA = 60          # Taibesi sheet needs ~2 months of daily data
COLORS = {"Aktual": "#1f2937", "Linear Regression": "#2563eb",
          "Random Forest": "#16a34a", "ARIMA": "#dc2626"}


# ---------------------------------------------------------------------------
# Data for Linear Regression / Random Forest
# ---------------------------------------------------------------------------
def build_panel(df: pd.DataFrame) -> pd.DataFrame:
    """One row = one observation; target = the NEXT price of the same series."""
    df = df.sort_values(SERIES + ["data"]).copy()
    g = df.groupby(SERIES)
    df["folin_tuir"] = g["folin_kg_usd"].shift(-1)          # target
    df["data_tuir"] = g["data"].shift(-1)
    gap = (df["data_tuir"] - df["data"]).dt.days
    # only consecutive observations: next day (daily) or next month (monthly)
    max_gap = np.where(df["frekuensia"] == "loron", 3, 45)
    df = df[gap <= max_gap]
    df = df.dropna(subset=NUM_FEATURES + ["folin_tuir"])
    # Relative features (% change, in logs). Price LEVELS differ a lot between
    # districts (Atauro vs Ainaro) and rice types, and can reach values never
    # seen in training; trees cannot predict above the range they saw. So LR
    # and RF learn the CHANGE to the next price, and we convert back:
    # next = today * exp(change).
    df["muda_kotuk"] = np.log(df["folin_kg_usd"] / df["folin_kotuk"])
    df["muda_7"] = np.log(df["folin_kg_usd"] / df["folin_7_loron_kotuk"])
    df["dist_media_7"] = np.log(df["folin_kg_usd"] / df["folin_media_7_dias"])
    df["target_muda"] = np.log(df["folin_tuir"] / df["folin_kg_usd"])
    # Day of week only means something for DAILY data (Taibesi market days).
    # WFP prices are always dated the 15th, so their weekday is noise -> -1.
    df["dia_semana_diariu"] = np.where(df["frekuensia"] == "loron", df["dia_semana"], -1)
    X = pd.get_dummies(df["produto"], prefix="produto", dtype=int)
    return pd.concat([df, X], axis=1)


def feature_cols(panel: pd.DataFrame) -> list[str]:
    return MODEL_FEATURES + sorted(c for c in panel.columns if c.startswith("produto_"))


def metrics(y, p) -> dict:
    return {"MAE": mean_absolute_error(y, p),
            "RMSE": float(np.sqrt(mean_squared_error(y, p))),
            "R2": r2_score(y, p) if len(y) > 1 else np.nan,
            "n_test": len(y)}


# ---------------------------------------------------------------------------
# ARIMA helpers
# ---------------------------------------------------------------------------
def arima_series(df: pd.DataFrame, produto: str) -> tuple[pd.Series, str, str] | None:
    """Pick one regular series per product. Returns (series, lokalizasaun,
    fonte, frequency). Priority: Dili daily sheet > Dili WFP > national median."""
    d = df[df["produto"] == produto]
    daily = d[(d["frekuensia"] == "loron") & (d["lokalizasaun"] == "Dili")]
    if daily["data"].nunique() >= MIN_DAILY_FOR_ARIMA:
        s = daily.groupby("data")["folin_kg_usd"].mean()
        s = s.asfreq("D").ffill()                    # market closed -> last price
        return s, "Dili", daily["fonte"].iloc[0], "loron"
    monthly = d[d["frekuensia"] == "fulan"]
    sub = monthly[monthly["lokalizasaun"] == "Dili"] if (monthly["lokalizasaun"] == "Dili").any() else None
    if sub is not None:
        s, label, fonte = sub.set_index("data")["folin_kg_usd"], sub["lokalizasaun"].iloc[0], sub["fonte"].iloc[0]
    elif len(d):
        s, label, fonte = d.groupby("data")["folin_kg_usd"].median(), "Median nasional", d["fonte"].iloc[0]
    else:
        return None
    s = s.sort_index()
    s.index = s.index.to_period("M").to_timestamp()     # month start, regular
    s = s.groupby(level=0).mean().asfreq("MS")
    # WFP had long breaks (2009-11, 2013-14, 2018-20). Start after the last
    # break longer than 12 months. Shorter gaps (months a market did not
    # report) stay as NaN: ARIMA's Kalman filter handles missing values.
    run = s.isna().astype(int).groupby(s.notna().cumsum()).transform("sum")
    long_gap = s.isna() & (run > 12)
    if long_gap.any():
        s = s[s.index > s[long_gap].index.max()]
    return s, label, fonte, "fulan"


def fit_best_arima(y: pd.Series):
    """Small grid search on AIC: p in 0..2, d in 0..1, q in 0..2."""
    best = None
    for p, d, q in iproduct(range(3), range(2), range(3)):
        try:
            res = ARIMA(y, order=(p, d, q)).fit()
            if best is None or res.aic < best[1].aic:
                best = ((p, d, q), res)
        except Exception:
            continue
    return best


def arima_one_step(y: pd.Series, cutoff: pd.Timestamp):
    """Train on y < cutoff, then predict each test point one step ahead."""
    train, test = y[y.index < cutoff], y[y.index >= cutoff]
    if train.notna().sum() < 24 or test.notna().sum() == 0:
        return None, None, None
    order, res = fit_best_arima(train)
    preds = {}
    for t in test.index:
        if pd.notna(test[t]):                      # only score months with a real price
            preds[t] = float(res.forecast(1).iloc[0])
        res = res.append(test.loc[[t]], refit=False)   # then reveal that month
    pred = pd.Series(preds)
    return order, pred, test.loc[pred.index]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    df = pd.read_csv(CLEAN_FILE, parse_dates=["data"])
    panel = build_panel(df)
    feats = feature_cols(panel)

    # chronological 80/20 split
    panel = panel.sort_values("data").reset_index(drop=True)
    cutoff = panel["data"].iloc[int(len(panel) * (1 - TEST_SIZE))]
    train, test = panel[panel["data"] < cutoff], panel[panel["data"] >= cutoff].copy()
    print(f"Split 80/20 at {cutoff.date()}: train {len(train)} rows, test {len(test)} rows")

    lr = make_pipeline(StandardScaler(), LinearRegression())
    rf = RandomForestRegressor(n_estimators=300, max_depth=6, min_samples_leaf=10,
                               random_state=RANDOM_STATE, n_jobs=-1)
    lr.fit(train[feats], train["target_muda"])
    rf.fit(train[feats], train["target_muda"])
    test["Linear Regression"] = test["folin_kg_usd"] * np.exp(lr.predict(test[feats]))
    test["Random Forest"] = test["folin_kg_usd"] * np.exp(rf.predict(test[feats]))

    # ---- ARIMA per product, on the series used for the forecast
    fc_rows, arima_rows, arima_info = [], [], {}
    created = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    for produto in sorted(df["produto"].unique()):
        picked = arima_series(df, produto)
        if picked is None:
            continue
        y, label, fonte, freq = picked
        order, pred, actual = arima_one_step(y, cutoff)
        if order is not None:
            arima_info[produto] = (label, order)
            arima_rows.append(pd.DataFrame({"produto": produto, "lokalizasaun": label, "fonte": fonte,
                                            "data": actual.index, "ARIMA": pred.values}))
        # final model on ALL data -> next 7 steps
        order_full, res = fit_best_arima(y)
        fc = res.get_forecast(FORECAST_HORIZON)
        ci = fc.conf_int(alpha=0.05)
        for step, (when, val) in enumerate(fc.predicted_mean.items(), start=1):
            fc_rows.append({
                "produto": produto, "lokalizasaun": label, "fonte": fonte,
                "frekuensia": freq, "passu": step,
                "data_predisaun": when.date(), "folin_predisaun": round(val, 3),
                "ci_95_baixu": round(max(ci.iloc[step - 1, 0], 0), 3),
                "ci_95_aas": round(ci.iloc[step - 1, 1], 3),
                "folin_ikus": round(y.iloc[-1], 3), "data_ikus": y.index[-1].date(),
                "model": f"ARIMA{order_full}", "kriadu_iha": created,
            })
        print(f"  ARIMA {produto:<11} series={label + ' / ' + fonte:<32} freq={freq:<5} "
              f"order={order_full} n={len(y)}")

    # ---- common test set: the ARIMA series rows (one per product)
    arima_df = pd.concat(arima_rows, ignore_index=True)
    arima_df["mes"] = arima_df["data"]
    # ARIMA predicts the price AT `mes`; LR/RF predict the NEXT price. Align on the
    # target month: take the LR/RF row whose next observation is that month.
    tgt = test.copy()
    tgt["mes"] = tgt["data_tuir"].dt.to_period("M").dt.to_timestamp()
    daily = tgt["frekuensia"] == "loron"                 # Taibesi: match the exact day
    tgt.loc[daily, "mes"] = tgt.loc[daily, "data_tuir"].dt.normalize()
    common = tgt.merge(arima_df[["produto", "lokalizasaun", "fonte", "mes", "ARIMA"]],
                       on=["produto", "lokalizasaun", "fonte", "mes"], how="inner")

    models = ["Linear Regression", "Random Forest", "ARIMA"]
    rows = [{"Model": m, **metrics(common["folin_tuir"], common[m]),
             "Test set": "Dili, 1 series per rice type"} for m in models]
    rows += [{"Model": m, **metrics(test["folin_tuir"], test[m]),
              "Test set": "All districts (panel)"} for m in models[:2]]
    table = pd.DataFrame(rows)
    per = (common.groupby("produto")
           .apply(lambda g: pd.DataFrame([{"Model": m, **metrics(g["folin_tuir"], g[m])}
                                          for m in models]), include_groups=False)
           .reset_index(level=0).reset_index(drop=True))

    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    table.round(4).to_csv(METRICS_FILE, index=False)
    per.round(4).to_csv(METRICS_FILE.with_name("model_comparison_per_produto.csv"), index=False)
    pd.DataFrame(fc_rows).to_csv(FORECAST_FILE, index=False)
    keep = ["data", "data_tuir", "produto", "lokalizasaun", "fonte", "folin_kg_usd",
            "folin_tuir", "Linear Regression", "Random Forest"]
    out = test[keep].merge(common[["data", "produto", "lokalizasaun", "fonte", "ARIMA"]],
                           on=["data", "produto", "lokalizasaun", "fonte"], how="left")
    out.round(4).to_csv(TEST_PRED_FILE, index=False)

    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": lr, "features": feats}, MODELS_DIR / "linear_regression.joblib")
    joblib.dump({"model": rf, "features": feats}, MODELS_DIR / "random_forest.joblib")

    # ---- print results
    pd.set_option("display.width", 120)
    print("\n=== Model comparison (target = next price, USD/kg) ===")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\n=== Per product (common test set) ===")
    print(per.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    imp = pd.Series(rf.feature_importances_, index=feats).sort_values(ascending=False)
    imp.round(4).to_csv(METRICS_FILE.with_name("rf_feature_importance.csv"), header=["importance"])
    print("\nRandom Forest feature importance (top 6):")
    print(imp.head(6).round(3).to_string())

    plot_actual_vs_pred(common, arima_info)
    print(f"\nSaved {METRICS_FILE.name}, {FORECAST_FILE.name}, {TEST_PRED_FILE.name}, figures")


def plot_actual_vs_pred(common: pd.DataFrame, info: dict) -> None:
    prods = sorted(common["produto"].unique())
    fig = make_subplots(rows=len(prods), cols=1, shared_xaxes=False,
                        subplot_titles=[f"{p} - {info[p][0]}" for p in prods],
                        vertical_spacing=0.08)
    for i, p in enumerate(prods, start=1):
        g = common[common["produto"] == p].sort_values("data_tuir")
        for name, col in [("Aktual", "folin_tuir"), ("Linear Regression", "Linear Regression"),
                          ("Random Forest", "Random Forest"), ("ARIMA", "ARIMA")]:
            fig.add_trace(go.Scatter(
                x=g["data_tuir"], y=g[col], name=name, legendgroup=name, showlegend=(i == 1),
                mode="lines+markers", line=dict(color=COLORS[name],
                                                width=3 if name == "Aktual" else 1.6,
                                                dash=None if name == "Aktual" else "dot"),
                marker=dict(size=4)), row=i, col=1)
        fig.update_yaxes(title_text="USD/kg", row=i, col=1)
    fig.update_layout(height=280 * len(prods), template="plotly_white",
                      title=dict(text="Aktual vs Predisaun (test set) / Actual vs Predicted",
                                 y=0.99, yanchor="top"),
                      legend=dict(orientation="h", yanchor="top", y=0.955, x=0.02,
                                  yref="container"), margin=dict(t=150))
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.write_html(FIGURES_DIR / "actual_vs_predicted.html", include_plotlyjs="cdn")
    try:
        fig.write_image(FIGURES_DIR / "actual_vs_predicted.png", width=1000, scale=2)
    except Exception as e:  # kaleido needs Chrome; the HTML is enough
        print(f"  (PNG skipped: {type(e).__name__})")


if __name__ == "__main__":
    main()
