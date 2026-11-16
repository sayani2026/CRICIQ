"""Unit tests for the engine on a synthetic Data Pack with hand-checked answers."""

import copy

import numpy as np
import pandas as pd
import pytest

from engine import load, match_state, pressure, scoring, win_prob
from engine.validation import CRICQError, validate_config, validate_schema

# ---------------- validation ----------------


def test_real_config_is_valid(cfg):
    validate_config(cfg)


@pytest.mark.parametrize(
    "path,value,message",
    [
        (("pressure", "weight_stakes"), 0.9, "add up to 1"),
        (("pressure", "high_pressure_pct"), 120, "at most 99"),
        (("score", "w_lift"), "high", "must be a number"),
        (("eligibility", "active_since"), 25, "a year like 2025"),
        (("eligibility", "bat_min_pressure_balls"), 0, "at least 1"),
    ],
)
def test_bad_config_is_rejected_with_a_clear_message(cfg, path, value, message):
    c = copy.deepcopy(cfg)
    c[path[0]][path[1]] = value
    with pytest.raises(CRICQError, match=message):
        validate_config(c)


def test_missing_column_is_named(datapack):
    raw = load.load_raw(datapack)
    raw["ball_by_ball"] = raw["ball_by_ball"].drop(columns=["bowler_id"])
    with pytest.raises(CRICQError, match="ball_by_ball.csv is missing column\\(s\\): bowler_id"):
        validate_schema(raw)


def test_missing_file_is_named(datapack):
    (datapack / "teams.csv").unlink()
    with pytest.raises(CRICQError, match="teams.csv"):
        load.load_raw(datapack)


def test_orphan_match_ids_are_caught(datapack):
    raw = load.load_raw(datapack)
    raw["ball_by_ball"].loc[0, "match_id"] = 999
    with pytest.raises(CRICQError, match="not found in matches.csv"):
        validate_schema(raw)


# ---------------- loading ----------------


@pytest.fixture
def built(cfg):
    b, m, players, quality, teams = load.build(cfg)
    return b, m, players, quality, teams


def test_format_coding_ipl_vs_a_team_events(built):
    b, m, *_ = built
    fmt = m.set_index("match_id").format
    assert fmt[101] == "IPL"
    assert fmt[102] == "Other T20"  # shares the 'T20' code with IPL but is not IPL
    assert fmt[103] == "T20I"


def test_team_tiers(built):
    *_, teams = built
    tier = teams.set_index("team").tier
    assert tier["Rajasthan Royals"] == 1 and tier["India"] == 1
    assert tier["India A"] == 2 and tier["Oman"] == 2


def test_extras_and_legal_balls(built):
    b, *_ = built
    first = b[(b.match_id == 101) & (b.innings == 1)]
    assert first.legal.sum() == 12  # 13 deliveries, one wide
    assert first.total.sum() == 20  # 19 off the bat + 1 wide
    wide = first[first.extras_type == "wide"].iloc[0]
    assert wide.faced == 0 and wide.bowler_runs == 1


# ---------------- scoreboard ----------------


def test_scoreboard_state(built):
    b, m, *_ = built
    s = match_state.add_state(b)
    chase = s[(s.match_id == 101) & (s.innings == 2)].reset_index(drop=True)
    assert (chase.target == 21).all()  # first innings 20 -> target 21
    assert chase.loc[0, "balls_left"] == 12  # rain-reduced: revised overs stored as 12 BALLS
    assert chase.loc[0, "runs_needed"] == 21
    assert chase.loc[3, "score_before"] == 10 and chase.loc[3, "wkts_before"] == 1
    assert chase.loc[3, "balls_left"] == 9
    first = s[(s.match_id == 101) & (s.innings == 1)].reset_index(drop=True)
    assert first.target.isna().all() and first.rrr.isna().all()


def test_reconciliation_against_result_text(built):
    b, m, *_ = built
    s = match_state.add_state(b)
    rec = match_state.reconcile(s, m)
    assert rec.ok.all() and len(rec) == 3


# ---------------- win probability rules ----------------


def test_terminal_states_follow_the_rules():
    d = pd.DataFrame({"runs_needed": [4, 4, 10], "wkts_in_hand": [3, 1, 5], "balls_left": [5, 5, 1]})
    four = win_prob.terminal(d, 4, 0, 2)
    assert four[0] == 1.0  # four off the bat wins it
    wicket = win_prob.terminal(d, 0, 1, 2)
    assert wicket[1] == 0.0  # last wicket falls -> lost
    dot = win_prob.terminal(d, 0, 0, 2)
    assert dot[2] == 0.0 and np.isnan(dot[0])  # balls run out -> lost; otherwise undecided


# ---------------- pressure ----------------


def test_pressure_index_range_and_share():
    rng = np.random.default_rng(0)
    n = 4000
    b = pd.DataFrame({"innings": rng.integers(1, 3, n), "leverage": rng.random(n), "squeeze": rng.random(n) * 3})
    out = pressure.add_pressure(b, 0.5, 0.5, 75)
    assert out.pressure_index.between(0, 100).all()
    assert abs(out.high_pressure.mean() - 0.25) < 0.01
    # more stakes and more squeeze can never mean less pressure
    hi = out.loc[(out.leverage > 0.9) & (out["squeeze"] > 2.7), "pressure_index"].min()
    lo = out.loc[(out.leverage < 0.1) & (out["squeeze"] < 0.3), "pressure_index"].max()
    assert hi > lo


# ---------------- scoring maths ----------------


def test_shrinkage_pulls_small_samples_harder():
    v = pd.Series([1.0] * 10 + [1.0] * 1000)
    w = pd.Series([1.0] * 1010)
    g = pd.Series(["small"] * 10 + ["big"] * 1000)
    m = scoring.shrunk_mean(v, w, g, k=100, mu=0.0)
    assert 0 < m["small"] < m["big"] < 1  # both pulled toward 0, the small sample much more


def test_estimate_k_is_positive_and_bounded():
    rng = np.random.default_rng(1)
    skill = np.repeat(rng.normal(0, 0.1, 50), 400)
    v = pd.Series(skill + rng.normal(0, 2.5, skill.size))
    g = pd.Series(np.repeat(np.arange(50), 400))
    k, mu = scoring.estimate_k(v, pd.Series(np.ones(v.size)), g)
    assert 30 <= k <= 5000 and abs(mu) < 0.1


def test_anchored_estimate_moves_toward_pressure_record_with_more_balls():
    S = pd.DataFrame(
        {"Ps": [10.0, 100.0], "Pw": [20.0, 200.0], "Ns": [0.0, 0.0], "Nw": [1000.0, 1000.0]}, index=["few", "many"]
    )
    A, Q, N = scoring._estimate(S, kA=500, muA=0.0, kq=200)
    # same raw pressure rate (0.5/ball); more pressure balls -> estimate sits further from overall ability
    assert (Q["many"] - A["many"]) > (Q["few"] - A["few"]) > 0


# ---------------- command line ----------------


def test_cli_exits_cleanly_on_bad_settings(tmp_path, capsys):
    import yaml

    import pipeline

    with open(pipeline.__file__.replace("pipeline.py", "config.yaml"), encoding="utf-8") as fh:
        c = yaml.safe_load(fh)
    c["pressure"]["weight_stakes"] = 0.9
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(c), encoding="utf-8")
    assert pipeline.cli(["--config", str(bad)]) == 2
    assert "add up to 1" in capsys.readouterr().out
