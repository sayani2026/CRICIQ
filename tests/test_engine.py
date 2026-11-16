"""Checks on the pipeline outputs. Run:  pytest -q   (after python pipeline.py)"""

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
PROC = ROOT / "data" / "processed"

pytestmark = pytest.mark.skipif(not (OUT / "model_report.json").exists(), reason="run python pipeline.py first")


@pytest.fixture(scope="module")
def rep():
    return json.load(open(OUT / "model_report.json"))


def test_scoreboard_matches_official_results(rep):
    assert rep["reconciliation"]["match_rate_pct"] >= 99.5


def test_win_probability_beats_guessing(rep):
    for r in rep["win_probability"]:
        assert r["brier"] < r["brier_baseline"]
    assert rep["win_probability"][1]["auc"] > 0.85


def test_expected_models_calibrated(rep):
    e = rep["expected_calibration"]
    assert abs(e["bat_runs_expected"] - e["bat_runs_actual"]) < 0.02
    assert abs(e["out_expected"] - e["out_actual"]) < 0.002


def test_pressure_index_is_concentrated(rep):
    chase = [m for m in rep["pressure"]["wp_movement"] if m["innings"] == 2][0]
    assert chase["share_of_wp_movement_pct"] > 1.5 * chase["share_of_balls_pct"]


def test_pressure_index_range():
    b = pd.read_parquet(PROC / "balls.parquet", columns=["pressure_index", "high_pressure"])
    assert b.pressure_index.between(0, 100).all()
    assert 0.2 < b.high_pressure.mean() < 0.3


@pytest.mark.parametrize("f", ["top10_batters.csv", "top10_bowlers.csv"])
def test_top10_lists_valid(f):
    t = pd.read_csv(OUT / f)
    assert len(t) == 10
    assert t.display_name.is_unique
    assert list(t["rank"]) == list(range(1, 11))
    assert t.clutch_score.is_monotonic_decreasing
    assert (t.score_lo <= t.clutch_score).all() and (t.clutch_score <= t.score_hi).all()
