import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, theme

rep = data.report()
theme.header("How it works", "The method in plain words, and the evidence that it holds up.")

# ---------------- 1. Pressure ----------------
st.subheader("1 · What counts as pressure")
theme.note(
    "Every ball gets a <b>Pressure Index</b> from 0 to 100, built from two parts:<br>"
    "<b>Stakes</b> — how much this one ball can swing the result. A model trained on these matches estimates each side's "
    "chance of winning; we measure the expected change in that chance across the likely outcomes (dot, 1, 2, 4, 6, wicket).<br>"
    "<b>Squeeze</b> — how tough the scoreboard is. Chasing: runs still needed compared with what a side normally scores with "
    "the balls and wickets left. Setting a total: the venue's par score compared with the projected total.<br>"
    f"The two are blended {rep['pressure']['weight_stakes']:.0%} / {rep['pressure']['weight_squeeze']:.0%}. "
    f"Balls in the top {100 - rep['pressure']['high_pressure_threshold_pct']}% count as <b>high pressure</b>."
)
st.write("")
b = data.balls()
a, c = st.columns(2, gap="large")
with a:
    st.markdown("**Where pressure lives in a chase**")
    theme.caption("Average Pressure Index by over and wickets down, second innings. Blank = fewer than 100 balls.")
    ch = b[b.innings == 2]
    h = (
        ch.groupby([ch.over, ch.wkts_before.clip(upper=7)])
        .agg(pi=("pressure_index", "mean"), n=("pressure_index", "size"))
        .reset_index()
    )
    h.loc[h.n < 100, "pi"] = np.nan
    z = h.pivot(index="wkts_before", columns="over", values="pi")
    fig = go.Figure(
        go.Heatmap(
            z=z.values,
            x=z.columns,
            y=["0", "1", "2", "3", "4", "5", "6", "7+"][: len(z)],
            colorscale=[[i / 6, c_] for i, c_ in enumerate(theme.PINK_RAMP)],
            zmin=20,
            zmax=80,
            colorbar=dict(title="Pressure", thickness=12),
            hovertemplate="Over %{x}, %{y} down<br>Pressure %{z:.0f}<extra></extra>",
            xgap=2,
            ygap=2,
        )
    )
    fig.update_layout(
        height=330,
        xaxis_title="Over",
        yaxis_title="Wickets down",
        xaxis=dict(dtick=1, gridcolor="rgba(0,0,0,0)"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig, use_container_width=True)
with c:
    st.markdown("**Proof: high-pressure balls are where matches are decided**")
    mv = pd.DataFrame(rep["pressure"]["wp_movement"])
    theme.caption("Share of all balls vs share of all win-probability swing that happens on high-pressure balls.")
    fig = go.Figure()
    labs = ["Setting a total", "Chasing"]
    fig.add_trace(
        go.Bar(
            x=labs,
            y=mv.share_of_balls_pct,
            name="Share of balls",
            marker_color=theme.NEUTRAL,
            hovertemplate="%{x}: %{y:.0f}% of balls<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=labs,
            y=mv.share_of_wp_movement_pct,
            name="Share of result-swing",
            marker_color=theme.PINK,
            hovertemplate="%{x}: %{y:.0f}% of win-probability swing<extra></extra>",
        )
    )
    fig.update_layout(barmode="group", height=330, yaxis_title="%", yaxis=dict(range=[0, 70]))
    st.plotly_chart(fig, use_container_width=True)

ph = data.table("pressure_by_phase")
if len(ph):
    ph["Innings"] = ph.innings.map({1: "Setting", 2: "Chasing"})
    pv = ph.pivot(index="Innings", columns="phase", values="high_share")[["Powerplay", "Middle", "Death"]].round(0)
    theme.caption(
        "Share of balls that are high pressure, by phase. Death overs carry the most pressure in both innings."
    )
    st.dataframe(pv.astype(int).astype(str) + "%", use_container_width=True)

# ---------------- 2. Models ----------------
st.write("")
st.subheader("2 · Are the models accurate?")
v = pd.DataFrame(rep["win_probability"])
cal = data.table("wp_calibration")
m1, m2 = st.columns([1, 1.3], gap="large")
with m1:
    theme.note(
        "The win-probability models were trained on 2022–2024 and tested on <b>2025–2026 matches they had never seen</b>.<br>"
        f"Chasing: accuracy score (AUC) <b>{v.auc.iloc[1]:.2f}</b> — it ranks a winning position above a losing one "
        f"{v.auc.iloc[1] * 100:.0f}% of the time.<br>"
        f"Setting a total: AUC <b>{v.auc.iloc[0]:.2f}</b> — first innings are harder to call, and scoring rose sharply in "
        "2025–26, so totals that once looked safe were chased more often.<br>"
        "For the rankings, every ball is scored by a model that never saw its match (5-fold cross-fitting)."
    )
    ec = rep["expected_calibration"]
    theme.caption(
        f"The 'average player' model is also on target: expected {ec['bat_runs_expected']:.3f} runs per ball vs "
        f"{ec['bat_runs_actual']:.3f} actual; dismissal chance {ec['out_expected'] * 100:.2f}% vs {ec['out_actual'] * 100:.2f}%."
    )
with m2:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0, 1], y=[0, 1], mode="lines", line=dict(color=theme.TRACK, dash="dot"), name="Perfect", hoverinfo="skip"
        )
    )
    for inn, col, lab in [(1, theme.BLUE, "Setting a total"), (2, theme.PINK, "Chasing")]:
        q = cal[cal.innings == inn]
        fig.add_trace(
            go.Scatter(
                x=q.pred,
                y=q.obs,
                mode="lines+markers",
                name=lab,
                line=dict(color=col, width=2),
                marker=dict(size=8),
                customdata=q[["n"]].values,
                hovertemplate=f"{lab}<br>Predicted %{{x:.0%}} → actually won %{{y:.0%}}<br>%{{customdata[0]}} balls<extra></extra>",
            )
        )
    fig.update_layout(
        height=320,
        xaxis=dict(title="Predicted win chance", tickformat=".0%"),
        yaxis=dict(title="Actual win rate", tickformat=".0%"),
    )
    st.plotly_chart(fig, use_container_width=True)
    theme.caption("Calibration on 2025–26: points near the dotted line mean the predicted chances came true.")

# ---------------- 3. Scoring ----------------
st.write("")
st.subheader("3 · How players are scored")
s = rep["scoring"]
theme.note(
    "<b>Runs added.</b> For every ball, a second model predicts what an <i>average</i> player would score (or concede) and how likely a "
    "wicket is, in exactly that situation. A player's value is what they actually did minus that expectation, with a wicket counted "
    f"as the runs a side typically loses (capped at {s['wicket_value_cap']:.0f} runs).<br>"
    "<b>Fair opposition.</b> Runs against strong bowlers count for more; wickets of strong batters count for more. Balls against "
    f"associate nations count {s['associate_weight']:.0%}. Recent seasons weigh more (each older season × {s['recency_decay']}).<br>"
    "<b>CRICQ Score</b> = 60% Quality + 15% Lift + 25% Consistency (each standardised), scaled so 50 = average ranked player.<br>"
    "<b>Small samples.</b> A player's pressure ability is estimated by starting from their overall ability and adjusting by what "
    "they did under pressure — the more pressure balls, the more their pressure record counts. How strongly to anchor was chosen "
    "by testing which setting best predicts pressure performance in matches the model had not seen.<br>"
    f"<b>Who is ranked.</b> At least {s['eligibility']['bat_min_pressure_balls']} pressure balls and "
    f"{s['eligibility']['bat_min_pressure_matches']} matches with pressure balls."
)
st.write("")
k1, k2 = st.columns(2, gap="large")
with k1:
    st.markdown("**Does the CRICQ Score predict the future?**")
    pc = data.table("predictive_check")
    theme.caption(
        "Scores built on 2022–24 only, compared with how players actually did under pressure in 2025–26 (rank correlation; 0 = no link)."
    )
    pc["Who"] = pc.role.map({"bat": "Batters", "bowl": "Bowlers"})
    fig = go.Figure()
    for key, lab, col in [
        ("Pressure", "Simple pressure stat", theme.NEUTRAL),
        ("CRICQ Quality", "Quality part alone", theme.BLUE),
        ("CRICQ Clutch", "Full CRICQ Score", theme.PINK),
    ]:
        q = pc[pc.method.str.startswith(key)]
        fig.add_trace(
            go.Bar(x=q.Who, y=q.correlation, name=lab, marker_color=col, hovertemplate="%{x}: %{y:.2f}<extra></extra>")
        )
    fig.add_hline(y=0, line=dict(color=theme.REF))
    fig.update_layout(barmode="group", height=300, yaxis_title="Correlation with 2025–26")
    st.plotly_chart(fig, use_container_width=True)
with k2:
    st.markdown("**Is pressure performance a repeatable skill?**")
    rp = data.table("repeatability")
    rp["Who"] = rp.role.map({"bat": "Batters", "bowl": "Bowlers"})
    theme.caption("Each player's pressure value in one half of their matches vs the other half.")
    fig = go.Figure()
    for sp, col in [("odd vs even matches", theme.BLUE), ("2022-24 vs 2025-26", theme.PINK)]:
        q = rp[rp.split == sp]
        fig.add_trace(
            go.Bar(
                x=q.Who,
                y=q.correlation,
                name=sp.replace("odd vs even matches", "Odd vs even matches"),
                marker_color=col,
                hovertemplate="%{x}: %{y:.2f}<extra></extra>",
            )
        )
    fig.add_hline(y=0, line=dict(color=theme.REF))
    fig.update_layout(barmode="group", height=300, yaxis_title="Correlation")
    st.plotly_chart(fig, use_container_width=True)
pcb = pc[pc.role == "bowl"].set_index("method").correlation
pct = pc[pc.role == "bat"].set_index("method").correlation
theme.note(
    "<b>What this means.</b> Bowling under pressure is a real, lasting skill: how a bowler handled pressure in 2022–24 carries "
    f"into 2025–26. Every method predicts it about equally well (CRICQ Score {pcb.filter(like='CRICQ Score').iloc[0]:.2f}, plain "
    f"pressure economy {pcb.filter(like='Pressure').iloc[0]:.2f}), so the CRICQ Score's advantage is fairness, not fortune-telling: "
    "it judges every ball against the situation and the opposition, rewards a consistent record, and shows its uncertainty.<br>"
    f"Batting under pressure is much noisier: nothing tested predicts 2025–26 pressure batting (all near {pct.abs().max():.2f} or below). "
    "Among established batters, a hot or cold run under pressure says little about the next one. That is why batting scores "
    "lean on overall quality and consistency, why their confidence ranges are wider, and why batting ranks 6–10 should be "
    "read as a group of near-equals."
)

# ---------------- 4. Robustness ----------------
st.write("")
st.subheader("4 · Do the rankings survive different choices?")
sens = data.table("sensitivity")
if len(sens):
    pv = sens.pivot(index="variant", columns="role", values="top10_kept").rename(
        columns={"bat": "Batters: top 10 kept", "bowl": "Bowlers: top 10 kept"}
    )
    sp = sens.pivot(index="variant", columns="role", values="spearman").rename(
        columns={"bat": "Batters: order agreement", "bowl": "Bowlers: order agreement"}
    )
    tab = pv.join(sp)
    tab.index.name = "Change tested"
    st.dataframe(
        tab,
        use_container_width=True,
        column_config={
            "Batters: top 10 kept": st.column_config.NumberColumn(format="%d / 10"),
            "Bowlers: top 10 kept": st.column_config.NumberColumn(format="%d / 10"),
            "Batters: order agreement": st.column_config.NumberColumn(format="%.2f"),
            "Bowlers: order agreement": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    theme.caption(
        "Each row changes one setting and re-runs everything. Order agreement = rank correlation with the main ranking (1.00 = identical)."
    )

# ---------------- 5. Limits ----------------
st.write("")
st.subheader("5 · Limits and data checks")
theme.note(
    "No pitch, weather, dew, field-placing or ball-tracking data exists in the Data Pack, so venue scoring is used as a stand-in "
    "for conditions. Bowling speed is only recorded for pace bowlers. Head-to-head records are thin (few pairs have met for 24+ "
    "balls) and are shown for interest only. Player roles come from batting position and the overs they bowl. "
    "Retired players and players with no match since 2024 get no rank. IPL 2027 "
    "availability comes from dated news reports until the official retention lists (17 Nov 2026); CRICQ does not "
    "predict auction prices."
)
dq = data.table("data_quality")
if len(dq):
    with st.expander("Data-quality log (every issue found and the decision taken)"):
        st.dataframe(
            dq.rename(columns={"check": "Check", "finding": "Finding", "decision": "Decision"}),
            hide_index=True,
            use_container_width=True,
        )
