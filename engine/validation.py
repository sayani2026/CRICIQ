"""Input validation: fail early, with messages a non-programmer can act on."""

from __future__ import annotations


class CRICQError(Exception):
    """A problem with the inputs or settings that the user can fix."""


# Columns each Data Pack file must provide (extra columns are fine).
REQUIRED_COLUMNS = {
    "ball_by_ball": [
        "match_id",
        "innings",
        "innings_ball_num",
        "batting_team_id",
        "bowling_team_id",
        "striker_id",
        "striker_name",
        "non_striker_id",
        "non_striker_name",
        "bowler_id",
        "bowler_name",
        "batting_type",
        "bowling_type",
        "pace_or_spin",
        "batting_order",
        "runs",
        "is_four",
        "is_six",
        "is_wicket",
        "dismissal_type",
        "dismissed_player_id",
        "extras_type",
        "extras1_runs",
        "extras_2_runs",
    ],
    "matches": [
        "match_id",
        "comp_id",
        "match_date",
        "stage",
        "venue_id",
        "venue_country",
        "home_team_id",
        "home_team",
        "away_team_id",
        "away_team",
        "first_inn_revised_overs",
        "second_inn_revised_overs",
        "revised_target",
        "knock_out",
        "win_team_id",
        "result",
    ],
    "competitions": ["comp_id", "comp_name", "match_format", "season"],
    "teams": ["comp_id", "team_id", "team_name"],
    "playing_eleven": ["match_id", "team_id", "player_id", "batting_order", "is_impact"],
    "competition_team_player_mapping": ["comp_id", "comp_name", "team_id", "team_name", "player_id", "player_name"],
}


def validate_schema(raw: dict) -> None:
    """Check every Data Pack table has the columns CRICQ needs and is not empty."""
    problems = []
    for name, cols in REQUIRED_COLUMNS.items():
        if name not in raw:
            problems.append(f"{name}.csv is missing")
            continue
        df = raw[name]
        if len(df) == 0:
            problems.append(f"{name}.csv is empty")
        missing = [c for c in cols if c not in df.columns]
        if missing:
            problems.append(f"{name}.csv is missing column(s): {', '.join(missing)}")
    if "ball_by_ball" in raw and "matches" in raw and not problems:
        unknown = set(raw["ball_by_ball"].match_id) - set(raw["matches"].match_id)
        if unknown:
            problems.append(f"ball_by_ball.csv has {len(unknown)} match_id(s) not found in matches.csv")
        bad_inn = ~raw["ball_by_ball"].innings.isin([1, 2, 3, 4])
        if bad_inn.any():
            problems.append(f"ball_by_ball.csv has {int(bad_inn.sum())} row(s) with an innings value other than 1-4")
    if problems:
        raise CRICQError("The Data Pack does not look right:\n  - " + "\n  - ".join(problems))


def _num(cfg, path, lo=None, hi=None, integer=False, problems=None):
    node = cfg
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            problems.append(f"'{path}' is missing")
            return
        node = node[key]
    if isinstance(node, bool) or not isinstance(node, int | float):
        problems.append(f"'{path}' must be a number (got {node!r})")
        return
    if integer and int(node) != node:
        problems.append(f"'{path}' must be a whole number (got {node})")
    if lo is not None and node < lo:
        problems.append(f"'{path}' must be at least {lo} (got {node})")
    if hi is not None and node > hi:
        problems.append(f"'{path}' must be at most {hi} (got {node})")


def validate_config(cfg: dict) -> None:
    """Check config.yaml values are present and in sensible ranges. Reports every problem at once."""
    if not isinstance(cfg, dict):
        raise CRICQError("config.yaml is empty or not a set of settings.")
    p: list[str] = []
    _num(cfg, "seed", 0, integer=True, problems=p)
    _num(cfg, "pressure.weight_stakes", 0, 1, problems=p)
    _num(cfg, "pressure.weight_squeeze", 0, 1, problems=p)
    _num(cfg, "pressure.high_pressure_pct", 50, 99, problems=p)
    _num(cfg, "weights.recency_decay", 0.1, 1, problems=p)
    _num(cfg, "weights.associate_opposition", 0, 1, problems=p)
    _num(cfg, "value.wicket_value_cap", 1, 100, problems=p)
    for r in ("bat", "bowl"):
        _num(cfg, f"eligibility.{r}_min_pressure_balls", 1, integer=True, problems=p)
        _num(cfg, f"eligibility.{r}_min_pressure_matches", 1, integer=True, problems=p)
    _num(cfg, "eligibility.match_min_pressure_balls", 1, integer=True, problems=p)
    for k in ("w_quality", "w_lift", "w_consistency"):
        _num(cfg, f"score.{k}", 0, 1, problems=p)
    _num(cfg, "score.bootstrap_reps", 0, 5000, integer=True, problems=p)
    act = cfg.get("eligibility", {}).get("active_since")
    if act is not None and (not isinstance(act, int) or not 2000 <= act <= 2100):
        p.append(f"'eligibility.active_since' must be a year like 2025, or null (got {act!r})")
    if not p:
        pw = cfg["pressure"]["weight_stakes"] + cfg["pressure"]["weight_squeeze"]
        if abs(pw - 1) > 1e-6:
            p.append(f"'pressure.weight_stakes' + 'pressure.weight_squeeze' must add up to 1 (got {pw:g})")
        sw = cfg["score"]["w_quality"] + cfg["score"]["w_lift"] + cfg["score"]["w_consistency"]
        if abs(sw - 1) > 1e-6:
            p.append(f"the three 'score.w_*' weights must add up to 1 (got {sw:g})")
        grid = cfg["score"].get("prior_k_grid")
        if not grid or not all(isinstance(k, int | float) and k > 0 for k in grid):
            p.append("'score.prior_k_grid' must be a list of positive numbers")
    a = cfg.get("auction")
    if a is not None:
        for k in ("status_file", "rr_squad_file"):
            if not a.get(k):
                p.append(f"'auction.{k}' must name a CSV file")
        _num(cfg, "auction.salary_cap_cr", 1, 1000, problems=p)
        _num(cfg, "auction.max_squad", 1, 40, integer=True, problems=p)
        _num(cfg, "auction.max_overseas", 0, 15, integer=True, problems=p)
        _num(cfg, "auction.quality_bar", 0, 100, problems=p)
        if not isinstance(a.get("needs"), dict) or not a.get("needs"):
            p.append("'auction.needs' must list at least one role")
        else:
            for k, nd in a["needs"].items():
                if not isinstance(nd, dict) or nd.get("table") not in ("bat", "bowl", "both"):
                    p.append(f"'auction.needs.{k}.table' must be bat, bowl or both")
                elif not isinstance(nd.get("want"), int) or nd["want"] < 0:
                    p.append(f"'auction.needs.{k}.want' must be a whole number")
        for k, v in (a.get("availability_prob") or {}).items():
            if not isinstance(v, int | float) or not 0 <= v <= 1:
                p.append(f"'auction.availability_prob.{k}' must be between 0 and 1")
    if not isinstance(cfg.get("full_members"), list) or not cfg.get("full_members"):
        p.append("'full_members' must be a list of team names")
    if p:
        raise CRICQError("config.yaml has problems:\n  - " + "\n  - ".join(p))
