"""CRICQ — one command from the raw Data Pack to every output.

    python pipeline.py            # full run (about 3-5 minutes)
    python pipeline.py --fast     # skip the sensitivity re-runs

Writes:
    data/processed/   balls.parquet, matches.parquet, players.parquet  (read by the dashboard)
    outputs/          top10_batters.csv, top10_bowlers.csv, batting_scores.csv, bowling_scores.csv,
                      model_report.json and supporting tables (read by the report and dashboard)
"""

import argparse
import json
import logging
import sys
import time

import numpy as np
import pandas as pd

from engine import auction as au
from engine import availability as av
from engine import expected as ex
from engine import factors as fx
from engine import load
from engine import match_state as ms
from engine import pressure as pr
from engine import rankings as rk
from engine import scoring as sc
from engine import win_prob as wp
from engine.config import load_config
from engine.validation import CRICQError

logger = logging.getLogger("cricq")
_T0 = time.time()


def log(msg):
    logger.info("[%6.1fs] %s", time.time() - _T0, msg)


def main(fast=False, config_path=None):
    """Run every step. Returns the two top-10 tables."""
    cfg = load_config(config_path)
    rng = np.random.default_rng(cfg["seed"])
    proc_dir, out_dir = cfg["paths"]["processed_dir"], cfg["paths"]["outputs_dir"]
    report = {}

    log(f"Step 1  loading Data Pack from {cfg['paths']['raw']}")
    b, m, players, quality, teams = load.build(cfg)

    log("Step 2  rebuilding the scoreboard for every ball")
    b = ms.add_state(b)
    rec = ms.reconcile(b, m)
    report["reconciliation"] = {
        "matches_checked": int(len(rec)),
        "matching": int(rec.ok.sum()),
        "match_rate_pct": round(rec.ok.mean() * 100, 2),
        "mismatches": rec[~rec.ok].match_id.tolist(),
    }
    quality.loc[len(quality)] = [
        "Scoreboard rebuild vs official results",
        f"{rec.ok.sum()} of {len(rec)} matches agree ({rec.ok.mean() * 100:.1f}%)",
        "Mismatch(es) are 1-run differences in the source result text; kept.",
    ]
    vpar, glob = ms.venue_par(b, m)
    vp = dict(zip(zip(vpar.venue_id, vpar.fmt, strict=True), vpar.par, strict=True))
    b["venue_par"] = [vp.get((v, f), glob.get(f, glob.mean())) for v, f in zip(b.venue_id, b.format, strict=True)]
    err = ms.expected_runs_table(b)

    log("Step 3  win-probability models (time-based validation + cross-fitting)")
    val, cal = wp.validate(b)
    b = wp.crossfit(b)

    log("Step 4  Pressure Index")
    b = pr.add_squeeze(b, err, vpar)
    pc = cfg["pressure"]
    b = pr.add_pressure(b, pc["weight_stakes"], pc["weight_squeeze"], pc["high_pressure_pct"])
    by_dec, by_phase = pr.validation_tables(b)
    mov = []
    for inn in (1, 2):
        d = b[b.innings == inn].copy()
        d["wp_next"] = d.groupby(["match_id"]).wp.shift(-1)
        if inn == 2:
            d["wp_next"] = d.wp_next.fillna(d.bat_won)
        d = d.dropna(subset=["wp_next"])
        mv = (d.wp_next - d.wp).abs()
        mov.append(
            {
                "innings": inn,
                "share_of_balls_pct": round(d.high_pressure.mean() * 100, 1),
                "share_of_wp_movement_pct": round(mv[d.high_pressure == 1].sum() / mv.sum() * 100, 1),
            }
        )

    log("Step 5  expected-outcome models and value added per ball")
    b = ex.add_expected(b, cfg["value"]["wicket_value_cap"])
    report["expected_calibration"] = {k: round(float(v), 4) for k, v in ex.calibration(b).items()}

    log("Step 6  opponent adjustment, CRICQ Scores, bootstrap")
    b = sc.add_weights(b, cfg)
    b, adj_info = sc.opponent_adjust(b)
    bat, mbat = sc.clutch_scores(b, "bat", cfg, rng)
    bowl, mbowl = sc.clutch_scores(b, "bowl", cfg, rng)
    cfg["_kq_bat"], cfg["_kq_bowl"] = mbat["k_anchor"], mbowl["k_anchor"]
    pcheck = sc.predictive_check(b, cfg, rng)

    log("Step 7  rankings, sensitivity, repeatability")
    bstats, wstats = sc.batting_stats(b), sc.bowling_stats(b)
    pl = players.set_index("player_id")
    status = squad = None
    if cfg.get("auction"):
        status = av.load_status(cfg["auction"]["status_file"])
        squad = av.load_rr_squad(cfg["auction"]["rr_squad_file"])
        reports = av.load_reports(cfg["auction"]["reports_file"])
        in_squads = set(players.loc[players.ipl_team_latest.notna(), "display_name"])
        for what, names in (("status", status.player), ("RR squad", squad.player), ("news reports", reports.player)):
            miss = av.unresolved(names, players, in_squads)
            if miss:
                quality.loc[len(quality)] = [
                    f"Names in {what} file",
                    f"{len(miss)} name(s) not found in the Data Pack: {', '.join(miss[:12])}",
                    "Ignored (usually domestic players with no matches 2022–26)",
                ]

    last_any = (
        pd.concat([b.groupby("striker_id").season_year.max(), b.groupby("bowler_id").season_year.max()])
        .groupby(level=0)
        .max()
    )

    def finish(tab, stats, role):
        t = tab.merge(stats, on="player_id", how="left", suffixes=("", "_stat"))
        for c in [
            "display_name",
            "team_label",
            "latest_team",
            "ipl_team_latest",
            "ipl_team_any",
            "country",
            "bat_hand",
            "bowl_type",
            "pace_spin",
            "ipl26_games",
            "ipl26_team_games",
        ]:
            t[c] = t.player_id.map(pl[c])
        t["at_rr"] = t.ipl_team_latest.eq("Rajasthan Royals")
        last = (
            b[b.faced == 1].groupby("striker_id").season_year.max()
            if role == "bat"
            else b.groupby("bowler_id").season_year.max()
        )
        t["last_season"] = t.player_id.map(last)
        # a player's IPL 2027 status is about the player, not the role: use his last match in any role
        t["last_any"] = t.player_id.map(last_any)
        if status is not None:
            t = av.apply(t, status, squad, cfg, reports=reports, directory=players)
            # team_label stays the 2026 team from the Data Pack (Round 1 is about the supplied data);
            # confirmed IPL 2027 moves are kept separately in team_2027 for the auction board.
        else:
            t["selectable"] = True
            t["in_pool"] = True
        t = t.sort_values("clutch_score", ascending=False)
        listable = t.eligible & t.selectable.astype(bool)
        t["rank"] = np.where(listable, listable.cumsum(), np.nan)
        t["rank_all"] = np.where(t.eligible, t.eligible.cumsum(), np.nan)
        return t

    bat_t, bowl_t = finish(bat, bstats, "bat"), finish(bowl, wstats, "bowl")
    if not fast:
        excl = {
            "bat": set(bat_t[~bat_t.selectable.astype(bool)].player_id),
            "bowl": set(bowl_t[~bowl_t.selectable.astype(bool)].player_id),
        }
        sens, hits, nvar = rk.sensitivity(b, cfg, bat_t, bowl_t, rng, exclude=excl)
        bat_t["top10_in_variants"] = bat_t.player_id.map(hits["bat"]).fillna(0).astype(int)
        bowl_t["top10_in_variants"] = bowl_t.player_id.map(hits["bowl"]).fillna(0).astype(int)
        report["n_sensitivity_variants"] = nvar
    else:
        sens = pd.DataFrame()
    rep = rk.repeatability(b, cfg)

    # ---------- write ----------
    log("Writing outputs")
    keep = [
        "match_id",
        "innings",
        "innings_ball_num",
        "ball_label",
        "over",
        "phase",
        "legal_before",
        "batting_team_id",
        "bowling_team_id",
        "batting_team",
        "bowling_team",
        "striker_id",
        "striker_name",
        "non_striker_id",
        "bowler_id",
        "bowler_name",
        "batting_type",
        "bowling_type",
        "pace_or_spin",
        "stroke",
        "delivery_style",
        "batting_order",
        "bat_runs",
        "extras",
        "total",
        "extras_type",
        "faced",
        "legal",
        "wkt",
        "striker_out",
        "bowler_wkt",
        "bowler_runs",
        "is_four",
        "is_six",
        "dismissal_type",
        "dismissed_player_id",
        "score_before",
        "wkts_before",
        "balls_left",
        "wkts_in_hand",
        "target",
        "runs_needed",
        "rrr",
        "wp",
        "leverage",
        "squeeze",
        "pressure_index",
        "high_pressure",
        "x_runs",
        "x_out",
        "bat_value",
        "bowl_value",
        "bat_adj",
        "bowl_adj",
        "w_bat",
        "w_bowl",
        "season_year",
        "format",
        "comp_name",
        "match_date",
        "venue_id",
        "venue_country",
        "venue_par",
        "knock_out",
        "bat_won",
        "bat_tier",
        "bowl_tier",
    ]
    log("Step 7b Cricket parameters (phase, wickets, pitch, opposition, matchups...)")
    rr_home = set(
        m.loc[(m.format == "IPL") & (m.home_team == "Rajasthan Royals") & (m.season_year >= 2023), "venue_id"]
    )
    bc = fx.context(b, rr_home)
    fcols = fx.FACTOR_COLUMNS
    ranked_bat = set(bat_t.loc[bat_t.p_balls >= 30, "player_id"])
    ranked_bowl = set(bowl_t.loc[bowl_t.p_balls >= 30, "player_id"])
    pd.concat(
        [fx.splits(bc, "bat", players=ranked_bat), fx.splits(bc, "bowl", players=ranked_bowl)], ignore_index=True
    ).to_parquet(out_dir / "player_factors.parquet", index=False)
    fx.matchups(bc).to_parquet(out_dir / "matchups.parquet", index=False)
    b = b.join(bc[fcols].astype("category"))
    keep += fcols
    b[keep].to_parquet(proc_dir / "balls.parquet", index=False)
    inn = (
        b.groupby(["match_id", "innings"])
        .agg(runs=("total", "sum"), wkts=("wkt", "sum"), team=("batting_team", "first"))
        .unstack()
    )
    mt = m.copy()
    for i in (1, 2):
        mt[f"inn{i}_team"] = mt.match_id.map(inn[("team", i)])
        mt[f"inn{i}_runs"] = mt.match_id.map(inn[("runs", i)])
        mt[f"inn{i}_wkts"] = mt.match_id.map(inn[("wkts", i)])
    mt["pressure_balls"] = mt.match_id.map(b.groupby("match_id").high_pressure.sum())
    mt["peak_pressure"] = mt.match_id.map(b.groupby("match_id").leverage.max())
    mt[mt.match_id.isin(b.match_id)].to_parquet(proc_dir / "matches.parquet", index=False)
    players.to_parquet(proc_dir / "players.parquet", index=False)
    vpar.to_csv(out_dir / "venue_par.csv", index=False)

    bat_t.to_csv(out_dir / "batting_scores.csv", index=False)
    bowl_t.to_csv(out_dir / "bowling_scores.csv", index=False)
    cols_b = [
        "rank",
        "display_name",
        "team_label",
        "role",
        "clutch_score",
        "score_lo",
        "score_hi",
        "rank_lo",
        "rank_hi",
        "p_top10",
        "p_balls",
        "p_matches",
        "p_runs",
        "p_sr",
        "n_sr",
        "p_bpd",
        "n_bpd",
        "quality",
        "lift",
        "consistency",
    ]
    cols_w = [
        "rank",
        "display_name",
        "team_label",
        "role",
        "pace_spin",
        "clutch_score",
        "score_lo",
        "score_hi",
        "rank_lo",
        "rank_hi",
        "p_top10",
        "p_balls",
        "p_matches",
        "p_wkts",
        "p_econ",
        "n_econ",
        "p_sr",
        "p_dot_pct",
        "quality",
        "lift",
        "consistency",
    ]
    if not fast:
        cols_b.append("top10_in_variants")
        cols_w.append("top10_in_variants")
    for extra in ("rank_all", "status_label", "team_2027"):
        if extra in bat_t.columns:
            cols_b.append(extra)
            cols_w.append(extra)
    rk.top10(bat_t)[cols_b].to_csv(out_dir / "top10_batters.csv", index=False)
    rk.top10(bowl_t)[cols_w].to_csv(out_dir / "top10_bowlers.csv", index=False)

    if squad is not None:
        log("Step 8  RR auction board (default projection)")
        state = au.squad_state(squad, au.default_release(squad), cfg)
        need_tab = au.needs(state["kept"], bat_t, bowl_t, cfg)
        pool = au.targets(
            bat_t, bowl_t, need_tab, set(state["kept"].player), cfg, released_names=set(state["released"].player)
        )
        shortlist = au.plan(pool, need_tab, state, cfg)
        au.watch_list(pool, need_tab).to_csv(out_dir / "auction_watch.csv", index=False)
        need_tab.to_csv(out_dir / "auction_needs.csv", index=False)
        pool.to_csv(out_dir / "auction_targets.csv", index=False)
        shortlist.to_csv(out_dir / "auction_plan.csv", index=False)
        au.projected_xi(state["kept"], shortlist, bat_t, bowl_t, cfg).to_csv(out_dir / "auction_xi.csv", index=False)
        au.not_available(bat_t, bowl_t).to_csv(out_dir / "auction_unavailable.csv", index=False)
        report["auction"] = {k: v for k, v in state.items() if k not in ("kept", "released")} | {
            "released": sorted(state["released"].player),
            "as_of": cfg["auction"].get("as_of"),
        }

    val.to_csv(out_dir / "wp_validation.csv", index=False)
    cal.to_csv(out_dir / "wp_calibration.csv", index=False)
    by_dec.to_csv(out_dir / "pressure_by_decile.csv", index=False)
    by_phase.to_csv(out_dir / "pressure_by_phase.csv", index=False)
    pd.DataFrame(mov).to_csv(out_dir / "pressure_wp_movement.csv", index=False)
    quality.to_csv(out_dir / "data_quality.csv", index=False)
    pcheck.to_csv(out_dir / "predictive_check.csv", index=False)
    rep.to_csv(out_dir / "repeatability.csv", index=False)
    if len(sens):
        sens.to_csv(out_dir / "sensitivity.csv", index=False)
    pd.concat([mbat["k_table"].assign(role="bat"), mbowl["k_table"].assign(role="bowl")]).to_csv(
        out_dir / "anchor_k_selection.csv", index=False
    )

    report.update(
        {
            "data": {
                "matches_with_balls": int(b.match_id.nunique()),
                "balls": int(len(b)),
                "ipl_matches": int(b[b.format == "IPL"].match_id.nunique()),
                "t20i_matches": int(b[b.format == "T20I"].match_id.nunique()),
                "other_matches": int(b[b.format == "Other T20"].match_id.nunique()),
                "first_date": str(b.match_date.min().date()),
                "last_date": str(b.match_date.max().date()),
                "venues": int(b.venue_id.nunique()),
            },
            "win_probability": val.round(4).to_dict("records"),
            "pressure": {
                "high_pressure_threshold_pct": pc["high_pressure_pct"],
                "weight_stakes": pc["weight_stakes"],
                "weight_squeeze": pc["weight_squeeze"],
                "share_high_pressure_pct": round(b.high_pressure.mean() * 100, 1),
                "wp_movement": mov,
            },
            "scoring": {
                "bat": {k: v for k, v in mbat.items() if k not in ("k_table", "stats", "blend_mean_sd")},
                "bowl": {k: v for k, v in mbowl.items() if k not in ("k_table", "stats", "blend_mean_sd")},
                "opponent_adjust": adj_info,
                "weights": cfg["score"],
                "wicket_value_cap": cfg["value"]["wicket_value_cap"],
                "eligibility": cfg["eligibility"],
                "recency_decay": cfg["weights"]["recency_decay"],
                "associate_weight": cfg["weights"]["associate_opposition"],
            },
        }
    )
    with open(out_dir / "model_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=lambda x: float(x) if hasattr(x, "__float__") else str(x))
    log("Done")
    top_b = rk.top10(bat_t)[["rank", "display_name", "team_label", "clutch_score", "p_balls"]]
    top_w = rk.top10(bowl_t)[["rank", "display_name", "team_label", "clutch_score", "p_balls"]]
    logger.info("\nTop 10 batters under pressure\n%s", top_b.to_string(index=False))
    logger.info("\nTop 10 bowlers under pressure\n%s", top_w.to_string(index=False))
    return top_b, top_w


def cli(argv=None):
    """Command-line entry point:  python pipeline.py [--fast] [--config FILE] [--log-level LEVEL]"""
    ap = argparse.ArgumentParser(description="Rebuild every CRICQ output from the Data Pack.")
    ap.add_argument("--fast", action="store_true", help="skip the sensitivity re-runs (about 10 seconds quicker)")
    ap.add_argument("--config", default=None, help="path to a settings file (default: config.yaml)")
    ap.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = ap.parse_args(argv)
    # Own handler (basicConfig is a no-op if anything configured logging first).
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(args.log_level)
    logger.propagate = False
    for noisy in ("matplotlib", "PIL", "fontTools"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        main(fast=args.fast, config_path=args.config)
    except CRICQError as e:
        logger.error("\nCRICQ could not run:\n%s", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(cli())
