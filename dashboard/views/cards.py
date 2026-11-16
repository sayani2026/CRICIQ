"""Player cards — every ranked player as a rated card. Click a card's button to open his full profile."""

import streamlit as st

from components import cards, data, theme

theme.header(
    "Player cards",
    "Every ranked player as a card. The big number is his CRICQ Score (50 = average regular player, 70+ elite, "
    "80+ icon); the six attributes are percentiles against all ranked players, under pressure.",
)

c1, c2, c3, c4 = st.columns([1, 1.2, 1.4, 1.4])
role_lbl = c1.segmented_control("Show", ["Batters", "Bowlers"], default="Batters", key="cd_role")
role = "bowl" if role_lbl == "Bowlers" else "bat"
t = data.scores(role)
ranked = t[t["rank"].notna()].sort_values("rank")
show_n = c2.select_slider(
    "How many",
    options=[10, 20, 30, 50, len(ranked)],
    value=10,
    key="cd_n",
    format_func=lambda n: "All" if n == len(ranked) else f"Top {n}",
)
roles = ["All roles"] + sorted(ranked.role.dropna().unique())
pick = c3.selectbox("Role", roles, key=f"cd_roleflt_{role}")
search = c4.text_input("Find a player", placeholder="Type a name", max_chars=60, key="cd_search")

v = ranked
if pick != "All roles":
    v = v[v.role == pick]
if search:
    v = v[v.display_name.str.contains(search[:60], case=False, na=False, regex=False)]
v = v.head(show_n)

theme.caption(
    "Attributes — "
    + " · ".join(f"<b>{c}</b> {theme.esc(lab.lower())}" for c, _, _, lab in cards.ATTRS[role])
    + ". Tiers: <b>ICON</b> 80+, <b>ELITE</b> 70–79, <b>RARE</b> 60–69, <b>BASE</b> under 60."
)
if not len(v):
    st.info("No ranked player matches these filters.")
else:
    cards.grid(t, role, v, per_row=5, key="cards")

with st.expander("Add player photos"):
    st.markdown(
        "Open the **Player Image** folder inside the project. Every ranked player has a placeholder file named for him, "
        "for example `viratkohliimage.pdf` or `timdavidimage.pdf`. Save the player's photo (one you have the right to use) "
        "with the same name — `viratkohliimage.jpg`, `.png`, `.webp`, or a PDF containing the picture — and refresh this "
        "page. The photo appears on his card. `player_list.csv` in that folder lists every exact file name."
    )
