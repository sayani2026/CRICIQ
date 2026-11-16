"""Step 7 — eligibility, final rankings, sensitivity and repeatability checks."""

import copy

import pandas as pd

from . import pressure as pr
from . import scoring as sc


def top10(table, n=10, exclude=None):
    """Official Round 1 list: the best performers under pressure in the supplied data, among players with enough
    pressure evidence. Only retired players and players with no match since 2024 are left out."""
    m = table.eligible.copy()
    if "selectable" in table.columns:
        m &= table.selectable.astype(bool)
    if exclude:
        m &= ~table.player_id.isin(exclude)
    return table[m].sort_values("clutch_score", ascending=False).head(n)


def _rescore(b, cfg, rng):
    b = sc.add_weights(b, cfg)
    b, _ = sc.opponent_adjust(b)
    bat, _ = sc.clutch_scores(b, "bat", cfg, rng, boot_reps=0, kq=cfg.get("_kq_bat"))
    bowl, _ = sc.clutch_scores(b, "bowl", cfg, rng, boot_reps=0, kq=cfg.get("_kq_bowl"))
    return bat, bowl


def sensitivity(b, cfg, base_bat, base_bowl, rng, exclude=None):
    """Change one setting at a time; measure how much of the top 10 survives."""
    variants = [
        ("High-pressure cut-off: top 30% of balls", ("pressure", "high_pressure_pct", 70)),
        ("High-pressure cut-off: top 20% of balls", ("pressure", "high_pressure_pct", 80)),
        ("Pressure blend: 65% stakes / 35% squeeze", ("pressure", "weight_stakes", 0.65)),
        ("Pressure blend: 35% stakes / 65% squeeze", ("pressure", "weight_stakes", 0.35)),
        ("Score blend: quality only", ("score", "mix", (1.0, 0.0, 0.0))),
        ("Score blend: 40/30/30", ("score", "mix", (0.4, 0.3, 0.3))),
        ("No recency weighting", ("weights", "recency_decay", 1.0)),
        ("Associate opposition counts fully", ("weights", "associate_opposition", 1.0)),
        ("Associate opposition counts 25%", ("weights", "associate_opposition", 0.25)),
        ("Stricter eligibility (200 balls, 15 matches)", ("eligibility", "strict", None)),
    ]
    excl = exclude if isinstance(exclude, dict) else {"bat": exclude or set(), "bowl": exclude or set()}
    base_sets = {
        "bat": set(top10(base_bat, exclude=excl["bat"]).player_id),
        "bowl": set(top10(base_bowl, exclude=excl["bowl"]).player_id),
    }
    rows, hits = [], {"bat": {}, "bowl": {}}
    for label, (sec, key, val) in variants:
        c = copy.deepcopy(cfg)
        if key == "weight_stakes":
            c["pressure"]["weight_stakes"], c["pressure"]["weight_squeeze"] = val, 1 - val
        elif key == "mix":
            c["score"]["w_quality"], c["score"]["w_lift"], c["score"]["w_consistency"] = val
        elif key == "strict":
            for r in ("bat", "bowl"):
                c["eligibility"][f"{r}_min_pressure_balls"] = 200
                c["eligibility"][f"{r}_min_pressure_matches"] = 15
        else:
            c[sec][key] = val
        bb = pr.add_pressure(
            b.copy(),
            c["pressure"]["weight_stakes"],
            c["pressure"]["weight_squeeze"],
            c["pressure"]["high_pressure_pct"],
        )
        vbat, vbowl = _rescore(bb, c, rng)
        for role, base, var in [("bat", base_bat, vbat), ("bowl", base_bowl, vbowl)]:
            t = set(top10(var, exclude=excl[role]).player_id)
            for pid in t:
                hits[role][pid] = hits[role].get(pid, 0) + 1
            both = base[base.eligible][["player_id", "clutch_score"]].merge(
                var[var.eligible][["player_id", "clutch_score"]], on="player_id"
            )
            rows.append(
                dict(
                    variant=label,
                    role=role,
                    top10_kept=len(base_sets[role] & t),
                    spearman=both.clutch_score_x.corr(both.clutch_score_y, method="spearman"),
                )
            )
    return pd.DataFrame(rows), hits, len(variants)


def repeatability(b, cfg):
    """Is pressure performance a repeatable skill? Split each player's matches into two halves."""
    out = []
    for role in ("bat", "bowl"):
        if role == "bat":
            d = b[(b.faced == 1) & (b.high_pressure == 1)]
            df = pd.DataFrame(
                {"pid": d.striker_id, "m": d.match_id, "v": d.bat_adj, "w": d.w_bat, "season": d.season_year}
            )
        else:
            d = b[b.high_pressure == 1]
            df = pd.DataFrame(
                {"pid": d.bowler_id, "m": d.match_id, "v": d.bowl_adj, "w": d.w_bowl, "season": d.season_year}
            )
        for split, mask in [("odd vs even matches", df.m % 2 == 0), ("2022-24 vs 2025-26", df.season <= 2024)]:
            a = (
                df[mask]
                .assign(wv=lambda x: x.v * x.w)
                .groupby("pid")
                .agg(n=("v", "size"), wv=("wv", "sum"), w=("w", "sum"))
            )
            c = (
                df[~mask]
                .assign(wv=lambda x: x.v * x.w)
                .groupby("pid")
                .agg(n=("v", "size"), wv=("wv", "sum"), w=("w", "sum"))
            )
            j = a.join(c, lsuffix="_a", rsuffix="_b").dropna()
            j = j[(j.n_a >= 60) & (j.n_b >= 60)]
            r = (j.wv_a / j.w_a).corr(j.wv_b / j.w_b)
            out.append(dict(role=role, split=split, players=len(j), correlation=r))
    return pd.DataFrame(out)
