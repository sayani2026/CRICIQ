"""Who can Rajasthan Royals actually buy? Player availability for the IPL 2027 auction.

A selector does not trust one article. CRICQ combines three kinds of evidence, all in editable files:

  1. Hard facts — data/external/player_status_2027.csv
     Retirements, confirmed trades, bans, eligibility risks, and (after 17 Nov) the official retained /
     released lists. A hard fact always wins.
  2. News consensus — data/external/retention_reports_2027.csv
     One row per (player, outlet) call: "retain" or "release", with source, date and kind
     (official / report / prediction / opinion). Each outlet counts once per player.
  3. Playing time — from the Data Pack: how many of the franchise's IPL 2026 matches the player played.
     Franchises keep their regulars (Tim David, Rohit Sharma) and cut players they did not pick.

For a player on a 2026 IPL squad:
     evidence = playing-time prior + Σ (source weight × vote)        vote: release +1, retain −1
     P(released) = 1 / (1 + e^-(baseline + evidence))
and the status follows from P: ≥ 0.70 tipped for release · 0.40–0.70 mixed reports ·
0.15–0.40 under contract · < 0.15 core player, likely retained.
Players not on a 2026 squad: retired / ineligible / inactive / free agent / must register, by rule.
"""

from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path

import pandas as pd

from .validation import CRICQError

STATUSES = {
    # status: (label, can be ranked in the official Round 1 lists?)
    # Round 1 ranks performance in the supplied data, so only retired players and players with no match since 2024
    # are left out. IPL availability (retentions, trades, eligibility) is shown for the auction board only.
    "released": ("Released — in auction", True),
    "likely_released": ("Tipped for release", True),
    "possible_release": ("Mixed reports — could be released", True),
    "free_agent": ("Not on a 2026 IPL squad", True),
    "not_in_ipl": ("Never in IPL — must register", True),
    "risk": ("Registered — eligibility risk", True),
    "banned": ("IPL ban — check eligibility", True),
    "under_contract": ("Under contract — only if released", True),
    "likely_retained": ("Core player — likely retained", True),
    "retained": ("Retained (official)", True),
    "traded": ("Traded — not available", True),
    "rr_squad": ("Rajasthan Royals squad", True),
    "opted_out": ("Opted out of IPL", True),
    "retired": ("Retired from IPL", False),
    "ineligible": ("Not eligible for IPL", True),
    "inactive": ("No match since 2024", False),
}
# Players Rajasthan Royals can actually sign at the 16 Dec auction. Only these get an official rank.
AUCTION_POOL = {"released", "likely_released", "possible_release", "free_agent", "not_in_ipl"}
KIND_WEIGHT = {"official": 10.0, "report": 2.0, "prediction": 1.0, "opinion": 0.5}
STATUS_COLUMNS = ["player", "status", "note", "source", "source_date"]
REPORT_COLUMNS = ["player", "team", "verdict", "source", "url", "date", "kind"]
RR = "Rajasthan Royals"
ALIASES = {
    "ms dhoni": "mahendra singh dhoni",
    "kl rahul": "lokesh rahul",
    "tilak varma": "namboori tilak varma",
    "shahrukh khan": "m shahrukh khan",
    "nitish kumar reddy": "nitish reddy",
    "pat cummins": "patrick cummins",
    "varun chakaravarthy": "varun chakravarthy",
    "vyshak vijaykumar": "vyshak kumar",
    "zak foulkes": "zakary foulkes",
    "will jacks": "william jacks",
    "auqib dar": "auqib nabi",
}


# ---------------------------------------------------------------- files
def _read(path: Path, required: list[str], what: str) -> pd.DataFrame:
    if not path.exists():
        raise CRICQError(f"{what} not found: {path}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise CRICQError(f"{path.name} is missing column(s): {', '.join(miss)}")
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


def load_status(path) -> pd.DataFrame:
    df = _read(Path(path), STATUS_COLUMNS, "Player status file")
    bad = sorted(set(df.status) - set(STATUSES))
    if bad:
        raise CRICQError(f"{Path(path).name}: unknown status value(s) {bad}. Allowed: {', '.join(sorted(STATUSES))}")
    dup = df.player[df.player.duplicated()].tolist()
    if dup:
        raise CRICQError(f"{Path(path).name}: players listed twice: {dup}")
    for c in ("team_2027", "nationality", "last_fee_cr"):
        if c not in df.columns:
            df[c] = ""
    return df


def load_reports(path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=REPORT_COLUMNS)
    df = _read(p, REPORT_COLUMNS, "Retention reports file")
    bad = sorted(set(df.verdict) - {"retain", "release"})
    if bad:
        raise CRICQError(f"{p.name}: verdict must be retain or release (got {bad})")
    badk = sorted(set(df.kind) - set(KIND_WEIGHT))
    if badk:
        raise CRICQError(f"{p.name}: kind must be one of {', '.join(KIND_WEIGHT)} (got {badk})")
    return df


def load_rr_squad(path) -> pd.DataFrame:
    df = _read(Path(path), ["player", "overseas", "fee_cr", "covers", "projection"], "RR squad file")
    bad = sorted(set(df.projection) - {"retain", "release", "review"})
    if bad:
        raise CRICQError(f"{Path(path).name}: projection must be retain, release or review (got {bad})")
    df["overseas"] = df.overseas.str.lower().isin(["yes", "y", "true", "1"])
    try:
        df["fee_cr"] = df.fee_cr.astype(float)
    except ValueError as e:
        raise CRICQError(f"{Path(path).name}: fee_cr must be a number in crore ({e})") from None
    df["covers"] = df.covers.str.split(";").map(lambda x: [s.strip() for s in x if s.strip()])
    for c in ("reason", "source"):
        if c not in df.columns:
            df[c] = ""
    return df


# ---------------------------------------------------------------- names
def _tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    return re.sub(r"[^a-z ]", " ", s).split()


def resolve_names(names, directory: pd.DataFrame, prefer: set | None = None) -> dict:
    """Map names written by journalists to Data Pack display names.

    Tries, in order: exact name, normalised name, known aliases, all-words match, first-initial + surname.
    When several players match, players in `prefer` (e.g. IPL 2026 squads) win; still-ambiguous names stay unresolved.
    """
    prefer = prefer or set()
    disp = directory.display_name.astype(str).tolist()
    norm = {d: " ".join(_tokens(d)) for d in disp}
    by_norm: dict[str, list[str]] = {}
    for d, n in norm.items():
        by_norm.setdefault(n, []).append(d)
    toks = {d: set(n.split()) for d, n in norm.items()}

    def pick(c):
        c = list(dict.fromkeys(c))
        if len(c) == 1:
            return c[0]
        p = [x for x in c if x in prefer]
        return p[0] if len(p) == 1 else None

    out = {}
    for raw in dict.fromkeys(names):
        if raw in norm:
            out[raw] = raw
            continue
        n = " ".join(_tokens(raw))
        n = ALIASES.get(n, n)
        hit = pick(by_norm.get(n, []))
        if hit is None:
            t = set(n.split())
            hit = pick([d for d, dt in toks.items() if t and t <= dt])
        if hit is None and len(n.split()) >= 2:
            first, last = n.split()[0], n.split()[-1]
            # only for initials ("M Shahrukh Khan" ↔ "Shahrukh Khan", "T Natarajan" ↔ "Thangarasu Natarajan")
            hit = pick(
                [
                    d
                    for d, dt in toks.items()
                    if last in dt
                    and (len(first) == 1 or any(len(x) == 1 for x in norm[d].split()[:1]))
                    and any(x.startswith(first[0]) for x in dt - {last})
                ]
            )
        out[raw] = hit
    return out


# ---------------------------------------------------------------- consensus
def playing_prior(games, team_games) -> tuple[float, str]:
    """Selector common sense: franchises keep the players they actually pick."""
    if not team_games or pd.isna(team_games) or team_games <= 0:
        return 0.0, ""
    share = games / team_games
    if share >= 0.6:
        return -1.5, f"regular: played {int(games)} of {int(team_games)} games in 2026"
    if share >= 0.3:
        return -0.5, f"rotation: played {int(games)} of {int(team_games)} games in 2026"
    if games > 0:
        return 0.4, f"fringe: played {int(games)} of {int(team_games)} games in 2026"
    return 0.8, f"did not play in 2026 ({int(team_games)} team games)"


def consensus(reports: pd.DataFrame) -> pd.DataFrame:
    """Per resolved player: weighted evidence and a readable vote summary (each outlet counted once)."""
    if not len(reports):
        return pd.DataFrame(columns=["display_name", "news_evidence", "n_release", "n_retain", "votes"])
    r = reports.dropna(subset=["display_name"]).copy()
    r["w"] = r.kind.map(KIND_WEIGHT)
    r["v"] = r.verdict.map({"release": 1, "retain": -1})
    r = r.sort_values("date").drop_duplicates(["display_name", "source"], keep="last")
    g = r.groupby("display_name")
    out = pd.DataFrame(
        {
            "news_evidence": g.apply(lambda x: float((x.w * x.v).sum()), include_groups=False),
            "n_release": g.v.apply(lambda v: int((v > 0).sum())),
            "n_retain": g.v.apply(lambda v: int((v < 0).sum())),
            "votes": g.apply(
                lambda x: "; ".join(f"{s} → {v}" for s, v in zip(x.source, x.verdict, strict=True)),
                include_groups=False,
            ),
            "first_url": g.url.last(),
            "latest_date": g.date.max(),
        }
    ).reset_index()
    return out


def p_release(evidence: float, baseline: float = -0.4) -> float:
    return 1.0 / (1.0 + math.exp(-(baseline + evidence)))


def status_from_p(p: float) -> str:
    if p >= 0.70:
        return "likely_released"
    if p >= 0.40:
        return "possible_release"
    if p >= 0.15:
        return "under_contract"
    return "likely_retained"


# ---------------------------------------------------------------- apply
def apply(
    t: pd.DataFrame,
    status: pd.DataFrame,
    rr_squad: pd.DataFrame,
    cfg: dict,
    reports: pd.DataFrame | None = None,
    directory: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Add availability columns to a player table.

    `t` needs display_name, country, ipl_team_latest, ipl_team_any, last_season (or last_any) and (optional)
    ipl26_games / ipl26_team_games. `directory` (all players) is used to resolve names in the files.
    """
    t = t.copy()
    a = cfg.get("auction", {})
    prob = a.get("availability_prob", {})
    active = cfg.get("eligibility", {}).get("active_since")
    directory = t if directory is None else directory
    squads = set(directory.loc[directory.ipl_team_latest.notna(), "display_name"])

    st = status.copy()
    st["display_name"] = st.player.map(resolve_names(st.player, directory, squads)).fillna(st.player)
    st = st.drop_duplicates("display_name").set_index("display_name")
    rr = rr_squad.copy()
    rr["display_name"] = rr.player.map(resolve_names(rr.player, directory, squads)).fillna(rr.player)
    rr = rr.set_index("display_name")
    cons = pd.DataFrame()
    if reports is not None and len(reports):
        rp = reports.copy()
        rp["display_name"] = rp.player.map(resolve_names(rp.player, directory, squads))
        cons = consensus(rp).set_index("display_name")
    games = t.get("ipl26_games", pd.Series(0, index=t.index))
    tgames = t.get("ipl26_team_games", pd.Series(float("nan"), index=t.index))
    latest_season = int(pd.to_numeric(t.get("last_season"), errors="coerce").max() or 0)

    def one(i, r):
        n = r.display_name
        if n in st.index:
            s = st.loc[n]
            return (
                s.status,
                s.team_2027 or r.ipl_team_latest,
                s.note,
                s.source,
                s.source_date,
                s.nationality,
                None,
                "",
            )
        if n in rr.index:
            x = rr.loc[n]
            return (
                "rr_squad",
                RR,
                f"RR projection: {x.projection} — {x.reason}",
                x.source,
                a.get("as_of", ""),
                "",
                None,
                "",
            )
        if r.country == "Pakistan":
            return ("ineligible", "", "Pakistan players have not played in the IPL since 2008", "", "", "", None, "")
        last = r.get("last_any", r.last_season)
        last = last if pd.notna(last) else 0
        if active and last < int(active):
            return (
                "inactive",
                "",
                f"Last match in this data: {int(last) if last else 'unknown'}",
                "",
                "",
                "",
                None,
                "",
            )
        if pd.notna(r.ipl_team_latest):
            prior, why = playing_prior(games[i], tgames[i])
            ev, votes, url, date = 0.0, "", "", ""
            if n in cons.index:
                c = cons.loc[n]
                ev, votes, url, date = c.news_evidence, c.votes, c.first_url, c.latest_date
            p = p_release(prior + ev)
            s = status_from_p(p)
            note = "; ".join(x for x in (why, votes and f"news: {votes}") if x)
            return (s, r.ipl_team_latest, note, url, date, "", p, votes)
        if r.country == "Bangladesh":
            return (
                "risk",
                "",
                "Bangladesh player: the BCCI had KKR release Mustafizur Rahman in 2026, so selection carries risk",
                "https://wisden.com/series/ipl-2026/cricket-news/explained-why-the-kolkata-knight-riders-were-instructed-to-exclude-mustafizur-rahman-from-their-ipl-2026-squad",
                "2026-01-03",
                "",
                None,
                "",
            )
        if pd.notna(r.ipl_team_any):
            return (
                "free_agent",
                "",
                f"Played for {r.ipl_team_any}; not on a {latest_season} squad",
                "",
                "",
                "",
                None,
                "",
            )
        return ("not_in_ipl", "", "No IPL matches 2022–26; must register for the auction", "", "", "", None, "")

    vals = pd.DataFrame([one(i, r) for i, r in t.iterrows()], index=t.index)
    vals.columns = [
        "status",
        "team_2027",
        "status_note",
        "status_source",
        "status_date",
        "nat_override",
        "p_rel",
        "news_votes",
    ]
    for c in vals.columns:
        t[c] = vals[c]
    t["status_label"] = t.status.map(lambda s: STATUSES[s][0])
    t["selectable"] = t.status.map(lambda s: STATUSES[s][1])
    t["in_pool"] = t.status.isin(AUCTION_POOL)
    nat = t.nat_override.where(t.nat_override.astype(bool), t.country)
    t["nationality"] = nat
    t["overseas"] = nat.notna() & (nat != "India")
    is_rr = t.display_name.isin(rr.index)
    t.loc[is_rr, "overseas"] = t.loc[is_rr, "display_name"].map(rr.overseas).astype(bool)
    base = t.status.map(lambda s: float(prob.get(s, 0.0)))
    t["avail_prob"] = t.p_rel.astype(float).where(t.p_rel.notna(), base).round(3)
    t.loc[t.status == "rr_squad", "avail_prob"] = 0.0
    return t.drop(columns=["nat_override", "p_rel"])


def unresolved(names, directory, prefer=None) -> list[str]:
    m = resolve_names(names, directory, prefer)
    return sorted(k for k, v in m.items() if v is None)
