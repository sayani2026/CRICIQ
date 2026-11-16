"""Matchups — batter vs bowler types and head-to-head records, normal and under pressure."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, theme

theme.header(
    "Matchups",
    "Who a player dominates and who troubles him — by bowler type, batter hand and head to head. "
    "Use it to plan which of RR's bowlers to bring on, or which auction target fixes a matchup gap.",
)
fac, mu = data.factors(), data.matchups()
if not len(fac) or not len(mu):
    st.warning("Matchup tables are missing. Run `python pipeline.py` again, then refresh.")
    st.stop()
pl = data.players().set_index("player_id")
name = pl.display_name

mode = st.segmented_control("Look at", ["A batter", "A bowler", "Head to head"], default="A batter", key="mu_mode")


def pick(role, key, label):
    t = data.scores(role)
    t = t[(t.p_balls >= 30) & ~t.player_id.isin(data.retired_ids())]
    t = t.sort_values(["eligible", "clutch_score"], ascending=[False, False])
    opts = t.player_id.tolist()
    return st.selectbox(
        label, opts, format_func=lambda p: f"{name.get(p, p)} ({theme.short(pl.team_label.get(p, ''))})", key=key
    )


def type_chart(rows, ylab, role):
    rows = rows.sort_values("per100")
    fig = go.Figure()
    for lab, col, val, n in [
        ("All balls", theme.BLUE, "per100", "balls"),
        ("Under pressure", theme.PINK, "p_per100", "p_balls"),
    ]:
        fig.add_trace(
            go.Bar(
                y=rows.level,
                x=rows[val],
                name=lab,
                orientation="h",
                marker=dict(color=col, cornerradius=4),
                customdata=rows[[n]].values,
                hovertemplate=f"<b>%{{y}}</b> · {lab}<br>%{{x:+.1f}} per 100 balls<br>%{{customdata[0]}} balls<extra></extra>",
            )
        )
    fig.add_vline(x=0, line=dict(color=theme.REF))
    fig.update_layout(
        barmode="group",
        height=320,
        xaxis_title=ylab,
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        legend=dict(orientation="h", y=1.12),
    )
    st.plotly_chart(fig, use_container_width=True)


def h2h_table(t, who, role):
    t = t.copy()
    t["Opponent"] = t[who].map(name)
    t["Team"] = t[who].map(pl.team_label).fillna("—").map(theme.short)
    t["Runs per 100"] = (100 * t.runs / t.balls).round(1)
    t["Value per 100"] = (100 * t.value / (t.balls + 30)) * (1 if role == "bat" else -1)
    return pd.DataFrame(
        {
            "Opponent": t.Opponent,
            "Team": t.Team,
            "Balls": t.balls,
            "Runs": t.runs,
            "Dismissals": t.outs,
            "Strike rate": t["Runs per 100"],
            "Pressure balls": t.p_balls,
            "Pressure runs": t.p_runs,
            "Pressure dismissals": t.p_outs,
            "Value per 100": t["Value per 100"].round(1),
        }
    ).sort_values("Value per 100", ascending=False)


if mode == "A batter":
    pid = pick("bat", "mu_bat", "Batter")
    f = fac[(fac.player_id == pid) & (fac.role == "bat") & (fac.factor == "bowler_type")]
    st.subheader(f"{name.get(pid)} against each bowler type")
    type_chart(
        f.assign(p_per100=f.p_value.fillna(0) * 100 / (f.p_balls + 30)), "Runs added per 100 balls vs average", "bat"
    )
    t = mu[(mu.striker_id == pid) & (mu.balls >= 12)]
    st.subheader("Head to head with individual bowlers (12+ balls)")
    h = h2h_table(t, "bowler_id", "bat")
    lc, rc = st.columns(2)
    with lc:
        st.markdown("**Bowlers he dominates**")
        st.dataframe(h.head(10), hide_index=True, use_container_width=True)
    with rc:
        st.markdown("**Bowlers who trouble him**")
        st.dataframe(h.tail(10).iloc[::-1], hide_index=True, use_container_width=True)
elif mode == "A bowler":
    pid = pick("bowl", "mu_bowl", "Bowler")
    f = fac[(fac.player_id == pid) & (fac.role == "bowl") & (fac.factor == "batter_hand")]
    st.subheader(f"{name.get(pid)} against right- and left-handers")
    type_chart(
        f.assign(p_per100=f.p_value.fillna(0) * 100 / (f.p_balls + 30)), "Runs saved per 100 balls vs average", "bowl"
    )
    t = mu[(mu.bowler_id == pid) & (mu.balls >= 12)]
    st.subheader("Head to head with individual batters (12+ balls)")
    h = h2h_table(t, "striker_id", "bowl")
    lc, rc = st.columns(2)
    with lc:
        st.markdown("**Batters he keeps quiet**")
        st.dataframe(h.head(10), hide_index=True, use_container_width=True)
    with rc:
        st.markdown("**Batters who get after him**")
        st.dataframe(h.tail(10).iloc[::-1], hide_index=True, use_container_width=True)
else:
    a, b_ = st.columns(2)
    with a:
        bat_id = pick("bat", "mu_h_bat", "Batter")
    with b_:
        bowl_id = pick("bowl", "mu_h_bowl", "Bowler")
    r = mu[(mu.striker_id == bat_id) & (mu.bowler_id == bowl_id)]
    if not len(r):
        st.info("These two have met for fewer than 6 balls in the data.")
    else:
        r = r.iloc[0]
        theme.kpi_row(
            [
                ("Balls", f"{int(r.balls)}", f"{int(r.p_balls)} of them under pressure"),
                ("Runs", f"{int(r.runs)}", f"Strike rate {100 * r.runs / r.balls:.0f}"),
                ("Dismissals", f"{int(r.outs)}", f"{int(r.p_outs)} under pressure"),
                (
                    "Edge",
                    name.get(bat_id) if r.value > 0 else name.get(bowl_id),
                    f"{abs(r.value):.1f} runs vs average across these balls",
                ),
            ]
        )
        theme.caption("Head-to-head samples are small: treat anything under ~30 balls as a hint, not proof.")
