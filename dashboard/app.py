"""CRICQ dashboard — run with:  streamlit run dashboard/app.py"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from components import auth, data, theme  # noqa: E402

theme.setup("Pressure intelligence")

if not data.ready():
    st.title("CRICQ")
    st.error("No processed data yet. Run `python pipeline.py` from the project folder first, then refresh this page.")
    st.stop()

auth.require_login()
data.sync()  # new pipeline results or edited CSVs show up on the next click, no restart needed

PAGES = Path(__file__).resolve().parent / "views"
nav = st.navigation(
    {
        "Round 1 · pressure rankings": [
            st.Page(PAGES / "home.py", title="Home", icon=":material/home:", default=True),
            st.Page(PAGES / "cards.py", title="Player cards", icon=":material/style:"),
            st.Page(PAGES / "rankings.py", title="Rankings", icon=":material/leaderboard:"),
            st.Page(PAGES / "player.py", title="Player profile", icon=":material/person:"),
            st.Page(PAGES / "compare.py", title="Compare", icon=":material/compare_arrows:"),
        ],
        "Selector tools": [
            st.Page(PAGES / "scout.py", title="Situation scout", icon=":material/tune:"),
            st.Page(PAGES / "matchups.py", title="Matchups", icon=":material/swords:"),
            st.Page(PAGES / "auction.py", title="Auction board (extra)", icon=":material/gavel:"),
        ],
        "Evidence": [
            st.Page(PAGES / "match.py", title="Match replay", icon=":material/timeline:"),
            st.Page(PAGES / "how_it_works.py", title="How it works", icon=":material/menu_book:"),
            st.Page(PAGES / "about.py", title="About & privacy", icon=":material/shield_lock:"),
        ],
    }
)

with st.sidebar:
    theme.brand_block()
    st.caption("Who wins the moments that decide a match?  \nIPL + T20I · 2022–2026")
    st.markdown(
        '<div style="margin:.55rem 0 .35rem;padding:.55rem .65rem;border-radius:10px;'
        'background:rgba(245,184,61,.08);border:1px solid rgba(245,184,61,.28)">'
        '<div style="font-size:.68rem;letter-spacing:.09em;text-transform:uppercase;color:#9fb0d6">Developer</div>'
        '<div style="font-size:1rem;font-weight:800;color:#F5B83D;line-height:1.2">Sayani Dutta</div>'
        '<a href="https://github.com/sayani-dutta" target="_blank" '
        'style="font-size:.78rem;color:#4F8FE6;text-decoration:none">github.com/sayani-dutta</a>'
        "</div>",
        unsafe_allow_html=True,
    )
    with st.expander("What do the words mean?"):
        for k, v in theme.GLOSSARY.items():
            st.markdown(f"**{k}** — {v}")
    auth.logout_button()
    if st.button("Reload data", icon=":material/refresh:", help="Re-read all results from disk"):
        st.cache_data.clear()
        st.rerun()
    VERSION = (
        (Path(__file__).resolve().parents[1] / "VERSION").read_text().strip()
        if (Path(__file__).resolve().parents[1] / "VERSION").exists()
        else ""
    )
    st.caption(
        f"CRICQ v{VERSION} · built for SupeRR Selector Season 2. Independent project — not affiliated with or "
        "endorsed by Rajasthan Royals, the IPL or the BCCI."
    )

nav.run()
