import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import cards, data, theme

theme.header("Player", "How one player's game changes when the pressure rises.")

bat, bowl = data.scores("bat"), data.scores("bowl")
c1, c2 = st.columns([1, 2.2])
role_lbl = c1.segmented_control(
    "As a", ["Batter", "Bowler"], default=None if "pl_role" in st.session_state else "Batter", key="pl_role"
)
role = "bowl" if role_lbl == "Bowler" else "bat"
t = bat if role == "bat" else bowl
pool = t[(t.p_balls >= 30) & ~t.player_id.isin(data.retired_ids())]
pool = pool.sort_values(["eligible", "clutch_score"], ascending=[False, False])
labels = pool.apply(
    lambda r: f"{r.display_name} · {r.team}" + ("" if r.eligible else " (below minimum)"), axis=1
).tolist()
ids = pool.player_id.tolist()
default = 0
if "pl_pid" in st.session_state and st.session_state.pl_pid in ids:
    default = ids.index(st.session_state.pl_pid)
choice = c2.selectbox("Player", range(len(ids)), index=default, format_func=lambda i: labels[i])
pid = ids[choice]
r = pool[pool.player_id == pid].iloc[0]

# ---------- header ----------
hc, h1, h2 = st.columns([1.05, 1.9, 1.05], gap="large")
with hc:
    cards.inject_css()
    st.markdown(cards.card_html(r, role, cards.attribute_table(t, role).loc[r.name].to_dict()), unsafe_allow_html=True)
with h1:
    tags = [theme.pill(r.team, "gray"), theme.pill(r.role, "blue")]
    if role == "bat" and pd.notna(r.bat_hand):
        tags.append(theme.pill("Left-handed" if r.bat_hand == "LHB" else "Right-handed", "gray"))
    if role == "bowl" and pd.notna(r.bowl_type):
        tags.append(theme.pill(r.bowl_type, "gray"))
    if r.at_rr:
        tags.append(theme.pill("Rajasthan Royals"))
    if pd.notna(r.get("status_label")):
        tags.append(theme.pill(f"2027: {r.status_label}", "" if r.get("avail_prob", 0) >= 0.35 else "gray"))
    st.header(str(r.display_name), anchor=False)
    st.markdown(" ".join(tags), unsafe_allow_html=True)
    if pd.notna(r.get("status_note")) and str(r.status_note):
        src = str(r.get("status_source") or "")
        link = f" · [source]({src})" if src.startswith("https://") else ""
        dt = f" ({r.status_date})" if pd.notna(r.get("status_date")) and str(r.status_date) else ""
        st.caption(f"{r.status_note}{dt}{link}")
with h2:
    n_ranked = int(t["rank"].notna().sum())
    if pd.notna(r["rank"]):
        rank_txt = f"Rank #{int(r['rank'])} of {n_ranked}"
    elif r.eligible:
        rank_txt = "Not ranked (retired or no match since 2024)"
    else:
        rank_txt = "Not ranked (below minimum)"
    rng = f"Range {r.score_lo:.0f}–{r.score_hi:.0f}" if pd.notna(r.get("score_lo")) else ""
    st.markdown(
        theme.kpi(
            "CRICQ Score",
            f"{r.clutch_score:.1f}",
            [f"{theme.score_word(r.clutch_score)} · {rank_txt}", rng],
            hero=True,
        ),
        unsafe_allow_html=True,
    )

P, N = data.overall(pid, role)
mv = data.match_values(pid, role, min_balls=6)
pos = int((mv.value > 0).sum())

# ---------- plain-English summary ----------
if role == "bat":
    s = (
        f"Under pressure, **{r.display_name}** scores at a strike rate of **{P.sr:.0f}** (normally {N.sr:.0f}) and is dismissed "
        f"once every **{P.bpd:.0f} balls** (normally every {N.bpd:.0f}). "
    )
else:
    s = (
        f"Under pressure, **{r.display_name}** concedes **{P.econ:.2f} runs an over** (normally {N.econ:.2f}) and takes a wicket "
        f"every **{P.sr:.0f} balls** (normally every {N.sr:.0f}). "
    )
if len(mv):
    s += f"He added value in **{pos} of {len(mv)}** pressure {'innings' if role == 'bat' else 'spells'} with 6+ pressure balls."
theme.note(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", theme.esc(s)))
st.write("")


# ---------- tiles ----------
def tile(col, label, p, n, fmt, better_high=True, unit=""):
    d = p - n
    good = d >= 0 if better_high else d <= 0
    col.metric(
        label,
        f"{fmt.format(p)}{unit}",
        f"{'+' if d >= 0 else '−'}{fmt.format(abs(d))} vs normal",
        delta_color="normal" if (d >= 0) == good else "inverse",
    )


k = st.columns(4)
if role == "bat":
    tile(k[0], "Strike rate under pressure", P.sr, N.sr, "{:.1f}")
    tile(k[1], "Balls per dismissal", P.bpd, N.bpd, "{:.1f}")
    tile(k[2], "Boundary %", P.bnd_pct, N.bnd_pct, "{:.1f}", unit="%")
    tile(k[3], "Dot-ball %", P.dot_pct, N.dot_pct, "{:.1f}", better_high=False, unit="%")
else:
    tile(k[0], "Economy under pressure", P.econ, N.econ, "{:.2f}", better_high=False)
    tile(k[1], "Balls per wicket", P.sr, N.sr, "{:.1f}", better_high=False)
    tile(k[2], "Dot-ball %", P.dot_pct, N.dot_pct, "{:.1f}", unit="%")
    tile(k[3], "Boundary % conceded", P.bnd_pct, N.bnd_pct, "{:.1f}", better_high=False, unit="%")
theme.caption(f"Based on {int(P.balls)} pressure balls and {int(N.balls)} normal balls.")

st.write("")
left, right = st.columns(2, gap="large")

# ---------- by situation ----------
with left:
    st.subheader("Normal vs pressure, by situation")
    sp = data.splits(pid, role)
    metric, mlabel = ("sr", "Strike rate") if role == "bat" else ("econ", "Economy (runs per over)")
    order = [
        "All",
        "Powerplay",
        "Middle",
        "Death",
        "vs pace",
        "vs spin",
        "vs right-handers",
        "vs left-handers",
        "IPL",
        "T20I",
    ]
    sp = sp[sp.group.isin(order)]
    sp["order"] = sp.group.map({g: i for i, g in enumerate(order)})
    sp = sp.sort_values("order")
    theme.caption(f"{mlabel}. Bars with fewer than 30 balls are faded — too few to trust.")
    fig = go.Figure()
    for lab, col in [("Normal", theme.BLUE), ("Pressure", theme.PINK)]:
        d = sp[sp.pressure == lab]
        fig.add_trace(
            go.Bar(
                y=d.group,
                x=d[metric],
                name=lab,
                orientation="h",
                marker_color=col,
                marker_opacity=np.where(d.balls >= 30, 1.0, 0.35),
                customdata=d[["balls"]].values,
                hovertemplate=f"<b>%{{y}}</b> · {lab}<br>{mlabel} %{{x:.1f}}<br>%{{customdata[0]:.0f}} balls<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="group",
        height=420,
        yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"),
        bargap=0.25,
        bargroupgap=0.08,
        xaxis_title=mlabel,
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- consistency ----------
with right:
    st.subheader("Innings by innings under pressure")
    theme.caption(
        "Runs added on pressure balls in each match (6+ pressure balls) versus an average player in the same spots. "
        "Above the line = delivered."
    )
    if len(mv):
        mv = mv.reset_index(drop=True)
        mv["n"] = mv.index + 1
        fig = go.Figure(
            go.Bar(
                x=mv.n,
                y=mv.value,
                marker_color=np.where(mv.value > 0, theme.PINK, theme.NEUTRAL),
                customdata=mv[["comp_name", "opponent", "balls", "runs", "outs", "match_date"]].values,
                hovertemplate=(
                    "%{customdata[5]|%d %b %Y} · %{customdata[0]}<br>vs %{customdata[1]}<br>%{customdata[2]} pressure balls, "
                    + (
                        "%{customdata[3]} runs, out %{customdata[4]}"
                        if role == "bat"
                        else "%{customdata[3]} runs conceded, %{customdata[4]} wkts"
                    )
                    + "<br>Runs added %{y:+.1f}<extra></extra>"
                ),
            )
        )
        fig.add_hline(y=0, line=dict(color=theme.REF))
        yrs = mv.groupby(mv.match_date.dt.year).n.min()
        fig.update_layout(
            height=420,
            yaxis_title="Runs added vs average",
            bargap=0.25,
            xaxis=dict(tickvals=yrs.values, ticktext=[str(y) for y in yrs.index], title="Matches in date order"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No matches with 6+ pressure balls.")

l2, r2 = st.columns(2, gap="large")
with l2:
    st.subheader("How the wickets fall under pressure" if role == "bowl" else "How he gets out under pressure")
    dm = data.dismissals(pid, role)
    if len(dm):
        fig = go.Figure(
            go.Bar(
                x=dm.values,
                y=dm.index,
                orientation="h",
                marker_color=theme.PINK,
                hovertemplate="%{y}: %{x}<extra></extra>",
            )
        )
        fig.update_layout(height=260, yaxis=dict(autorange="reversed", gridcolor="rgba(0,0,0,0)"), xaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("None recorded on pressure balls.")
with r2:
    st.subheader("Season by season")
    d = data.bat_balls(pid) if role == "bat" else data.bowl_balls(pid)
    rows = []
    for (s_, hp), g in d.groupby(["season_year", "high_pressure"]):
        a = data._bat_agg(g) if role == "bat" else data._bowl_agg(g)
        rows.append({"season": s_, "kind": "Pressure" if hp else "Normal", "v": a[metric], "balls": a.balls})
    ss = pd.DataFrame(rows)
    fig = go.Figure()
    for lab, col in [("Normal", theme.BLUE), ("Pressure", theme.PINK)]:
        q = ss[ss.kind == lab]
        fig.add_trace(
            go.Scatter(
                x=q.season,
                y=q.v,
                name=lab,
                mode="lines+markers",
                line=dict(color=col, width=2),
                marker=dict(size=9),
                customdata=q[["balls"]].values,
                hovertemplate=f"%{{x}} · {lab}<br>{mlabel} %{{y:.1f}}<br>%{{customdata[0]:.0f}} balls<extra></extra>",
            )
        )
    fig.update_layout(height=260, xaxis=dict(dtick=1), yaxis_title=mlabel)
    st.plotly_chart(fig, use_container_width=True)

# ---------- parameters ----------
st.write("")
st.subheader("Parameters — where he adds value, and where he doesn't")
fac = data.factors()
f = fac[(fac.player_id == pid) & (fac.role == role)].copy() if len(fac) else fac
if len(f):
    f["p_per100"] = 100 * f.p_value.fillna(0) / (f.p_balls + 30)
    best, worst = data.fx.strengths(f, pid)
    word = "adds" if role == "bat" else "saves"

    def line(x):
        return ", ".join(f"{data.fx.FACTORS[r.factor].lower()}: {r.level} ({r.per100:+.0f})" for r in x.itertuples())

    theme.note(
        f"<b>Strongest situations:</b> {theme.esc(line(best))}.<br><b>Weakest situations:</b> {theme.esc(line(worst))}."
        f"<br>Numbers are runs he {word} per 100 balls compared with an average player in the same spot."
    )
    st.write("")
    order = list(data.fx.FACTORS)
    f["fo"] = f.factor.map({k: i for i, k in enumerate(order)})
    f = f.sort_values(["fo", "per100"], ascending=[True, False])
    st.dataframe(
        pd.DataFrame(
            {
                "Parameter": f.factor.map(data.fx.FACTORS),
                "Situation": f.level,
                "Balls": f.balls,
                ("Strike rate" if role == "bat" else "Economy"): f.rate.round(1 if role == "bat" else 2),
                "Value per 100 (all)": f.per100.round(1),
                "Pressure balls": f.p_balls,
                "Value per 100 (pressure)": f.p_per100.round(1),
            }
        ),
        hide_index=True,
        use_container_width=True,
        height=420,
        column_config={
            "Value per 100 (all)": st.column_config.NumberColumn(format="%+.1f"),
            "Value per 100 (pressure)": st.column_config.NumberColumn(format="%+.1f"),
        },
    )
    theme.caption(
        "Pitch type uses the venue's normal first-innings score (the Data Pack has no pitch reports). "
        "Rows with under 30 balls are noisy. Head-to-head records are on the Matchups page."
    )
else:
    st.info("Parameter splits appear after the pipeline has been re-run.")

with st.expander("Score breakdown"):
    b1, b2, b3 = st.columns(3)
    b1.metric(
        "Quality", f"{r.quality * 100:+.1f}", help=theme.GLOSSARY["Quality"] + " Shown as runs per 100 pressure balls."
    )
    b2.metric("Lift", f"{r.lift * 100:+.1f}", help=theme.GLOSSARY["Lift"] + " Runs per 100 balls.")
    b3.metric("Consistency", f"{r.consistency * 100:.0f}%", help=theme.GLOSSARY["Consistency"])
    if "top10_in_variants" in r and r.eligible:
        st.caption(
            f"Made the top 10 in {int(r.top10_in_variants)} of 10 alternative set-ups. "
            f"Chance of a top-10 rank when re-sampling his matches: {r.p_top10 * 100:.0f}%."
        )
