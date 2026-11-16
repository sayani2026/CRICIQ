"""Step 3 — win-probability models.

Two models (setting a total / chasing), gradient boosting with monotonic constraints so the
model always respects cricket logic (more wickets in hand never lowers your chance, etc.).
* Validation: train on 2022-2024, test on 2025-2026 seasons the model never saw.
* Predictions used downstream are cross-fitted (5 folds grouped by match), so no ball is
  scored by a model that saw its own match.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

F1 = ["score_before", "balls_left", "wkts_in_hand", "venue_par", "is_ipl"]
C1 = [1, 1, 1, -1, 0]
F2 = ["runs_needed", "balls_left", "wkts_in_hand", "rrr", "is_ipl"]
C2 = [-1, 1, 1, -1, 0]

# outcome set used for leverage: (runs, wicket)
OUTCOMES = [(0, 0), (1, 0), (2, 0), (4, 0), (6, 0), (0, 1)]


def _model(cst):
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, min_samples_leaf=200, l2_regularization=1.0, monotonic_cst=cst, random_state=7
    )


def _feats(df, inn):
    return df[F1] if inn == 1 else df[F2]


def shifted(df, runs, wicket):
    s = df.copy()
    s["score_before"] = s.score_before + runs
    s["balls_left"] = (s.balls_left - 1).clip(lower=1)
    s["wkts_in_hand"] = (s.wkts_in_hand - wicket).clip(lower=0)
    s["runs_needed"] = s.runs_needed - runs
    s["rrr"] = s.runs_needed / s.balls_left * 6
    return s


def terminal(df, runs, wicket, inn):
    """Win probability forced by the rules after an outcome (chase won / all out / balls gone)."""
    out = np.full(len(df), np.nan)
    if inn == 2:
        won = (df.runs_needed - runs) <= 0
        lost = ((df.wkts_in_hand - wicket) <= 0) | ((df.balls_left - 1) <= 0)
        out[np.asarray(lost & ~won)] = 0.0
        out[np.asarray(won)] = 1.0
    return out


def validate(b):
    """Time-based hold-out: train <= 2024, test 2025-2026."""
    rows = []
    cal = []
    for inn, F, C in [(1, F1, C1), (2, F2, C2)]:
        d = b[(b.innings == inn) & b.has_result]
        tr, te = d[d.season_year <= 2024], d[d.season_year >= 2025]
        mdl = _model(C).fit(tr[F], tr.bat_won)
        p = mdl.predict_proba(te[F])[:, 1]
        rows.append(
            dict(
                innings=inn,
                train_balls=len(tr),
                test_balls=len(te),
                auc=roc_auc_score(te.bat_won, p),
                brier=brier_score_loss(te.bat_won, p),
                brier_baseline=brier_score_loss(te.bat_won, np.full(len(te), tr.bat_won.mean())),
            )
        )
        bins = pd.cut(p, np.linspace(0, 1, 11), include_lowest=True)
        c = (
            pd.DataFrame({"pred": p, "obs": te.bat_won.values, "bin": bins})
            .groupby("bin", observed=True)
            .agg(pred=("pred", "mean"), obs=("obs", "mean"), n=("obs", "size"))
            .reset_index(drop=True)
        )
        c["innings"] = inn
        cal.append(c)
    return pd.DataFrame(rows), pd.concat(cal)


def crossfit(b, n_splits=5):
    """Cross-fitted WP before the ball and expected |change| in WP over likely outcomes (leverage)."""
    b["wp"] = np.nan
    b["leverage"] = np.nan
    # outcome probabilities by innings x phase x format, from legal balls
    leg = b[b.legal == 1].copy()
    leg["oc"] = np.select(
        [leg.wkt == 1, leg.bat_runs >= 6, leg.bat_runs >= 4, leg.bat_runs >= 2, leg.bat_runs == 1],
        ["W", "6", "4", "2", "1"],
        "0",
    )
    probs = leg.groupby(["innings", "phase", "format"]).oc.value_counts(normalize=True).unstack(fill_value=0)
    key = {"0": (0, 0), "1": (1, 0), "2": (2, 0), "4": (4, 0), "6": (6, 0), "W": (0, 1)}
    for inn, F, C in [(1, F1, C1), (2, F2, C2)]:
        idx = b.index[b.innings == inn]
        d = b.loc[idx]
        train_mask = d.has_result.values
        gkf = GroupKFold(n_splits=n_splits)
        wp = np.zeros(len(d))
        lev = np.zeros(len(d))
        pr = probs.loc[inn].reindex(pd.MultiIndex.from_arrays([d.phase, d.format])).fillna(0)
        for tr, te in gkf.split(d, groups=d.match_id):
            trm = tr[train_mask[tr]]
            mdl = _model(C).fit(d.iloc[trm][F], d.iloc[trm].bat_won)
            dt = d.iloc[te]
            w0 = mdl.predict_proba(dt[F])[:, 1]
            wp[te] = w0
            acc = np.zeros(len(te))
            for code, (r, w) in key.items():
                s = shifted(dt, r, w)
                w1 = mdl.predict_proba(_feats(s, inn))[:, 1]
                t = terminal(dt, r, w, inn)
                w1 = np.where(np.isnan(t), w1, t)
                acc += pr[code].values[te] * np.abs(w1 - w0)
            lev[te] = acc
        b.loc[idx, "wp"] = wp
        b.loc[idx, "leverage"] = lev
    return b
