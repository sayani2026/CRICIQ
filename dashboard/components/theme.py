"""Look and feel: Royals-inspired dark theme, plain-English glossary, small HTML blocks, Plotly defaults.

Colours follow the Rajasthan Royals kit: royal pink, royal blue and gold trim on a deep navy ground.
To show an official logo, place the file at  assets/logo.png  (it is not shipped with CRICQ).
"""

import html
import re
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]

# ---- palette (dark) ----
BG = "#0A1A1F"  # page ground — deep royal navy
SIDEBAR = "#0E2127"
CARD = "#12292F"
CARD2 = "#1A2858"
LINE = "#234A52"
GRID = "#1E3B42"
TEXT = "#EAF4F2"  # 16.3:1 on BG
TEXT2 = "#B9C3E2"  # 9.6:1
MUTED = "#86A5A4"  # 7.0:1
PINK = "#14C4A3"  # Royals pink — pressure + accent (fills, bars, lines)
PINK_TEXT = "#45E0C2"  # pink for text on dark (6.6:1)
BLUE = "#9B8CFF"  # royal blue — normal
ROYAL = "#6D5BD0"  # kit blue (trim stripe, chips)
GOLD = "#F4C150"  # gold trim — top-3 and elite highlights (9.4:1)
GOOD = "#5FD6A6"
BAD = "#FF8F6B"
TRACK = "#2A4A50"
NEUTRAL = "#4E6A72"
REF = "#86A5A4"
PINK_RAMP = ["#1A2552", "#3A2560", "#62226C", "#8E1F77", "#BC1C80", "#EA1A85", "#FF8FC6"]
NAVY = TEXT  # backwards-compatible name

TEAM_SHORT = {
    "Chennai Super Kings": "CSK",
    "Delhi Capitals": "DC",
    "Gujarat Titans": "GT",
    "Kolkata Knight Riders": "KKR",
    "Lucknow Super Giants": "LSG",
    "Mumbai Indians": "MI",
    "Punjab Kings": "PBKS",
    "Rajasthan Royals": "RR",
    "Royal Challengers Bengaluru": "RCB",
    "Sunrisers Hyderabad": "SRH",
    "United Arab Emirates": "UAE",
    "United States Of America": "USA",
}


def short(team):
    return TEAM_SHORT.get(team, team)


GLOSSARY = {
    "CRICQ Score": "How well a player performs when the match is on the line. 50 = an average regular player. "
    "60+ is very good, 70+ is elite.",
    "Pressure Index": "A 0-100 rating of how much pressure a ball carries: how much it can swing the result, "
    "plus how tough the scoreboard is.",
    "Pressure ball": "A ball in the top 25% of the Pressure Index.",
    "Quality": "Runs added per pressure ball compared with an average player in exactly the same situation, "
    "adjusted for the strength of the opposition.",
    "Lift": "Does the player rise or dip? Their pressure value minus their own normal value.",
    "Consistency": "Share of pressure innings (or spells) of 6+ pressure balls where the player added value.",
    "Confidence range": "Where the score would land 90% of the time if their matches had gone slightly "
    "differently (re-sampled 300 times).",
    "Top-10 in tests": "In how many of 10 alternative set-ups (different cut-offs and weights) the player "
    "still made the top 10.",
}

LOGO = next(
    (
        p
        for p in [ROOT / "assets" / "logo.png", ROOT / "assets" / "logo.svg", ROOT / "assets" / "logo.jpg"]
        if p.exists()
    ),
    None,
)


def setup(title):
    st.set_page_config(page_title=f"{title} · CRICQ", page_icon=":material/sports_cricket:", layout="wide")
    st.logo(str(LOGO or ROOT / "assets" / "cricq_wordmark.svg"), size="large")
    st.markdown(
        f"""
<style>
  [data-testid="stAppViewContainer"] {{ background: {BG}; }}
  [data-testid="stHeader"] {{ background: {BG}; }}
  [data-testid="stSidebar"] {{ background: {SIDEBAR}; border-right: 1px solid {LINE}; }}
  [data-testid="stSidebarHeader"] img, [data-testid="stLogo"] {{ height: 2.6rem !important; max-width: 15rem; }}
  [data-testid="stAppViewContainer"]::before {{ content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px; z-index: 999990;
      background: linear-gradient(90deg, {PINK} 0 62%, {ROYAL} 62% 88%, {GOLD} 88% 100%); }}
  .block-container {{ padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1320px; }}
  h1, h2, h3 {{ color: {TEXT}; letter-spacing: -0.2px; }}
  .cq-sub {{ color: {TEXT2}; font-size: 1.02rem; margin-top: -0.6rem; margin-bottom: 1.2rem; }}
  .cq-kpi {{ border: 1px solid {LINE}; border-radius: 14px; padding: 14px 18px; background: {CARD}; height: 100%; }}
  .cq-kpi .l {{ color: {TEXT2}; font-size: 0.82rem; font-weight: 500; }}
  .cq-kpi .v {{ color: {TEXT}; font-size: 1.85rem; font-weight: 700; line-height: 1.25; margin-top: 4px; }}
  .cq-kpi .n {{ color: {MUTED}; font-size: 0.8rem; margin-top: 2px; }}
  .cq-kpi.hero {{ border-color: {PINK}; }}
  .cq-kpi.hero .v {{ color: {PINK_TEXT}; }}
  .cq-note {{ background: {CARD2}; border-radius: 12px; padding: 12px 16px; color: {TEXT}; font-size: 0.95rem; line-height: 1.55; }}
  .cq-note b {{ color: {PINK_TEXT}; }}
  .cq-cap {{ color: {TEXT2}; font-size: 0.88rem; margin: -0.3rem 0 0.4rem; }}
  .cq-pill {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
             background: #3A1838; color: #F7A8CF; margin-right: 6px; }}
  .cq-pill.blue {{ background: #1B3264; color: #B9D1FA; }}
  .cq-pill.gray {{ background: {CARD2}; color: {TEXT2}; }}
  .cq-pill.gold {{ background: #3A2E12; color: {GOLD}; }}
  .cq-step {{ border: 1px solid {LINE}; border-radius: 14px; padding: 14px 16px; height: 100%; background: {CARD}; }}
  .cq-step .h {{ font-weight: 700; color: {TEXT}; margin-bottom: 4px; }}
  .cq-step .h span {{ color: {GOLD}; }}
  .cq-step .t {{ color: {TEXT2}; font-size: 0.92rem; line-height: 1.5; }}
  .cq-brand {{ display: flex; align-items: center; gap: 10px; margin: 2px 0 6px; }}
  .cq-brand .mk {{ width: 36px; height: 36px; border-radius: 10px; background: {PINK}; display: flex; align-items: center; justify-content: center; }}
  .cq-brand .wm {{ font-weight: 800; font-size: 1.35rem; letter-spacing: 0.5px; color: {TEXT}; line-height: 1; }}
  .cq-brand .wm span {{ color: {PINK_TEXT}; }}
  .cq-brand .tg {{ font-size: 0.74rem; color: {TEXT2}; margin-top: 3px; }}
  .cq-trim {{ height: 4px; border-radius: 2px; margin: 8px 0 4px;
             background: linear-gradient(90deg, {PINK} 0 62%, {ROYAL} 62% 88%, {GOLD} 88% 100%); }}
  div[data-testid="stMetricValue"] {{ color: {TEXT}; }}

  /* ---------------- motion ---------------- */
  @keyframes cqUp {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: none; }} }}
  @keyframes cqFade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  @keyframes cqTrim {{ 0% {{ background-position: 0% 50%; }} 100% {{ background-position: 200% 50%; }} }}
  @keyframes cqShine {{ 0% {{ background-position: -200% 0; }} 100% {{ background-position: 200% 0; }} }}
  @keyframes cqPulse {{ 0%,100% {{ opacity: .55; transform: scale(1); }} 50% {{ opacity: 1; transform: scale(1.35); }} }}
  @keyframes cqDraw {{ from {{ stroke-dashoffset: 1600; }} to {{ stroke-dashoffset: 0; }} }}
  [data-testid="stAppViewContainer"]::before {{ background: linear-gradient(90deg, {PINK}, {ROYAL}, {GOLD}, {PINK}, {ROYAL}) !important;
      background-size: 200% 100% !important; animation: cqTrim 6s linear infinite; }}
  .cq-trim {{ background: linear-gradient(90deg, {PINK}, {ROYAL}, {GOLD}, {PINK}) !important; background-size: 200% 100% !important;
      animation: cqTrim 5s linear infinite; }}
  h1 {{ background: linear-gradient(100deg, {TEXT} 0%, {TEXT} 40%, {PINK_TEXT} 50%, {TEXT} 60%, {TEXT} 100%);
        background-size: 200% 100%; -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
        animation: cqUp .6s cubic-bezier(.2,.8,.2,1) both, cqShine 7s ease-in-out 1s infinite; }}
  .cq-sub {{ animation: cqUp .6s .08s cubic-bezier(.2,.8,.2,1) both; }}
  .cq-kpi, .cq-step, .cq-note {{ animation: cqUp .6s cubic-bezier(.2,.8,.2,1) both;
      transition: transform .3s cubic-bezier(.2,.8,.2,1), border-color .3s, box-shadow .3s; }}
  [data-testid="stColumn"]:nth-child(2) .cq-kpi, [data-testid="stColumn"]:nth-child(2) .cq-step {{ animation-delay: .07s; }}
  [data-testid="stColumn"]:nth-child(3) .cq-kpi, [data-testid="stColumn"]:nth-child(3) .cq-step {{ animation-delay: .14s; }}
  [data-testid="stColumn"]:nth-child(4) .cq-kpi, [data-testid="stColumn"]:nth-child(4) .cq-step {{ animation-delay: .21s; }}
  .cq-kpi:hover, .cq-step:hover {{ transform: translateY(-4px); border-color: {PINK}; box-shadow: 0 14px 34px rgba(0,0,0,.35); }}
  [data-testid="stDataFrame"], [data-testid="stPlotlyChart"], [data-testid="stTabs"] {{ animation: cqFade .7s ease both; }}
  [data-testid="stSidebarNav"] a {{ transition: transform .2s ease, background .2s ease; }}
  [data-testid="stSidebarNav"] a:hover {{ transform: translateX(4px); }}
  .stButton button, [data-testid="stPageLink"] a {{ transition: transform .2s ease, box-shadow .25s ease, border-color .25s ease; }}
  .stButton button:hover {{ transform: translateY(-2px); box-shadow: 0 8px 22px rgba(234,26,133,.28); border-color: {PINK}; }}
  [data-testid="stPageLink"] a:hover {{ transform: translateX(3px); }}
  .cq-live {{ display: inline-flex; align-items: center; gap: 8px; color: {TEXT2}; font-size: .8rem; font-weight: 600;
      letter-spacing: 1.5px; text-transform: uppercase; }}
  .cq-live i {{ width: 8px; height: 8px; border-radius: 50%; background: {PINK}; box-shadow: 0 0 12px {PINK};
      animation: cqPulse 1.6s ease-in-out infinite; }}
  .cq-wave {{ width: 100%; height: 56px; margin: -6px 0 6px; }}
  .cq-wave path {{ fill: none; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round;
      stroke-dasharray: 1600; animation: cqDraw 2.6s cubic-bezier(.4,0,.2,1) both; }}
  /* ---------------- final polish ---------------- */
  @property --cqa {{ syntax: '<angle>'; initial-value: 0deg; inherits: false; }}
  @property --cqn {{ syntax: '<integer>'; initial-value: 0; inherits: false; }}
  @keyframes cqAurora {{ 0% {{ transform: translate3d(-4%, -3%, 0) rotate(0deg) scale(1); }}
                        50% {{ transform: translate3d(3%, 2%, 0) rotate(8deg) scale(1.08); }}
                        100% {{ transform: translate3d(-2%, 4%, 0) rotate(-6deg) scale(1.02); }} }}
  @keyframes cqStars {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-600px); }} }}
  @keyframes cqBorder {{ to {{ --cqa: 360deg; }} }}
  @keyframes cqKpiCount {{ from {{ --cqn: 0; }} to {{ --cqn: var(--to); }} }}
  @keyframes cqTicker {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
  @keyframes cqGrow {{ from {{ width: 0; opacity: 0; }} to {{ width: 64px; opacity: 1; }} }}
  @keyframes cqReveal {{ from {{ opacity: 0; transform: translateY(40px) scale(.98); }} to {{ opacity: 1; transform: none; }} }}
  @keyframes cqOrb {{ 0%,100% {{ transform: translate(0,0) scale(1); }} 50% {{ transform: translate(30px,-18px) scale(1.15); }} }}

  /* living background: slow aurora + drifting star dust behind everything */
  [data-testid="stAppViewContainer"]::after {{ content: ""; position: fixed; inset: -20%; z-index: 0; pointer-events: none;
      background: radial-gradient(38% 30% at 18% 22%, rgba(234,26,133,.16), transparent 70%),
                  radial-gradient(34% 28% at 82% 18%, rgba(37,74,165,.30), transparent 70%),
                  radial-gradient(30% 26% at 70% 82%, rgba(245,184,61,.07), transparent 70%),
                  radial-gradient(40% 34% at 30% 85%, rgba(79,143,230,.12), transparent 70%);
      animation: cqAurora 26s ease-in-out infinite alternate; will-change: transform; }}
  [data-testid="stMain"]::before {{ content: ""; position: fixed; left: 0; right: 0; top: 0; height: 200vh; z-index: 0;
      pointer-events: none; opacity: .5;
      background-image: radial-gradient(1.2px 1.2px at 12% 18%, #fff, transparent), radial-gradient(1px 1px at 72% 34%, #fff, transparent),
                        radial-gradient(1.4px 1.4px at 38% 62%, #F7A8CF, transparent), radial-gradient(1px 1px at 88% 76%, #fff, transparent),
                        radial-gradient(1.2px 1.2px at 56% 88%, #B9D1FA, transparent), radial-gradient(1px 1px at 24% 44%, #fff, transparent);
      background-size: 600px 600px; animation: cqStars 90s linear infinite; }}
  [data-testid="stMain"] {{ position: relative; z-index: 1; background: transparent; }}
  [data-testid="stAppViewContainer"] > section, .block-container {{ position: relative; z-index: 1; }}

  /* glass tiles with a rotating gradient border on hover */
  .cq-kpi, .cq-step {{ background: linear-gradient(180deg, rgba(26,40,88,.78), rgba(19,31,72,.62)) padding-box,
        conic-gradient(from var(--cqa), {LINE}, {LINE}) border-box; border: 1px solid transparent;
        backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); }}
  .cq-kpi:hover, .cq-step:hover {{ background: linear-gradient(180deg, rgba(30,46,100,.9), rgba(19,31,72,.75)) padding-box,
        conic-gradient(from var(--cqa), {PINK}, {ROYAL}, {GOLD}, {PINK}) border-box; animation: cqBorder 3s linear infinite;
        border-color: transparent; }}
  .cq-kpi.hero {{ background: linear-gradient(180deg, rgba(58,24,72,.65), rgba(19,31,72,.7)) padding-box,
        conic-gradient(from var(--cqa), {PINK}, {ROYAL}, {GOLD}, {PINK}) border-box; animation: cqUp .6s both, cqBorder 5s linear infinite; }}
  .cq-kpi .v.cnt {{ counter-reset: k var(--cqn); animation: cqKpiCount 1.6s cubic-bezier(.2,.8,.2,1) both; animation-delay: .2s; --cqn: var(--to); }}
  .cq-kpi .v.cnt .c::before {{ content: counter(k); }}

  /* headings get a growing accent bar */
  [data-testid="stHeadingWithActionElements"] h3::after, [data-testid="stHeadingWithActionElements"] h2::after {{
      content: ""; display: block; height: 3px; width: 64px; margin-top: 8px; border-radius: 2px;
      background: linear-gradient(90deg, {PINK}, {GOLD}); animation: cqGrow .9s .15s cubic-bezier(.2,.8,.2,1) both; }}

  /* tabs, scrollbar, selection */
  [data-baseweb="tab-highlight"] {{ background: linear-gradient(90deg, {PINK}, {GOLD}) !important; height: 3px !important;
      box-shadow: 0 0 12px rgba(234,26,133,.6); }}
  button[data-baseweb="tab"] {{ transition: color .25s, transform .25s; }}
  button[data-baseweb="tab"]:hover {{ transform: translateY(-2px); }}
  ::selection {{ background: rgba(234,26,133,.45); color: #fff; }}
  * {{ scrollbar-width: thin; scrollbar-color: {PINK} transparent; }}
  ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
  ::-webkit-scrollbar-thumb {{ background: linear-gradient({PINK}, {ROYAL}); border-radius: 8px; }}
  [data-testid="stSidebarNav"] a[aria-current="page"] {{ background: linear-gradient(90deg, rgba(234,26,133,.28), rgba(37,74,165,.18)) !important;
      box-shadow: inset 3px 0 0 {PINK}; }}

  /* broadcast ticker */
  .cq-ticker {{ position: relative; display: flex; align-items: center; overflow: hidden; border-radius: 12px; margin: 4px 0 14px;
      background: linear-gradient(90deg, rgba(234,26,133,.12), rgba(37,74,165,.18)); border: 1px solid {LINE}; height: 42px; }}
  .cq-ticker .lab {{ flex: none; height: 100%; display: flex; align-items: center; gap: 8px; padding: 0 14px; z-index: 2;
      font-weight: 800; font-size: .74rem; letter-spacing: 1.6px; color: #fff; background: linear-gradient(90deg, {PINK}, #B5146A); }}
  .cq-ticker .lab i {{ width: 7px; height: 7px; border-radius: 50%; background: #fff; animation: cqPulse 1.4s ease-in-out infinite; }}
  .cq-ticker .track {{ display: flex; gap: 34px; white-space: nowrap; padding-left: 24px; animation: cqTicker 48s linear infinite; }}
  .cq-ticker:hover .track {{ animation-play-state: paused; }}
  .cq-ticker .it {{ color: {TEXT2}; font-size: .86rem; }}
  .cq-ticker .it b {{ color: {TEXT}; }} .cq-ticker .it em {{ font-style: normal; color: {GOLD}; font-weight: 800; margin-left: 4px; }}
  .cq-ticker .it span {{ color: {PINK_TEXT}; font-weight: 800; margin-right: 6px; }}

  /* hero panel */
  .cq-hero {{ position: relative; overflow: hidden; border-radius: 22px; padding: 22px 26px; margin: 2px 0 14px;
      border: 1px solid {LINE}; background: linear-gradient(135deg, rgba(37,74,165,.35), rgba(19,31,72,.55) 45%, rgba(234,26,133,.18)); }}
  .cq-hero .orb {{ position: absolute; border-radius: 50%; filter: blur(30px); pointer-events: none; animation: cqOrb 9s ease-in-out infinite; }}
  .cq-hero .o1 {{ width: 220px; height: 220px; background: rgba(234,26,133,.35); top: -80px; right: 8%; }}
  .cq-hero .o2 {{ width: 180px; height: 180px; background: rgba(79,143,230,.35); bottom: -90px; left: 12%; animation-delay: -4s; }}
  .cq-hero .stats {{ position: relative; display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }}
  .cq-hero .st b {{ display: block; font-size: 2.3rem; font-weight: 900; letter-spacing: -1px; line-height: 1.05;
      background: linear-gradient(90deg, #fff, #F7A8CF); -webkit-background-clip: text; background-clip: text; color: transparent; }}
  .cq-hero .st b.cnt {{ counter-reset: k var(--cqn); animation: cqKpiCount 1.8s cubic-bezier(.2,.8,.2,1) both; --cqn: var(--to); }}
  .cq-hero .st b.cnt .c::before {{ content: counter(k); }}
  .cq-hero .st > span {{ color: {TEXT2}; font-size: .84rem; }}
  .cq-hero .st {{ animation: cqUp .7s cubic-bezier(.2,.8,.2,1) both; }}
  .cq-hero .st:nth-child(2) {{ animation-delay: .08s; }} .cq-hero .st:nth-child(3) {{ animation-delay: .16s; }}
  .cq-hero .st:nth-child(4) {{ animation-delay: .24s; }}

  /* scroll-driven reveal where the browser supports it (Chrome / Edge) */
  @supports (animation-timeline: view()) {{
    [data-testid="stPlotlyChart"], [data-testid="stDataFrame"], .cq-step {{
      animation: cqReveal linear both; animation-timeline: view(); animation-range: entry 0% cover 22%; }}
  }}

  /* ---------- mobile / small screens ---------- */
  @media (max-width: 640px) {{
    .block-container {{ padding-left: .7rem !important; padding-right: .7rem !important; padding-top: 1.1rem !important; }}
    /* stack all side-by-side columns (player cards, panels) to full width */
    [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: .55rem !important; }}
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {{
        flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important; }}
    /* hero: 2 numbers per row instead of 4, smaller */
    .cq-hero {{ padding: 18px 16px !important; border-radius: 16px !important; }}
    .cq-hero .stats {{ grid-template-columns: repeat(2, 1fr) !important; gap: 14px !important; }}
    .cq-hero .st b {{ font-size: 1.7rem !important; }}
    /* headings scale down so they don't overflow */
    h1 {{ font-size: 1.85rem !important; line-height: 1.15 !important; }}
    h2 {{ font-size: 1.3rem !important; }}
    h3 {{ font-size: 1.1rem !important; }}
    .cq-sub {{ font-size: .95rem !important; }}
    /* KPI / stat tiles */
    .cq-kpi {{ padding: 12px 14px !important; }}
    .cq-kpi .v {{ font-size: 1.5rem !important; }}
    /* player cards: one per row, centered */
    .cq-flip, .cq-in, .cq-card {{ max-width: 340px !important; margin-left: auto !important; margin-right: auto !important; }}
    /* tables and charts stay inside the screen (scroll instead of overflow) */
    [data-testid="stDataFrame"], [data-testid="stPlotlyChart"] {{ max-width: 100% !important; }}
    .cq-ticker .it {{ font-size: .8rem !important; }}
  }}

  @media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation: none !important; transition: none !important; }}
    .cq-kpi .v.cnt, .cq-hero .st b.cnt {{ --cqn: var(--to); }}
  }}
</style>""",
        unsafe_allow_html=True,
    )


def brand_block():
    """Kit-trim stripe and tagline under the sidebar logo (the official logo, if placed in assets/logo.png)."""
    st.markdown(
        '<div class="cq-trim"></div><div class="cq-brand"><div><div class="tg" style="font-size:0.8rem">'
        + ("CRICQ · " if LOGO else "")
        + "Clutch intelligence for Rajasthan Royals</div></div></div>",
        unsafe_allow_html=True,
    )


def header(title, sub):
    st.title(title)
    st.markdown(f'<div class="cq-sub">{sub}</div>', unsafe_allow_html=True)


def pressure_wave():
    """Animated 'match pulse' line: calm, then a pressure spike, drawn on load (decorative)."""
    pts = [0, 2, -2, 3, -1, 2, -3, 4, -2, 1, 3, -4, 6, -5, 9, -12, 20, -26, 14, -8, 5, -3, 2, -1, 1, 0]
    step = 1200 / (len(pts) - 1)
    d = "M" + " L".join(f"{i * step:.0f},{28 - v:.0f}" for i, v in enumerate(pts))
    st.markdown(
        f"""<svg class="cq-wave" viewBox="0 0 1200 56" preserveAspectRatio="none" aria-hidden="true">
<defs><linearGradient id="cqw" x1="0" x2="1"><stop offset="0" stop-color="{BLUE}"/><stop offset=".55" stop-color="{BLUE}"/>
<stop offset=".7" stop-color="{PINK}"/><stop offset="1" stop-color="{GOLD}"/></linearGradient></defs>
<path d="{d}" stroke="url(#cqw)"/></svg>""",
        unsafe_allow_html=True,
    )


def ticker(items, label="PRESSURE RANKINGS"):
    """Broadcast-style scrolling ticker. items = [(tag, name, team, score)]; content is duplicated for a seamless loop."""
    one = "".join(
        f'<span class="it"><span>{esc(tag)}</span><b>{esc(n)}</b> · {esc(t)}<em>{s:.1f}</em></span>'
        for tag, n, t, s in items
    )
    st.markdown(
        f'<div class="cq-ticker"><div class="lab"><i></i>{esc(label)}</div><div class="track">{one}{one}</div></div>',
        unsafe_allow_html=True,
    )


def hero_stats(stats):
    """Big animated numbers. stats = [(value, caption)]; whole numbers up to 9999 count up from 0."""
    cells = "".join(
        f'<div class="st">{counted(v, cls="b").replace("<div", "<b").replace("</div>", "</b>")}<span>{esc(c)}</span></div>'
        for v, c in stats
    )
    st.markdown(
        f'<div class="cq-hero"><div class="orb o1"></div><div class="orb o2"></div><div class="stats">{cells}</div></div>',
        unsafe_allow_html=True,
    )


def live_tag(text):
    st.markdown(f'<span class="cq-live"><i></i>{esc(text)}</span>', unsafe_allow_html=True)


def esc(x):
    """Escape any data-derived text before it goes into HTML (player, team, competition names...)."""
    return html.escape(str(x), quote=True)


_NUM = re.compile(r"^(?P<pre>[^\d]{0,2})(?P<int>\d{1,4})(?P<rest>(?:\.\d+)?(?:%| cr| balls|K)?)$")


def counted(value, cls="v"):
    """Value markup that counts up from 0 when it is a simple number like 58%, ₹29.80 cr or 4 (CSS only)."""
    m = _NUM.match(str(value))
    if not m:
        return f'<div class="{cls}">{esc(value)}</div>'
    return (
        f'<div class="{cls} cnt" style="--to:{int(m["int"])}">{esc(m["pre"])}<span class="c"></span>'
        f"{esc(m['rest'])}</div>"
    )


def kpi(label, value, note="", hero=False):
    """Card with plain-text parts; everything is escaped. A list note becomes separate lines."""
    cls = "cq-kpi hero" if hero else "cq-kpi"
    n = "<br>".join(esc(x) for x in note) if isinstance(note, (list, tuple)) else esc(note)
    return f'<div class="{cls}"><div class="l">{esc(label)}</div>{counted(value)}<div class="n">{n}</div></div>'


def kpi_row(items):
    cols = st.columns(len(items))
    for c, it in zip(cols, items, strict=True):
        c.markdown(kpi(*it), unsafe_allow_html=True)


def pill(text, tone=""):
    return f'<span class="cq-pill {tone}">{esc(text)}</span>'


def caption(text):
    st.markdown(f'<div class="cq-cap">{text}</div>', unsafe_allow_html=True)


def note(text):
    st.markdown(f'<div class="cq-note">{text}</div>', unsafe_allow_html=True)


def score_word(s):
    if s >= 70:
        return "Elite"
    if s >= 60:
        return "Very good"
    if s >= 50:
        return "Above average"
    if s >= 40:
        return "Below average"
    return "Struggles"


# ---- Plotly defaults (dark) ----
_t = go.layout.Template()
_t.layout = go.Layout(
    font=dict(family="Inter, Segoe UI, sans-serif", color=TEXT, size=13),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(
        gridcolor=GRID,
        zerolinecolor=GRID,
        linecolor=GRID,
        tickfont=dict(color=TEXT2),
        title=dict(font=dict(color=TEXT2)),
    ),
    yaxis=dict(
        gridcolor=GRID,
        zerolinecolor=LINE,
        linecolor=GRID,
        tickfont=dict(color=TEXT2),
        title=dict(font=dict(color=TEXT2)),
    ),
    hoverlabel=dict(bgcolor=CARD2, bordercolor=LINE, font=dict(color=TEXT)),
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None, font=dict(color=TEXT2)),
    colorway=[BLUE, PINK, NEUTRAL],
)
pio.templates["cricq"] = _t
pio.templates.default = "cricq"
