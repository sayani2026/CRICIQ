"""Write submission/UNSTOP_ENTRY.md from the current rankings (run after pipeline.py)."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
b = pd.read_csv(OUT / "top10_batters.csv")
w = pd.read_csv(OUT / "top10_bowlers.csv")


def check(t, what):
    """The brief: ranks 1-10 in order, no player repeated within a list."""
    assert len(t) == 10, f"{what}: expected 10 players, got {len(t)}"
    assert t["rank"].astype(int).tolist() == list(range(1, 11)), f"{what}: ranks are not 1-10 in order"
    assert t.display_name.is_unique, f"{what}: a player is repeated"


def rows(t):
    return [
        f"| {int(r['rank'])} | {r.display_name} | {r.team_label} | {r.clutch_score:.1f} | "
        f"{r.score_lo:.0f}–{r.score_hi:.0f} | {int(r.get('top10_in_variants', 0))}/10 |"
        for _, r in t.iterrows()
    ]


check(b, "Batters")
check(w, "Bowlers")
hdr = ["| Rank | Player | Team | CRICQ Score | 90% range | Top-10 in tests |", "|---|---|---|---|---|---|"]
lines = [
    "# Unstop entry sheet — SupeRR Selector Season 2, Round 1",
    "",
    "Round 1 asks for *the 10 best-performing batters under pressure and the 10 best-performing bowlers under pressure*,",
    "selected in rank order (1 to 10) in the Unstop dropdowns, with no player repeated, matching the methodology report.",
    "",
    "These lists come only from the supplied Data Pack (IPL + T20I, 2022 onwards). Players need 150 pressure balls and",
    "12 pressure matches to be ranked. Retired players and players with no match since 2024 are not ranked.",
    "",
    "## Top 10 batters under pressure",
    "",
    *hdr,
    *rows(b),
    "",
    "## Top 10 bowlers under pressure",
    "",
    *hdr,
    *rows(w),
    "",
    "## Checklist",
    "",
    "- [ ] Batters Rank 1–10 entered in exactly this order",
    "- [ ] Bowlers Rank 1–10 entered in exactly this order",
    "- [ ] No player repeated within a list (checked automatically when this sheet was written)",
    "- [ ] Report uploaded: report/CRICQ_Methodology_Report.pdf (put your name on the cover: build_report.bat)",
    "- [ ] Names match Unstop's spelling (e.g. 'Namboori Tilak Varma' may appear as 'Tilak Varma')",
    "",
]
(ROOT / "submission").mkdir(exist_ok=True)
(ROOT / "submission" / "UNSTOP_ENTRY.md").write_text("\n".join(lines), encoding="utf-8")
print("Wrote submission/UNSTOP_ENTRY.md")
