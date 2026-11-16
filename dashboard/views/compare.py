import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, theme

theme.header("Compare", "Put two players side by side, or check a batter against a bowler.")

mode = st.segmented_control(
    "Compare", ["Two batters", "Two bowlers", "Batter v bowler"], default="Two batters", key="cmp_mode"
)

if mode in ("Two batters", "Two bowlers"):
    role = "bat" if mode == "Two batters" else "bowl"
    t = data.scores(role)
    pool = t[(t.p_balls >= 30) & ~t.player_id.isin(data.retired_ids())]
    pool = pool.sort_values(["eligible", "clutch_score"], ascending=[False, False])
    names = pool.display_name.tolist()
    ids = pool.player_id.tolist()
    a, b = st.columns(2)
    ia = a.selectbox("Player A", range(len(ids)), index=0, format_func=lambda i: f"{names[i]} · {pool.team.iloc[i]}")
    ib = b.selectbox(
        "Player B",
        range(len(ids)),
        index=min(1, len(ids) - 1),
        format_func=lambda i: f"{names[i]} · {pool.team.iloc[i]}",
    )
    ra, rb = pool.iloc[ia], pool.iloc[ib]
    Pa, Na = data.overall(ids[ia], role)
    Pb, Nb = data.overall(ids[ib], role)

    def rank(r):
        return f"#{int(r['rank'])}" if pd.notna(r["rank"]) else "—"

    if role == "bat":
        rows = [
            ("CRICQ Score", ra.clutch_score, rb.clutch_score, "{:.1f}", True),
            ("Rank", None, None, None, None),
            ("Pressure balls faced", Pa.balls, Pb.balls, "{:.0f}", None),
            ("Strike rate under pressure", Pa.sr, Pb.sr, "{:.1f}", True),
            ("Strike rate normally", Na.sr, Nb.sr, "{:.1f}", True),
            ("Balls per dismissal (pressure)", Pa.bpd, Pb.bpd, "{:.1f}", True),
            ("Boundary % (pressure)", Pa.bnd_pct, Pb.bnd_pct, "{:.1f}", True),
            ("Dot-ball % (pressure)", Pa.dot_pct, Pb.dot_pct, "{:.1f}", False),
            ("Consistency", ra.consistency * 100, rb.consistency * 100, "{:.0f}%", True),
        ]
    else:
        rows = [
            ("CRICQ Score", ra.clutch_score, rb.clutch_score, "{:.1f}", True),
            ("Rank", None, None, None, None),
            ("Pressure balls bowled", Pa.balls, Pb.balls, "{:.0f}", None),
            ("Economy under pressure", Pa.econ, Pb.econ, "{:.2f}", False),
            ("Economy normally", Na.econ, Nb.econ, "{:.2f}", False),
            ("Wickets (pressure)", Pa.wkts, Pb.wkts, "{:.0f}", True),
            ("Balls per wicket (pressure)", Pa.sr, Pb.sr, "{:.1f}", False),
            ("Dot-ball % (pressure)", Pa.dot_pct, Pb.dot_pct, "{:.1f}", True),
            ("Consistency", ra.consistency * 100, rb.consistency * 100, "{:.0f}%", True),
        ]
    out = []
    for lab, va, vb, fmt, hib in rows:
        if lab == "Rank":
            out.append({"": lab, ra.display_name: rank(ra), rb.display_name: rank(rb), "Edge": ""})
            continue
        edge = ""
        if hib is not None and abs(va - vb) > 1e-9:
            edge = ra.display_name if (va > vb) == hib else rb.display_name
        out.append({"": lab, ra.display_name: fmt.format(va), rb.display_name: fmt.format(vb), "Edge": edge})
    st.dataframe(pd.DataFrame(out), hide_index=True, use_container_width=True)

    st.subheader("Under pressure, by phase")
    metric, mlabel = ("sr", "Strike rate") if role == "bat" else ("econ", "Economy")
    sa, sb = data.splits(ids[ia], role), data.splits(ids[ib], role)
    groups = ["All", "Powerplay", "Middle", "Death"]
    fig = go.Figure()
    for r_, s_, col in [(ra, sa, theme.BLUE), (rb, sb, theme.PINK)]:
        d = s_[(s_.pressure == "Pressure") & s_.group.isin(groups)].set_index("group").reindex(groups)
        fig.add_trace(
            go.Bar(
                x=groups,
                y=d[metric],
                name=r_.display_name,
                marker_color=col,
                customdata=d[["balls"]].values,
                hovertemplate=f"<b>{r_.display_name}</b> · %{{x}}<br>{mlabel} %{{y:.1f}} under pressure<br>%{{customdata[0]:.0f}} balls<extra></extra>",
            )
        )
    fig.update_layout(barmode="group", height=360, yaxis_title=f"{mlabel} under pressure", bargap=0.3)
    st.plotly_chart(fig, use_container_width=True)
    theme.caption("Pressure balls only. Hover to see how many balls each bar is based on.")
else:
    bt, bw = data.scores("bat"), data.scores("bowl")
    gone = data.retired_ids()
    bp = bt[(bt.p_balls >= 30) & ~bt.player_id.isin(gone)].sort_values("clutch_score", ascending=False)
    wp = bw[(bw.p_balls >= 30) & ~bw.player_id.isin(gone)].sort_values("clutch_score", ascending=False)
    a, b = st.columns(2)
    i = a.selectbox("Batter", range(len(bp)), format_func=lambda k: f"{bp.display_name.iloc[k]} · {bp.team.iloc[k]}")
    j = b.selectbox("Bowler", range(len(wp)), format_func=lambda k: f"{wp.display_name.iloc[k]} · {wp.team.iloc[k]}")
    h2h, n = data.head_to_head(bp.player_id.iloc[i], wp.player_id.iloc[j])
    if n == 0:
        st.info("These two have not faced each other in this data.")
    else:
        cols = st.columns(2)
        for c, (lab, g) in zip(cols, h2h.items(), strict=True):
            with c:
                st.subheader(lab)
                if g is None or g.balls == 0:
                    st.write("No balls.")
                    continue
                theme.kpi_row(
                    [
                        ("Balls", f"{int(g.balls)}", ""),
                        ("Runs", f"{int(g.runs)}", f"SR {g.sr:.0f}"),
                        ("Dismissals", f"{int(g.outs)}", f"Dot % {g.dot_pct:.0f}"),
                    ]
                )
        if n < 24:
            theme.note(
                f"Only {n} balls between them — treat this as a story, not evidence. "
                "Head-to-heads are shown for interest and are not used in the rankings."
            )
        else:
            theme.caption("Head-to-heads are shown for interest; they are not used in the rankings.")
