"""Cricket parameters: tagging balls and measuring players in each situation."""

import numpy as np
import pandas as pd

from engine import factors as fx


def _balls(n=240):
    rng = np.random.default_rng(1)
    return pd.DataFrame(
        {
            "match_id": np.repeat([1, 2], n // 2),
            "innings": np.tile(np.repeat([1, 2], n // 4), 2),
            "innings_ball_num": np.tile(np.arange(n // 4), 4),
            "wkts_in_hand": rng.integers(0, 11, n),
            "wkt": (rng.random(n) < 0.06).astype(int),
            "venue_par": np.repeat([150.0, 200.0], n // 2),
            "venue_id": np.repeat([3, 9], n // 2),
            "knock_out": 0,
            "format": "IPL",
            "phase": np.tile(["Powerplay", "Middle", "Death"], n // 3),
            "high_pressure": rng.random(n) < 0.3,
            "bowling_type": np.tile(
                ["Right-arm Fast", "Right-arm offbreak", "Slow left-arm orthodox", "Left-arm Fast"], n // 4
            ),
            "batting_type": np.tile(["RHB", "LHB"], n // 2),
            "bat_tier": 1,
            "bowl_tier": 1,
            "faced": 1,
            "legal": 1,
            "striker_id": np.tile([10, 11], n // 2),
            "bowler_id": np.tile([20, 21, 22], n // 3),
            "bat_runs": rng.integers(0, 7, n),
            "bowler_runs": rng.integers(0, 7, n),
            "striker_out": 0,
            "bowler_wkt": 0,
            "bat_adj": rng.normal(0, 1, n),
            "bowl_adj": rng.normal(0, 1, n),
        }
    )


def test_context_levels():
    c = fx.context(_balls(), rr_home_venues={3})
    for col in fx.FACTOR_COLUMNS:
        assert col in c.columns and c[col].notna().all()
    assert set(c.bowler_type_f) == {"Right-arm pace", "Off-spin", "Left-arm spin", "Left-arm pace"}
    assert set(c.rr_home_f) == {"At RR home venues", "Elsewhere"}
    assert c.pitch_f.str.startswith("Low").any() and c.pitch_f.str.startswith("High").any()


def test_splits_and_scout_are_consistent():
    c = fx.context(_balls())
    sp = fx.splits(c, "bat", min_balls=1)
    one = sp[(sp.player_id == 10) & (sp.factor == "phase")]
    assert one.balls.sum() == (c.striker_id == 10).sum()  # the phase levels partition the balls
    r = fx.scout(c, "bowl", {"phase": ["Death"]}, min_balls=1)
    assert set(r.player_id) <= {20, 21, 22} and r.per100.is_monotonic_decreasing
    mu = fx.matchups(c, min_balls=1)
    assert mu.balls.sum() == len(c)
