"""RR Auction Board — turn pressure rankings into an IPL 2027 auction plan for Rajasthan Royals.

Every step is transparent and every input is editable by a selector:
  1. Squad state  — which RR players are kept → purse left, squad slots, overseas slots.
  2. Needs        — for each role, RR's strength = average CRICQ Score of its best `want` players
                    in that role (unranked squad players count at replacement level, 45).
                    Gap = quality bar (55) − strength.  Gap ≥ 7 → High, ≥ 3 → Medium, else Low.
  3. Targets      — every ranked player who could be in the auction pool, scored in the role they fit:
                    Priority = CRICQ Score in that role + need bonus (High +10, Medium +5) + 15 × availability
  4. Plan         — fill RR's open slots with realistic targets only (CRICQ Score ≥ 50, availability ≥ 35%):
                    High needs ask for 2 picks, Medium for 1; the best target across open needs goes first,
                    so scarce overseas slots go to the strongest overseas options. Two back-ups per slot.
                    Players still under contract elsewhere go on a watch list for release day.
"""

from __future__ import annotations

import pandas as pd

NEED_BONUS = {"High": 10.0, "Medium": 5.0, "Low": 0.0}
AVAIL_WEIGHT = 15.0
BUYBACK_PROB = 0.9
BUYBACK_LABEL = "Released by RR — buy back cheaper?"

KEEP_COLS = [
    "player_id",
    "display_name",
    "status",
    "status_label",
    "status_note",
    "status_source",
    "status_date",
    "team_2027",
    "nationality",
    "overseas",
    "avail_prob",
    "pace_spin",
    "role",
    "clutch_score",
    "score_lo",
    "score_hi",
    "p_balls",
    "last_season",
]


def squad_state(squad: pd.DataFrame, release: set[str], cfg: dict) -> dict:
    a = cfg["auction"]
    kept = squad[~squad.player.isin(release)].copy()
    gone = squad[squad.player.isin(release)].copy()
    return {
        "kept": kept,
        "released": gone,
        "purse_cr": round(a["salary_cap_cr"] - kept.fee_cr.sum(), 2),
        "freed_cr": round(gone.fee_cr.sum(), 2),
        "squad_kept": int(len(kept)),
        "slots": int(max(a["max_squad"] - len(kept), 0)),
        "overseas_kept": int(kept.overseas.sum()),
        "overseas_slots": int(max(a["max_overseas"] - kept.overseas.sum(), 0)),
    }


def default_release(squad: pd.DataFrame, include_review: bool = True) -> set[str]:
    p = {"release", "review"} if include_review else {"release"}
    return set(squad[squad.projection.isin(p)].player)


def _fits(t: pd.DataFrame, nd: dict) -> pd.Series:
    m = pd.Series(True, index=t.index)
    if "roles" in nd:
        m &= t.role.isin(nd["roles"])
    if "pace_spin" in nd:
        m &= t.pace_spin.eq(nd["pace_spin"])
    for col, lo in (nd.get("min_share") or {}).items():
        m &= t.get(col, pd.Series(0.0, index=t.index)).fillna(0) >= lo
    return m


def role_table(bat: pd.DataFrame, bowl: pd.DataFrame, nd: dict) -> pd.DataFrame:
    """Players who fit one need, with their CRICQ Score *in that role* (all-rounders: bat/bowl average)."""
    if nd["table"] == "both":
        b = bat[["player_id", "clutch_score", "role", "eligible"]]
        w = bowl[_fits(bowl, {k: v for k, v in nd.items() if k == "pace_spin"})]
        j = w[[c for c in KEEP_COLS + ["eligible"] if c in w.columns]].merge(
            b, on="player_id", suffixes=("_bowl", "_bat")
        )
        j["eligible"] = j.eligible_bowl & j.eligible_bat
        j["clutch_score"] = (j.clutch_score_bowl + j.clutch_score_bat) / 2
        j["role"] = "All-rounder (" + j.role_bat + " / " + j.role_bowl + ")"
        j["score_lo"] = j["score_hi"] = float("nan")
        return j.drop(columns=["eligible_bowl", "eligible_bat"])
    t = bat if nd["table"] == "bat" else bowl
    return t[_fits(t, nd)][[c for c in KEEP_COLS + ["eligible"] if c in t.columns]].copy()


def needs(kept: pd.DataFrame, bat: pd.DataFrame, bowl: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    a = cfg["auction"]
    bar, repl = a["quality_bar"], a.get("replacement_level", 45)
    rows = []
    for key, nd in a["needs"].items():
        who = kept[kept.covers.map(lambda c, k=key: k in c)].player
        # a squad player counts in the role they are listed for, using the matching ranking
        t = role_table(bat, bowl, {k: v for k, v in nd.items() if k in ("table", "pace_spin")})
        sc = t[t.eligible].set_index("display_name").clutch_score
        scores = sorted(((p, float(sc[p]) if p in sc.index else None) for p in who), key=lambda x: -(x[1] or repl))
        vals = [s if s is not None else repl for _, s in scores][: nd["want"]]
        vals += [repl - 5] * (nd["want"] - len(vals))  # an empty slot is worse than an unproven player
        strength = sum(vals) / max(len(vals), 1)
        gap = bar - strength
        level = "High" if gap >= 7 else "Medium" if gap >= 3 else "Low"
        rows.append(
            dict(
                need=key,
                label=nd["label"],
                want=nd["want"],
                strength=round(strength, 1),
                gap=round(gap, 1),
                level=level,
                proven=sum(1 for _, s in scores if s is not None and s >= bar),
                squad_players=", ".join(f"{p} ({s:.0f})" if s is not None else f"{p} (unranked)" for p, s in scores),
            )
        )
    return pd.DataFrame(rows).sort_values("gap", ascending=False).reset_index(drop=True)


def targets(
    bat: pd.DataFrame,
    bowl: pd.DataFrame,
    need_tab: pd.DataFrame,
    kept_names: set[str],
    cfg: dict,
    released_names: set[str] = frozenset(),
    min_prob: float = 0.15,
) -> pd.DataFrame:
    """One row per (player, need) for every ranked player who might be in the auction pool."""
    level = need_tab.set_index("need").level
    rows = []
    for key, nd in cfg["auction"]["needs"].items():
        c = role_table(bat, bowl, nd)
        c = c[c.eligible].copy()
        c["need"], c["need_label"] = key, nd["label"]
        rows.append(c)
    pool = pd.concat(rows, ignore_index=True)
    pool = pool[~pool.display_name.isin(kept_names)].copy()
    back = pool.display_name.isin(released_names)
    pool.loc[back, "avail_prob"] = BUYBACK_PROB
    pool.loc[back, "status_label"] = BUYBACK_LABEL
    pool = pool[pool.avail_prob >= min_prob]
    pool["need_level"] = pool.need.map(level)
    pool["priority"] = pool.clutch_score + pool.need_level.map(NEED_BONUS) + AVAIL_WEIGHT * pool.avail_prob
    return pool.sort_values("priority", ascending=False).reset_index(drop=True)


def plan(pool: pd.DataFrame, need_tab: pd.DataFrame, state: dict, cfg: dict, backups: int = 2) -> pd.DataFrame:
    """Shortlist one target per open slot.

    Each need asks for picks (High: 2, Medium: 1). At every step the single best realistic target across
    all needs that still ask is taken, so scarce overseas slots go to the strongest overseas options rather
    than to whichever need happens to be listed first. Spare slots go to the best remaining fit anywhere.
    """
    a = cfg["auction"]
    lo_score, lo_prob = a.get("plan_min_score", 50), a.get("plan_min_prob", 0.35)
    real = pool[(pool.clutch_score >= lo_score) & (pool.avail_prob >= lo_prob)]
    lvl = need_tab.set_index("need").level
    ask = {n: {"High": 2, "Medium": 1}.get(lvl[n], 0) for n in need_tab.need}
    slots, os_slots = state["slots"], state["overseas_slots"]
    picked, rows = set(), []
    while len(rows) < slots:
        open_needs = [n for n, k in ask.items() if k > 0] or list(ask)
        cand = real[real.need.isin(open_needs) & ~real.player_id.isin(picked)]
        if os_slots <= 0:
            cand = cand[~cand.overseas.astype(bool)]
        if not len(cand):
            if any(ask.values()):
                ask = {n: 0 for n in ask}  # nothing realistic left for the open needs: use spare slots
                continue
            break
        top = cand.iloc[0]  # pool is sorted by priority
        key = top.need
        picked.add(top.player_id)
        os_slots -= int(bool(top.overseas))
        ask[key] = max(ask.get(key, 0) - 1, 0)
        alts = pool[(pool.need == key) & ~pool.player_id.isin(picked) & (pool.clutch_score >= lo_score)]
        if os_slots <= 0:
            alts = alts[~alts.overseas.astype(bool)]
        alts = alts.iloc[:backups]
        rows.append(
            dict(
                slot=len(rows) + 1,
                need=key,
                need_label=top.need_label,
                need_level=top.need_level,
                target=top.display_name,
                overseas=bool(top.overseas),
                clutch_score=round(float(top.clutch_score), 1),
                availability=top.status_label,
                avail_prob=float(top.avail_prob),
                priority=round(float(top.priority), 1),
                plan_b=", ".join(f"{r.display_name} ({r.clutch_score:.0f})" for r in alts.itertuples()),
            )
        )
    return pd.DataFrame(rows)


def watch_list(pool: pd.DataFrame, need_tab: pd.DataFrame, n: int = 12) -> pd.DataFrame:
    """Strong fits still under contract: bid only if their team releases them on 17 Nov."""
    hot = set(need_tab[need_tab.level != "Low"].need)
    w = pool[(pool.status == "under_contract") & pool.need.isin(hot) & (pool.clutch_score >= 52)]
    return w.sort_values("clutch_score", ascending=False).drop_duplicates("player_id").head(n)


def not_available(bat: pd.DataFrame, bowl: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """The best pressure players RR can't sign — so nobody builds a plan around them."""
    out = []
    for lab, t in (("Batter", bat), ("Bowler", bowl)):
        x = t[t.eligible & (t.avail_prob < 0.15) & (t.status != "rr_squad")]
        x = x.sort_values("clutch_score", ascending=False).head(n).assign(kind=lab)
        out.append(
            x[["kind", "display_name", "clutch_score", "status_label", "team_2027", "status_note", "status_source"]]
        )
    return pd.concat(out, ignore_index=True)


XI_TEMPLATE = [
    # (slot label, need key used to judge the player, score source)
    ("Wicketkeeper", "wicketkeeper", "bat"),
    ("Pace bowler", "pace", "bowl"),
    ("Pace bowler", "pace", "bowl"),
    ("Pace bowler", "pace", "bowl"),
    ("Spinner", "spin", "bowl"),
    ("Spinner", "spin", "bowl"),
    ("All-rounder", "allrounder", "both"),
    ("Top order", "top_order", "bat"),
    ("Top order", "top_order", "bat"),
    ("Top order", "top_order", "bat"),
    ("Finisher", "finisher", "bat"),
    ("Finisher", "finisher", "bat"),
]
_COVERS = {
    "wicketkeeper": {"wicketkeeper"},
    "pace": {"pace_death", "pace_powerplay", "allrounder_pace"},
    "spin": {"spin", "allrounder_spin"},
    "allrounder": {"allrounder_pace", "allrounder_spin"},
    "top_order": {"top_order"},
    "finisher": {"finisher", "wicketkeeper", "allrounder_pace", "allrounder_spin"},
}


def _score_of(name, bat, bowl, how, repl):
    def one(t):
        r = t[t.display_name == name]
        if not len(r):
            return None
        r = r.iloc[0]
        if bool(r.eligible):
            return float(r.clutch_score)
        # too few pressure balls to be ranked: credit at most 'replacement + 5' so small samples can't dominate
        return min(float(r.clutch_score), repl + 5) if r.p_balls >= 40 else None

    b, w = one(bat), one(bowl)
    if how == "bat":
        return b if b is not None else repl
    if how == "bowl":
        return w if w is not None else repl
    vals = [v if v is not None else repl for v in (b, w)]
    return sum(vals) / 2


def projected_xi(kept: pd.DataFrame, picks: pd.DataFrame, bat: pd.DataFrame, bowl: pd.DataFrame, cfg: dict):
    """RR's best XI + Impact Player from the players kept plus the auction shortlist (max 4 overseas)."""
    repl = cfg["auction"].get("replacement_level", 45)
    pool = [
        dict(player=r.player, covers=set(r.covers), overseas=bool(r.overseas), source="Kept") for r in kept.itertuples()
    ]
    for r in picks.itertuples() if len(picks) else []:
        pool.append(dict(player=r.target, covers={r.need}, overseas=bool(r.overseas), source="Auction target"))
    used, os_used, rows = set(), 0, []
    for label, key, how in XI_TEMPLATE:
        best = None
        for c in pool:
            if c["player"] in used or not (c["covers"] & _COVERS[key]):
                continue
            if c["overseas"] and os_used >= 4:
                continue
            sc = _score_of(c["player"], bat, bowl, how, repl)
            if best is None or sc > best[1]:
                best = (c, sc)
        if best is None:
            rows.append(dict(slot=label, player="— gap —", score=None, overseas=False, source="Need to buy"))
            continue
        c, sc = best
        used.add(c["player"])
        os_used += int(c["overseas"])
        rows.append(
            dict(slot=label, player=c["player"], score=round(sc, 1), overseas=c["overseas"], source=c["source"])
        )
    xi = pd.DataFrame(rows)
    xi["role_in_xi"] = ["XI"] * 11 + ["Impact Player"]
    return xi
