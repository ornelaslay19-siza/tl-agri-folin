"""
dashboard/style.py - Visual identity for the dashboard
=======================================================
One place for colours, fonts, the Plotly chart template and the HTML pieces
(header band, price cards). app.py only calls the functions below.

Design idea (Timor-Leste):
  - background  : misty paddy-field green-grey
  - header band : deep paddy green, edged with a woven "tais" diamond
                  stripe in gold and flag red
  - accent      : gold; flag red is used ONLY for price increases
  - type        : Bricolage Grotesque (title, prices), Public Sans (text)
"""

from __future__ import annotations

import html
from urllib.parse import quote

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
BG = "#F2F5F1"          # page background (paddy mist)
SURFACE = "#FFFFFF"     # cards, charts
INK = "#16261F"         # main text
MUTED = "#5E6E66"       # secondary text
LINE = "#DCE4DE"        # borders, grid lines
PADDY = "#0F3D30"       # header, sidebar
PADDY_SOFT = "#E3EEE8"  # soft green fills
GOLD = "#E2A21B"        # accent
RED = "#C8322B"         # price up (Timor flag red)
GREEN = "#2F7D4F"       # price down

# Rice type colours, the same in every chart
COR = {
    "Fos Lokal": "#3478A6",       # local rice: river blue (paddy fields)
    "Fos Importadu": "#D99412",   # imported rice: gold
}
AREA = {"Dili": "#0F3D30", "Munisípiu seluk": "#A9BDB2"}

DISPLAY = "'Bricolage Grotesque', 'Public Sans', sans-serif"
BODY = "'Public Sans', system-ui, sans-serif"

# Woven tais stripe: diamonds in gold and red on paddy green (inline SVG)
_TAIS_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='28' height='12' viewBox='0 0 28 12'>"
    "<rect width='28' height='12' fill='#0F3D30'/>"
    "<path d='M0 6 L7 0 L14 6 L7 12 Z' fill='#E2A21B'/>"
    "<path d='M14 6 L21 0 L28 6 L21 12 Z' fill='#C8322B'/>"
    "<path d='M4 6 L7 3.5 L10 6 L7 8.5 Z' fill='#0F3D30'/>"
    "<path d='M18 6 L21 3.5 L24 6 L21 8.5 Z' fill='#F2F5F1'/>"
    "</svg>"
)
_TAIS = "data:image/svg+xml," + quote(_TAIS_SVG)


# ---------------------------------------------------------------------------
# Page CSS
# ---------------------------------------------------------------------------
def _html(block: str) -> None:
    """st.markdown ends an HTML block at a blank line, so remove blank lines."""
    st.markdown("\n".join(l for l in block.splitlines() if l.strip()), unsafe_allow_html=True)


def inject_css() -> None:
    _html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Public+Sans:wght@400;500;600&display=swap');
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
  background: {BG};
  font-family: {BODY};
  color: {INK};
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.2rem; max-width: 1280px; }}
h1, h2, h3, h4 {{ font-family: {DISPLAY}; color: {INK}; letter-spacing: -0.01em; }}

/* Sidebar: deep paddy green */
[data-testid="stSidebar"] {{ background: {PADDY}; }}
[data-testid="stSidebar"] * {{ color: #E8F0EB; }}
[data-testid="stSidebar"] h2 {{ font-size: 1.15rem; }}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] span {{ color: {PADDY}; }}
[data-testid="stSidebar"] .stButton > button {{
  background: {GOLD}; color: {PADDY}; border: 0; font-weight: 600;
}}
[data-testid="stSidebar"] .stButton > button:hover {{ background: #F0B53A; color: {PADDY}; }}
[data-testid="stSidebar"] .stButton > button * {{ color: {PADDY}; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.15); }}

/* Header band with tais edge */
.tl-hero {{
  background: {PADDY}; color: #fff; border-radius: 18px 18px 0 0;
  padding: 1.6rem 1.8rem 1.3rem; margin-top: .4rem;
}}
.tl-hero h1 {{
  color: #fff; font-size: clamp(1.6rem, 3.2vw, 2.5rem); line-height: 1.1;
  margin: 0 0 .35rem; padding: 0; font-weight: 700;
}}
.tl-hero p {{ color: #CFE0D6; margin: 0; font-size: .98rem; max-width: 68ch; }}
.tl-tais {{ height: 12px; background: url("{_TAIS}") repeat-x; border-radius: 0 0 4px 4px; }}
.tl-status {{
  display: flex; flex-wrap: wrap; gap: .6rem 1.6rem; align-items: center;
  margin-top: 1.1rem; font-size: .9rem; color: #CFE0D6;
}}
.tl-status b {{ color: #fff; font-weight: 600; }}
.tl-live {{
  display: inline-flex; align-items: center; gap: .45rem;
  background: rgba(226,162,27,0.16); color: #FBE3A8; padding: .3rem .7rem;
  border-radius: 999px; font-weight: 600;
}}
.tl-live::before {{
  content: ""; width: 8px; height: 8px; border-radius: 50%; background: {GOLD};
  box-shadow: 0 0 0 0 rgba(226,162,27,.7); animation: tl-pulse 2.4s infinite;
}}
@keyframes tl-pulse {{
  0% {{ box-shadow: 0 0 0 0 rgba(226,162,27,.6); }}
  70% {{ box-shadow: 0 0 0 9px rgba(226,162,27,0); }}
  100% {{ box-shadow: 0 0 0 0 rgba(226,162,27,0); }}
}}
@media (prefers-reduced-motion: reduce) {{ .tl-live::before {{ animation: none; }} }}

/* Sources strip */
.tl-sources {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 1px;
  background: {LINE}; border: 1px solid {LINE}; border-top: 0; border-radius: 0 0 14px 14px;
  overflow: hidden; margin-bottom: 1.4rem;
}}
.tl-sources div {{ background: {SURFACE}; padding: .8rem 1rem; font-size: .86rem; color: {MUTED}; }}
.tl-sources b {{ display: block; color: {INK}; font-weight: 600; margin-bottom: .15rem; }}

.tl-note {{
  background: #FFF6E0; border-left: 4px solid {GOLD}; color: #6A4D07;
  padding: .7rem 1rem; border-radius: 8px; font-size: .9rem; margin: -.4rem 0 1.2rem;
}}

/* Section headings */
.tl-section {{ display: flex; align-items: baseline; gap: .8rem; margin: .2rem 0 .7rem; }}
.tl-section .t {{ font-family: {DISPLAY}; font-weight: 700; font-size: 1.35rem; color: {INK}; }}
.tl-section span {{ color: {MUTED}; font-size: .88rem; }}

/* Price board */
.tl-board {{
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: .7rem; margin-bottom: 1.6rem;
}}
@media (max-width: 1150px) {{ .tl-board {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 640px)  {{ .tl-board {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.tl-card {{
  background: {SURFACE}; border: 1px solid {LINE}; border-radius: 14px;
  padding: .9rem 1rem .8rem; display: flex; flex-direction: column; gap: .25rem;
  min-height: 168px;
}}
.tl-card .name {{ display: flex; align-items: center; gap: .45rem; font-weight: 600; font-size: .95rem; white-space: nowrap; }}
.tl-card .dot {{ width: 10px; height: 10px; border-radius: 3px; flex: none; }}
.tl-card .en {{ color: {MUTED}; font-weight: 400; font-size: .78rem; margin-top: -.2rem; }}
.tl-card .price {{
  font-family: {DISPLAY}; font-weight: 700; font-size: 1.75rem; line-height: 1.1; margin-top: .2rem;
  font-variant-numeric: tabular-nums; color: {INK};
}}
.tl-card .price small {{ font-family: {BODY}; font-size: .78rem; color: {MUTED}; font-weight: 400; }}
.tl-card .chg {{ font-size: .8rem; font-weight: 600; }}
.tl-card .up {{ color: {RED}; }}
.tl-card .down {{ color: {GREEN}; }}
.tl-card .flat {{ color: {MUTED}; font-weight: 500; }}
.tl-card .meta {{ color: {MUTED}; font-size: .78rem; margin-top: auto; }}
.tl-card svg {{ display: block; margin: .15rem 0; }}
.tl-card.empty {{ background: transparent; border-style: dashed; }}
.tl-card.empty .price {{ color: #A9B6AF; }}
.tl-card.top {{ background: {PADDY}; border-color: {PADDY}; }}
.tl-card.top, .tl-card.top .price {{ color: #fff; }}
.tl-card.top .meta, .tl-card.top .en {{ color: #BFD3C7; }}
.tl-card.top .label {{ color: {GOLD}; font-weight: 600; font-size: .85rem; }}
.tl-card.cheap {{ background: {PADDY_SOFT}; border-color: {PADDY_SOFT}; }}
.tl-card.cheap .label {{ color: {GREEN}; font-weight: 600; font-size: .85rem; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: .3rem; border-bottom: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{
  background: transparent; border-radius: 10px 10px 0 0; padding: .55rem 1rem;
  font-weight: 500; color: {MUTED};
}}
.stTabs [aria-selected="true"] {{ background: {SURFACE}; color: {PADDY}; font-weight: 600; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {GOLD}; height: 3px; }}

/* Charts and tables sit on white cards */
[data-testid="stPlotlyChart"] {{
  background: {SURFACE}; border: 1px solid {LINE}; border-radius: 14px; padding: .5rem .6rem;
  overflow: hidden;
}}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
[data-testid="stExpander"] {{ background: {SURFACE}; border-radius: 12px; border-color: {LINE}; }}
.tl-foot {{ color: {MUTED}; font-size: .8rem; margin-top: 2rem; padding-top: .8rem; border-top: 1px solid {LINE}; }}
</style>
""")


# ---------------------------------------------------------------------------
# Plotly template (applied to every chart)
TEMPLATE = "plotly_white+timor"
# ---------------------------------------------------------------------------
def register_plotly_template() -> None:
    pio.templates["timor"] = go.layout.Template(layout=go.Layout(
        font=dict(family="Public Sans, sans-serif", color=INK, size=13),
        title=dict(font=dict(family="Bricolage Grotesque, sans-serif", size=17, color=INK), x=0.01),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        colorway=list(COR.values()),
        xaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor=LINE, tickcolor=LINE, zeroline=False),
        yaxis=dict(gridcolor=LINE, zeroline=False, linecolor="rgba(0,0,0,0)"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        hoverlabel=dict(bgcolor=PADDY, font=dict(color="#fff", family="Public Sans, sans-serif")),
        margin=dict(l=10, r=10, t=56, b=10),
    ))
    pio.templates.default = TEMPLATE


# ---------------------------------------------------------------------------
# HTML pieces
# ---------------------------------------------------------------------------
def hero(title: str, subtitle: str, updated: str, next_run: str, newest: str,
         sources: list[tuple[str, str]], interval_h: int) -> None:
    src = "".join(f"<div><b>{html.escape(n)}</b>{html.escape(d)}</div>" for n, d in sources)
    st.markdown(f"""
<div class="tl-hero">
  <h1>{html.escape(title)}</h1>
  <p>{html.escape(subtitle)}</p>
  <div class="tl-status">
    <span class="tl-live">Atualizadu: {updated} (Dili)</span>
    <span>Rekolla tuir mai / next collection <b>{next_run}</b></span>
    <span>Dadus foun liu / newest price <b>{newest}</b></span>
    <span>Update kada <b>{interval_h} oras</b> / every {interval_h} h</span>
  </div>
</div>
<div class="tl-tais"></div>
<div class="tl-sources">{src}</div>
""", unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="tl-note">{html.escape(text)}</div>', unsafe_allow_html=True)


def section(title: str, hint: str = "") -> None:
    st.markdown(f'<div class="tl-section"><span class="t">{html.escape(title)}</span>'
                f'<span>{html.escape(hint)}</span></div>', unsafe_allow_html=True)


def sparkline(values: list[float], color: str, w: int = 150, h: int = 34) -> str:
    """Tiny inline SVG line of the last prices (no axes, just the shape)."""
    if len(values) < 2:
        return f'<svg width="{w}" height="{h}"></svg>'
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pts = [(i * (w - 6) / (len(values) - 1) + 3, h - 4 - (v - lo) / span * (h - 8))
           for i, v in enumerate(values)]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (f'<svg width="100%" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'aria-hidden="true"><polyline points="{path}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round" '
            f'vector-effect="non-scaling-stroke"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{color}"/></svg>')


def _change(info: dict) -> str:
    """'▲ +0.05 (+3.1%)' in red when the price went up, green when down."""
    if info["prev"] is None:
        return '<span class="chg flat">&nbsp;</span>'
    d = info["folin"] - info["prev"]
    if abs(d) < 0.005:
        return '<span class="chg flat">= hanesan períodu kotuk / no change</span>'
    cls, arrow = ("up", "▲") if d > 0 else ("down", "▼")
    return (f'<span class="chg {cls}">{arrow} {d:+.2f} ({100 * d / info["prev"]:+.1f}%) '
            f'vs períodu kotuk</span>')


def rice_board(cards: dict, english: dict, dear: dict | None, cheap: dict | None,
               window: str) -> None:
    """Two rice price cards (Dili) + most expensive and cheapest district."""
    out = []
    for p, info in cards.items():
        dot = f'<span class="dot" style="background:{COR.get(p, MUTED)}"></span>'
        name = (f'<div class="name">{dot}{html.escape(p)}</div>'
                f'<div class="en">{english[p]}</div>')
        if info is None:
            out.append(f'<div class="tl-card empty">{name}<div class="price">—</div>'
                       f'<div class="meta">Seidauk iha dadus / no data yet</div></div>')
            continue
        out.append(
            f'<div class="tl-card">{name}'
            f'<div class="price">${info["folin"]:.2f} <small>/kg</small></div>{_change(info)}'
            f'{sparkline(info["hist"], COR.get(p, MUTED))}'
            f'<div class="meta">{html.escape(info["lok"])} · {info["data"]:%b %Y}</div></div>')
    for d, cls, label in [(dear, "top", "Munisípiu karun liu / Most expensive district"),
                          (cheap, "cheap", "Munisípiu baratu liu / Cheapest district")]:
        if d is None:
            continue
        out.append(
            f'<div class="tl-card {cls}"><div class="label">{label}</div>'
            f'<div class="price">{html.escape(d["name"])}</div>'
            f'<div class="en">${d["usd"]:.2f}/kg, média fos / average rice price</div>'
            f'<div class="meta">{html.escape(window)}</div></div>')
    st.markdown(f'<div class="tl-board">{"".join(out)}</div>', unsafe_allow_html=True)


def footer(text: str) -> None:
    st.markdown(f'<div class="tl-foot">{html.escape(text)}</div>', unsafe_allow_html=True)
