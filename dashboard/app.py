"""
dashboard/app.py - Dashboard Folin Fos Timor-Leste (Streamlit)
==============================================================
Capstone Project DIT - Mining and Exploring - Topic 3
Rice only: Fos Lokal (local rice) and Fos Importadu (imported rice).

Run from the repository root:
    streamlit run dashboard/app.py

Reads the files made by the pipeline:
    data/processed/agri_prices_clean.csv   (src/preprocessing.py)
    data/processed/forecast_7.csv          (src/model.py, ARIMA)
    reports/model_comparison.csv           (src/model.py)
    reports/model_comparison_per_produto.csv
    data/raw/collection_log.csv            (src/collect.py)
The button "Rekolla dadus agora" runs the whole pipeline again.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "dashboard"))
from config import (  # noqa: E402
    CLEAN_FILE, COLLECTION_LOG, FORECAST_FILE, METRICS_FILE,
    POLLING_INTERVAL_HOURS, PRODUTU,
)

import style  # noqa: E402  (dashboard/style.py: colours, fonts, cards)
from style import AREA, COR, PADDY  # noqa: E402

DILI_TZ = ZoneInfo("Asia/Dili")
HOTU = "Hotu / All"
PER_PRODUCT_FILE = METRICS_FILE.with_name("model_comparison_per_produto.csv")

st.set_page_config(page_title="Folin Fos TL", page_icon="🌾", layout="wide")
style.inject_css()
style.register_plotly_template()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600)          # re-read the files at most once per hour
def load():
    df = pd.read_csv(CLEAN_FILE, parse_dates=["data"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    fc = pd.read_csv(FORECAST_FILE, parse_dates=["data_predisaun", "data_ikus"]) \
        if FORECAST_FILE.exists() else pd.DataFrame()
    metrics = pd.read_csv(METRICS_FILE) if METRICS_FILE.exists() else pd.DataFrame()
    per = pd.read_csv(PER_PRODUCT_FILE) if PER_PRODUCT_FILE.exists() else pd.DataFrame()
    log = pd.read_csv(COLLECTION_LOG, parse_dates=["run_utc"]) \
        if COLLECTION_LOG.exists() else pd.DataFrame()
    return df, fc, metrics, per, log


def run_pipeline() -> tuple[bool, str]:
    out = []
    for script in ["collect.py", "preprocessing.py", "model.py"]:
        r = subprocess.run([sys.executable, str(ROOT / "src" / script)],
                           capture_output=True, text=True, cwd=ROOT)
        out.append(f"$ python src/{script}\n{r.stdout[-1500:]}{r.stderr[-800:]}")
        if r.returncode != 0:
            return False, "\n".join(out)
    return True, "\n".join(out)


def current_price(df: pd.DataFrame, produto: str) -> dict | None:
    """Latest rice price for the price card. Priority: Dili from the daily
    Taibesi sheet, then Dili district (WFP), then the median of all districts.
    Also returns the last 18 prices for the sparkline."""
    d = df[df["produto"] == produto]
    if d.empty:
        return None
    for mask, label in [
        (d["fonte"].str.startswith("Google Sheet") & (d["lokalizasaun"] == "Dili"), "Dili (Taibesi)"),
        (d["lokalizasaun"] == "Dili", "Dili"),
    ]:
        s = d[mask].sort_values("data")
        if len(s):
            break
    else:
        s, label = d.groupby("data", as_index=False)["folin_kg_usd"].median(), "Median nasional"
    series = s.groupby("data")["folin_kg_usd"].median()
    return {"folin": series.iloc[-1], "prev": series.iloc[-2] if len(series) > 1 else None,
            "data": series.index[-1], "lok": label, "hist": series.tail(18).tolist()}


def district_extremes(df: pd.DataFrame) -> tuple[dict | None, dict | None, str]:
    """Most expensive and cheapest district: mean rice price (both types) over
    the last 12 months of WFP data. Districts with < 3 prices are skipped."""
    w = df[df["fonte"] == "WFP/HDX"]
    if w.empty:
        return None, None, ""
    end = w["data"].max()
    start = end - pd.DateOffset(months=12) + pd.Timedelta(days=1)
    g = w[w["data"] >= start].groupby("lokalizasaun")["folin_kg_usd"].agg(["mean", "count"])
    g = g[g["count"] >= 3]
    if g.empty:
        return None, None, ""
    hi, lo = g["mean"].idxmax(), g["mean"].idxmin()
    window = f"12 fulan ikus / last 12 months ({start:%b %Y} – {end:%b %Y})"
    return ({"name": hi, "usd": g.loc[hi, "mean"]}, {"name": lo, "usd": g.loc[lo, "mean"]}, window)


def show(fig) -> None:
    """Every chart uses the dashboard template (fonts, colours, white card)."""
    fig.update_layout(template=style.TEMPLATE, paper_bgcolor=style.SURFACE,
                      plot_bgcolor=style.SURFACE, font=dict(family="Public Sans, sans-serif"),
                      title_font=dict(family="Bricolage Grotesque, sans-serif", size=17,
                                      color=style.INK))
    st.plotly_chart(fig, width="stretch", theme=None)


df, fc, metrics, per, log = load()

# ---------------------------------------------------------------------------
# Header band
# ---------------------------------------------------------------------------
last_run = log["run_utc"].max() if len(log) else df["timestamp"].max()
last_run = pd.Timestamp(last_run).tz_localize("UTC") if pd.Timestamp(last_run).tzinfo is None \
    else pd.Timestamp(last_run)
last_run_dili = last_run.tz_convert(DILI_TZ)
next_run = last_run_dili + timedelta(hours=POLLING_INTERVAL_HOURS)

style.hero(
    title="Dashboard Folin Fos Timor-Leste – Real Time",
    subtitle="Monitorizasaun no predisaun folin Fos Lokal no Fos Importadu kada munisípiu. "
             "Rice price monitoring and prediction by district, in USD/kg.",
    updated=f"{last_run_dili:%d-%m-%Y %H:%M}",
    next_run=f"{next_run:%d-%m-%Y %H:%M}",
    newest=f"{df['data'].max():%d-%m-%Y}",
    interval_h=POLLING_INTERVAL_HOURS,
    sources=[
        ("WFP Food Prices Timor-Leste", "HDX API · Fos Lokal no Fos Importadu · média kada munisípiu, "
                                        "kada fulan / district average, monthly"),
        ("Google Sheet Taibesi / Manleu", "Dili · folin fos kada loron hatama husi merkadu / "
                                          "daily rice prices typed at the market"),
    ],
)

if len(log):
    latest = log[log["run_utc"] == log["run_utc"].max()]
    if (latest["status"] == "cache").any():
        style.note("Koneksaun ba fonte online falla iha rekolla ikus, entaun dadus mai husi download "
                   "ikus ne'ebé di'ak (cache). / The online source could not be reached in the last run; "
                   "showing the last good download.")

# ---------------------------------------------------------------------------
# Price board (KPI cards)
# ---------------------------------------------------------------------------
style.section("Folin fos agora / Current rice price", "USD/kg · kompara ho períodu kotuk / vs previous period")
cards = {p: current_price(df, p) for p in PRODUTU}
dear, cheap, window = district_extremes(df)
style.rice_board(cards, PRODUTU, dear, cheap, window)

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Filtru / Filters")
    produtos = st.multiselect("Tipu fos / Rice type", list(PRODUTU),
                              default=[p for p in PRODUTU if p in df["produto"].unique()])
    lok_all = sorted(df["lokalizasaun"].unique())
    default_lok = [l for l in lok_all if l in ("Dili", "Baucau", "Bobonaro")]
    lokais = st.multiselect("Munisípiu / District", [HOTU] + lok_all, default=default_lok)
    if HOTU in lokais or not lokais:
        lokais = lok_all
    dmin, dmax = df["data"].min().date(), df["data"].max().date()
    start_default = max(dmin, pd.Timestamp("2020-05-01").date())
    period = st.date_input("Períodu / Date range", (start_default, dmax), min_value=dmin, max_value=dmax)
    st.divider()
    if st.button("Rekolla dadus agora / Collect now", width="stretch"):
        with st.spinner("Rekolla, prosesa no treina modelu... / collecting, cleaning, training..."):
            ok, out = run_pipeline()
        st.cache_data.clear()
        (st.success if ok else st.error)("Remata! / Done." if ok else "Erro / Error")
        with st.expander("Log"):
            st.code(out)

if not produtos:
    produtos = list(PRODUTU)
d0, d1 = (period if isinstance(period, (list, tuple)) and len(period) == 2 else (start_default, dmax))
in_period = df["data"].between(pd.Timestamp(d0), pd.Timestamp(d1))
f = df[df["produto"].isin(produtos) & df["lokalizasaun"].isin(lokais) & in_period]

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["Tendénsia / Trend", "Predisaun 7 / Forecast",
                                  "Modelu / Models", "Dadus / Data"])

with tab1:
    if f.empty:
        st.warning("La iha dadus ba filtru ne'e. / No data for this filter.")
    else:
        line = f.groupby(["data", "produto", "lokalizasaun"])["folin_kg_usd"].mean().reset_index()
        fig = px.line(line, x="data", y="folin_kg_usd", color="lokalizasaun", line_dash="produto",
                      markers=True, color_discrete_map={"Dili": PADDY},
                      color_discrete_sequence=["#D99412", "#3478A6", "#8A5BA6", "#C8322B", "#4E9A3A",
                                               "#6B3E26", "#2A9D8F", "#B5838D", "#7A7A7A"],
                      labels={"lokalizasaun": "Munisípiu", "produto": "Fos"})
        fig.update_traces(line=dict(width=2.2), marker=dict(size=5))
        fig.update_layout(title="Tendénsia folin fos kada munisípiu / Rice price trend by district",
                          yaxis_title="USD/kg", xaxis_title="", height=500, hovermode="x unified",
                          legend=dict(orientation="h", y=-0.12, yanchor="top", x=0, title=""),
                          margin=dict(t=60, b=90))
        show(fig)

    a, b = st.columns(2)
    # Both comparisons use ALL districts (WFP only: same source, same method),
    # so the district filter does not hide the ranking.
    wfp = df[df["produto"].isin(produtos) & (df["fonte"] == "WFP/HDX") & in_period]
    with a:
        if wfp.empty:
            st.info("La iha dadus WFP iha períodu ne'e. / No WFP data in this period.")
        else:
            avg = wfp.groupby("lokalizasaun")["folin_kg_usd"].mean().sort_values().reset_index()
            avg["area"] = avg["lokalizasaun"].eq("Dili").map({True: "Dili", False: "Munisípiu seluk"})
            fig = px.bar(avg, y="lokalizasaun", x="folin_kg_usd", color="area", orientation="h",
                         text_auto=".2f", color_discrete_map=AREA,
                         title="Folin média kada munisípiu / Average price by district")
            fig.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, xaxis_title="USD/kg", yaxis_title="", height=480,
                              bargap=0.3, yaxis=dict(categoryorder="total ascending"),
                              xaxis=dict(range=[0, avg["folin_kg_usd"].max() * 1.15]))
            show(fig)
    with b:
        if not wfp.empty:
            cmp = (wfp.assign(area=wfp["lokalizasaun"].eq("Dili").map({True: "Dili", False: "Munisípiu seluk"}))
                   .groupby(["produto", "area"])["folin_kg_usd"].mean().reset_index())
            fig = px.bar(cmp, x="produto", y="folin_kg_usd", color="area", barmode="group",
                         text_auto=".2f", color_discrete_map=AREA,
                         title="Dili vs munisípiu seluk / Dili vs other districts")
            fig.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False)
            fig.update_layout(yaxis_title="USD/kg", xaxis_title="", legend_title="", height=480,
                              bargap=0.3, margin=dict(t=90),
                              legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0))
            show(fig)

with tab2:
    if fc.empty:
        st.warning("Seidauk iha predisaun. Halai `python src/model.py`. / No forecast yet.")
    else:
        fp = fc[fc["produto"].isin(produtos)]
        freq = "loron / days" if (fp["frekuensia"] == "loron").all() else "períodu / steps"
        st.markdown(f"**Predisaun ARIMA ba 7 {freq} tuir mai** · ARIMA forecast, 95% interval")
        if (fp["frekuensia"] == "fulan").any():
            st.caption("WFP publika dadus kada fulan, entaun passu ida = fulan ida. Bainhira Google Sheet "
                       "Taibesi iha ≥ 60 loron dadus, predisaun sai kada loron. / WFP is monthly: one step "
                       "= one month. With ≥ 60 days of Taibesi data the forecast becomes daily.")
        pick = st.selectbox("Tipu fos ba grafiku / Rice type for the chart", sorted(fp["produto"].unique()))
        g = fp[fp["produto"] == pick]
        hist = df[(df["produto"] == pick) & (df["lokalizasaun"] == g["lokalizasaun"].iloc[0])
                  & (df["fonte"] == g["fonte"].iloc[0])]
        if hist.empty:   # e.g. national median series
            hist = df[(df["produto"] == pick)].groupby("data", as_index=False)["folin_kg_usd"].median()
        hist = hist.sort_values("data").tail(36)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist["data"], y=hist["folin_kg_usd"], name="Aktual / Actual",
                                 mode="lines+markers", line=dict(color=COR.get(pick, PADDY), width=2.2)))
        fig.add_trace(go.Scatter(x=pd.concat([g["data_predisaun"], g["data_predisaun"][::-1]]),
                                 y=pd.concat([g["ci_95_aas"], g["ci_95_baixu"][::-1]]),
                                 fill="toself", fillcolor="rgba(226,162,27,0.18)",
                                 mode="lines", line=dict(width=0), name="95% interval",
                                 hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=g["data_predisaun"], y=g["folin_predisaun"], name="Predisaun",
                                 mode="lines+markers", line=dict(color=PADDY, dash="dash", width=2.2)))
        fig.update_layout(title=f"{pick} - {g['lokalizasaun'].iloc[0]} ({g['model'].iloc[0]})",
                          yaxis_title="USD/kg", height=400, legend=dict(orientation="h", y=-0.15))
        show(fig)

        # One row = one step; each cell shows the price and its own date.
        when = fp["data_predisaun"].dt.strftime("%b %Y").where(
            fp["frekuensia"] == "fulan", fp["data_predisaun"].dt.strftime("%d-%m-%Y"))
        fp = fp.assign(sel=fp["folin_predisaun"].map("${:.2f}".format) + "  (" + when + ")"
                       + "  [" + fp["ci_95_baixu"].map("{:.2f}".format) + "–"
                       + fp["ci_95_aas"].map("{:.2f}".format) + "]")
        table = fp.pivot(index="passu", columns="produto", values="sel").reset_index()
        table = table.rename(columns={"passu": "Passu / Step"})
        st.markdown("**Tabela predisaun / Forecast table (USD/kg, [intervalu 95%])**")
        st.dataframe(table, hide_index=True, width="stretch")
        st.caption("Serie / series: " + "; ".join(
            f"{p}: {s} {m}" for p, s, m in fp.groupby("produto")[["lokalizasaun", "model"]].first()
            .itertuples()) + f" · kriadu iha / created {fp['kriadu_iha'].iloc[0]}")

with tab3:
    if metrics.empty:
        st.warning("Halai `python src/model.py`.")
    else:
        st.markdown("**Komparasaun modelu / Model comparison** · Linear Regression, Random Forest, ARIMA · "
                    "target = folin tuir mai (next price), test = 20% dadus ikus (chronological split)")
        fmt = {"MAE": "{:.3f}", "RMSE": "{:.3f}", "R2": "{:.3f}"}
        for test_set, part in metrics.groupby("Test set", sort=False):
            st.markdown(f"*Test set: {test_set}* · MAE no RMSE ki'ik liu = di'ak liu (matak / green)")
            st.dataframe(part.drop(columns="Test set").style.format(fmt)
                         .highlight_min(subset=["MAE", "RMSE"], color="#D7EBDD")
                         .highlight_max(subset=["R2"], color="#D7EBDD"),
                         hide_index=True, width="stretch")
        if not per.empty:
            st.markdown("*Kada tipu fos / per rice type (Dili)*")
            st.dataframe(per.style.format(fmt), hide_index=True, width="stretch")
        st.caption("R² ba fos hotu hamutuk aas liu tanba Fos Lokal no Fos Importadu iha nível folin "
                   "diferente; haree mós tabela kada tipu fos. / Pooled R² is higher because local and "
                   "imported rice have different price levels; also read the per-rice-type table.")
        png = ROOT / "reports" / "figures" / "actual_vs_predicted.png"
        with st.expander("Aktual vs Predisaun (test set) / Actual vs predicted"):
            if png.exists():
                st.image(str(png), width="stretch")
            else:
                st.caption("Grafiku PNG seidauk iha: instala `kaleido` no halai `python src/model.py`. "
                           "Versaun interativa: reports/figures/actual_vs_predicted.html")

with tab4:
    tbl = f.sort_values("data", ascending=False)[
        ["data", "produto", "folin_kg_usd", "lokalizasaun", "n_merkadu", "fonte", "timestamp", "source_url"]]
    st.dataframe(tbl, hide_index=True, width="stretch",
                 column_config={"data": st.column_config.DateColumn("data"),
                                "source_url": st.column_config.LinkColumn("source_url")})
    st.download_button("Download CSV", tbl.to_csv(index=False).encode("utf-8"),
                       "folin_fos_tl.csv", "text/csv")
    if len(log):
        with st.expander("Log rekolla dadus / Collection log"):
            st.dataframe(log.sort_values("run_utc", ascending=False), hide_index=True,
                         width="stretch")

style.footer("Capstone Project · Mining and Exploring · Dili Institute of Technology (DIT) 2026 · "
             "Dadus: WFP/HDX, merkadu Taibesi")
