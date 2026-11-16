"""Build the CRICQ methodology report (PDF) from pipeline outputs.

python report/build_report.py            ->  report/CRICQ_Methodology_Report.pdf
"""

import json
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
PROC = ROOT / "data" / "processed"
FIG = ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
AUTHOR = sys.argv[1] if len(sys.argv) > 1 else "[Your name / team name]"

NAVY, INK2, GRID = "#14213D", "#4A5675", "#E6E8EF"
PINK, BLUE, GREY = "#14C4A3", "#2F6FD0", "#B9C0D0"  # Royals pink (pressure), blue (normal)
ROYAL, GOLD = "#6D5BD0", "#F4C150"
PINK_RAMP = ["#FDEDF5", "#F9C6DF", "#F296C3", "#EE5BA3", "#14C4A3", "#B0105F", "#6E0A3B"]

# ---------------- fonts ----------------
FONT_DIRS = [Path("/usr/share/fonts/truetype"), Path("C:/Windows/Fonts"), Path("/Library/Fonts")]


def _find(name):
    for d in FONT_DIRS:
        for p in d.rglob(name) if d.exists() else []:
            return p
    return None


BODY, BODY_B, HEAD = "Helvetica", "Helvetica-Bold", "Helvetica-Bold"
for nm, fn in [
    ("Body", "LiberationSans-Regular.ttf"),
    ("Body-B", "LiberationSans-Bold.ttf"),
    ("Body-I", "LiberationSans-Italic.ttf"),
    ("Head", "Poppins-SemiBold.ttf"),
    ("Head2", "Poppins-Bold.ttf"),
]:
    p = _find(fn)
    if p:
        pdfmetrics.registerFont(TTFont(nm, str(p)))
if "Body" in pdfmetrics.getRegisteredFontNames():
    BODY, BODY_B = "Body", "Body-B"
    pdfmetrics.registerFontFamily(
        "Body",
        normal="Body",
        bold="Body-B",
        italic="Body-I" if _find("LiberationSans-Italic.ttf") else "Body",
        boldItalic="Body-B",
    )
if "Head" in pdfmetrics.getRegisteredFontNames():
    HEAD = "Head"
elif "Head2" in pdfmetrics.getRegisteredFontNames():
    HEAD = "Head2"
mpl_font = _find("LiberationSans-Regular.ttf")
if mpl_font:
    font_manager.fontManager.addfont(str(mpl_font))
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(mpl_font)).get_name()
plt.rcParams.update(
    {
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.titlecolor": NAVY,
    }
)

# ---------------- styles ----------------
S = {
    "title": ParagraphStyle("title", fontName=HEAD, fontSize=30, leading=36, textColor=colors.HexColor(NAVY)),
    "sub": ParagraphStyle("sub", fontName=BODY, fontSize=13, leading=18, textColor=colors.HexColor(INK2)),
    "h1": ParagraphStyle(
        "h1", fontName=HEAD, fontSize=17, leading=22, textColor=colors.HexColor(NAVY), spaceBefore=4, spaceAfter=8
    ),
    "h2": ParagraphStyle(
        "h2", fontName=HEAD, fontSize=12, leading=16, textColor=colors.HexColor(NAVY), spaceBefore=10, spaceAfter=4
    ),
    "body": ParagraphStyle(
        "body",
        fontName=BODY,
        fontSize=9.6,
        leading=14,
        textColor=colors.HexColor(NAVY),
        spaceAfter=6,
        alignment=TA_LEFT,
    ),
    "small": ParagraphStyle(
        "small", fontName=BODY, fontSize=8, leading=11, textColor=colors.HexColor(INK2), spaceAfter=4
    ),
    "cell": ParagraphStyle("cell", fontName=BODY, fontSize=7.8, leading=10, textColor=colors.HexColor(NAVY)),
    "cellb": ParagraphStyle("cellb", fontName=BODY_B, fontSize=7.8, leading=10, textColor=colors.HexColor(NAVY)),
    "callout": ParagraphStyle(
        "callout",
        fontName=BODY,
        fontSize=9.6,
        leading=14,
        textColor=colors.HexColor(NAVY),
        backColor=colors.HexColor("#F4F5F9"),
        borderPadding=(8, 10, 8, 10),
        spaceBefore=6,
        spaceAfter=12,
    ),
}


def P(t, s="body"):
    return Paragraph(t, S[s])


def bullets(items):
    return [P(f"&bull;&nbsp; {t}") for t in items]


def table(rows, widths, header=True, zebra=True, align_right_from=None):
    data = [
        [c if isinstance(c, Paragraph) else Paragraph(str(c), S["cellb" if (header and i == 0) else "cell"]) for c in r]
        for i, r in enumerate(rows)
    ]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(NAVY)),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F6F7FA")))
    t.setStyle(TableStyle(st))
    return t


def fig_img(path, width_mm):
    from PIL import Image as PImage

    w, h = PImage.open(path).size
    wd = width_mm * mm
    return Image(str(path), width=wd, height=wd * h / w)


def save(fig, name):
    p = FIG / f"{name}.png"
    fig.savefig(p, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p


# ---------------- data ----------------
with open(OUT / "model_report.json", encoding="utf-8") as fh:
    rep = json.load(fh)
bat = pd.read_csv(OUT / "batting_scores.csv")
bowl = pd.read_csv(OUT / "bowling_scores.csv")
sens = pd.read_csv(OUT / "sensitivity.csv") if (OUT / "sensitivity.csv").exists() else pd.DataFrame()
rpt = pd.read_csv(OUT / "repeatability.csv")
pchk = pd.read_csv(OUT / "predictive_check.csv")
ksel = pd.read_csv(OUT / "anchor_k_selection.csv")
cal = pd.read_csv(OUT / "wp_calibration.csv")
dec = pd.read_csv(OUT / "pressure_by_decile.csv")
phase = pd.read_csv(OUT / "pressure_by_phase.csv")
dq = pd.read_csv(OUT / "data_quality.csv")
balls = pd.read_parquet(
    PROC / "balls.parquet",
    columns=[
        "match_id",
        "innings",
        "innings_ball_num",
        "over",
        "wkts_before",
        "pressure_index",
        "high_pressure",
        "wp",
        "legal_before",
        "wkt",
        "batting_team",
        "striker_name",
        "bowler_name",
        "ball_label",
    ],
)
tb = bat[bat["rank"].notna()].sort_values("rank")
tw = bowl[bowl["rank"].notna()].sort_values("rank")
top_b, top_w = tb.head(10), tw.head(10)
d = rep["data"]
pr = rep["pressure"]
sc = rep["scoring"]
wpv = pd.DataFrame(rep["win_probability"])
mov = {r["innings"]: r for r in pr["wp_movement"]}
nvar = rep.get("n_sensitivity_variants", 10)

# ---------------- figures ----------------
# F1 heatmap
ch = balls[balls.innings == 2]
h = (
    ch.groupby([ch.over, ch.wkts_before.clip(upper=7)])
    .agg(pi=("pressure_index", "mean"), n=("pressure_index", "size"))
    .reset_index()
)
h.loc[h.n < 100, "pi"] = np.nan
z = h.pivot(index="wkts_before", columns="over", values="pi").reindex(range(8))
fig, ax = plt.subplots(figsize=(6.6, 2.7))

cmap = LinearSegmentedColormap.from_list("p", PINK_RAMP)
cmap.set_bad("white")
im = ax.imshow(np.ma.masked_invalid(z.values), aspect="auto", cmap=cmap, vmin=20, vmax=80, origin="lower")
ax.set_xticks(range(20))
ax.set_xticklabels(range(1, 21))
ax.set_yticks(range(8))
ax.set_yticklabels(["0", "1", "2", "3", "4", "5", "6", "7+"])
ax.set_xlabel("Over of the chase")
ax.set_ylabel("Wickets down")
ax.grid(False)
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("Mean Pressure Index", color=INK2)
cb.outline.set_visible(False)
ax.set_title("Where pressure lives in a chase (blank = fewer than 100 balls)", loc="left")
f_heat = save(fig, "f1_pressure_heatmap")

# F2 movement + phase
fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.5))
labs = ["Setting a total", "Chasing"]
x = np.arange(2)
axs[0].bar(
    x - 0.18, [mov[1]["share_of_balls_pct"], mov[2]["share_of_balls_pct"]], 0.34, color=GREY, label="Share of balls"
)
axs[0].bar(
    x + 0.18,
    [mov[1]["share_of_wp_movement_pct"], mov[2]["share_of_wp_movement_pct"]],
    0.34,
    color=PINK,
    label="Share of win-probability swing",
)
for i, (a, b_) in enumerate(
    [
        (mov[1]["share_of_balls_pct"], mov[1]["share_of_wp_movement_pct"]),
        (mov[2]["share_of_balls_pct"], mov[2]["share_of_wp_movement_pct"]),
    ]
):
    axs[0].text(i - 0.18, a + 1, f"{a:.0f}%", ha="center", fontsize=8, color=NAVY)
    axs[0].text(i + 0.18, b_ + 1, f"{b_:.0f}%", ha="center", fontsize=8, color=NAVY)
axs[0].set_xticks(x)
axs[0].set_xticklabels(labs)
axs[0].set_ylim(0, 70)
axs[0].set_ylabel("%")
axs[0].legend(frameon=False, fontsize=7.5, loc="upper left")
axs[0].set_title("High-pressure balls decide matches", loc="left")
ph = phase.copy()
order = ["Powerplay", "Middle", "Death"]
for j, (inn, col, lab) in enumerate([(1, BLUE, "Setting"), (2, PINK, "Chasing")]):
    q = ph[ph.innings == inn].set_index("phase").reindex(order)
    axs[1].bar(np.arange(3) + (j - 0.5) * 0.36, q.high_share, 0.34, color=col, label=lab)
axs[1].set_xticks(range(3))
axs[1].set_xticklabels(order)
axs[1].set_ylabel("% of balls high pressure")
axs[1].legend(frameon=False, fontsize=7.5)
axs[1].set_title("High-pressure share by phase", loc="left")
fig.tight_layout()
f_move = save(fig, "f2_pressure_evidence")

# F3 calibration
fig, ax = plt.subplots(figsize=(3.4, 2.9))
ax.plot([0, 1], [0, 1], ls=":", color="#7A869F", lw=1, label="Perfect")
for inn, col, lab in [(1, BLUE, "Setting a total"), (2, PINK, "Chasing")]:
    q = cal[cal.innings == inn]
    ax.plot(q.pred, q.obs, "-o", color=col, ms=4, lw=1.8, label=lab)
ax.set_xlabel("Predicted win chance")
ax.set_ylabel("Actual win rate (2025-26)")
ax.legend(frameon=False, fontsize=7.5)
ax.set_title("Win-probability calibration", loc="left")
f_cal = save(fig, "f3_calibration")

# F4 match example
m_id = 31250 if 31250 in set(balls.match_id) else balls.groupby("match_id").pressure_index.max().idxmax()
xm = balls[balls.match_id == m_id].sort_values(["innings", "innings_ball_num"]).copy()
chaser = xm[xm.innings == 2].batting_team.iloc[0]
xm["wpc"] = np.where(xm.innings == 2, xm.wp, 1 - xm.wp)
xm["xpos"] = (xm.innings - 1) * 20 + xm.legal_before / 6
fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.0, 3.1), sharex=True, gridspec_kw=dict(height_ratios=[3, 1], hspace=0.08))
a1.plot(xm.xpos, xm.wpc, color=PINK, lw=1.8)
w = xm[xm.wkt == 1]
a1.scatter(w.xpos, w.wpc, s=22, facecolor="white", edgecolor=NAVY, zorder=3, lw=1.2)
a1.axhline(0.5, ls=":", color="#7A869F", lw=0.8)
a1.axvline(20, color=GRID)
a1.set_ylim(0, 1)
a1.set_yticks([0, 0.25, 0.5, 0.75, 1])
a1.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
a1.set_ylabel(f"{chaser.split()[0]} win %")
a1.set_title("Example: KKR 223/6 v RR 224/8, IPL 2024 — win chance and pressure, ball by ball", loc="left")
a2.bar(xm.xpos, xm.pressure_index, width=0.17, color=np.where(xm.high_pressure == 1, PINK, "#C9CEDB"))
a2.set_ylim(0, 100)
a2.set_ylabel("Pressure")
a2.axvline(20, color=GRID)
a2.set_xticks([0, 5, 10, 15, 20, 25, 30, 35, 40])
a2.set_xticklabels(["0", "5", "10", "15", "20 | 0", "5", "10", "15", "20"])
a2.set_xlabel("Overs: KKR batting | RR chasing")
f_match = save(fig, "f4_match_example")


def ci_plot(t, name, title):
    t = t.iloc[::-1]
    fig, ax = plt.subplots(figsize=(3.5, 3.4))
    y = np.arange(len(t))
    ax.hlines(y, t.score_lo, t.score_hi, color="#C9CEDB", lw=5)
    ax.scatter(t.clutch_score, y, color=PINK, s=34, zorder=3, edgecolor="white", lw=1)
    ax.set_yticks(y)
    ax.set_yticklabels(t.display_name, fontsize=7.6)
    ax.axvline(50, ls=":", color="#7A869F", lw=0.8)
    ax.set_xlabel("CRICQ Score (90% range)")
    ax.set_title(title, loc="left")
    ax.grid(axis="y", visible=False)
    return save(fig, name)


f_cib = ci_plot(top_b, "f5_ci_batters", "Top-10 batters")
f_ciw = ci_plot(top_w, "f6_ci_bowlers", "Top-10 bowlers")


def dumbbell(t, a, b, name, title, xlabel):
    t = t.iloc[::-1]
    fig, ax = plt.subplots(figsize=(3.5, 3.4))
    y = np.arange(len(t))
    ax.hlines(y, t[a], t[b], color="#C9CEDB", lw=2)
    ax.scatter(t[a], y, color=BLUE, s=26, zorder=3, label="Normal")
    ax.scatter(t[b], y, color=PINK, s=26, zorder=3, label="Pressure")
    ax.set_yticks(y)
    ax.set_yticklabels(t.display_name, fontsize=7.6)
    ax.set_xlabel(xlabel)
    ax.legend(frameon=False, fontsize=7, loc="lower right")
    ax.set_title(title, loc="left")
    ax.grid(axis="y", visible=False)
    return save(fig, name)


f_db = dumbbell(top_b, "n_sr", "p_sr", "f7_bat_sr", "Strike rate: normal vs pressure", "Strike rate")
f_dw = dumbbell(top_w, "n_econ", "p_econ", "f8_bowl_econ", "Economy: normal vs pressure", "Runs per over")

# F9 reliability
fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.5))
for j, (role, _label) in enumerate([("bat", "Batters"), ("bowl", "Bowlers")]):
    q = rpt[rpt.role == role]
    axs[0].bar(
        j - 0.18,
        q[q.split.str.startswith("odd")].correlation.iloc[0],
        0.34,
        color=BLUE,
        label="Odd vs even matches" if j == 0 else None,
    )
    axs[0].bar(
        j + 0.18,
        q[q.split.str.startswith("2022")].correlation.iloc[0],
        0.34,
        color=PINK,
        label="2022-24 vs 2025-26" if j == 0 else None,
    )
axs[0].axhline(0, color="#7A869F", lw=0.8)
axs[0].set_xticks([0, 1])
axs[0].set_xticklabels(["Batters", "Bowlers"])
axs[0].set_ylabel("Correlation")
axs[0].legend(frameon=False, fontsize=7)
axs[0].set_title("Does pressure value repeat?", loc="left")
for j, (role, _label) in enumerate([("bat", "Batters"), ("bowl", "Bowlers")]):
    q = pchk[pchk.role == role].reset_index(drop=True)
    for i, (col, ll) in enumerate([(GREY, "Simple pressure stat"), (BLUE, "Quality part"), (PINK, "CRICQ Score")]):
        axs[1].bar(j + (i - 1) * 0.26, q.correlation.iloc[i], 0.24, color=col, label=ll if j == 0 else None)
axs[1].axhline(0, color="#7A869F", lw=0.8)
axs[1].set_xticks([0, 1])
axs[1].set_xticklabels(["Batters", "Bowlers"])
axs[1].legend(frameon=False, fontsize=7)
axs[1].set_title("2022-24 rating vs 2025-26 pressure value", loc="left")
fig.tight_layout()
f_rel = save(fig, "f9_reliability")


# ---------------- document ----------------
def on_page(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont(BODY, 7.5)
        canvas.setFillColor(colors.HexColor(INK2))
        canvas.drawString(
            18 * mm, 10 * mm, "CRICQ · Most Reliable Players Under Pressure · SupeRR Selector Season 2"
        )
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        y = A4[1] - 12 * mm
        for x0, x1, c in [(18, 32, PINK), (32, 38, ROYAL), (38, 41, GOLD)]:
            canvas.setStrokeColor(colors.HexColor(c))
            canvas.setLineWidth(1.6)
            canvas.line(x0 * mm, y, x1 * mm, y)
    canvas.restoreState()


doc = SimpleDocTemplate(
    str(ROOT / "report" / "CRICQ_Methodology_Report.pdf"),
    pagesize=A4,
    leftMargin=18 * mm,
    rightMargin=18 * mm,
    topMargin=17 * mm,
    bottomMargin=17 * mm,
    title="CRICQ — Most Reliable Players Under Pressure",
    author=AUTHOR,
    subject="SupeRR Selector Season 2 · Round 1 methodology report",
)
W = A4[0] - 36 * mm
st = []


# ---- cover ----
def kit_band():
    t = Table([["", "", ""]], colWidths=[W * 0.62, W * 0.26, W * 0.12], rowHeights=[3 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(PINK)),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(ROYAL)),
                ("BACKGROUND", (2, 0), (2, 0), colors.HexColor(GOLD)),
            ]
        )
    )
    return t


st += [
    kit_band(),
    Spacer(1, 37 * mm),
    P("CRIC<font color='#14C4A3'>Q</font>", "title"),
    Spacer(1, 4),
    P("Identifying the most reliable players under pressure", "sub"),
    Spacer(1, 3),
    P("SupeRR Selector Season 2 · Round 1 · Methodology report", "sub"),
    Spacer(1, 18 * mm),
]
cover = [
    [
        "Data",
        f"{d['matches_with_balls']} matches ({d['ipl_matches']} IPL, {d['t20i_matches']} T20I, {d.get('other_matches', 0)} other T20) · "
        f"{d['balls']:,} deliveries · {d['first_date']} to {d['last_date']}",
    ],
    [
        "Pressure",
        f"Pressure Index (0-100) on every ball; top {100 - pr['high_pressure_threshold_pct']}% = high pressure",
    ],
    [
        "Players ranked",
        f"{int(tb.shape[0])} batters and {int(tw.shape[0])} bowlers with enough pressure evidence "
        "(retired players and players with no match since 2024 excluded)",
    ],
    ["Prepared by", AUTHOR],
    ["Date", date.today().strftime("%d %B %Y")],
]
st.append(
    table(
        [[P(f"<b>{a}</b>", "cell"), P(b_, "cell")] for a, b_ in cover],
        [35 * mm, W - 35 * mm],
        header=False,
        zebra=False,
    )
)
st.append(Spacer(1, 60 * mm))
st.append(
    P(
        "Independent project prepared for the SupeRR Selector Season 2 competition. Not affiliated with or endorsed by "
        "Rajasthan Royals, the IPL or the BCCI. All figures are reproducible from the supplied Data Pack with the accompanying code.",
        "small",
    )
)
st.append(PageBreak())

# ---- 1. summary ----
st.append(P("1. Summary", "h1"))
st.append(
    P(
        "CRICQ rates the pressure on every ball of IPL and T20I cricket since January 2022, measures what each player added on the "
        "highest-pressure balls compared with an average player in exactly the same situation, and ranks players on the quality, lift and "
        "consistency of that pressure performance — with small samples pulled toward the average and every rank given a confidence range. "
        "The two lists below are the 10 best-performing batters and bowlers under pressure in the supplied data, as the Round 1 brief "
        "asks. Rankings rest only on the Data Pack; the one exclusion is players who have retired or not played since 2024, because "
        "the ratings are meant to inform future selection. Section 8 is an optional extra showing how Rajasthan Royals could apply "
        "the same scores at the IPL 2027 auction; it does not change the rankings."
    )
)
st.append(P("Final rankings", "h2"))


def rank_rows(t, role):
    if role == "bat":
        rows = [
            [
                "#",
                "Player",
                "Team",
                "Clutch (90% range)",
                "Pressure balls",
                "SR press. / normal",
                "Balls per dismissal press. / normal",
                "Top-10 in tests",
            ]
        ]
        for _, r in t.iterrows():
            rows.append(
                [
                    int(r["rank"]),
                    r.display_name,
                    r.team_label,
                    f"{r.clutch_score:.1f} ({r.score_lo:.0f}-{r.score_hi:.0f})",
                    int(r.p_balls),
                    f"{r.p_sr:.0f} / {r.n_sr:.0f}",
                    f"{r.p_bpd:.0f} / {r.n_bpd:.0f}",
                    f"{int(r.get('top10_in_variants', 0))}/{nvar}",
                ]
            )
        wd = [7 * mm, 33 * mm, 33 * mm, 25 * mm, 16 * mm, 20 * mm, 22 * mm, W - 156 * mm]
    else:
        rows = [
            [
                "#",
                "Player",
                "Team",
                "Clutch (90% range)",
                "Pressure balls",
                "Econ. press. / normal",
                "Wkts (press.)",
                "Top-10 in tests",
            ]
        ]
        for _, r in t.iterrows():
            rows.append(
                [
                    int(r["rank"]),
                    r.display_name,
                    r.team_label,
                    f"{r.clutch_score:.1f} ({r.score_lo:.0f}-{r.score_hi:.0f})",
                    int(r.p_balls),
                    f"{r.p_econ:.2f} / {r.n_econ:.2f}",
                    int(r.p_wkts),
                    f"{int(r.get('top10_in_variants', 0))}/{nvar}",
                ]
            )
        wd = [7 * mm, 33 * mm, 33 * mm, 25 * mm, 16 * mm, 22 * mm, 18 * mm, W - 154 * mm]
    return rows, wd


r_, w_ = rank_rows(top_b, "bat")
st += [P("<b>Top 10 batters under pressure</b>", "body"), table(r_, w_), Spacer(1, 8)]
r_, w_ = rank_rows(top_w, "bowl")
st += [P("<b>Top 10 bowlers under pressure</b>", "body"), table(r_, w_), Spacer(1, 6)]
st.append(
    P(
        "Team = 2026 IPL franchise, otherwise national side. Retired players and players with no match since 2024 are not ranked. "
        "'Top-10 in tests' = number of "
        f"{nvar} alternative set-ups (different cut-offs, weights and eligibility rules) in which the player still made the top 10.",
        "small",
    )
)
st.append(P("Key findings", "h2"))
pcb = pchk[pchk.role == "bowl"].set_index("method").correlation
rb = rpt.set_index(["role", "split"]).correlation
st += bullets(
    [
        f"<b>Pressure is concentrated.</b> In chases, the {mov[2]['share_of_balls_pct']:.0f}% of balls flagged high pressure carry "
        f"{mov[2]['share_of_wp_movement_pct']:.0f}% of all movement in win probability ({mov[1]['share_of_wp_movement_pct']:.0f}% when setting a total).",
        "<b>Death overs of close games carry the most pressure,</b> but early collapses in a chase are also high-pressure moments.",
        f"<b>Bowling under pressure is a lasting skill.</b> A bowler's pressure value in 2022-24 correlates "
        f"{rb[('bowl', '2022-24 vs 2025-26')]:.2f} with 2025-26; for batters it is {rb[('bat', '2022-24 vs 2025-26')]:.2f}.",
        "<b>Batting under pressure is noisy.</b> Among established batters, pressure form swings a lot season to season, so batting "
        "ratings lean on overall quality and consistency, and batting ranks 6-10 should be read as near-equals.",
        f"<b>Robustness:</b> {int((top_b.head(5).get('top10_in_variants', 0) >= nvar).sum())} of the top five batters and "
        f"{int((top_w.head(5).get('top10_in_variants', 0) >= nvar).sum())} of the top five bowlers stay in the top 10 under every "
        "alternative set-up tested; lower ranks are closer calls.",
    ]
)
st.append(Spacer(1, 10))

# ---- 2. data ----
st.append(P("2. Data and preparation", "h1"))
st.append(
    P(
        f"All six Data Pack files were joined on match, competition, team and player IDs: {d['balls']:,} deliveries from "
        f"{d['matches_with_balls']} matches across {d['venues']} venues. Every quality issue found and the decision taken is listed below. "
        f"The live scoreboard was rebuilt for every ball (score, wickets, legal balls, target, runs needed) and checked against the "
        f"official result: {rep['reconciliation']['matching']} of {rep['reconciliation']['matches_checked']} matches agree "
        f"({rep['reconciliation']['match_rate_pct']}%)."
    )
)
rows = [["Check", "Finding", "Decision"]] + dq[["check", "finding", "decision"]].values.tolist()
st.append(table(rows, [38 * mm, 62 * mm, W - 100 * mm]))
st.append(PageBreak())

# ---- 3. pressure ----
st.append(P("3. Pressure definition", "h1"))
st.append(
    P(
        "Pressure is the combination of <b>what is at stake</b> on a ball and <b>how hard the scoreboard makes it</b>. "
        "Either alone misses something: a desperate chase can be nearly lost (low stakes) yet brutally hard, and a "
        "level game in the 10th over has stakes without scoreboard squeeze. CRICQ therefore blends two parts."
    )
)
st.append(P("Part 1 — Stakes (win-probability leverage)", "h2"))
st.append(
    P(
        "Two gradient-boosting models estimate the batting side's chance of winning before every ball — one for setting a total "
        "(score, balls left, wickets in hand, venue par, competition) and one for chasing (runs needed, balls left, wickets in hand, "
        "required rate, competition). Both are constrained so they always respect cricket logic (e.g. more wickets in hand can never "
        "lower the chance of winning). Stakes = the expected absolute change in win probability across the likely outcomes of the ball "
        "(dot, 1, 2, 4, 6, wicket), weighted by how often each happens in that innings and phase. Rules are applied exactly: a chase "
        "that reaches the target is won; all out or balls exhausted is lost."
    )
)
st.append(P("Part 2 — Squeeze (scoreboard difficulty)", "h2"))
st.append(
    P(
        "<b>Chasing:</b> runs still needed ÷ the runs a side normally scores with the balls and wickets left (learned from the data). "
        "<b>Setting a total:</b> the venue's par score ÷ the projected total (current score + normal runs still to come). Venue par is "
        "each ground's average first-innings total, shrunk toward its country average when a ground has few matches — the best "
        "available stand-in for pitch conditions, which the data does not record."
    )
)
st.append(P("Combining", "h2"))
st.append(
    P(
        f"Each part is converted to a percentile (squeeze within each innings), blended {pr['weight_stakes']:.0%} / {pr['weight_squeeze']:.0%}, "
        f"and re-ranked to a 0-100 <b>Pressure Index</b>. Balls at or above the {pr['high_pressure_threshold_pct']}th percentile are "
        f"<b>high-pressure balls</b> ({pr['share_high_pressure_pct']:.0f}% of all balls). The same index is used for batting and bowling: "
        "a high-pressure ball is high pressure for both the batter and the bowler."
    )
)
st.append(fig_img(f_heat, 165))
st.append(fig_img(f_move, 170))
st.append(
    P(
        "Evidence the index separates pressure from ordinary situations: high-pressure balls account for a far larger share of the "
        "swing in match outcomes than their share of balls, and death overs carry the highest share of high-pressure balls in both innings.",
        "small",
    )
)
st.append(P("Model accuracy", "h2"))
t_ = Table(
    [
        [
            fig_img(f_cal, 78),
            [
                P(
                    f"The win-probability models were trained on 2022-2024 and tested on <b>2025-2026 matches they never saw</b>.<br/>"
                    f"<b>Chasing:</b> AUC {wpv.auc.iloc[1]:.2f}, Brier {wpv.brier.iloc[1]:.3f} (vs {wpv.brier_baseline.iloc[1]:.3f} for a no-skill guess).<br/>"
                    f"<b>Setting a total:</b> AUC {wpv.auc.iloc[0]:.2f}, Brier {wpv.brier.iloc[0]:.3f} (vs {wpv.brier_baseline.iloc[0]:.3f}). First "
                    "innings are inherently harder to call, and scoring rose sharply in 2025-26 so totals that once looked safe were chased more often; "
                    "the model is slightly over-confident for big first-innings positions.<br/>"
                    "For all ratings, every ball is scored by a model that never saw its own match (5-fold cross-fitting grouped by match)."
                )
            ],
        ]
    ],
    colWidths=[82 * mm, W - 82 * mm],
)
t_.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
st.append(t_)
st.append(fig_img(f_match, 170))
st.append(
    P(
        "In this match Rajasthan Royals' win chance fell to about 1% before the final overs; the Pressure Index correctly marks those "
        "final overs as the highest-pressure balls of the game.",
        "small",
    )
)
st.append(PageBreak())

# ---- 4. performance ----
st.append(P("4. Performance measurement", "h1"))
ec = rep["expected_calibration"]
st.append(
    P(
        "Raw strike rates and economies are unfair under pressure, because situations differ: needing 40 off 15 is not the same as "
        "needing 6 off 6. CRICQ judges every ball against what an <b>average player would have done in exactly that situation</b>."
    )
)
st += bullets(
    [
        "<b>Expected-outcome models.</b> Four cross-fitted gradient-boosting models predict, for each ball, expected runs off the bat, the "
        "chance the striker is out, expected runs charged to the bowler and the chance of a bowler's wicket. Features describe only the "
        "situation (innings, over, wickets in hand, balls left, required rate, squeeze, venue par, competition, pace or spin, season) — never "
        f"the player. Calibration: expected {ec['bat_runs_expected']:.3f} vs actual {ec['bat_runs_actual']:.3f} runs per ball; dismissal "
        f"chance {ec['out_expected'] * 100:.2f}% vs {ec['out_actual'] * 100:.2f}%.",
        "<b>Value added per ball (runs).</b> Batting = (runs - expected runs) - wicket value × (out - chance of out). Bowling = (expected "
        "runs - runs conceded) + wicket value × (wicket - chance of wicket). Wicket value = runs a side typically loses by losing one more "
        f"wicket at that moment, capped at {sc['wicket_value_cap']:.0f} runs (about the average wicket value) because uncapped late-innings "
        "wicket costs made player ratings noticeably less repeatable.",
        "<b>Player baselines.</b> Every player has a normal value (all non-pressure balls) and a pressure value. Their difference is the "
        "player's <b>lift</b>: do they rise or dip when it matters?",
        "<b>Familiar stats alongside.</b> Strike rate, balls per dismissal, boundary %, dot %, economy and balls per wicket are reported "
        "split by pressure vs normal so the scores can be checked against plain numbers.",
    ]
)
st.append(P("The CRICQ Score", "h2"))
w8 = sc["weights"]
st.append(
    P(
        f"CRICQ Score = 50 + 10 × standardised blend of <b>Quality</b> ({w8['w_quality']:.0%}), <b>Lift</b> ({w8['w_lift']:.0%}) and "
        f"<b>Consistency</b> ({w8['w_consistency']:.0%}), where 50 = the average ranked player.",
        "callout",
    )
)
st += bullets(
    [
        "<b>Quality</b> — value added per high-pressure ball, adjusted for opposition and anchored to overall ability (section 5).",
        "<b>Lift</b> — pressure value minus the player's own normal value.",
        "<b>Consistency</b> — share of pressure innings or spells (6+ pressure balls) in which the player added value, shrunk toward the "
        "league share with a prior of 6 innings so a handful of innings cannot produce 100%.",
    ]
)
st.append(PageBreak())

# ---- 5. fairness ----
st.append(P("5. Fair comparisons", "h1"))
el = sc["eligibility"]
st += bullets(
    [
        f"<b>Eligibility.</b> At least {el['bat_min_pressure_balls']} high-pressure balls faced (bowled) and {el['bat_min_pressure_matches']} "
        f"matches with pressure balls. This leaves {len(tb)} batters and {len(tw)} bowlers. A stricter rule (200 balls, 15 matches) barely "
        "changes the top 10 (section 7).",
        "<b>Opposition strength.</b> Every ball is adjusted for the quality of the opponent: bowler quality is estimated from all balls they "
        "bowled and added back to the batters who faced them (and vice versa), alternated three times so both sides settle. Balls against "
        f"associate nations and A-teams count {sc['associate_weight']:.0%}.",
        "<b>IPL and T20I together.</b> Both formats are pooled because pressure is the same skill in both, and pooling doubles the evidence. "
        "Competition is a feature in every model, so a run is judged against IPL norms in the IPL and T20I norms in T20Is.",
        f"<b>Recency.</b> Each season counts {sc['recency_decay']} times the next, so 2026 counts fully and 2022 about half — relevant for an "
        "IPL 2027 auction without discarding older evidence.",
        "<b>Match context.</b> Innings, phase, wickets, balls left, required rate, venue par and season are all inside the expected-outcome "
        "models, so openers and finishers, pace and spin, high- and low-scoring venues are all compared fairly.",
    ]
)
st.append(P("Small samples: anchoring pressure ability to overall ability", "h2"))
kb = ksel[ksel.role == "bowl"].iloc[0]
kt = ksel[ksel.role == "bat"].iloc[0]
st.append(
    P(
        "A few hundred pressure balls is a small sample, so raw pressure averages are mostly luck. CRICQ estimates each player's "
        "pressure ability by <b>starting from their overall ability</b> (itself shrunk toward the league average) and moving it toward "
        "their pressure record in proportion to how many pressure balls they have (empirical Bayes). The anchor strength was chosen by "
        "testing which setting best predicts each player's pressure value in matches it had not seen (odd vs even matches, and "
        "2022-24 vs 2025-26). On odd vs even matches, the anchored estimate predicts held-out pressure value far better than the raw "
        f"pressure record alone (bowlers {kb.raw_pressure_only:.2f} -> {max(kb.filter(like='k=')):.2f}; batters "
        f"{kt.raw_pressure_only:.2f} -> {max(kt.filter(like='k=')):.2f}). Chosen anchor: {sc['bowl']['k_anchor']:.0f} balls (bowlers), "
        f"{sc['bat']['k_anchor']:.0f} balls (batters)."
    )
)
st.append(PageBreak())

# ---- 6. evidence ----
st.append(P("6. Evidence for the top 10", "h1"))
st.append(
    P(
        "Left: each player's CRICQ Score with its 90% range from 300 bootstrap re-samples of their matches. Right: the plain "
        "numbers — normal vs pressure — behind each ranking."
    )
)
t_ = Table([[fig_img(f_cib, 84), fig_img(f_db, 84)], [fig_img(f_ciw, 84), fig_img(f_dw, 84)]], colWidths=[W / 2, W / 2])
st.append(t_)
st.append(PageBreak())
st.append(P("Player notes", "h2"))


def note_b(r):
    return (
        f"<b>{int(r['rank'])}. {r.display_name}</b> ({r.role.lower()}, {r.team_label}) — SR {r.p_sr:.0f} under pressure vs {r.n_sr:.0f} "
        f"normally; out every {r.p_bpd:.0f} pressure balls vs {r.n_bpd:.0f}; added value in {int(r.spells_positive)} of "
        f"{int(r.pressure_spells)} pressure innings; top 10 in {int(r.get('top10_in_variants', 0))}/{nvar} tests "
        f"({r.p_top10 * 100:.0f}% of re-samples)."
    )


def note_w(r):
    return (
        f"<b>{int(r['rank'])}. {r.display_name}</b> ({r.role.lower()}, {r.pace_spin.lower() if isinstance(r.pace_spin, str) else ''}, "
        f"{r.team_label}) — economy {r.p_econ:.2f} under pressure vs {r.n_econ:.2f}; {int(r.p_wkts)} pressure wickets (one every "
        f"{r.p_sr:.0f} balls); added value in {int(r.spells_positive)} of {int(r.pressure_spells)} pressure spells; top 10 in "
        f"{int(r.get('top10_in_variants', 0))}/{nvar} tests ({r.p_top10 * 100:.0f}% of re-samples)."
    )


st.append(P("<b>Batters</b>"))
st += [P(note_b(r), "small") for _, r in top_b.iterrows()]
st.append(Spacer(1, 4))
st.append(P("<b>Bowlers</b>"))
st += [P(note_w(r), "small") for _, r in top_w.iterrows()]
st.append(P("Next in line (ranks 11-15)", "h2"))
nb = ", ".join(f"{r.display_name} ({r.clutch_score:.1f})" for _, r in tb.iloc[10:15].iterrows())
nw = ", ".join(f"{r.display_name} ({r.clutch_score:.1f})" for _, r in tw.iloc[10:15].iterrows())
st.append(P(f"<b>Batters:</b> {nb}.<br/><b>Bowlers:</b> {nw}."))
st.append(PageBreak())

# ---- 7. reliability ----
st.append(P("7. Reliability and limitations", "h1"))
st.append(P("Is pressure performance a repeatable skill?", "h2"))
st.append(fig_img(f_rel, 170))
st.append(
    P(
        f"Left: each player's pressure value in one half of their matches vs the other half. Right: ratings built only on 2022-24, "
        "compared with actual 2025-26 pressure value (rank correlation). <b>Bowling</b> pressure value repeats "
        f"({rb[('bowl', '2022-24 vs 2025-26')]:.2f} across eras); every rating method predicts it about equally well "
        f"(CRICQ Score {pcb.filter(like='CRICQ Score').iloc[0]:.2f}, plain economy {pcb.filter(like='Pressure').iloc[0]:.2f}), so the Clutch "
        "Score's benefit is fairness and transparency rather than better forecasting. <b>Batting</b> pressure value does not repeat "
        "among established batters, which is why batting ranks carry wider ranges and ranks 6-10 are close to interchangeable.",
        "small",
    )
)
if len(sens):
    st.append(P("Sensitivity: do the rankings survive different choices?", "h2"))
    pv = sens.pivot(index="variant", columns="role", values="top10_kept")
    sp = sens.pivot(index="variant", columns="role", values="spearman")
    rows = [
        [
            "Change tested",
            "Batters: top 10 kept",
            "Bowlers: top 10 kept",
            "Batters: rank agreement",
            "Bowlers: rank agreement",
        ]
    ]
    for v_ in pv.index:
        rows.append(
            [
                v_,
                f"{pv.loc[v_, 'bat']}/10",
                f"{pv.loc[v_, 'bowl']}/10",
                f"{sp.loc[v_, 'bat']:.2f}",
                f"{sp.loc[v_, 'bowl']:.2f}",
            ]
        )
    st.append(table(rows, [72 * mm, 24 * mm, 24 * mm, 26 * mm, W - 146 * mm]))
    st.append(
        P(
            "Rank agreement = Spearman correlation between the main CRICQ Scores and those from the changed set-up, over all ranked players.",
            "small",
        )
    )
st.append(P("Limitations", "h2"))
st += bullets(
    [
        "No pitch, weather, dew, field-setting or ball-tracking data exists; venue par is used as the stand-in for conditions.",
        "First-innings win probability is harder to estimate (AUC ~0.68) and slightly over-confident for big totals in the high-scoring 2025-26 seasons.",
        "Batting pressure performance is weakly repeatable among established players; batting ranks are less certain than bowling ranks.",
        "Head-to-head batter-bowler records are thin (few pairs have 24+ balls) and are shown in the dashboard for interest only.",
        "Roles are inferred from batting position and the overs a bowler bowls; fielding contributions are not rated.",
        "Player availability for IPL 2027 (retentions, releases, trades) comes from dated news reports until the official lists are "
        "published on 17 Nov 2026; the status file must be updated then and the board re-run.",
        "CRICQ does not predict auction prices; maximum bids remain a management decision.",
    ]
)
st.append(PageBreak())


# ---- 8. auction translation ----
def _lc(s):
    return s[:1].lower() + s[1:]


if (OUT / "auction_plan.csv").exists():
    an = pd.read_csv(OUT / "auction_needs.csv")
    ap = pd.read_csv(OUT / "auction_plan.csv")
    au_ = pd.read_csv(OUT / "auction_unavailable.csv")
    ar = rep.get("auction", {})
    st.append(P("8. Extra: how Rajasthan Royals could use this at the IPL 2027 auction", "h1"))
    st.append(
        P(
            "A ranking answers <i>who is most reliable under pressure</i>. An auction plan must also answer <i>who can Rajasthan "
            "Royals actually buy</i> and <i>where is RR short</i>. CRICQ adds both, with every input in an editable, sourced file "
            f"(status as of {ar.get('as_of', '')}; official retention lists are due on 17 November 2026; auction 16 December, Goa)."
        )
    )
    gone_b = bat[bat.eligible & ~bat.in_pool.astype(bool)].sort_values("rank_all")
    gone_w = bowl[bowl.eligible & ~bowl.in_pool.astype(bool)].sort_values("rank_all")
    gl = "; ".join(
        f"{r.display_name} (would rank {int(r.rank_all)}, {_lc(r.status_label)})"
        for _, r in pd.concat([gone_b, gone_w]).iterrows()
        if r.rank_all <= 6
    )
    st += bullets(
        [
            "<b>Not part of the ranking.</b> The Round 1 lists above are unchanged by anything in this section. Here the same "
            f"scores are filtered to players RR could actually buy. Top-rated players RR cannot sign: {gl or 'none'}.",
            "<b>Who can be bought.</b> Hard facts first (retirements, confirmed trades, bans, and the official lists once "
            "published). Otherwise a consensus: every outlet's retain/release call (sourced report 2, prediction list 1, "
            "opinion 0.5; each outlet once) plus 2026 playing time (regulars count as a strong 'retain'). "
            "P(released) = 1/(1+e^-(-0.4 + evidence)); 70%+ tipped for release, under 15% core player. So Tim David (RCB, "
            "16 of 16 games, two outlets 'retain') is a 2% chance, not a target.",
            "<b>Where RR is short.</b> For each role, RR's strength is the average CRICQ Score of its best players in that role; "
            "the gap to 55 (proven under pressure) sets the need: 7+ High, 3-7 Medium.",
            "<b>Who to target.</b> Priority = CRICQ Score in the role + need bonus (High +10, Medium +5) + 15 x availability. "
            "The shortlist takes only realistic targets (score 50+, 35%+ availability) and respects RR's overseas slots.",
        ]
    )
    st.append(
        P(
            f"<b>Default projection.</b> Releasing {', '.join(ar.get('released', []))} leaves RR with "
            f"{ar.get('squad_kept', '')} players, {ar.get('slots', '')} open slots ({ar.get('overseas_slots', '')} overseas) and an "
            f"estimated purse of Rs {ar.get('purse_cr', 0):.2f} crore (reported Rs 130 crore cap minus kept fees).",
            "body",
        )
    )
    rows = [["Role", "Need", "RR strength", "RR players (CRICQ Score)"]]
    for _, r in an.iterrows():
        rows.append([r.label, r.level, f"{r.strength:.1f}", P(str(r.squad_players), "cell")])
    st.append(table(rows, [42 * mm, 16 * mm, 20 * mm, W - 78 * mm]))
    st.append(Spacer(1, 6))
    if len(ap):
        rows = [["Slot", "Role", "Target", "Clutch", "Availability", "Plan B"]]
        for _, r in ap.iterrows():
            rows.append(
                [
                    int(r.slot),
                    r.need_label,
                    r.target + (" (OS)" if r.overseas else ""),
                    f"{r.clutch_score:.0f}",
                    r.availability,
                    P(str(r.plan_b) if pd.notna(r.plan_b) else "-", "cell"),
                ]
            )
        st.append(P("<b>Shortlist for the open slots</b>", "body"))
        st.append(table(rows, [10 * mm, 38 * mm, 34 * mm, 14 * mm, 38 * mm, W - 134 * mm]))
    if (OUT / "auction_xi.csv").exists():
        xi = pd.read_csv(OUT / "auction_xi.csv")
        st.append(
            P(
                "<b>Projected XI + Impact Player:</b> "
                + ", ".join(
                    f"{r.player} ({r.slot.lower()}{', target' if r.source == 'Auction target' else ''})"
                    for r in xi.itertuples()
                    if r.role_in_xi == "XI"
                )
                + ". Impact Player: "
                + ", ".join(xi[xi.role_in_xi != "XI"].player)
                + ".",
                "small",
            )
        )
    if (OUT / "player_factors.parquet").exists():
        st.append(
            P(
                "<b>Cricket parameters.</b> Every ball is also tagged by phase, setting or chasing, wickets in hand, collapse "
                "(2+ wickets in 3 overs), pitch type (venue par terciles - the Data Pack has no pitch reports), opposition "
                "strength, knockout or league, competition, bowler type faced (right/left-arm pace, off-spin, leg-spin, left-arm "
                "spin), batter hand bowled to, and RR's home venues. Each player gets runs added (or saved) per 100 balls versus "
                "an average player in the same spot, in every one of these situations, normal and under pressure, plus "
                "batter-versus-bowler head-to-heads. The dashboard's Situation scout ranks players in any combination "
                "(e.g. death overs, chasing, low-scoring ground).",
                "small",
            )
        )
    top_na = au_.sort_values("clutch_score", ascending=False).head(8)
    st.append(
        P(
            "<b>Top pressure players RR cannot plan around:</b> "
            + "; ".join(f"{r.display_name} ({_lc(r.status_label)})" for _, r in top_na.iterrows())
            + ". The dashboard's Auction board lets selectors change releases, see the effect on purse, slots and needs, and "
            "keep a watch list of strong fits still under contract.",
            "small",
        )
    )
    st.append(PageBreak())

# ---- 9. reproducibility ----
st.append(P("9. Reproducing the results", "h1"))
st.append(P("Everything is produced by code from the six Data Pack files; no number is entered by hand."))
st += bullets(
    [
        "<b>python pipeline.py</b> — runs steps 1-7 (load, scoreboard, win probability, Pressure Index, expected outcomes, scoring, "
        "rankings, sensitivity) in about 2 minutes and writes data/processed/ and outputs/.",
        "<b>streamlit run dashboard/app.py</b> — opens the interactive dashboard (Home, Rankings, Auction board, Player, Compare, Match replay, How it works).",
        "<b>data/external/</b> — player_status_2027.csv and rr_squad_2027.csv: sourced, dated availability and RR squad files for the auction board.",
        "<b>python report/build_report.py</b> — rebuilds this report from the outputs.",
        "<b>config.yaml</b> holds every tunable number (pressure blend and cut-off, weights, eligibility, wicket-value cap, bootstrap size, random seed).",
        "Libraries: Python, pandas, NumPy, scikit-learn (HistGradientBoosting models, GroupKFold), Streamlit, Plotly, Matplotlib, ReportLab.",
    ]
)
rows = [
    ["Module", "What it does"],
    ["engine/load.py", "Reads and joins the six CSVs; extras coding; team tiers; player directory; data-quality log"],
    [
        "engine/match_state.py",
        "Live scoreboard per ball; venue par; expected-runs-remaining table; result reconciliation",
    ],
    ["engine/win_prob.py", "Win-probability models, time-based validation, cross-fitting, leverage"],
    ["engine/pressure.py", "Squeeze, Pressure Index, validation tables"],
    ["engine/expected.py", "Expected-outcome models and value added per ball"],
    [
        "engine/scoring.py",
        "Weights, opponent adjustment, anchored estimates, CRICQ Score, bootstrap, predictive check",
    ],
    ["engine/rankings.py", "Top-10 selection, sensitivity tests, repeatability"],
    ["engine/availability.py", "IPL 2027 player status (sourced file + rules) and chance of being in the auction pool"],
    ["engine/auction.py", "RR squad state, role needs, auction targets, shortlist and watch list"],
]
st.append(table(rows, [42 * mm, W - 42 * mm]))

doc.build(st, onFirstPage=on_page, onLaterPages=on_page)
print("Wrote", ROOT / "report" / "CRICQ_Methodology_Report.pdf")
