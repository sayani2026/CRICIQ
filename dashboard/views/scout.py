"""Situation scout — rank players in any combination of cricket parameters."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, theme
from components.data import fx

theme.header(
    "Situation scout",
    "Pick the situation — phase, setting or chasing, wickets in hand, collapse, pitch type, opposition, knockout, "
    "bowler type or batter hand — and see who adds the most runs in exactly that spot.",
)
if not data.has_factors():
    st.warning("Parameters are not in the processed data yet. Run `python pipeline.py` again, then refresh.")
    st.stop()

b = data.balls()
PRESETS = {
    "Custom": {},
    "Death overs, under pressure": {"phase": ["Death"], "pressure": ["High pressure"]},
    "Finishing a chase": {"phase": ["Death"], "innings": ["Chasing"]},
    "Defending a total at the death": {"phase": ["Death"], "innings": ["Setting a total"]},
    "Rescuing a collapse": {"collapse": ["Collapse (2+ wickets in last 3 overs)"]},
    "Tail exposed (0–4 wickets in hand)": {"wickets": ["0–4 wickets in hand"]},
    "Powerplay, under pressure": {"phase": ["Powerplay"], "pressure": ["High pressure"]},
    "Knockout matches": {"stage": ["Knockout"]},
    "Low-scoring (slow) grounds": {"pitch": [x for x in b.pitch_f.cat.categories if x.startswith("Low")]},
    "High-scoring (flat) grounds": {"pitch": [x for x in b.pitch_f.cat.categories if x.startswith("High")]},
    "At RR home venues": {"rr_home": ["At RR home venues"]},
}

c1, c2, c3 = st.columns([1, 1.6, 1])
role = c1.segmented_control("Show", ["Batters", "Bowlers"], default="Bowlers", key="sc_role")
role = "bat" if role == "Batters" else "bowl"
preset = c2.selectbox("Start from a situation", list(PRESETS), index=1, key="sc_preset")
seasons = c3.select_slider("Seasons", options=list(range(2022, 2027)), value=(2022, 2026), key="sc_seasons")

facs = fx.BAT_FACTORS if role == "bat" else fx.BOWL_FACTORS
chosen = {}
with st.container(border=True):
    st.markdown("**Parameters** — leave a box empty for 'any'.")
    cols = st.columns(4)
    for i, f in enumerate(facs):
        col = fx._col(f, role)
        levels = [x for x in b[col].cat.categories if (b[col] == x).any()]
        default = [x for x in PRESETS[preset].get(f, []) if x in levels]
        chosen[f] = cols[i % 4].multiselect(
            fx.FACTORS[f], levels, default=default, key=f"sc_{role}_{preset}_{f}", placeholder="Any"
        )

d1, d2, d3 = st.columns([1, 1, 1.2])
min_balls = d1.slider("Minimum balls in this situation", 12, 300, 48, step=6, key="sc_min")
buyable = d2.toggle("Only players RR could buy", help="At least 35% chance of being in the IPL 2027 auction.")
hide_rr = d3.toggle("Hide Rajasthan Royals players")

x = b[(b.season_year >= seasons[0]) & (b.season_year <= seasons[1])]
res = fx.scout(x, role, chosen, min_balls=min_balls)
res = res[~res.player_id.isin(data.retired_ids())]  # retired / inactive players are never suggested
sc = data.scores(role)
info = sc.set_index("player_id")
pl = data.players().set_index("player_id")
res["Player"] = res.player_id.map(pl.display_name)
res["Team"] = res.player_id.map(pl.team_label).fillna("—").map(theme.short)
if "status_label" in sc.columns:
    res["2027 status"] = res.player_id.map(info.status_label).fillna("Not ranked overall")
    res["avail"] = res.player_id.map(info.avail_prob).fillna(0)
    res["is_rr"] = res.player_id.map(info.status).eq("rr_squad")
    if buyable:
        res = res[res.avail >= 0.35]
    if hide_rr:
        res = res[~res.is_rr]
res["CRICQ Score"] = res.player_id.map(info.clutch_score)

label = " · ".join(f"{fx.FACTORS[f]}: {', '.join(v)}" for f, v in chosen.items() if v) or "All situations"
theme.note(f"<b>Situation:</b> {theme.esc(label)} · seasons {seasons[0]}–{seasons[1]}. {len(res)} players qualify.")
st.write("")
if not len(res):
    st.info("No player has enough balls in this situation. Lower the minimum or widen the parameters.")
    st.stop()

top = res.head(15).iloc[::-1]
rate_lab = "Strike rate" if role == "bat" else "Economy"
fig = go.Figure(
    go.Bar(
        x=top.per100,
        y=top.Player,
        orientation="h",
        marker=dict(color=[theme.PINK if v > 0 else theme.NEUTRAL for v in top.per100], cornerradius=4),
        customdata=top[["balls", "runs", "outs", "rate"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>%{x:+.1f} runs per 100 balls vs average<br>%{customdata[0]} balls · "
            + (
                "%{customdata[1]} runs · out %{customdata[2]} · SR %{customdata[3]:.1f}"
                if role == "bat"
                else "%{customdata[1]} runs · %{customdata[2]} wkts · econ %{customdata[3]:.2f}"
            )
            + "<extra></extra>"
        ),
    )
)
fig.add_vline(x=0, line=dict(color=theme.REF))
fig.update_layout(
    height=480,
    xaxis_title=("Runs added" if role == "bat" else "Runs saved")
    + " per 100 balls vs an average player in the same spot",
    yaxis=dict(gridcolor="rgba(0,0,0,0)"),
    margin=dict(l=10, r=10, t=10, b=40),
)
st.plotly_chart(fig, use_container_width=True)

show = pd.DataFrame(
    {
        "Player": res.Player,
        "Team": res.Team,
        "2027 status": res.get("2027 status", ""),
        "Balls": res.balls,
        "Runs": res.runs,
        ("Outs" if role == "bat" else "Wickets"): res.outs,
        rate_lab: res.rate.round(2 if role == "bowl" else 1),
        "Value per 100 balls": res.per100.round(1),
        "CRICQ Score (overall)": res["CRICQ Score"].round(1),
    }
)
st.dataframe(
    show,
    hide_index=True,
    use_container_width=True,
    height=440,
    column_config={
        "Value per 100 balls": st.column_config.NumberColumn(
            format="%+.1f",
            help="Runs above an average player in the same situation, per 100 balls (shrunk for small samples)",
        )
    },
)
theme.caption(
    "Value per 100 balls compares each ball with what an average player would produce in the same match situation, "
    f"so different conditions are fair to compare. Small samples are pulled toward zero ({fx.K_BALLS} balls of 'average')."
)
