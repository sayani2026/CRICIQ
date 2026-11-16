"""Step 5 — what an average player would do on each ball, and how much each player added.

Four cross-fitted models (5 folds grouped by match):
  batting : expected runs off the bat, chance the striker is out      (balls faced)
  bowling : expected runs charged to bowler, chance of a bowler wicket (all deliveries)
Features describe only the SITUATION (innings, over, wickets in hand, balls left, required rate,
scoreboard squeeze, venue par, format, pace or spin) — never the player — so the expectation is
"an average player in exactly this spot".

Value added (in runs) per ball:
  batting = (runs - expected runs) - wicket value x (out - chance of out)
  bowling = (expected runs - runs conceded) + wicket value x (wicket - chance of wicket)
Wicket value = runs a side typically loses by losing one more wicket at that moment.
"""

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

FEATS = [
    "innings",
    "over",
    "wkts_in_hand",
    "balls_left",
    "rrr_f",
    "squeeze",
    "venue_par",
    "is_ipl",
    "spin",
    "season_year",
]


def _prep(b):
    b["rrr_f"] = np.where(b.innings == 2, b.rrr.clip(0, 36), -1.0)
    b["spin"] = b.pace_or_spin.eq("Spin").astype(int)
    return b


def _crossfit(d, target, kind, n_splits=5):
    pred = np.zeros(len(d))
    for tr, te in GroupKFold(n_splits=n_splits).split(d, groups=d.match_id):
        if kind == "reg":
            mdl = HistGradientBoostingRegressor(
                loss="poisson", max_iter=250, learning_rate=0.05, min_samples_leaf=200, random_state=3
            )
            mdl.fit(d.iloc[tr][FEATS], d.iloc[tr][target])
            pred[te] = mdl.predict(d.iloc[te][FEATS])
        else:
            mdl = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.05, min_samples_leaf=200, random_state=3)
            mdl.fit(d.iloc[tr][FEATS], d.iloc[tr][target])
            pred[te] = mdl.predict_proba(d.iloc[te][FEATS])[:, 1]
    return pred


def add_expected(b, wicket_cap=8.0):
    b = _prep(b)
    b["wicket_value"] = b.wicket_value.clip(upper=wicket_cap)
    fi = b.index[b.faced == 1]
    d = b.loc[fi]
    b.loc[fi, "x_runs"] = _crossfit(d, "bat_runs", "reg")
    b.loc[fi, "x_out"] = _crossfit(d, "striker_out", "clf")
    b["x_bowl_runs"] = _crossfit(b, "bowler_runs", "reg")
    b["x_bowl_wkt"] = _crossfit(b, "bowler_wkt", "clf")
    b["bat_value"] = np.where(
        b.faced == 1, (b.bat_runs - b.x_runs) - b.wicket_value * (b.striker_out - b.x_out), np.nan
    )
    b["bowl_value"] = (b.x_bowl_runs - b.bowler_runs) + b.wicket_value * (b.bowler_wkt - b.x_bowl_wkt)
    return b


def calibration(b):
    f = b[b.faced == 1]
    return {
        "bat_runs_actual": f.bat_runs.mean(),
        "bat_runs_expected": f.x_runs.mean(),
        "out_actual": f.striker_out.mean(),
        "out_expected": f.x_out.mean(),
        "bowl_runs_actual": b.bowler_runs.mean(),
        "bowl_runs_expected": b.x_bowl_runs.mean(),
        "bowl_wkt_actual": b.bowler_wkt.mean(),
        "bowl_wkt_expected": b.x_bowl_wkt.mean(),
    }
