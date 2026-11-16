"""Shared fixtures: a tiny, hand-checkable synthetic Data Pack."""

import copy
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _innings(match_id, inn, bat_id, bowl_id, batters, bowler, runs_list, wicket_at=(), extras=None):
    """One innings: runs_list = runs off the bat per delivery; extras = {delivery_index: (type, runs)}."""
    rows, extras = [], extras or {}
    for k, r in enumerate(runs_list, start=1):
        et, er = extras.get(k, (None, 0))
        wk = k in wicket_at
        rows.append(
            {
                "match_id": match_id,
                "innings": inn,
                "overid": (k - 1) // 6 + 1,
                "over_ball_num": (k - 1) % 6 + 1,
                "innings_ball_num": k,
                "batting_team_id": bat_id,
                "bowling_team_id": bowl_id,
                "striker_id": batters[0][0],
                "striker_name": batters[0][1],
                "non_striker_id": batters[1][0],
                "non_striker_name": batters[1][1],
                "bowler_id": bowler[0],
                "bowler_name": bowler[1],
                "batting_type": "RHB",
                "bowling_type": "Right-arm Fast",
                "batting_order": 1,
                "runs": r,
                "is_four": r == 4,
                "is_six": r == 6,
                "is_wicket": wk,
                "dismissal_type_id": None,
                "dismissal_type": "Bowled" if wk else None,
                "dismissed_player_id": batters[0][0] if wk else None,
                "extras_type": et,
                "extras1_runs": er,
                "extras_2_runs": 0,
                "pace_or_spin": "Pace",
                "bowl_speed": 140,
                "stroke": "Drive",
                "delivery_style": "Seam",
                "over_or_around": "Over",
                "on_or_off": "Off-side",
                "delivery_ist_time": "2025-04-01 00:00:00 UTC",
            }
        )
    return rows


@pytest.fixture
def datapack(tmp_path):
    """Three 2-over matches written as the six Data Pack CSVs. Returns the folder."""
    comps = pd.DataFrame(
        [
            {"comp_id": 1, "comp_name": "IPL 2025", "match_format": "T20", "season": "2025"},
            {"comp_id": 2, "comp_name": "Asia Cup Rising Stars 2025", "match_format": "T20", "season": "2025"},
            {"comp_id": 3, "comp_name": "India in England T20I Series 2025", "match_format": "T20I", "season": "2025"},
        ]
    )
    teams = pd.DataFrame(
        [
            {"comp_id": 1, "team_id": 2, "team_name": "Mumbai Indians"},
            {"comp_id": 1, "team_id": 3, "team_name": "Rajasthan Royals"},
            {"comp_id": 2, "team_id": 222, "team_name": "India A"},
            {"comp_id": 2, "team_id": 313, "team_name": "Oman"},
            {"comp_id": 3, "team_id": 18, "team_name": "India"},
            {"comp_id": 3, "team_id": 22, "team_name": "England"},
        ]
    )
    m = []
    for mid, comp, h, hn, a, an, win, res, rev1, rev2, rt in [
        (101, 1, 2, "Mumbai Indians", 3, "Rajasthan Royals", 3, "Rajasthan Royals won by 9 wickets", 12, 12, None),
        (102, 2, 222, "India A", 313, "Oman", 222, "India A won by 5 runs", None, None, None),
        (103, 3, 18, "India", 22, "England", 18, "India won by 3 runs", None, None, None),
    ]:
        m.append(
            {
                "match_id": mid,
                "comp_id": comp,
                "match_number": 1,
                "match_date": "2025-04-0" + str(mid - 100),
                "stage": "League",
                "venue_id": 1,
                "venue_country": "India",
                "home_team_id": h,
                "home_team": hn,
                "away_team_id": a,
                "away_team": an,
                "home_team_captain_id": None,
                "away_team_captain_id": None,
                "toss_win_team_id": h,
                "toss_opted": "Batting",
                "man_of_the_match": 0,
                "first_inn_revised_overs": rev1,
                "second_inn_revised_overs": rev2,
                "revised_target": rt,
                "knock_out": 0,
                "win_team_id": win,
                "result": res,
            }
        )
    matches = pd.DataFrame(m)
    p = {
        i: (i, n)
        for i, n in [
            (1, "Rohit Bat"),
            (2, "Ishan Bat"),
            (3, "Jos Bat"),
            (4, "Sanju Bat"),
            (5, "Bumrah Bowl"),
            (6, "Boult Bowl"),
            (7, "Abhishek A"),
            (8, "Oman Bat"),
            (9, "Oman Bowl"),
            (10, "India A Bowl"),
            (11, "Kohli Bat"),
            (12, "Buttler Bat"),
            (13, "Archer Bowl"),
            (14, "Arshdeep Bowl"),
            (15, "Samad (India)"),
            (16, "Samad (Pak)"),
        ]
    }
    b = []
    # match 101: rain-reduced to 12 balls each; MI 20/1 (incl. a wide), RR chase 21 for 1 wicket down -> RR won by 9 wkts
    b += _innings(
        101,
        1,
        2,
        3,
        [p[1], p[2]],
        p[6],
        [1, 4, 0, 6, 1, 0, 2, 0, 1, 0, 4, 0, 0],
        wicket_at=(6,),
        extras={3: ("wide", 1)},
    )
    b += _innings(101, 2, 3, 2, [p[3], p[4]], p[5], [4, 6, 0, 1, 4, 6], wicket_at=(3,))
    # match 102: India A 30/0 off 12, Oman 25/2 off 12 -> India A by 5 runs
    b += _innings(102, 1, 222, 313, [p[7], p[15]], p[9], [6, 0, 4, 1, 1, 6, 0, 4, 2, 2, 0, 4])
    b += _innings(102, 2, 313, 222, [p[8], p[16]], p[10], [2, 2, 2, 6, 0, 1, 4, 0, 4, 0, 2, 2], wicket_at=(5, 10))
    # match 103: India 18/0 off 12, England 15/1 off 12 -> India by 3 runs
    b += _innings(103, 1, 18, 22, [p[11], p[1]], p[13], [1, 1, 2, 1, 4, 0, 1, 1, 2, 1, 4, 0])
    b += _innings(103, 2, 22, 18, [p[12], p[3]], p[14], [0, 1, 4, 1, 0, 0, 1, 2, 4, 1, 1, 0], wicket_at=(6,))
    balls = pd.DataFrame(b)
    xi = pd.DataFrame(
        [
            {
                "match_id": r.match_id,
                "team_id": r.batting_team_id,
                "player_id": r.striker_id,
                "batting_order": 1,
                "is_played": True,
                "is_captain": False,
                "is_wk": False,
                "is_impact": 0,
                "is_impact_off": 0,
            }
            for r in balls.drop_duplicates(["match_id", "striker_id"]).itertuples()
        ]
    )
    mp = []
    for comp, team_id, team_name, pids in [
        (1, 2, "Mumbai Indians", [1, 2, 6]),
        (1, 3, "Rajasthan Royals", [3, 4, 5]),
        (2, 222, "India A", [7, 10, 15]),
        (2, 313, "Oman", [8, 9, 16]),
        (3, 18, "India", [11, 1, 14]),
        (3, 22, "England", [12, 13, 3]),
    ]:
        name = comps.set_index("comp_id").comp_name[comp]
        mp += [
            {
                "comp_id": comp,
                "comp_name": name,
                "team_id": team_id,
                "team_name": team_name,
                "player_id": i,
                "player_name": p[i][1],
            }
            for i in pids
        ]
    for name, df in [
        ("ball_by_ball", balls),
        ("matches", matches),
        ("competitions", comps),
        ("teams", teams),
        ("playing_eleven", xi),
        ("competition_team_player_mapping", pd.DataFrame(mp)),
    ]:
        df.to_csv(tmp_path / f"{name}.csv", index=False)
    return tmp_path


@pytest.fixture
def cfg(datapack):
    """The real config.yaml, pointed at the synthetic Data Pack."""
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        c = yaml.safe_load(fh)
    c = copy.deepcopy(c)
    c["paths"]["raw"] = datapack
    return c
