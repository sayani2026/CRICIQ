"""Home — the Round 1 answer first, then the evidence, then how RR could use it at the 2027 auction."""

import pandas as pd
import streamlit as st

from components import cards, data, theme

rep = data.report()
bat, bowl = data.scores("bat"), data.scores("bowl")
mov = {r["innings"]: r for r in rep["pressure"]["wp_movement"]}
cfg = data.auction_cfg()
has_board = cfg is not None and "status" in bat.columns

theme.header(
    "Who wins the moments that decide a match?",
    "CRICQ scores the pressure on every ball of IPL and T20I cricket since 2022 and rewards the players who "
    "lift their game when it matters most — not just the ones who are good anyway.",
)

d = rep["data"]
n_ranked = int(bat["rank"].notna().sum() + bowl["rank"].notna().sum())
theme.hero_stats(
    [
        (f"{round(d['balls'] / 1000)}K", "balls rated for pressure"),
        (f"{d['matches_with_balls']}", "IPL and T20I matches since 2022"),
        (f"{n_ranked}", "batters and bowlers ranked"),
        (f"{mov[2]['share_of_wp_movement_pct']:.0f}%", "of chase swing happens on pressure balls"),
    ]
)
tb_ = bat[bat["rank"].notna()].sort_values("rank").head(10)
tw_ = bowl[bowl["rank"].notna()].sort_values("rank").head(10)
tops = pd.concat(
    [
        tb_.assign(tag="BAT #" + tb_["rank"].astype(int).astype(str)),
        tw_.assign(tag="BOWL #" + tw_["rank"].astype(int).astype(str)),
    ]
).sort_values("clutch_score", ascending=False)
theme.ticker([(r.tag, r.display_name, theme.short(r.team), r.clutch_score) for _, r in tops.iterrows()])
theme.pressure_wave()

# ---------------- 1. Round 1 answer ----------------
st.subheader("Round 1 answer · top 10 batters and bowlers under pressure")
theme.caption(
    "The 10 best-performing batters and bowlers under pressure in the supplied IPL and T20I data (2022 onwards), in rank "
    "order — exactly what the SupeRR Selector Round 1 brief asks for. Players need enough pressure evidence to be ranked "
    "(150 pressure balls and 12 pressure matches). Retired players and players with no match since 2024 are not ranked."
)


def top_table(t):
    top = t[t["rank"].notna()].sort_values("rank").head(10)
    show = pd.DataFrame(
        {
            "Rank": top["rank"].astype(int),
            "Player": top.display_name,
            "Team": top.team,
            "CRICQ Score": top.clutch_score.round(1),
            "90% range": top.score_lo.round(0).astype(int).astype(str)
            + "–"
            + top.score_hi.round(0).astype(int).astype(str),
            "Pressure balls": top.p_balls.astype(int),
            "Tests": top.get("top10_in_variants", pd.Series(0, index=top.index)).astype(int).astype(str) + "/10",
        }
    )
    st.dataframe(
        show,
        hide_index=True,
        use_container_width=True,
        height=388,
        column_config={
            "Rank": st.column_config.NumberColumn(width=50),
            "Player": st.column_config.TextColumn(width=190),
            "Team": st.column_config.TextColumn(width=190),
            "CRICQ Score": st.column_config.ProgressColumn(
                "CRICQ Score",
                min_value=40,
                max_value=90,
                format="%.1f",
                width=170,
                help=theme.GLOSSARY["CRICQ Score"],
            ),
            "90% range": st.column_config.TextColumn(width=90, help=theme.GLOSSARY["Confidence range"]),
            "Tests": st.column_config.TextColumn(width=60, help=theme.GLOSSARY["Top-10 in tests"]),
        },
    )


tb1, tb2 = st.tabs(["Top 10 batters", "Top 10 bowlers"])
for tab, t, role in ((tb1, bat, "bat"), (tb2, bowl, "bowl")):
    with tab:
        cards.grid(t, role, t[t["rank"].notna()].sort_values("rank").head(5), per_row=5, key="home")
        top_table(t)
        st.page_link("views/cards.py", label="See every player as a card", icon=":material/style:")
theme.caption(
    "Team = 2026 IPL franchise, otherwise national side. 90% range = where the score would land if his matches had gone "
    "slightly differently. Tests = in how many of 10 alternative set-ups he still makes the top 10."
)

# ---------------- 2. evidence ----------------
st.write("")
st.subheader("What the data says")
d = rep["data"]
rp = data.table("repeatability")
rp_t = rp[rp.split.str.startswith("2022")].set_index("role").correlation
i1, i2, i3 = st.columns(3)
i1.markdown(
    theme.kpi(
        "Pressure decides matches",
        f"{mov[2]['share_of_wp_movement_pct']:.0f}%",
        f"of all win-probability swing in chases happens on the {mov[2]['share_of_balls_pct']:.0f}% of balls we flag as high pressure",
    ),
    unsafe_allow_html=True,
)
i2.markdown(
    theme.kpi(
        "Bowling under pressure is a lasting skill",
        f"{rp_t['bowl']:.2f} vs {rp_t['bat']:.2f}",
        "How well 2022-24 pressure performance carries into 2025-26: bowlers vs batters (correlation). "
        "Buy pressure bowlers with confidence; treat batting form with more caution.",
    ),
    unsafe_allow_html=True,
)
i3.markdown(
    theme.kpi(
        "Data behind every number",
        f"{d['balls']:,} balls",
        f"{d['matches_with_balls']} matches ({d['ipl_matches']} IPL, {d['t20i_matches']} T20I), "
        f"{d['first_date'][:7]} to {d['last_date'][:7]}",
    ),
    unsafe_allow_html=True,
)
st.write("")
c1, c2, c3, c4 = st.columns(4)
c1.page_link("views/scout.py", label="Situation scout — any parameter", icon=":material/tune:")
c2.page_link("views/matchups.py", label="Matchups — head to head", icon=":material/swords:")
c3.page_link("views/rankings.py", label="Full rankings", icon=":material/leaderboard:")
c4.page_link("views/how_it_works.py", label="How the scores are built", icon=":material/menu_book:")

# ---------------- 3. extra: how RR would use it ----------------
st.write("")
st.subheader("Extra · how Rajasthan Royals could use this at the IPL 2027 auction")
theme.caption(
    "Not part of the Round 1 ranking. Applies the same pressure scores to the players RR could realistically buy, "
    "using dated news reports and 2026 playing time to judge who will be in the auction pool."
)
if has_board:
    a = cfg["auction"]
    bd = data.board()
    stt, plan, needs, xi = bd["state"], bd["plan"], bd["needs"], bd["xi"]
    theme.note(
        f"<b>Status as of {theme.esc(a.get('as_of', ''))}.</b> Official retention lists are due on <b>17 Nov 2026</b>. "
        "Until then each player's availability is a consensus of dated news reports plus how often his franchise picked "
        "him in 2026 — regulars like Tim David (RCB) or Rohit Sharma (MI) are treated as kept, so they are not targets."
    )
    st.write("")
    theme.kpi_row(
        [
            (
                "Purse for the auction",
                f"₹{stt['purse_cr']:.2f} cr",
                f"Reported ₹{a['salary_cap_cr']} cr cap − kept fees",
            ),
            ("Open squad slots", f"{stt['slots']}", f"{stt['overseas_slots']} of them overseas"),
            (
                "High-need roles",
                f"{int((needs.level == 'High').sum())}",
                ", ".join(needs[needs.level == "High"].label) or "None",
            ),
            ("Players released (projection)", f"{len(bd['release'])}", f"Frees ₹{stt['freed_cr']:.2f} cr"),
        ]
    )
    st.write("")
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.subheader("Auction shortlist")
        if len(plan):
            for _, r in plan.iterrows():
                tags = [
                    theme.pill(f"{r.need_level} need", "" if r.need_level == "High" else "blue"),
                    theme.pill(r.need_label, "gray"),
                ]
                if r.overseas:
                    tags.append(theme.pill("Overseas", "gold"))
                st.markdown(
                    f'<div class="cq-step" style="margin-bottom:8px"><div class="h">{int(r.slot)} · {theme.esc(r.target)} '
                    f'<span style="color:{theme.TEXT2};font-weight:500">— CRICQ Score {r.clutch_score:.0f}</span></div>'
                    f'<div class="t">{" ".join(tags)}<br>{theme.esc(r.availability)} ({r.avail_prob:.0%} chance he is in the '
                    f"auction) · Plan B: {theme.esc(r.plan_b or '—')}</div></div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No realistic targets for the open slots. Open the Auction board to change releases.")
        st.page_link("views/auction.py", label="Open the full Auction board", icon=":material/gavel:")
    with right:
        st.subheader("Projected XI + Impact Player")
        x = xi.copy()
        x["Player"] = x.player + x.overseas.map({True: " ✈", False: ""})
        st.dataframe(
            pd.DataFrame(
                {
                    "Role": x.slot.where(x.role_in_xi == "XI", "Impact Player"),
                    "Player": x.Player,
                    "Score": x.score,
                    "From": x.source,
                }
            ),
            hide_index=True,
            use_container_width=True,
            height=458,
            column_config={
                "Score": st.column_config.NumberColumn(format="%.0f", help="CRICQ Score in that role"),
            },
        )
        theme.caption("✈ = overseas (max 4 in the XI). Built from the players RR keeps plus the shortlist.")
else:
    st.warning("Run `python pipeline.py` to build the auction board.")


# ---------- developer credit ----------
st.divider()
st.markdown(
    '<div style="text-align:center;padding:1.1rem 0 .4rem">'
    '<div style="font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:#9fb0d6">Designed &amp; built by</div>'
    '<div style="font-size:1.55rem;font-weight:800;color:#F5B83D;line-height:1.3">Sayani Dutta</div>'
    '<div style="font-size:.85rem;color:#8ea2cc;margin-top:.15rem">'
    "CRICQ — an independent cricket-analytics project for Rajasthan Royals' SupeRR Selector Season 2</div>"
    '<a href="https://github.com/sayani2026" target="_blank" '
    'style="display:inline-block;margin-top:.45rem;font-size:.85rem;color:#4F8FE6;text-decoration:none">'
    "↗ github.com/sayani2026</a>"
    "</div>",
    unsafe_allow_html=True,
)
