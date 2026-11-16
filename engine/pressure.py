"""Step 4 — the Pressure Index (0-100).

Pressure Index = blend of two parts, each ranked as a percentile:
  1. STAKES  — how much this ball can swing the result: the expected change in win probability
               over the likely outcomes (dot, 1, 2, 4, 6, wicket).
  2. SQUEEZE — how tough the scoreboard is:
       chasing: runs still needed / runs a side normally scores with these balls and wickets left
       setting: venue par score / projected total (current score + normal runs still to come)
     ranked within each innings so both innings contribute.
The blend is re-ranked to 0-100. Balls at or above the configured percentile are "high pressure".
"""

import numpy as np
import pandas as pd


def add_squeeze(b, err, vpar):
    fmt = b.format.values
    bl = b.balls_left.clip(0, 120).astype(int).values
    wk = b.wkts_in_hand.clip(0, 10).astype(int).values
    rest = np.where(fmt == "IPL", err["IPL"][bl, wk], err["T20I"][bl, wk])
    b["par_rest"] = rest
    # wicket value: runs a side loses (on average) by losing one more wicket now
    wk1 = np.clip(wk - 1, 0, 10)
    rest1 = np.where(fmt == "IPL", err["IPL"][bl, wk1], err["T20I"][bl, wk1])
    b["wicket_value"] = np.clip(rest - rest1, 0, None)
    par = b.venue_par * b.inn_balls / 120
    projected = b.score_before + rest
    sq1 = par / projected.clip(lower=1)
    sq2 = b.runs_needed / np.clip(rest, 0.5, None)
    b["squeeze"] = np.where(b.innings == 1, sq1, sq2)
    b["squeeze"] = b["squeeze"].clip(0, 4)
    return b


def add_pressure(b, w_stakes=0.5, w_squeeze=0.5, high_pct=75):
    b["stakes_pct"] = b.leverage.rank(pct=True)
    b["squeeze_pct"] = b.groupby("innings")["squeeze"].rank(pct=True)
    blend = w_stakes * b.stakes_pct + w_squeeze * b.squeeze_pct
    b["pressure_index"] = (blend.rank(pct=True) * 100).round(1)
    b["high_pressure"] = (b.pressure_index >= high_pct).astype(int)
    return b


def validation_tables(b):
    """Evidence that the index separates pressure from ordinary balls."""
    t = b[b.faced == 1].copy()
    t["decile"] = pd.cut(
        t.pressure_index,
        np.arange(0, 101, 10),
        labels=[f"{i}-{i + 10}" for i in range(0, 100, 10)],
        include_lowest=True,
    )
    by_dec = t.groupby("decile", observed=True).agg(
        balls=("faced", "size"),
        dismissal_pct=("striker_out", "mean"),
        dot_pct=("bat_runs", lambda s: (s == 0).mean()),
        boundary_pct=("is_four", "mean"),
        six_pct=("is_six", "mean"),
        strike_rate=("bat_runs", "mean"),
    )
    by_dec["dismissal_pct"] *= 100
    by_dec["dot_pct"] *= 100
    by_dec["boundary_pct"] = (by_dec.boundary_pct + by_dec.six_pct) * 100
    by_dec["strike_rate"] *= 100
    by_dec = by_dec.drop(columns="six_pct").reset_index()
    by_phase = (
        b.groupby(["innings", "phase"])
        .agg(mean_pi=("pressure_index", "mean"), high_share=("high_pressure", "mean"), balls=("pressure_index", "size"))
        .reset_index()
    )
    by_phase["high_share"] *= 100
    return by_dec, by_phase
