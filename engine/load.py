"""Step 1 — load, clean and join the six Data Pack CSVs, and record every data-quality decision."""

import numpy as np
import pandas as pd

from .validation import CRICQError, validate_schema

ILLEGAL = {"wide", "Overstep", "other"}  # deliveries that do not count as a legal ball
NO_BALL = {"Overstep", "other"}  # no-ball variants (batter still faces the ball)
NOT_BOWLER_WICKET = {"RunOut", "Retire Out", "Obstracting the field", "Obstructing the field"}


def _bool(s):
    return s.astype(str).str.strip().str.lower().eq("true")


TABLES = ["ball_by_ball", "matches", "competitions", "teams", "playing_eleven", "competition_team_player_mapping"]


def load_raw(raw):
    """Read the six Data Pack CSVs and check they have what the engine needs."""
    missing = [n for n in TABLES if not (raw / f"{n}.csv").exists()]
    if missing:
        raise CRICQError(f"Missing Data Pack file(s) in {raw}: " + ", ".join(f"{n}.csv" for n in missing))
    r = {n: pd.read_csv(raw / f"{n}.csv", low_memory=False) for n in TABLES}
    validate_schema(r)
    return r


def build(cfg):
    raw = load_raw(cfg["paths"]["raw"])
    b, m, c = raw["ball_by_ball"].copy(), raw["matches"].copy(), raw["competitions"].copy()
    q = []  # data-quality log: (check, finding, decision)

    # ---- competitions / matches ----
    # IPL seasons and two A-team tournaments share the code "T20"; only comps named IPL are IPL.
    c["format"] = np.select(
        [c.comp_name.str.startswith("IPL"), c.match_format.eq("T20I")], ["IPL", "T20I"], "Other T20"
    )
    c["season_year"] = c.season.astype(str).str[:4].astype(int)
    m = m.merge(c[["comp_id", "comp_name", "format", "season_year"]], on="comp_id", how="left")
    m["match_date"] = pd.to_datetime(m.match_date)
    m["is_ipl"] = m.format.eq("IPL").astype(int)
    m["knock_out"] = m.knock_out.fillna(0).astype(int)
    m["win_team_id"] = m.win_team_id.where(m.win_team_id.fillna(0) > 0)
    m["has_result"] = m.win_team_id.notna()
    nores = (~m.has_result).sum()
    q.append(
        (
            "Matches without a winner",
            f"{nores} (no result / abandoned / tied without super over)",
            "Kept for player stats where balls exist; excluded from win-probability training.",
        )
    )
    noballs = len(set(m.match_id) - set(b.match_id))
    q.append(("Matches with no ball-by-ball data", f"{noballs}", "Abandoned before a ball; ignored."))
    rev = m.first_inn_revised_overs.notna().sum() + m.second_inn_revised_overs.notna().sum()
    q.append(
        (
            "Rain-reduced innings",
            f"{rev} innings; revised overs stored as BALLS (e.g. 114 = 19 overs)",
            "Used as the innings length; revised_target used as the chase target.",
        )
    )

    full = set(cfg["full_members"])
    tm = pd.concat(
        [
            m[["home_team_id", "home_team", "format"]].set_axis(["team_id", "team", "format"], axis=1),
            m[["away_team_id", "away_team", "format"]].set_axis(["team_id", "team", "format"], axis=1),
        ]
    )
    tm = tm.drop_duplicates("team_id")
    tm["tier"] = np.where(tm.format.eq("IPL") | tm.team.isin(full), 1, 2)  # A-teams and associates = tier 2
    team_name = dict(zip(tm.team_id, tm.team, strict=True))
    team_tier = dict(zip(tm.team_id, tm.tier, strict=True))
    assoc = sorted(tm[tm.tier == 2].team.unique())
    other = sorted(c[c.format == "Other T20"].comp_name)
    q.append(
        (
            "Format coding",
            f"IPL and two A-team events ({'; '.join(other)}) share the code 'T20'",
            "Only competitions named IPL are treated as IPL; the A-team events are labelled 'Other T20'.",
        )
    )
    q.append(
        (
            "Second-tier teams (associates and A-teams)",
            ", ".join(assoc),
            f"Balls against these teams weighted x{cfg['weights']['associate_opposition']} in player ratings.",
        )
    )

    # ---- balls ----
    sup = b.innings.isin([3, 4]).sum()
    q.append(("Super-over balls", f"{sup}", "Excluded: too few to rate and not comparable to a 20-over innings."))
    b = b[b.innings.isin([1, 2])].copy()
    dup = b.duplicated(["match_id", "innings", "innings_ball_num"]).sum()
    q.append(("Duplicate deliveries", f"{dup}", "None found."))
    b["extras_type"] = b.extras_type.fillna("none")
    b["bat_runs"] = b.runs.fillna(0).astype(int)
    b["extras"] = (b.extras1_runs.fillna(0) + b.extras_2_runs.fillna(0)).astype(int)
    b["total"] = b.bat_runs + b.extras
    b["legal"] = (~b.extras_type.isin(ILLEGAL)).astype(int)
    b["is_noball"] = b.extras_type.isin(NO_BALL).astype(int)
    b["is_wide"] = b.extras_type.eq("wide").astype(int)
    b["faced"] = 1 - b.is_wide  # batter faced it (legal or no-ball)
    b["wkt"] = _bool(b.is_wicket).astype(int)
    b["is_four"] = _bool(b.is_four).astype(int)
    b["is_six"] = _bool(b.is_six).astype(int)
    b["striker_out"] = (b.wkt.eq(1) & b.dismissed_player_id.eq(b.striker_id)).astype(int)
    b["bowler_wkt"] = (b.wkt.eq(1) & ~b.dismissal_type.isin(NOT_BOWLER_WICKET)).astype(int)
    # runs charged to the bowler: off the bat + wides + no-ball penalty (not byes / leg-byes)
    b["bowler_runs"] = b.bat_runs + np.where(b.extras_type.isin(ILLEGAL), b.extras1_runs.fillna(0), 0).astype(int)
    q.append(
        (
            "Extras coding",
            "wide / Overstep / other / byes / legbyes / Penalty",
            "'Overstep' and 'other' are no-balls (batter faced, not a legal ball). Byes and leg-byes are not charged to the bowler.",
        )
    )

    # ---- names: IDs are the key; disambiguate shared names ----
    names = pd.concat(
        [
            b[["striker_id", "striker_name"]].set_axis(["player_id", "name"], axis=1),
            b[["non_striker_id", "non_striker_name"]].set_axis(["player_id", "name"], axis=1),
            b[["bowler_id", "bowler_name"]].set_axis(["player_id", "name"], axis=1),
        ]
    ).drop_duplicates("player_id")
    shared = names.groupby("name").player_id.nunique()
    shared = shared[shared > 1].index.tolist()
    q.append(
        (
            "Same name, different players",
            ", ".join(shared),
            "Players identified by ID; display name gets their team in brackets.",
        )
    )

    b = b.merge(
        m[
            [
                "match_id",
                "comp_id",
                "comp_name",
                "format",
                "is_ipl",
                "season_year",
                "match_date",
                "venue_id",
                "venue_country",
                "knock_out",
                "stage",
                "win_team_id",
                "has_result",
                "revised_target",
                "first_inn_revised_overs",
                "second_inn_revised_overs",
                "home_team",
                "away_team",
                "result",
            ]
        ],
        on="match_id",
        how="left",
    )
    b["bat_tier"] = b.batting_team_id.map(team_tier).fillna(1).astype(int)
    b["bowl_tier"] = b.bowling_team_id.map(team_tier).fillna(1).astype(int)
    b["batting_team"] = b.batting_team_id.map(team_name)
    b["bowling_team"] = b.bowling_team_id.map(team_name)
    b = b.sort_values(["match_id", "innings", "innings_ball_num"]).reset_index(drop=True)

    # ---- player directory ----
    p11 = raw["playing_eleven"]
    mp = raw["competition_team_player_mapping"].merge(c[["comp_id", "format", "season_year"]], on="comp_id")
    last_team = mp.sort_values("season_year").groupby("player_id").tail(1).set_index("player_id").team_name
    ipl26 = mp[(mp.format == "IPL") & (mp.season_year == mp[mp.format == "IPL"].season_year.max())]
    ipl_team = ipl26.drop_duplicates("player_id").set_index("player_id").team_name
    intl = mp[mp.format == "T20I"].groupby("player_id").team_name.agg(lambda s: s.value_counts().index[0])
    players = names.copy()
    players["latest_team"] = players.player_id.map(last_team)
    players["ipl_team_latest"] = players.player_id.map(ipl_team)
    ipl_any = mp[mp.format == "IPL"].sort_values("season_year").groupby("player_id").tail(1).set_index("player_id")
    players["ipl_team_any"] = players.player_id.map(ipl_any.team_name)
    players["ipl_last_season"] = players.player_id.map(ipl_any.season_year)
    players["country"] = players.player_id.map(intl)
    bt = b.drop_duplicates("striker_id").set_index("striker_id").batting_type
    bw = b.drop_duplicates("bowler_id").set_index("bowler_id")
    players["bat_hand"] = players.player_id.map(bt)
    players["bowl_type"] = players.player_id.map(bw.bowling_type)
    players["pace_spin"] = players.player_id.map(bw.pace_or_spin)
    players["team_label"] = players.ipl_team_latest.fillna(players.country).fillna(players.latest_team)
    players["display_name"] = np.where(
        players.name.isin(shared),
        players.name + " (" + players.country.fillna(players.latest_team).fillna("?") + ")",
        players.name,
    )
    # IPL 2026 playing time: how often the franchise picked the player (a strong retention signal)
    ipl_max = m.loc[m.format == "IPL", "season_year"].max()
    m26 = set(m.loc[(m.format == "IPL") & (m.season_year == ipl_max), "match_id"])
    p26 = p11[p11.match_id.isin(m26) & _bool(p11.is_played)]
    team_games = p26.groupby("team_id").match_id.nunique()
    players["ipl26_games"] = players.player_id.map(p26.groupby("player_id").match_id.nunique()).fillna(0).astype(int)
    squad_tid = ipl26.drop_duplicates("player_id").set_index("player_id").team_id
    players["ipl26_team_games"] = players.player_id.map(squad_tid).map(team_games)
    players["impact_sub_apps"] = (
        players.player_id.map(p11[p11.is_impact == 1].groupby("player_id").size()).fillna(0).astype(int)
    )

    q_df = pd.DataFrame(q, columns=["check", "finding", "decision"])
    return b, m, players, q_df, tm
