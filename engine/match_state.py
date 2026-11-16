"""Step 2 — rebuild the live scoreboard for every ball and check it against official results."""

import re

import numpy as np
import pandas as pd


def add_state(b):
    g = b.groupby(["match_id", "innings"], sort=False)
    b["score_before"] = g.total.cumsum() - b.total
    b["wkts_before"] = g.wkt.cumsum() - b.wkt
    b["legal_before"] = g.legal.cumsum() - b.legal
    b["inn_balls"] = np.where(b.innings == 1, b.first_inn_revised_overs, b.second_inn_revised_overs)
    b["inn_balls"] = pd.Series(b.inn_balls).fillna(120).astype(int).values
    tot = b.groupby(["match_id", "innings"]).total.sum().unstack()
    b["first_total"] = b.match_id.map(tot[1]).fillna(0).astype(int)
    b["target"] = np.where(b.revised_target.notna(), b.revised_target, b.first_total + 1)
    b.loc[b.innings == 1, "target"] = np.nan
    b["balls_left"] = (b.inn_balls - b.legal_before).clip(lower=1)
    b["wkts_in_hand"] = (10 - b.wkts_before).clip(lower=0)
    b["over"] = (b.legal_before // 6 + 1).clip(upper=20).astype(int)
    b["phase"] = pd.cut(b.over, [0, 6, 15, 20], labels=["Powerplay", "Middle", "Death"]).astype(str)
    b["crr"] = np.where(b.legal_before > 0, b.score_before / b.legal_before.clip(lower=1) * 6, 0.0)
    b["runs_needed"] = b.target - b.score_before
    b["rrr"] = np.where(b.innings == 2, b.runs_needed / b.balls_left * 6, np.nan)
    b["ball_label"] = (b.legal_before // 6).astype(str) + "." + (b.legal_before % 6 + 1).astype(str)
    # wickets in the previous 18 balls of this innings (collapse signal)
    b["wkts_last18"] = g.wkt.transform(lambda s: s.shift(1).rolling(18, min_periods=1).sum()).fillna(0)
    b["bat_won"] = np.where(b.has_result, (b.batting_team_id == b.win_team_id).astype(float), np.nan)
    return b


def venue_par(b, m):
    """Par first-innings total per venue, shrunk toward the country+format average (k = 6 matches)."""
    f = (
        b[(b.innings == 1)]
        .groupby("match_id")
        .agg(
            total=("total", "sum"),
            balls=("inn_balls", "first"),
            venue_id=("venue_id", "first"),
            country=("venue_country", "first"),
            fmt=("format", "first"),
        )
    )
    f = f[f.balls >= 120]
    ctry = f.groupby(["country", "fmt"]).total.mean()
    glob = f.groupby("fmt").total.mean()
    v = (
        f.groupby(["venue_id", "fmt"])
        .agg(n=("total", "size"), mean=("total", "mean"), country=("country", "first"))
        .reset_index()
    )
    k = 6
    prior = [ctry.get((c, fm), glob.get(fm, glob.mean())) for c, fm in zip(v.country, v.fmt, strict=True)]
    v["par"] = (v.n * v["mean"] + k * np.array(prior)) / (v.n + k)
    return v, glob


def expected_runs_table(b):
    """Average runs still to come in a full 20-over innings from (balls left, wickets in hand), per format.
    Learned with a gradient-boosting model constrained to rise with balls left and wickets in hand."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    full = b[(b.inn_balls == 120) & (b.innings == 1)]
    rest = full.groupby(["match_id", "innings"]).total.transform("sum") - full.score_before
    X = np.c_[full.balls_left, full.wkts_in_hand, full.is_ipl]
    mdl = HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.05, min_samples_leaf=100, monotonic_cst=[1, 1, 0], random_state=0
    ).fit(X, rest)
    out = {}
    bl, wk = np.meshgrid(np.arange(121), np.arange(11), indexing="ij")
    for fmt, ipl in [("IPL", 1), ("T20I", 0)]:
        grid = mdl.predict(np.c_[bl.ravel(), wk.ravel(), np.full(bl.size, ipl)]).reshape(121, 11)
        grid[0, :] = 0
        grid[:, 0] = 0
        out[fmt] = np.clip(grid, 0, None)
    return out


def reconcile(b, m):
    """Check rebuilt totals against official result text. Returns a table of checks."""
    tot = b.groupby(["match_id", "innings"]).agg(total=("total", "sum"), wk=("wkt", "sum")).unstack()
    rows = []
    for r in m[m.has_result & m.match_id.isin(tot.index)].itertuples():
        res = str(r.result).lower()
        if "super over" in res or "tie" in res or "d/l" in res or "dls" in res or "method" in res:
            continue
        t1, t2 = tot.loc[r.match_id, ("total", 1)], tot.loc[r.match_id, ("total", 2)]
        w2 = tot.loc[r.match_id, ("wk", 2)]
        mr = re.search(r"(\d+)\s*run", res)
        mw = re.search(r"(\d+)\s*(wicket|wkt)", res)
        if mr and not pd.notna(r.revised_target):
            ok = (t1 - t2) == int(mr.group(1))
            rows.append((r.match_id, "runs", ok))
        elif mw:
            tgt = r.revised_target if pd.notna(r.revised_target) else t1 + 1
            ok = (t2 >= tgt) and (10 - w2 == int(mw.group(1)) or w2 < 10)
            rows.append((r.match_id, "wickets", ok))
    return pd.DataFrame(rows, columns=["match_id", "type", "ok"])
