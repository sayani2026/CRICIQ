"""Cricket parameters — how each player performs in every kind of situation.

The CRICQ Score answers "who is reliable under pressure". Selectors also ask *which* pressure:
a death over in a chase, a collapse, a slow pitch, a strong attack, a knockout, left-arm pace...
This module tags every ball with those parameters and measures players in each one.

Every number is **runs above an average player in the same situation, per 100 balls**
(batters: runs added; bowlers: runs saved, wickets included at the capped wicket value). A shrinkage
of `K_BALLS` balls toward zero stops tiny samples from topping a list.

Parameters (column → levels)
  phase        Powerplay (1–6) · Middle (7–15) · Death (16–20)
  innings      Setting a total · Chasing
  wickets      Batting side 8–10 wickets in hand · 5–7 · 0–4 (tail exposed)
  collapse     2+ wickets in the last 3 overs · Normal
  pitch        Low-scoring ground · Average ground · High-scoring ground   (venue par terciles — the Data Pack has
               no pitch reports, so the venue's normal first-innings score stands in for pitch type)
  opposition   Strong opposition (Test nations / IPL) · Weaker opposition
  stage        Knockout · League
  competition  IPL · T20I · Other T20
  bowler_type  Right-arm pace · Left-arm pace · Off-spin · Leg-spin · Left-arm spin      (batters only)
  batter_hand  vs right-handers · vs left-handers                                        (bowlers only)
  pressure     High pressure (top 25%) · Normal
  rr_home      At RR home venues · Elsewhere
"""

from __future__ import annotations

import numpy as np
import pandas as pd

K_BALLS = 30
FACTORS = {
    "phase": "Phase of innings",
    "innings": "Setting or chasing",
    "wickets": "Wickets in hand",
    "collapse": "Collapse in progress",
    "pitch": "Pitch / ground type",
    "opposition": "Opposition strength",
    "stage": "Match stage",
    "competition": "Competition",
    "bowler_type": "Bowler type faced",
    "batter_hand": "Batter hand bowled to",
    "pressure": "Pressure",
    "rr_home": "RR home venues",
}
FACTOR_COLUMNS = [f"{f}_f" for f in FACTORS if f != "opposition"] + ["opp_bat_f", "opp_bowl_f"]
BAT_FACTORS = [f for f in FACTORS if f != "batter_hand"]
BOWL_FACTORS = [f for f in FACTORS if f != "bowler_type"]


def _bowler_type(s: pd.Series) -> pd.Series:
    s = s.fillna("").str.lower()
    out = np.select(
        [
            s.str.contains("offbreak|off-break|off break"),
            s.str.contains("leg-break|legbreak|leg break|googly"),
            s.str.contains("orthodox|chinaman|left-arm wrist|slow left"),
            s.str.startswith("left-arm"),
            s.str.startswith("right-arm"),
        ],
        ["Off-spin", "Leg-spin", "Left-arm spin", "Left-arm pace", "Right-arm pace"],
        default="Other",
    )
    return pd.Series(out, index=s.index)


def context(b: pd.DataFrame, rr_home_venues: set | None = None) -> pd.DataFrame:
    """Add one column per parameter (string levels) to the ball table. Super overs are dropped."""
    b = b[b.innings.isin([1, 2])].drop(columns=[c for c in FACTOR_COLUMNS if c in b.columns]).copy()
    b["innings_f"] = np.where(b.innings == 1, "Setting a total", "Chasing")
    w = b.wkts_in_hand
    b["wickets_f"] = np.select([w >= 8, w >= 5], ["8–10 wickets in hand", "5–7 wickets in hand"], "0–4 wickets in hand")
    recent = (
        b.groupby(["match_id", "innings"], sort=False)
        .wkt.transform(lambda x: x.shift(1, fill_value=0).rolling(18, min_periods=1).sum())
        .fillna(0)
    )
    b["collapse_f"] = np.where(recent >= 2, "Collapse (2+ wickets in last 3 overs)", "No collapse")
    par = b.groupby("match_id").venue_par.first()
    lo, hi = par.quantile([1 / 3, 2 / 3])
    b["pitch_f"] = np.select(
        [b.venue_par < lo, b.venue_par > hi],
        [f"Low-scoring ground (par < {lo:.0f})", f"High-scoring ground (par > {hi:.0f})"],
        f"Average ground (par {lo:.0f}–{hi:.0f})",
    )
    b["stage_f"] = np.where(b.knock_out.astype(int) == 1, "Knockout", "League")
    b["competition_f"] = b.format.astype(str)
    b["phase_f"] = b.phase.astype(str)
    b["pressure_f"] = np.where(b.high_pressure.astype(bool), "High pressure", "Normal")
    b["bowler_type_f"] = _bowler_type(b.bowling_type)
    b["batter_hand_f"] = np.where(b.batting_type == "LHB", "vs left-handers", "vs right-handers")
    b["opp_bat_f"] = np.where(b.bowl_tier == 1, "Strong opposition", "Weaker opposition")  # batter's opponent
    b["opp_bowl_f"] = np.where(b.bat_tier == 1, "Strong opposition", "Weaker opposition")  # bowler's opponent
    home = rr_home_venues or set()
    b["rr_home_f"] = np.where(b.venue_id.isin(home), "At RR home venues", "Elsewhere")
    return b


def _col(factor: str, role: str) -> str:
    if factor == "opposition":
        return "opp_bat_f" if role == "bat" else "opp_bowl_f"
    return f"{factor}_f"


def _agg(x: pd.DataFrame, role: str, k: float) -> pd.DataFrame:
    """Aggregate a ball slice per player: balls, runs, outs, strike/economy rate, value per 100 (shrunk)."""
    if role == "bat":
        x = x[x.faced == 1]
        g = x.groupby("striker_id")
        out = pd.DataFrame(
            {
                "balls": g.size(),
                "runs": g.bat_runs.sum(),
                "outs": g.striker_out.sum(),
                "value": g.bat_adj.sum(),
            }
        )
        out["rate"] = 100 * out.runs / out.balls  # strike rate
    else:
        x = x[x.legal == 1]
        g = x.groupby("bowler_id")
        out = pd.DataFrame(
            {
                "balls": g.size(),
                "runs": g.bowler_runs.sum(),
                "outs": g.bowler_wkt.sum(),
                "value": g.bowl_adj.sum(),
            }
        )
        out["rate"] = 6 * out.runs / out.balls  # economy
    out["per100"] = 100 * out.value / (out.balls + k)
    out.index.name = "player_id"
    return out


def splits(b: pd.DataFrame, role: str, players=None, min_balls: int = 12, k: float = K_BALLS) -> pd.DataFrame:
    """Long table: one row per (player, parameter, level) with all-ball and high-pressure numbers."""
    rows = []
    facs = BAT_FACTORS if role == "bat" else BOWL_FACTORS
    hp = b[b.high_pressure.astype(bool)]
    for f in facs:
        col = _col(f, role)
        for lev, part in b.groupby(col, observed=True):
            a = _agg(part, role, k)
            p = _agg(hp[hp[col] == lev], role, k).add_prefix("p_")
            t = a.join(p, how="left")
            t = t[t.balls >= min_balls]
            t["factor"], t["level"] = f, lev
            rows.append(t.reset_index())
    out = pd.concat(rows, ignore_index=True)
    if players is not None:
        out = out[out.player_id.isin(players)]
    out["role"] = role
    for c in ("p_balls", "p_runs", "p_outs"):
        out[c] = out[c].fillna(0).astype(int)
    return out


def matchups(b: pd.DataFrame, min_balls: int = 6) -> pd.DataFrame:
    """Batter vs bowler head-to-head, all balls and high-pressure balls."""
    x = b[b.faced == 1]
    key = ["striker_id", "bowler_id"]

    def agg(d):
        g = d.groupby(key)
        return pd.DataFrame(
            {"balls": g.size(), "runs": g.bat_runs.sum(), "outs": g.striker_out.sum(), "value": g.bat_adj.sum()}
        )

    a = agg(x)
    p = agg(x[x.high_pressure.astype(bool)]).add_prefix("p_")
    t = a.join(p, how="left").fillna({"p_balls": 0, "p_runs": 0, "p_outs": 0, "p_value": 0.0})
    t = t[t.balls >= min_balls].reset_index()
    for c in ("p_balls", "p_runs", "p_outs"):
        t[c] = t[c].astype(int)
    return t


def scout(b: pd.DataFrame, role: str, filters: dict, min_balls: int = 40, k: float = K_BALLS) -> pd.DataFrame:
    """Rank players in any combination of parameters, e.g.
    scout(b, "bowl", {"phase": ["Death"], "innings": ["Setting a total"], "pressure": ["High pressure"]})."""
    x = b
    for f, levels in (filters or {}).items():
        if levels:
            x = x[x[_col(f, role)].isin(levels)]
    t = _agg(x, role, k)
    t = t[t.balls >= min_balls].sort_values("per100", ascending=False)
    return t.reset_index()


def strengths(sp: pd.DataFrame, pid, top: int = 3, min_balls: int = 30):
    """A player's best and worst situations (by value per 100 balls) — for plain-English scouting notes."""
    x = sp[(sp.player_id == pid) & (sp.balls >= min_balls) & (sp.factor != "pressure")]
    x = x.sort_values("per100", ascending=False)
    return x.head(top), x.tail(top).iloc[::-1]
