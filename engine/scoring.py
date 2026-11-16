"""Step 6 — CRICQ Score and reliability.

For every batter and bowler:
  QUALITY      value added per high-pressure ball, adjusted for the strength of the opposition
  LIFT         pressure value minus the player's own normal value (do they rise or dip?)
  CONSISTENCY  share of pressure innings/spells (6+ pressure balls) with positive value
Small samples are pulled toward the league average (empirical-Bayes shrinkage; the pull strength
is estimated from the data). Every ball is weighted by recency and by opposition tier.
CRICQ Score = 50 + 10 x standardised blend (0.55 quality, 0.20 lift, 0.25 consistency) — 50 is an
average eligible player. A bootstrap over each player's matches gives a confidence range and a
rank range.
"""

import numpy as np
import pandas as pd


def add_weights(b, cfg):
    latest = b.season_year.max()
    rec = cfg["weights"]["recency_decay"] ** (latest - b.season_year)
    a = cfg["weights"]["associate_opposition"]
    b["w_bat"] = rec * np.where(b.bowl_tier == 2, a, 1.0)
    b["w_bowl"] = rec * np.where(b.bat_tier == 2, a, 1.0)
    return b


def estimate_k(v, w, g, min_n=60):
    """Shrinkage strength k = within-player ball variance / between-player true-skill variance."""
    d = pd.DataFrame({"v": v, "w": w, "g": g}).dropna()
    mu = np.average(d.v, weights=d.w)
    s2 = np.average((d.v - mu) ** 2, weights=d.w)
    agg = d.assign(wv=d.v * d.w).groupby("g").agg(n=("w", "sum"), s=("wv", "sum"))
    agg = agg[agg.n >= min_n]
    m = agg.s / agg.n
    tau2 = np.average((m - mu) ** 2, weights=agg.n) - np.average(s2 / agg.n, weights=agg.n)
    tau2 = max(tau2, s2 / 5000)
    return float(np.clip(s2 / tau2, 30, 5000)), float(mu)


def shrunk_mean(v, w, g, k, mu):
    d = pd.DataFrame({"wv": v * w, "w": w, "g": g}).groupby("g").sum()
    return (d.wv + k * mu) / (d.w + k)


def opponent_adjust(b, passes=3):
    """Alternate: bowler quality from batters faced, batter quality from bowlers faced."""
    fb = b.faced == 1
    b["bat_adj"] = b.bat_value
    b["bowl_adj"] = b.bowl_value
    info = {}
    for _ in range(passes):
        kb, mub = estimate_k(b.bowl_adj, b.w_bowl, b.bowler_id)
        q_bowl = shrunk_mean(b.bowl_adj, b.w_bowl, b.bowler_id, kb, mub) - mub
        b["bat_adj"] = np.where(fb, b.bat_value + b.bowler_id.map(q_bowl).fillna(0), np.nan)
        kt, mut = estimate_k(b.loc[fb, "bat_adj"], b.loc[fb, "w_bat"], b.loc[fb, "striker_id"])
        q_bat = shrunk_mean(b.loc[fb, "bat_adj"], b.loc[fb, "w_bat"], b.loc[fb, "striker_id"], kt, mut) - mut
        b["bowl_adj"] = b.bowl_value + b.striker_id.map(q_bat).fillna(0)
        info = {"k_bowl_all": kb, "k_bat_all": kt}
    return b, info


def _player_sums(df):
    """Per-player weighted sums for pressure (P), normal (N) balls."""
    x = df.assign(wv=df.v * df.w)
    P = x[x.hp == 1].groupby("pid").agg(Ps=("wv", "sum"), Pw=("w", "sum"))
    N = x[x.hp == 0].groupby("pid").agg(Ns=("wv", "sum"), Nw=("w", "sum"))
    return P.join(N, how="outer").fillna(0)


def _estimate(S, kA, muA, kq):
    """Overall ability A (shrunk to league), then pressure Q and normal N anchored to A."""
    A = (S.Ps + S.Ns + kA * muA) / (S.Pw + S.Nw + kA)
    Q = (S.Ps + kq * A) / (S.Pw + kq)
    N = (S.Ns + kq * A) / (S.Nw + kq)
    return A, Q, N


def choose_prior_k(df, grid, kA, muA, min_p=60):
    """Pick the anchor strength that best predicts a player's pressure value in matches it has not seen."""
    res = []
    for name, mask in [("odd/even matches", df.m % 2 == 0), ("2022-24 -> 2025-26", df.season <= 2024)]:
        Sa, Sb = _player_sums(df[mask]), _player_sums(df[~mask])
        na = df[mask & (df.hp == 1)].groupby("pid").size()
        nb = df[~mask & (df.hp == 1)].groupby("pid").size()
        keep = na[na >= min_p].index.intersection(nb[nb >= min_p].index)
        Sa, Sb = Sa.loc[keep], Sb.loc[keep]
        target = Sb.Ps / Sb.Pw
        raw = Sa.Ps / Sa.Pw
        row = {"split": name, "players": len(keep), "raw_pressure_only": raw.corr(target, method="spearman")}
        Aa = (Sa.Ps + Sa.Ns + kA * muA) / (Sa.Pw + Sa.Nw + kA)
        row["overall_only"] = Aa.corr(target, method="spearman")
        for k in grid:
            _, Q, _ = _estimate(Sa, kA, muA, k)
            row[f"k={k}"] = Q.corr(target, method="spearman")
        res.append(row)
    t = pd.DataFrame(res)
    kcols = [f"k={k}" for k in grid]
    best = grid[int(np.argmax(t[kcols].mean().values))]
    return best, t


def _consistency(df, mmin, league_share=None):
    x = df[df.hp == 1].assign(wv=lambda d: d.v * d.w)
    mm = x.groupby(["pid", "m"]).agg(n=("v", "size"), wv=("wv", "sum"))
    mm = mm[mm.n >= mmin]
    if league_share is None:
        league_share = (mm.wv > 0).mean()
    pos = (mm.wv > 0).groupby("pid").agg(["sum", "size"])
    C = (pos["sum"] + 6 * league_share) / (pos["size"] + 6)
    return C, pos, league_share


def clutch_scores(b, role, cfg, rng, boot_reps=None, kq=None):
    """role: 'bat' or 'bowl'. Returns (per-player table, meta)."""
    if role == "bat":
        d = b[b.faced == 1]
        df = pd.DataFrame(
            {
                "pid": d.striker_id,
                "m": d.match_id,
                "v": d.bat_adj,
                "w": d.w_bat,
                "hp": d.high_pressure,
                "season": d.season_year,
            }
        )
        min_b, min_m = cfg["eligibility"]["bat_min_pressure_balls"], cfg["eligibility"]["bat_min_pressure_matches"]
    else:
        d = b
        df = pd.DataFrame(
            {
                "pid": d.bowler_id,
                "m": d.match_id,
                "v": d.bowl_adj,
                "w": d.w_bowl,
                "hp": d.high_pressure,
                "season": d.season_year,
            }
        )
        min_b, min_m = cfg["eligibility"]["bowl_min_pressure_balls"], cfg["eligibility"]["bowl_min_pressure_matches"]
    sc = cfg["score"]
    mmin = cfg["eligibility"]["match_min_pressure_balls"]
    kA, muA = estimate_k(df.v, df.w, df.pid)
    ktable = None
    if kq is None:
        kq, ktable = choose_prior_k(df, sc["prior_k_grid"], kA, muA)
    S = _player_sums(df)
    A, Q, N = _estimate(S, kA, muA, kq)
    C, pos, league_share = _consistency(df, mmin)
    comp = pd.DataFrame({"overall": A, "quality": Q, "normal": N})
    comp["lift"] = comp.quality - comp.normal
    comp["consistency"] = C.reindex(comp.index).fillna(league_share)
    comp["pressure_spells"] = pos["size"].reindex(comp.index).fillna(0).astype(int)
    comp["spells_positive"] = pos["sum"].reindex(comp.index).fillna(0).astype(int)
    cnt = df[df.hp == 1].groupby("pid").agg(p_balls=("v", "size"), p_matches=("m", "nunique"))
    tot = df.groupby("pid").agg(balls=("v", "size"), matches=("m", "nunique"))
    comp = comp.join(cnt).join(tot).fillna({"p_balls": 0, "p_matches": 0})
    comp["eligible"] = (comp.p_balls >= min_b) & (comp.p_matches >= min_m)
    act = cfg["eligibility"].get("active_since")
    if act:
        comp["eligible"] &= comp.index.map(df.groupby("pid").season.max()).fillna(0) >= int(act)
    el = comp[comp.eligible]
    stats = {c: (el[c].mean(), el[c].std()) for c in ["quality", "lift", "consistency"]}

    def blend(q, lift, c):
        return (
            sc["w_quality"] * (q - stats["quality"][0]) / stats["quality"][1]
            + sc["w_lift"] * (lift - stats["lift"][0]) / stats["lift"][1]
            + sc["w_consistency"] * (c - stats["consistency"][0]) / stats["consistency"][1]
        )

    comp["blend"] = blend(comp.quality, comp.lift, comp.consistency)
    bm, bs = comp.loc[comp.eligible, "blend"].mean(), comp.loc[comp.eligible, "blend"].std()
    comp["clutch_score"] = 50 + 10 * (comp.blend - bm) / bs
    meta = {
        "k_overall": kA,
        "k_anchor": kq,
        "league_share_positive": float(league_share),
        "eligible": int(comp.eligible.sum()),
        "k_table": ktable,
        "stats": stats,
        "blend_mean_sd": (bm, bs),
    }

    reps = sc["bootstrap_reps"] if boot_reps is None else boot_reps
    if reps > 0:
        pids = el.index.tolist()
        g = df[df.pid.isin(pids)].assign(wv=lambda x: x.v * x.w, P=lambda x: x.hp == 1)
        g["Pw"] = np.where(g.P, g.w, 0)
        g["Ps"] = np.where(g.P, g.wv, 0)
        g["Nw"] = np.where(~g.P, g.w, 0)
        g["Ns"] = np.where(~g.P, g.wv, 0)
        g["Pn"] = g.P.astype(int)
        per = g.groupby(["pid", "m"])[["Pw", "Ps", "Pn", "Nw", "Ns"]].sum().reset_index()
        boot = np.zeros((reps, len(pids)))
        for j, pid in enumerate(pids):
            a = per[per.pid == pid][["Pw", "Ps", "Pn", "Nw", "Ns"]].to_numpy()
            idx = rng.integers(0, len(a), size=(reps, len(a)))
            s_ = a[idx]
            Pw, Ps, Pn, Nw, Ns = [s_[:, :, i] for i in range(5)]
            Aa = (Ps.sum(1) + Ns.sum(1) + kA * muA) / (Pw.sum(1) + Nw.sum(1) + kA)
            q = (Ps.sum(1) + kq * Aa) / (Pw.sum(1) + kq)
            n = (Ns.sum(1) + kq * Aa) / (Nw.sum(1) + kq)
            ok = Pn >= mmin
            c = (((Ps > 0) & ok).sum(1) + 6 * league_share) / (ok.sum(1) + 6)
            boot[:, j] = 50 + 10 * (blend(q, q - n, c) - bm) / bs
        ranks = (-boot).argsort(1).argsort(1) + 1
        comp.loc[pids, "score_lo"] = np.percentile(boot, 5, axis=0)
        comp.loc[pids, "score_hi"] = np.percentile(boot, 95, axis=0)
        comp.loc[pids, "rank_lo"] = np.percentile(ranks, 5, axis=0)
        comp.loc[pids, "rank_hi"] = np.percentile(ranks, 95, axis=0)
        comp.loc[pids, "p_top10"] = (ranks <= 10).mean(0)
    comp.index.name = "player_id"
    return comp.reset_index(), meta


def predictive_check(b, cfg, rng):
    """Score players on 2022-24 only, then see how well each method predicts 2025-26 pressure value."""
    early = b[b.season_year <= 2024]
    late = b[b.season_year >= 2025]
    rows = []
    for role in ("bat", "bowl"):
        tab, meta = clutch_scores(early, role, cfg, rng, boot_reps=0)
        if role == "bat":
            d = late[(late.faced == 1) & (late.high_pressure == 1)]
            fut = (
                d.assign(wv=d.bat_adj * d.w_bat)
                .groupby("striker_id")
                .agg(n=("wv", "size"), wv=("wv", "sum"), w=("w_bat", "sum"))
            )
            e = early[(early.faced == 1) & (early.high_pressure == 1)]
            raw = e.groupby("striker_id").agg(n=("bat_runs", "size"), r=("bat_runs", "sum"))
            raw_metric = raw.r / raw.n * 100  # pressure strike rate
            raw_name = "Pressure strike rate (2022-24)"
        else:
            d = late[late.high_pressure == 1]
            fut = (
                d.assign(wv=d.bowl_adj * d.w_bowl)
                .groupby("bowler_id")
                .agg(n=("wv", "size"), wv=("wv", "sum"), w=("w_bowl", "sum"))
            )
            e = early[(early.high_pressure == 1)]
            raw = e.groupby("bowler_id").agg(n=("legal", "sum"), r=("bowler_runs", "sum"))
            raw_metric = -(raw.r / raw.n.clip(lower=1) * 6)  # pressure economy (lower is better)
            raw_name = "Pressure economy (2022-24)"
        fut = fut[fut.n >= 60]
        target = fut.wv / fut.w
        t = tab.set_index("player_id")
        t = t[t.p_balls >= 60]
        common = t.index.intersection(target.index).intersection(raw_metric.index)
        rows.append(
            dict(
                role=role,
                players=len(common),
                method=raw_name,
                correlation=raw_metric.loc[common].corr(target.loc[common], method="spearman"),
            )
        )
        rows.append(
            dict(
                role=role,
                players=len(common),
                method="CRICQ Quality alone (2022-24)",
                correlation=t.loc[common, "quality"].corr(target.loc[common], method="spearman"),
            )
        )
        rows.append(
            dict(
                role=role,
                players=len(common),
                method="CRICQ CRICQ Score (2022-24)",
                correlation=t.loc[common, "clutch_score"].corr(target.loc[common], method="spearman"),
            )
        )
    return pd.DataFrame(rows)


def batting_stats(b):
    d = b[b.faced == 1]

    def agg(x):
        return x.groupby("striker_id").agg(
            balls=("faced", "size"),
            runs=("bat_runs", "sum"),
            outs=("striker_out", "sum"),
            fours=("is_four", "sum"),
            sixes=("is_six", "sum"),
            dots=("bat_runs", lambda s: (s == 0).sum()),
        )

    P, N = agg(d[d.high_pressure == 1]), agg(d[d.high_pressure == 0])
    out = P.add_prefix("p_").join(N.add_prefix("n_"), how="outer").fillna(0)
    for pre in ["p_", "n_"]:
        out[pre + "sr"] = out[pre + "runs"] / out[pre + "balls"].clip(lower=1) * 100
        out[pre + "avg"] = out[pre + "runs"] / out[pre + "outs"].clip(lower=1)
        out[pre + "bpd"] = out[pre + "balls"] / out[pre + "outs"].clip(lower=1)
        out[pre + "bnd_pct"] = (out[pre + "fours"] + out[pre + "sixes"]) / out[pre + "balls"].clip(lower=1) * 100
        out[pre + "dot_pct"] = out[pre + "dots"] / out[pre + "balls"].clip(lower=1) * 100
    pos = b[b.faced == 1].drop_duplicates(["match_id", "striker_id"]).groupby("striker_id").batting_order.median()
    out["bat_pos"] = pos
    out["role"] = pd.cut(
        out.bat_pos, [0, 2, 4, 7, 20], labels=["Opener", "Top order", "Middle / finisher", "Lower order"]
    ).astype(str)
    out.index.name = "player_id"
    return out.reset_index()


def bowling_stats(b):
    def agg(x):
        return x.groupby("bowler_id").agg(
            balls=("legal", "sum"),
            runs=("bowler_runs", "sum"),
            wkts=("bowler_wkt", "sum"),
            dots=("bat_runs", lambda s: 0),
            bnd=("is_four", "sum"),
            sixes=("is_six", "sum"),
        )

    d = b.assign(dot=((b.total == 0) & (b.legal == 1)).astype(int))

    def agg2(x):
        a = x.groupby("bowler_id").agg(
            balls=("legal", "sum"),
            runs=("bowler_runs", "sum"),
            wkts=("bowler_wkt", "sum"),
            dots=("dot", "sum"),
            fours=("is_four", "sum"),
            sixes=("is_six", "sum"),
        )
        return a

    P, N = agg2(d[d.high_pressure == 1]), agg2(d[d.high_pressure == 0])
    out = P.add_prefix("p_").join(N.add_prefix("n_"), how="outer").fillna(0)
    for pre in ["p_", "n_"]:
        out[pre + "econ"] = out[pre + "runs"] / out[pre + "balls"].clip(lower=1) * 6
        out[pre + "sr"] = out[pre + "balls"] / out[pre + "wkts"].clip(lower=1)
        out[pre + "dot_pct"] = out[pre + "dots"] / out[pre + "balls"].clip(lower=1) * 100
        out[pre + "bnd_pct"] = (out[pre + "fours"] + out[pre + "sixes"]) / out[pre + "balls"].clip(lower=1) * 100
    ph = d[d.legal == 1].groupby(["bowler_id", "phase"]).size().unstack(fill_value=0)
    sh = ph.div(ph.sum(1), axis=0)
    role = np.where(
        sh.get("Death", 0) >= 0.35,
        "Death specialist",
        np.where(sh.get("Powerplay", 0) >= 0.40, "Powerplay specialist", "Middle overs"),
    )
    out["role"] = pd.Series(role, index=sh.index)
    out["pp_share"] = sh.get("Powerplay", 0)
    out["death_share"] = sh.get("Death", 0)
    out.index.name = "player_id"
    return out.reset_index()
