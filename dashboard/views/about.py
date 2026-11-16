from pathlib import Path

import streamlit as st

from components import auth, data, theme

ROOT = Path(__file__).resolve().parents[2]
version = (ROOT / "VERSION").read_text().strip() if (ROOT / "VERSION").exists() else "1.0.0"
rep = data.report()

theme.header("About & privacy", "What CRICQ is, where its data comes from, and how it keeps that data safe.")

a, b = st.columns(2, gap="large")
with a:
    st.subheader("About CRICQ", anchor=False)
    theme.note(
        "CRICQ is a pressure-intelligence system built for <b>Rajasthan Royals' SupeRR Selector Season 2</b> (Round 1). "
        "It rates the pressure on every ball of IPL and T20I cricket since 2022 and ranks the batters and bowlers who perform "
        "best and most reliably when the match is on the line."
    )
    st.write("")
    d = rep["data"]
    theme.kpi_row(
        [
            ("Version", version, "Release"),
            ("Data", f"{d['balls']:,} balls", f"{d['first_date'][:7]} to {d['last_date'][:7]}"),
        ]
    )
    st.write("")
    st.subheader("Independent project", anchor=False)
    theme.note(
        "CRICQ is an independent analytics project created for a competition. It is <b>not affiliated with, endorsed by "
        "or produced by</b> Rajasthan Royals, the Indian Premier League, the BCCI or the ICC. Team and competition names are "
        "used only to describe the data. No team logo is included; the colours are a tribute to the Royals' kit."
    )
with b:
    st.subheader("Privacy, in short", anchor=False)
    st.markdown("""
- **Runs on your computer.** By default the dashboard only opens on this machine (`localhost`).
- **No tracking.** No analytics, advertising or usage statistics are collected or sent anywhere.
- **No accounts, no uploads.** CRICQ does not ask for, store or process information about the people who use it.
- **Only cricket data.** It uses the six Data Pack files supplied by the organisers: match records and the names and
  on-field statistics of professional players, used only to analyse sporting performance.
- **Nothing leaves the folder.** Results are written to the project's `outputs/` and `data/processed/` folders only.
""")
    st.subheader("Security, in short", anchor=False)
    st.markdown(f"""
- Optional **password sign-in** (salted PBKDF2 hash, constant-time check, lock-out after 5 tries).
  Currently **{"ON" if auth.enabled() else "OFF"}** — see `SECURITY.md` to switch it on.
- Hardened server settings: local-only address, XSRF and CORS protection, uploads disabled, error details hidden from visitors.
- All names from the data are escaped before display; downloads are protected against spreadsheet formula injection.
- Every number is reproducible from the raw files with `python pipeline.py`; outputs carry SHA-256 checksums.
""")
st.write("")
with st.expander("Full privacy policy"):
    p = ROOT / "PRIVACY.md"
    st.markdown(p.read_text(encoding="utf-8") if p.exists() else "See PRIVACY.md in the project folder.")
with st.expander("Security policy"):
    p = ROOT / "SECURITY.md"
    st.markdown(p.read_text(encoding="utf-8") if p.exists() else "See SECURITY.md in the project folder.")
with st.expander("Open-source software used"):
    p = ROOT / "THIRD_PARTY_NOTICES.md"
    st.markdown(p.read_text(encoding="utf-8") if p.exists() else "See THIRD_PARTY_NOTICES.md in the project folder.")
