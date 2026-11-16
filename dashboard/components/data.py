"""Cached data access for the dashboard. Everything comes from pipeline.py outputs."""

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engine import auction as au  # noqa: E402, F401  (re-exported for the auction view)
from engine import availability as av  # noqa: E402
from engine import factors as fx  # noqa: E402, F401  (re-exported for the scout and matchup views)


def data_stamp():
    """Fingerprint of every input the dashboard reads (outputs, processed data, external files, config)."""
    files = [ROOT / "config.yaml", ROOT / "VERSION"]
    for d in (OUT, PROC, ROOT / "data" / "external", ROOT / "Player Image", ROOT / "assets" / "players"):
        if d.exists():
            files += [p for p in d.iterdir() if p.is_file()]
    return tuple(sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in files if p.exists()))


@st.cache_resource
def _seen():
    return {"stamp": None}


def sync():
    """Drop every cached table when the pipeline (or an edited CSV) has changed the data on disk.

    Without this, a dashboard left running keeps showing the previous results until it is restarted.
    """
    s, seen = data_stamp(), _seen()
    if seen["stamp"] != s:
        st.cache_data.clear()
        seen["stamp"] = s


def ready():
    return (PROC / "balls.parquet").exists() and (OUT / "batting_scores.csv").exists()


@st.cache_data(show_spinner=False)
def balls():
    b = pd.read_parquet(PROC / "balls.parquet")
    b["match_date"] = pd.to_datetime(b.match_date)
    return b


@st.cache_data(show_spinner=False)
def matches():
    m = pd.read_parquet(PROC / "matches.parquet")
    m["match_date"] = pd.to_datetime(m.match_date)
    return m


@st.cache_data(show_spinner=False)
def players():
    return pd.read_parquet(PROC / "players.parquet")


@st.cache_data(show_spinner=False)
def scores(role):
    t = pd.read_csv(OUT / ("batting_scores.csv" if role == "bat" else "bowling_scores.csv"))
    t["team"] = t.team_label.fillna("—")
    return t


@st.cache_data(show_spinner=False)
def table(name):
    p = OUT / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def report():
    return json.load(open(OUT / "model_report.json"))


# ---------------- auction board ----------------
@st.cache_data(show_spinner=False)
def auction_cfg():
    """config.yaml with the auction section's file paths resolved (None if the section is missing)."""
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    a = cfg.get("auction")
    if not a:
        return None
    for k in ("status_file", "rr_squad_file", "reports_file"):
        if a.get(k):
            a[k] = str((ROOT / a[k]).resolve())
    return cfg


@st.cache_data(show_spinner=False)
def rr_squad():
    return av.load_rr_squad(auction_cfg()["auction"]["rr_squad_file"])


@st.cache_data(show_spinner=False)
def status_file():
    return av.load_status(auction_cfg()["auction"]["status_file"])


@st.cache_data(show_spinner=False)
def reports_file():
    a = auction_cfg()["auction"]
    return av.load_reports(a["reports_file"]) if a.get("reports_file") else pd.DataFrame(columns=av.REPORT_COLUMNS)


@st.cache_data(show_spinner=False)
def board(release: frozenset | None = None):
    """Auction board for a given release set (None = the default projection). Cached per release set."""
    cfg = auction_cfg()
    bat, bowl = scores("bat"), scores("bowl")
    sq = rr_squad()
    rel = set(au.default_release(sq)) if release is None else set(release)
    state = au.squad_state(sq, rel, cfg)
    need_tab = au.needs(state["kept"], bat, bowl, cfg)
    pool = au.targets(bat, bowl, need_tab, set(state["kept"].player), cfg, released_names=rel)
    plan = au.plan(pool, need_tab, state, cfg)
    xi = au.projected_xi(state["kept"], plan, bat, bowl, cfg)
    return {"release": rel, "state": state, "needs": need_tab, "pool": pool, "plan": plan, "xi": xi}


@st.cache_data(show_spinner=False)
def factors():
    p = OUT / "player_factors.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def matchups():
    p = OUT / "matchups.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


@st.cache_data(show_spinner=False)
def retired_ids():
    """Players never shown in searches: retired (status file) or no match since the configured active season."""
    b = balls()
    last = pd.concat([b.groupby("striker_id").season_year.max(), b.groupby("bowler_id").season_year.max()])
    last = last.groupby(level=0).max()
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        since = (yaml.safe_load(fh).get("eligibility") or {}).get("active_since") or 0
    out = set(last[last < since].index)
    for role in ("bat", "bowl"):
        t = scores(role)
        if "status" in t.columns:
            out |= set(t.loc[t.status.isin(["retired", "inactive"]), "player_id"])
    return out


def has_factors():
    return "phase_f" in balls().columns


def name_of(pid):
    p = players().set_index("player_id")
    return p.display_name.get(pid, str(pid))


# ---------------- per-player splits ----------------
def _bat_agg(d):
    g = pd.Series(
        {
            "balls": len(d),
            "runs": d.bat_runs.sum(),
            "outs": d.striker_out.sum(),
            "boundaries": (d.is_four + d.is_six).sum(),
            "dots": (d.bat_runs == 0).sum(),
        }
    )
    g["sr"] = g.runs / max(g.balls, 1) * 100
    g["bpd"] = g.balls / max(g.outs, 1)
    g["avg"] = g.runs / max(g.outs, 1)
    g["bnd_pct"] = g.boundaries / max(g.balls, 1) * 100
    g["dot_pct"] = g.dots / max(g.balls, 1) * 100
    return g


def _bowl_agg(d):
    legal = d.legal.sum()
    g = pd.Series(
        {
            "balls": legal,
            "runs": d.bowler_runs.sum(),
            "wkts": d.bowler_wkt.sum(),
            "dots": ((d.total == 0) & (d.legal == 1)).sum(),
            "boundaries": (d.is_four + d.is_six).sum(),
        }
    )
    g["econ"] = g.runs / max(legal, 1) * 6
    g["sr"] = legal / max(g.wkts, 1)
    g["dot_pct"] = g.dots / max(legal, 1) * 100
    g["bnd_pct"] = g.boundaries / max(legal, 1) * 100
    return g


@st.cache_data(show_spinner=False)
def bat_balls(pid):
    b = balls()
    return b[(b.striker_id == pid) & (b.faced == 1)]


@st.cache_data(show_spinner=False)
def bowl_balls(pid):
    b = balls()
    return b[b.bowler_id == pid]


def splits(pid, role):
    d = bat_balls(pid) if role == "bat" else bowl_balls(pid)
    agg = _bat_agg if role == "bat" else _bowl_agg
    rows = []
    dims = [
        ("All balls", pd.Series("All", index=d.index)),
        ("Phase", d.phase),
        ("Bowling", d.pace_or_spin.map({"Pace": "vs pace", "Spin": "vs spin"})),
        ("Competition", d.format),
    ]
    if role == "bowl":
        dims[2] = ("Batter", d.batting_type.map({"RHB": "vs right-handers", "LHB": "vs left-handers"}))
    for dim, key in dims:
        for k, g in d.groupby([key, d.high_pressure]):
            val, hp = k
            r = agg(g)
            r["dimension"], r["group"], r["pressure"] = dim, val, "Pressure" if hp else "Normal"
            rows.append(r)
    return pd.DataFrame(rows)


def overall(pid, role):
    d = bat_balls(pid) if role == "bat" else bowl_balls(pid)
    agg = _bat_agg if role == "bat" else _bowl_agg
    return agg(d[d.high_pressure == 1]), agg(d[d.high_pressure == 0])


def match_values(pid, role, min_balls=1):
    d = bat_balls(pid) if role == "bat" else bowl_balls(pid)
    v = "bat_adj" if role == "bat" else "bowl_adj"
    p = d[d.high_pressure == 1]
    g = (
        p.groupby(["match_id", "match_date", "comp_name", "batting_team", "bowling_team"])
        .agg(
            balls=(v, "size"),
            value=(v, "sum"),
            runs=("bat_runs" if role == "bat" else "bowler_runs", "sum"),
            outs=("striker_out" if role == "bat" else "bowler_wkt", "sum"),
        )
        .reset_index()
    )
    g = g[g.balls >= min_balls].sort_values("match_date")
    g["opponent"] = g.bowling_team if role == "bat" else g.batting_team
    return g


def dismissals(pid, role):
    if role == "bat":
        d = bat_balls(pid)
        d = d[(d.high_pressure == 1) & (d.striker_out == 1)]
    else:
        d = bowl_balls(pid)
        d = d[(d.high_pressure == 1) & (d.bowler_wkt == 1)]
    return d.dismissal_type.replace({"Stump": "Stumped", "RunOut": "Run out"}).value_counts()


def head_to_head(bat_id, bowl_id):
    b = balls()
    d = b[(b.striker_id == bat_id) & (b.bowler_id == bowl_id) & (b.faced == 1)]
    out = {}
    for lab, g in [("All", d), ("Under pressure", d[d.high_pressure == 1])]:
        a = _bat_agg(g) if len(g) else None
        out[lab] = a
    return out, len(d)


def match_label(m):
    res = str(m.result) if pd.notna(m.result) else ""
    return f"{m.comp_name} · {m.inn1_team} v {m.inn2_team} · {m.match_date:%d %b %Y} · {res}"
