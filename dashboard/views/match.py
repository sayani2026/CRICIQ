import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from components import data, theme

theme.header("Match replay", "Every ball of a match: its pressure, the win chances, and who handled it.")

m = data.matches().copy()
m = m[m.inn2_runs.notna()].sort_values("match_date", ascending=False)
f1, f2 = st.columns([1, 2.6])
comps = ["All"] + sorted(m.comp_name.unique(), key=lambda s: (not s.startswith("IPL"), s))
comp = f1.selectbox("Competition", comps, index=0)
close_only = f1.toggle("Only tight finishes", value=True, help="Matches with the highest pressure peaks.")
mm = m if comp == "All" else m[m.comp_name == comp]
if close_only:
    mm = mm[mm.peak_pressure >= mm.peak_pressure.quantile(0.75)] if len(mm) > 8 else mm
mm = mm.reset_index(drop=True)
labels = [data.match_label(r) for r in mm.itertuples()]
default = 0
ids = mm.match_id.tolist()
if 31250 in ids:
    default = ids.index(31250)
k = f2.selectbox("Match", range(len(mm)), index=default, format_func=lambda i: labels[i])
mr = mm.iloc[k]

b = data.balls()
x = b[b.match_id == mr.match_id].sort_values(["innings", "innings_ball_num"]).copy()
chasers = x[x.innings == 2].batting_team.iloc[0]
setters = x[x.innings == 1].batting_team.iloc[0]
x["wp_chase"] = np.where(x.innings == 2, x.wp, 1 - x.wp)
x["xpos"] = (x.innings - 1) * 20 + x.legal_before / 6
x["outcome"] = np.select(
    [x.wkt == 1, x.extras_type == "wide", x.total == 0], ["WICKET", "wide", "dot"], x.total.astype(str) + " run(s)"
)

c1, c2, c3 = st.columns([2.2, 1, 1])
c1.subheader(
    f"{setters} {int(mr.inn1_runs)}/{int(mr.inn1_wkts)}  v  {chasers} {int(mr.inn2_runs)}/{int(mr.inn2_wkts)}",
    anchor=False,
)
c1.markdown(
    theme.pill(mr.comp_name, "gray") + theme.pill(f"{mr.match_date:%d %b %Y}", "gray") + theme.pill(mr.result),
    unsafe_allow_html=True,
)
low = x[x.innings == 2].wp_chase.min()
c2.markdown(theme.kpi(f"{chasers} lowest win chance", f"{low * 100:.0f}%", "during the chase"), unsafe_allow_html=True)
c3.markdown(
    theme.kpi("High-pressure balls", f"{int(x.high_pressure.sum())}", f"of {len(x)} deliveries"), unsafe_allow_html=True
)

st.write("")
st.subheader(f"{chasers}' chance of winning, ball by ball")
theme.caption(
    "Line = win chance for the chasing side before each ball. Rings = wickets. "
    "The strip below shows the Pressure Index of every ball (pink = high pressure)."
)
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.74, 0.26], vertical_spacing=0.04)
hover = (
    "<b>%{customdata[0]}</b> · over %{customdata[1]}<br>%{customdata[2]} to %{customdata[3]}: %{customdata[4]}"
    "<br>Win chance %{y:.0%} · Pressure %{customdata[5]:.0f}<extra></extra>"
)
cd = x[["batting_team", "ball_label", "bowler_name", "striker_name", "outcome", "pressure_index"]].values
fig.add_trace(
    go.Scatter(
        x=x.xpos,
        y=x.wp_chase,
        mode="lines",
        line=dict(color=theme.PINK, width=2.4),
        customdata=cd,
        hovertemplate=hover,
        showlegend=False,
    ),
    row=1,
    col=1,
)
w = x[x.wkt == 1]
fig.add_trace(
    go.Scatter(
        x=w.xpos,
        y=w.wp_chase,
        mode="markers",
        marker=dict(size=10, color=theme.BG, line=dict(color=theme.TEXT, width=2)),
        customdata=w[["batting_team", "ball_label", "bowler_name", "striker_name", "outcome", "pressure_index"]].values,
        hovertemplate=hover,
        showlegend=False,
    ),
    row=1,
    col=1,
)
fig.add_trace(
    go.Bar(
        x=x.xpos,
        y=x.pressure_index,
        marker_color=np.where(x.high_pressure == 1, theme.PINK, theme.TRACK),
        customdata=cd,
        hovertemplate="over %{customdata[1]} · Pressure %{y:.0f}<extra></extra>",
        showlegend=False,
    ),
    row=2,
    col=1,
)
fig.add_hline(y=0.5, line=dict(color=theme.REF, dash="dot"), row=1, col=1)
fig.add_vline(x=20, line=dict(color=theme.TRACK))
fig.update_yaxes(tickformat=".0%", range=[0, 1], title_text="Win chance", row=1, col=1)
fig.update_yaxes(range=[0, 100], title_text="Pressure", row=2, col=1)
fig.update_xaxes(
    tickvals=[0, 5, 10, 15, 20, 25, 30, 35, 40],
    ticktext=["0", "5", "10", "15", "20 | 0", "5", "10", "15", "20"],
    title_text=f"Overs — {setters} batting | {chasers} chasing",
    row=2,
    col=1,
)
fig.update_layout(height=520, bargap=0)
st.plotly_chart(fig, use_container_width=True)

left_col, right_col = st.columns([1.35, 1], gap="large")
with left_col:
    st.subheader("The moments that decided it")
    x["wp_after"] = x.groupby("innings").wp_chase.shift(-1)
    last2 = x.innings == 2
    x.loc[last2 & x.wp_after.isna(), "wp_after"] = float(mr.win_team_id == x[x.innings == 2].batting_team_id.iloc[0])
    x["swing"] = (x.wp_after - x.wp_chase) * 100
    top = x.sort_values("pressure_index", ascending=False).head(8).sort_values(["innings", "innings_ball_num"])
    show = pd.DataFrame(
        {
            "Over": top.ball_label,
            "Batter": top.striker_name,
            "Bowler": top.bowler_name,
            "What happened": top.outcome,
            "Pressure": top.pressure_index.round(0),
            "Win-chance swing": top.swing.map(lambda v: "" if pd.isna(v) else f"{v:+.0f} pts"),
        }
    )
    st.dataframe(
        show,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Win-chance swing": st.column_config.TextColumn(
                help=f"How much {chasers}' chance of winning moved on that ball."
            )
        },
    )
with right_col:
    st.subheader("Who handled the pressure")
    p = x[x.high_pressure == 1]
    bt = (
        p[p.faced == 1]
        .groupby("striker_name")
        .agg(balls=("faced", "size"), runs=("bat_runs", "sum"), out=("striker_out", "sum"), added=("bat_value", "sum"))
        .sort_values("added", ascending=False)
    )
    bw = (
        p.groupby("bowler_name")
        .agg(
            balls=("legal", "sum"), runs=("bowler_runs", "sum"), wkts=("bowler_wkt", "sum"), added=("bowl_value", "sum")
        )
        .sort_values("added", ascending=False)
    )
    st.markdown("**Batting** (pressure balls only)")
    st.dataframe(
        pd.DataFrame(
            {
                "Batter": bt.index,
                "Runs": bt.runs.astype(int),
                "Balls": bt.balls.astype(int),
                "Out": bt.out.astype(int),
                "Runs added": bt.added.round(1),
            }
        ).head(5),
        hide_index=True,
        use_container_width=True,
        column_config={"Runs added": st.column_config.NumberColumn(format="%+.1f")},
    )
    st.markdown("**Bowling** (pressure balls only)")
    st.dataframe(
        pd.DataFrame(
            {
                "Bowler": bw.index,
                "Balls": bw.balls.astype(int),
                "Runs": bw.runs.astype(int),
                "Wkts": bw.wkts.astype(int),
                "Runs saved": bw.added.round(1),
            }
        ).head(5),
        hide_index=True,
        use_container_width=True,
        column_config={"Runs saved": st.column_config.NumberColumn(format="%+.1f")},
    )
    theme.caption("Runs added / saved = compared with an average player facing exactly the same situations.")
