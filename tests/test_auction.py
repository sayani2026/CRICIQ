"""Availability rules and the RR auction board logic, on small hand-made tables."""

import pandas as pd
import pytest
import yaml

from engine import auction as au
from engine import availability as av
from engine.config import ROOT
from engine.validation import CRICQError, validate_config


@pytest.fixture()
def acfg():
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        c = yaml.safe_load(fh)
    c["auction"]["salary_cap_cr"] = 100
    return c


def _players():
    return pd.DataFrame(
        {
            "player_id": [1, 2, 3, 4, 5, 6, 7],
            "display_name": [
                "Retired Guy",
                "Pak Player",
                "Old Timer",
                "Contract Man",
                "Free Agent",
                "New Face",
                "RR Bowler",
            ],
            "country": ["India", "Pakistan", "India", None, "England", "Zimbabwe", None],
            "ipl_team_latest": [None, None, None, "Mumbai Indians", None, None, "Rajasthan Royals"],
            "ipl_team_any": ["KKR", None, "CSK", "Mumbai Indians", "Delhi Capitals", None, "Rajasthan Royals"],
            "last_season": [2026, 2026, 2023, 2026, 2025, 2026, 2026],
            "ipl26_games": [0, 0, 0, 14, 0, 0, 10],
            "ipl26_team_games": [None, None, None, 14, None, None, 14],
        }
    )


def _status():
    return pd.DataFrame(
        [
            {
                "player": "Retired Guy",
                "status": "retired",
                "note": "x",
                "source": "https://a",
                "source_date": "2026-01-01",
                "team_2027": "",
                "nationality": "",
                "last_fee_cr": "",
            }
        ]
    )


def _squad():
    return pd.DataFrame(
        {
            "player": ["RR Bowler", "RR Bat", "RR Star"],
            "overseas": [False, True, True],
            "fee_cr": [5.0, 10.0, 20.0],
            "covers": [["pace_death"], ["finisher"], ["top_order"]],
            "projection": ["retain", "release", "retain"],
            "reason": ["", "", ""],
            "source": ["", "", ""],
        }
    )


def test_status_rules(acfg):
    t = av.apply(_players(), _status(), _squad(), acfg).set_index("display_name")
    assert t.loc["Retired Guy", "status"] == "retired" and not t.loc["Retired Guy", "selectable"]
    # Round 1 ranks performance, so IPL eligibility doesn't remove a player from the lists; retirement does
    assert t.loc["Pak Player", "status"] == "ineligible" and t.loc["Pak Player", "selectable"]
    assert not t.loc["Old Timer", "selectable"]
    assert t.loc["Old Timer", "status"] == "inactive"
    assert t.loc["Contract Man", "status"] == "likely_retained"  # a regular in 2026 → kept
    assert t.loc["Free Agent", "status"] == "free_agent" and t.loc["Free Agent", "overseas"]
    assert t.loc["New Face", "status"] == "not_in_ipl"
    assert t.loc["RR Bowler", "status"] == "rr_squad" and t.loc["RR Bowler", "avail_prob"] == 0
    assert t.loc["Free Agent", "avail_prob"] == acfg["auction"]["availability_prob"]["free_agent"]


def test_status_file_validation(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("player,status,note,source,source_date\nA,maybe,x,y,z\n", encoding="utf-8")
    with pytest.raises(CRICQError, match="unknown status"):
        av.load_status(p)
    p.write_text("player,status,note,source,source_date\nA,retired,x,y,z\nA,retired,x,y,z\n", encoding="utf-8")
    with pytest.raises(CRICQError, match="listed twice"):
        av.load_status(p)


def test_real_files_load():
    s = av.load_status(ROOT / "data" / "external" / "player_status_2027.csv")
    q = av.load_rr_squad(ROOT / "data" / "external" / "rr_squad_2027.csv")
    r = av.load_reports(ROOT / "data" / "external" / "retention_reports_2027.csv")
    assert s.set_index("player").status["Andre Russell"] == "retired"
    td = r[r.player == "Tim David"]
    assert len(td) >= 2 and (td.verdict == "retain").all()
    assert q.overseas.sum() <= 9 and q.fee_cr.gt(0).all()


def test_squad_state(acfg):
    st = au.squad_state(_squad(), {"RR Bat"}, acfg)
    assert st["purse_cr"] == 75.0 and st["freed_cr"] == 10.0
    assert st["slots"] == acfg["auction"]["max_squad"] - 2
    assert st["overseas_slots"] == acfg["auction"]["max_overseas"] - 1


def _tables():
    bat = pd.DataFrame(
        {
            "player_id": [10, 11, 12],
            "display_name": ["RR Bat", "Target Finisher", "Kept Elsewhere"],
            "eligible": [True, True, True],
            "clutch_score": [45.0, 60.0, 80.0],
            "role": ["Middle / finisher"] * 3,
            "pace_spin": [None] * 3,
            "status": ["rr_squad", "likely_released", "likely_retained"],
            "status_label": ["", "Tipped for release", "Core"],
            "status_note": [""] * 3,
            "status_source": [""] * 3,
            "status_date": [""] * 3,
            "team_2027": [""] * 3,
            "nationality": ["India"] * 3,
            "overseas": [False, False, True],
            "avail_prob": [0.0, 0.75, 0.03],
            "score_lo": [40.0] * 3,
            "score_hi": [70.0] * 3,
            "p_balls": [200] * 3,
            "last_season": [2026] * 3,
        }
    )
    bowl = bat.iloc[:0].assign(pp_share=[], death_share=[])
    return bat, bowl


def test_needs_targets_plan(acfg):
    acfg["auction"]["needs"] = {
        "finisher": {"label": "Finisher", "want": 1, "table": "bat", "roles": ["Middle / finisher"]}
    }
    bat, bowl = _tables()
    sq = _squad()
    st = au.squad_state(sq, {"RR Bat"}, acfg)
    nt = au.needs(st["kept"], bat, bowl, acfg)
    assert nt.iloc[0].level == "High"  # nobody kept covers finisher → empty slot scores below replacement
    pool = au.targets(bat, bowl, nt, set(st["kept"].player), acfg, released_names={"RR Bat"})
    assert "Kept Elsewhere" not in set(pool.display_name)  # 3% availability is filtered out
    assert pool.set_index("display_name").avail_prob["RR Bat"] == au.BUYBACK_PROB  # released RR player can be re-bought
    pl = au.plan(pool, nt, st, acfg)
    assert pl.iloc[0].target == "Target Finisher"
    assert len(pl) <= st["slots"]


def test_auction_config_checked(acfg):
    acfg["auction"]["needs"]["finisher"]["table"] = "nope"
    acfg["auction"]["availability_prob"]["retired"] = 2
    with pytest.raises(CRICQError) as e:
        validate_config(acfg)
    assert "needs.finisher.table" in str(e.value) and "availability_prob.retired" in str(e.value)


def test_news_consensus_and_playing_time(acfg):
    p = _players()
    rep = pd.DataFrame(
        [
            dict(
                player="Contract Man",
                team="Mumbai Indians",
                verdict="release",
                source=s,
                url="u",
                date="2026-11-01",
                kind="prediction",
            )
            for s in ("A", "B", "C", "D")
        ]
        + [
            dict(
                player="Contract Man",
                team="Mumbai Indians",
                verdict="release",
                source="A",
                url="u",
                date="2026-11-02",
                kind="prediction",
            )
        ]
    )
    t = av.apply(p, _status(), _squad(), acfg, reports=rep).set_index("display_name")
    # four outlets (A counted once) outweigh being a regular → tipped for release
    assert t.loc["Contract Man", "status"] == "likely_released"
    assert 0.7 <= t.loc["Contract Man", "avail_prob"] < 1
    assert av.playing_prior(14, 14)[0] < 0 < av.playing_prior(0, 14)[0]
    assert av.status_from_p(0.05) == "likely_retained" and av.status_from_p(0.9) == "likely_released"


def test_name_resolution():
    d = pd.DataFrame(
        {
            "display_name": [
                "Mahendra Singh Dhoni",
                "M Shahrukh Khan",
                "Himmat Singh",
                "Mayank Yadav",
                "Namboori Tilak Varma",
            ],
            "ipl_team_latest": ["CSK", "GT", "LSG", "LSG", "MI"],
        }
    )
    m = av.resolve_names(["MS Dhoni", "Shahrukh Khan", "Harnoor Singh", "Mangesh Yadav", "Tilak Varma"], d)
    assert m["MS Dhoni"] == "Mahendra Singh Dhoni" and m["Shahrukh Khan"] == "M Shahrukh Khan"
    assert m["Tilak Varma"] == "Namboori Tilak Varma"
    assert m["Harnoor Singh"] is None and m["Mangesh Yadav"] is None  # never guess a different player


def test_projected_xi_respects_overseas(acfg):
    kept = pd.DataFrame(
        {
            "player": [f"P{i}" for i in range(14)],
            "overseas": [True] * 6 + [False] * 8,
            "covers": [["pace_death"], ["spin"], ["top_order"], ["finisher"], ["wicketkeeper"], ["allrounder_pace"]]
            + [
                ["pace_death"],
                ["pace_powerplay"],
                ["spin"],
                ["top_order"],
                ["top_order"],
                ["finisher"],
                ["wicketkeeper"],
                ["spin"],
            ],
        }
    )
    empty = pd.DataFrame(columns=["display_name", "eligible", "clutch_score", "p_balls"])
    xi = au.projected_xi(kept, pd.DataFrame(), empty, empty, acfg)
    assert len(xi) == 12 and xi.overseas.sum() <= 4
    real = xi[xi.player != "— gap —"].player
    assert real.is_unique


def test_official_list_is_pure_pressure_ranking_minus_retired():
    from engine.rankings import top10

    t = pd.DataFrame(
        {
            "player_id": [1, 2, 3, 4],
            "display_name": ["Kept Star", "Released Guy", "Retired Legend", "Free Agent"],
            "eligible": [True, True, True, True],
            "selectable": [True, True, False, True],
            "in_pool": [False, True, False, True],
            "clutch_score": [90.0, 60.0, 80.0, 55.0],
        }
    )
    # a star his team will keep stays in (Round 1 is about performance); a retired player does not
    assert top10(t).display_name.tolist() == ["Kept Star", "Released Guy", "Free Agent"]
