import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, theme

theme.header(
    "Rankings",
    "Every ranked batter and bowler under pressure (the Round 1 ranking), with filters for roles, teams and the "
    "IPL 2027 auction.",
)

role = st.segmented_control("Show", ["Batters", "Bowlers"], default="Batters", key="rk_role")
role = "bat" if role != "Bowlers" else "bowl"
t = data.scores(role).copy()

f1, f2, f3, f4 = st.columns([1.3, 1.1, 1.1, 1.2])
roles = sorted(t[t.eligible].role.dropna().unique())
pick_roles = f1.multiselect("Role", roles, placeholder="All roles")
if role == "bat":
    hand = f2.multiselect(
        "Batting hand",
        ["RHB", "LHB"],
        placeholder="Both",
        format_func=lambda x: {"RHB": "Right-handed", "LHB": "Left-handed"}[x],
    )
else:
    hand = f2.multiselect("Bowling", ["Pace", "Spin"], placeholder="Pace and spin")
teams = sorted(t[t.eligible].team.dropna().unique())
pick_team = f3.multiselect("Team", teams, placeholder="All teams")
search = f4.text_input("Find a player", placeholder="Type a name", max_chars=60)

has_status = "status" in t.columns
g1, g2, g3, g4 = st.columns(4)
buyable = g1.toggle(
    "Only players RR could buy in 2027",
    help="Extra filter for the auction: keeps players who are, or are likely to be, in the IPL 2027 auction pool "
    "(released, tipped for release, mixed reports, free agents, must register). Off = the full Round 1 ranking.",
    disabled=not has_status,
)
not_rr = g2.toggle("Hide Rajasthan Royals players", help="Hides players on RR's current squad.")
gone = g3.toggle(
    "Show retired / inactive players",
    help="Retired players and players with no match since 2024. They are never given a rank.",
)
show_all = g4.toggle(
    "Include players below the minimum",
    help="Players with fewer than 150 pressure balls or 12 pressure matches. "
    "Their scores are less certain and they have no rank.",
)

v = t if show_all else t[t.eligible]
if pick_roles:
    v = v[v.role.isin(pick_roles)]
if hand:
    v = v[v.bat_hand.isin(hand)] if role == "bat" else v[v.pace_spin.isin(hand)]
if pick_team:
    v = v[v.team.isin(pick_team)]
if search:
    v = v[v.display_name.str.contains(search[:60], case=False, na=False, regex=False)]
if not_rr:
    v = v[~v.at_rr]
if has_status:
    if not gone:
        v = v[v.selectable.astype(bool)]
    if buyable:
        v = v[v.in_pool.astype(bool)]
v = v.sort_values("clutch_score", ascending=False)

theme.caption(f"{len(v)} players shown. Sorted by CRICQ Score. Hover over a column title for what it means.")

rng = v.apply(lambda r: f"{r.score_lo:.0f}–{r.score_hi:.0f}" if pd.notna(r.get("score_lo")) else "—", axis=1)
tests = v.get("top10_in_variants", pd.Series(0, index=v.index)).fillna(0).astype(int).astype(str) + " / 10"
if role == "bat":
    show = pd.DataFrame(
        {
            "Rank": v["rank"],
            "Player": v.display_name,
            "Team": v.team,
            "2027 status": v.get("status_label", pd.Series("", index=v.index)),
            "Role": v.role,
            "CRICQ Score": v.clutch_score.round(1),
            "Range": rng,
            "Pressure balls": v.p_balls.astype(int),
            "SR under pressure": v.p_sr.round(1),
            "SR normally": v.n_sr.round(1),
            "Balls per dismissal (pressure)": v.p_bpd.round(1),
            "Consistency": (v.consistency * 100).round(0),
            "Top-10 in tests": tests,
        }
    )
else:
    show = pd.DataFrame(
        {
            "Rank": v["rank"],
            "Player": v.display_name,
            "Team": v.team,
            "2027 status": v.get("status_label", pd.Series("", index=v.index)),
            "Role": v.role,
            "Type": v.pace_spin,
            "CRICQ Score": v.clutch_score.round(1),
            "Range": rng,
            "Pressure balls": v.p_balls.astype(int),
            "Wickets (pressure)": v.p_wkts.astype(int),
            "Economy under pressure": v.p_econ.round(2),
            "Economy normally": v.n_econ.round(2),
            "Dot % (pressure)": v.p_dot_pct.round(1),
            "Consistency": (v.consistency * 100).round(0),
            "Top-10 in tests": tests,
        }
    )

st.dataframe(
    show,
    hide_index=True,
    use_container_width=True,
    height=520,
    column_config={
        "Rank": st.column_config.NumberColumn(format="%d"),
        "CRICQ Score": st.column_config.ProgressColumn(
            min_value=20, max_value=90, format="%.1f", help=theme.GLOSSARY["CRICQ Score"]
        ),
        "Range": st.column_config.TextColumn(help=theme.GLOSSARY["Confidence range"]),
        "Consistency": st.column_config.NumberColumn(format="%d%%", help=theme.GLOSSARY["Consistency"]),
        "Top-10 in tests": st.column_config.TextColumn(help=theme.GLOSSARY["Top-10 in tests"]),
        "Pressure balls": st.column_config.NumberColumn(help=theme.GLOSSARY["Pressure ball"]),
        "2027 status": st.column_config.TextColumn(
            help="IPL 2027 availability from dated news reports (official lists due 17 Nov 2026)."
        ),
    },
)


def _safe_csv(df):
    """Stop spreadsheet formula injection: text cells starting with = + - @ get a leading apostrophe."""
    d = df.copy()
    for c in d.columns:  # every column: text dtype differs between pandas 2 (object) and 3 (str)
        d[c] = d[c].map(lambda x: "'" + x if isinstance(x, str) and x[:1] in ("=", "+", "-", "@") else x)
    return d.to_csv(index=False).encode("utf-8-sig")


st.download_button(
    "Download this list (CSV)", _safe_csv(show), file_name=f"cricq_{role}_rankings.csv", icon=":material/download:"
)

st.write("")
st.subheader("How sure are we? Top 20 with confidence ranges")
theme.caption(
    "Dot = CRICQ Score. Line = where the score lands 90% of the time if their matches had gone slightly differently. "
    "Overlapping lines mean those players are hard to separate."
)
top = v[v.score_lo.notna()].head(20).iloc[::-1]
fig = go.Figure()
for _, r in top.iterrows():
    fig.add_shape(
        type="line",
        x0=r.score_lo,
        x1=r.score_hi,
        y0=r.display_name,
        y1=r.display_name,
        line=dict(color=theme.TRACK, width=6),
    )
fig.add_trace(
    go.Scatter(
        x=top.clutch_score,
        y=top.display_name,
        mode="markers",
        marker=dict(size=12, color=theme.PINK, line=dict(color=theme.BG, width=2)),
        showlegend=False,
        customdata=top[["score_lo", "score_hi", "p_balls"]].values,
        hovertemplate="<b>%{y}</b><br>CRICQ Score %{x:.1f}<br>Range %{customdata[0]:.0f}–%{customdata[1]:.0f}"
        "<br>%{customdata[2]:.0f} pressure balls<extra></extra>",
    )
)
fig.add_vline(
    x=50, line=dict(color=theme.REF, dash="dot"), annotation_text="Average regular player", annotation_position="top"
)
fig.update_layout(
    height=max(320, 26 * len(top) + 60), xaxis_title="CRICQ Score", yaxis=dict(gridcolor="rgba(0,0,0,0)")
)
st.plotly_chart(fig, use_container_width=True)
