"""RR Auction Board — from pressure rankings to an IPL 2027 auction plan for Rajasthan Royals."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import data, theme
from components.data import au

theme.header(
    "RR Auction Board · IPL 2027",
    "Who Rajasthan Royals should keep, where the squad is short under pressure, "
    "and which players they can realistically buy on 16 December in Goa.",
)

cfg = data.auction_cfg()
if cfg is None:
    st.warning("The auction section is missing from config.yaml, so the board can't be built.")
    st.stop()
a = cfg["auction"]
bat, bowl = data.scores("bat"), data.scores("bowl")
if "status" not in bat.columns:
    st.warning("Rankings were built without player availability. Run `python pipeline.py` again, then refresh.")
    st.stop()
squad = data.rr_squad()

theme.note(
    f"<b>Data as of {theme.esc(a.get('as_of', ''))}.</b> Official retention and release lists are due on "
    "<b>17 November 2026</b>; until then, statuses come from dated news reports and are marked as such. "
    "Update <code>data/external/player_status_2027.csv</code> and <code>rr_squad_2027.csv</code> when the lists "
    "are out, then run the pipeline again. Auction: 16 Dec 2026, Goa."
)

# ---------------- Step 1: keep or release ----------------
st.subheader("1 · Who RR keeps")
theme.caption(
    "Tick the players to release. The default follows news reports and CRICQ's pressure numbers; "
    "'review' players are released by default. Purse = salary cap minus the fees of everyone kept."
)


def _score(name, t):
    r = t[(t.display_name == name) & t.eligible]
    return round(float(r.clutch_score.iloc[0]), 1) if len(r) else None


ed = pd.DataFrame(
    {
        "Release": squad.projection.isin(["release", "review"]),
        "Player": squad.player,
        "Overseas": squad.overseas,
        "Fee (₹ cr)": squad.fee_cr,
        "Bat score": [f"{v:.1f}" if v is not None else "—" for v in (_score(p, bat) for p in squad.player)],
        "Bowl score": [f"{v:.1f}" if v is not None else "—" for v in (_score(p, bowl) for p in squad.player)],
        "Projection": squad.projection,
        "Why": squad.reason,
    }
)
edited = st.data_editor(
    ed,
    hide_index=True,
    use_container_width=True,
    height=420,
    disabled=[c for c in ed.columns if c != "Release"],
    column_config={
        "Release": st.column_config.CheckboxColumn(help="Ticked = released before the auction"),
        "Fee (₹ cr)": st.column_config.NumberColumn(format="%.2f"),
        "Bat score": st.column_config.TextColumn(
            help="CRICQ Score as a batter (— = not enough pressure balls to rank)"
        ),
        "Bowl score": st.column_config.TextColumn(
            help="CRICQ Score as a bowler (— = not enough pressure balls to rank)"
        ),
        "Why": st.column_config.TextColumn(width="large"),
    },
    key="rr_release_editor",
)
release = set(edited.loc[edited.Release, "Player"])
state = au.squad_state(squad, release, cfg)
theme.kpi_row(
    [
        (
            "Purse for the auction",
            f"₹{state['purse_cr']:.2f} cr",
            f"Cap ₹{a['salary_cap_cr']} cr (reported) − kept fees",
        ),
        ("Squad slots to fill", f"{state['slots']}", f"{state['squad_kept']} kept of {a['max_squad']} max"),
        (
            "Overseas slots",
            f"{state['overseas_slots']}",
            f"{state['overseas_kept']} overseas kept of {a['max_overseas']}",
        ),
        ("Freed by releases", f"₹{state['freed_cr']:.2f} cr", f"{len(release)} players released"),
    ]
)
if state["squad_kept"] > a["max_squad"] or state["overseas_kept"] > a["max_overseas"]:
    st.error("Too many players kept for IPL squad limits. Release more players.")

# ---------------- Step 2: needs ----------------
st.write("")
st.subheader("2 · Where RR is short under pressure")
theme.caption(
    f"Strength = average CRICQ Score of RR's best players in each role (players without enough pressure balls "
    f"count as {a.get('replacement_level', 45)}). Gap to {a['quality_bar']} (proven under pressure): "
    "7+ = High need, 3–7 = Medium, under 3 = Low."
)
need_tab = au.needs(state["kept"], bat, bowl, cfg)
tone = {"High": theme.PINK, "Medium": theme.GOLD, "Low": theme.NEUTRAL}
nt = need_tab.iloc[::-1]
fig = go.Figure(
    go.Bar(
        x=nt.strength,
        y=nt.label,
        orientation="h",
        marker=dict(color=[tone[x] for x in nt.level], cornerradius=4),
        text=[f"{lv} need · {s:.0f}" for lv, s in zip(nt.level, nt.strength, strict=True)],
        textposition="outside",
        textfont=dict(color=theme.TEXT2),
        customdata=nt[["squad_players", "gap"]].values,
        hovertemplate="<b>%{y}</b><br>Strength %{x:.1f} (gap %{customdata[1]:.1f})<br>%{customdata[0]}<extra></extra>",
    )
)
fig.add_vline(
    x=a["quality_bar"],
    line=dict(color=theme.REF, dash="dot"),
    annotation_text="Proven under pressure",
    annotation_position="top",
)
fig.update_layout(
    height=300,
    xaxis=dict(range=[35, 70], title="RR strength in the role (CRICQ Score)"),
    yaxis=dict(gridcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig, use_container_width=True)
with st.expander("Who covers each role now"):
    st.dataframe(
        need_tab[["label", "level", "strength", "gap", "squad_players"]].rename(
            columns={
                "label": "Role",
                "level": "Need",
                "strength": "Strength",
                "gap": "Gap",
                "squad_players": "RR players (score)",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

# ---------------- Step 3: plan ----------------
pool = au.targets(bat, bowl, need_tab, set(state["kept"].player), cfg, released_names=release)
plan = au.plan(pool, need_tab, state, cfg)
st.write("")
st.subheader("3 · Auction shortlist")
theme.caption(
    f"One target per open slot, realistic picks only (CRICQ Score ≥ {a.get('plan_min_score', 50)}, at least "
    f"{a.get('plan_min_prob', 0.35):.0%} likely to be in the auction). Priority = CRICQ Score in the role + need bonus "
    "(High +10, Medium +5) + 15 × availability. Overseas slots go to the strongest overseas options first."
)
if len(plan):
    per = state["purse_cr"] / max(state["slots"], 1)
    cards = st.columns(min(len(plan), 4))
    for i, r in plan.iterrows():
        with cards[i % len(cards)]:
            tags = [
                theme.pill(f"{r.need_level} need", "" if r.need_level == "High" else "blue"),
                theme.pill(r.need_label, "gray"),
            ]
            if r.overseas:
                tags.append(theme.pill("Overseas", "gray"))
            st.markdown(
                theme.kpi(
                    f"Slot {r.slot}",
                    r.target,
                    [f"CRICQ Score {r.clutch_score:.0f} · {r.availability}", f"Plan B: {r.plan_b or '—'}"],
                ),
                unsafe_allow_html=True,
            )
            st.markdown(" ".join(tags), unsafe_allow_html=True)
    theme.caption(
        f"Budget guide: ₹{state['purse_cr']:.2f} cr across {state['slots']} slots ≈ ₹{per:.1f} cr a slot on average. "
        "CRICQ does not predict prices — set a maximum bid for each target before the auction."
    )
else:
    st.info(
        "No open slots, or no realistic targets for the open needs. Release more players or relax the filters below."
    )

# ---------------- Projected XI ----------------
st.write("")
st.subheader("4 · Projected XI + Impact Player")
theme.caption(
    "Best combination from the players RR keeps plus the shortlist: keeper, 3 pace, 2 spin, 1 all-rounder, "
    "3 top-order and 2 finishers (the 12th is the Impact Player), with at most 4 overseas. Score = CRICQ Score in "
    f"that role; players with too few pressure balls count at {a.get('replacement_level', 45)}–{a.get('replacement_level', 45) + 5}."
)
xi = au.projected_xi(state["kept"], plan, bat, bowl, cfg)
st.dataframe(
    pd.DataFrame(
        {
            "Role": xi.slot.where(xi.role_in_xi == "XI", "Impact Player (" + xi.slot.str.lower() + ")"),
            "Player": xi.player,
            "CRICQ Score in role": xi.score,
            "Overseas": xi.overseas,
            "From": xi.source,
        }
    ),
    hide_index=True,
    use_container_width=True,
    height=458,
    column_config={
        "CRICQ Score in role": st.column_config.ProgressColumn(min_value=30, max_value=80, format="%.0f"),
    },
)

# ---------------- Target finder ----------------
st.write("")
st.subheader("Target finder")
f1, f2, f3, f4 = st.columns([1.4, 1, 1, 1.2])
labels = dict(zip(need_tab.need, need_tab.label, strict=True))
pick = f1.multiselect("Role", list(labels), format_func=lambda k: labels[k], placeholder="All roles")
nat = f2.segmented_control("Players", ["All", "Indian", "Overseas"], default="All")
minp = f3.select_slider(
    "Availability at least",
    options=[0.15, 0.2, 0.35, 0.45, 0.6, 0.75, 0.9],
    value=0.35,
    format_func=lambda x: f"{x:.0%}",
)
search = f4.text_input("Find a player", placeholder="Type a name", max_chars=60, key="auc_search")
v = pool[pool.avail_prob >= minp]
if pick:
    v = v[v.need.isin(pick)]
if nat == "Indian":
    v = v[~v.overseas.astype(bool)]
elif nat == "Overseas":
    v = v[v.overseas.astype(bool)]
if search:
    v = v[v.display_name.str.contains(search[:60], case=False, na=False, regex=False)]
show = pd.DataFrame(
    {
        "Player": v.display_name,
        "Fits": v.need_label,
        "Need": v.need_level,
        "CRICQ Score": v.clutch_score.round(1),
        "Availability": v.status_label,
        "Chance in auction": (v.avail_prob * 100).round(0),
        "Overseas": v.overseas.astype(bool),
        "Why (playing time + news)": v.status_note,
        "Priority": v.priority.round(1),
        "Source": v.status_source.where(v.status_source.astype(str).str.startswith("http")),
    }
)
st.dataframe(
    show,
    hide_index=True,
    use_container_width=True,
    height=420,
    column_config={
        "CRICQ Score": st.column_config.ProgressColumn(min_value=20, max_value=90, format="%.1f"),
        "Chance in auction": st.column_config.NumberColumn(
            format="%d%%", help="Rough chance the player is in the 16 Dec pool"
        ),
        "Source": st.column_config.LinkColumn(display_text="source"),
        "Why (playing time + news)": st.column_config.TextColumn(width="large"),
    },
)

# ---------------- Watch list + unavailable ----------------
c1, c2 = st.columns(2)
with c1:
    st.subheader("Watch list for 17 Nov")
    theme.caption(
        "Strong fits for RR's needs who are still under contract. Move them up the plan if they are released."
    )
    wl = au.watch_list(pool, need_tab)
    st.dataframe(
        pd.DataFrame(
            {
                "Player": wl.display_name,
                "Team": wl.team_2027.map(theme.short),
                "Fits": wl.need_label,
                "CRICQ Score": wl.clutch_score.round(1),
                "Overseas": wl.overseas.astype(bool),
            }
        ),
        hide_index=True,
        use_container_width=True,
    )
with c2:
    st.subheader("Top players RR can't sign")
    theme.caption("Retained cores, trades, retirements and IPL-ineligible players — no plan should depend on them.")
    na = au.not_available(bat, bowl, n=8)
    st.dataframe(
        pd.DataFrame(
            {
                "Player": na.display_name,
                "As": na.kind,
                "CRICQ Score": na.clutch_score.round(1),
                "Why not": na.status_label,
                "Team": na.team_2027.fillna("").map(theme.short),
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

with st.expander("Sources and how availability is decided"):
    st.markdown(
        "**1 · Hard facts win** — `data/external/player_status_2027.csv`: retirements, confirmed trades, bans, eligibility "
        "risks and, after 17 Nov, the official retained / released lists (status `retained` or `released`).  \n"
        "**2 · News consensus** — `data/external/retention_reports_2027.csv`: every outlet's call on every player "
        "(retain / release), weighted by kind: official 10, sourced report 2, prediction list 1, opinion 0.5. "
        "Each outlet counts once per player.  \n"
        "**3 · Playing time** — from the Data Pack: regulars (60%+ of their team's 2026 games) count as a strong "
        "'retain'; players who did not play count toward 'release'.  \n"
        "Chance of release = 1 / (1 + e^−(−0.4 + playing-time + news)). ≥ 70% tipped for release · 40–70% mixed · "
        "15–40% under contract · under 15% core player. Pakistan players can't play the IPL; Bangladesh players carry "
        "a selection risk; players not on a 2026 squad are free agents or must register."
    )
    t1, t2 = st.tabs(["Hard facts", "News calls"])
    with t1:
        stf = data.status_file()
        st.dataframe(
            stf[["player", "status", "team_2027", "note", "source_date", "source"]],
            hide_index=True,
            use_container_width=True,
            column_config={"source": st.column_config.LinkColumn(display_text="open")},
        )
    with t2:
        rpf = data.reports_file()
        st.dataframe(
            rpf[["player", "team", "verdict", "source", "kind", "date", "url"]],
            hide_index=True,
            use_container_width=True,
            column_config={"url": st.column_config.LinkColumn(display_text="open")},
        )
