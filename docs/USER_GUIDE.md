# CRICQ — User guide

## Opening the dashboard

**Windows:** double-click `setup.bat` once (installs everything), then `run_dashboard.bat` whenever you want to use it.
Your browser opens at `http://localhost:8501`. Close the black window to stop it.

If the password is switched on (see `SECURITY.md`), sign in first. After 5 wrong tries the form locks for a minute.

## The pages

### Home — the Round 1 answer
The two lists Round 1 asks for: the top 10 batters and top 10 bowlers under pressure, in rank order, with Clutch
Score, 90% range, pressure balls and **Tests** (how many of 10 alternative set-ups still put the player in the top 10;
10/10 = rock solid). Then the key findings, and — clearly marked as an extra — how RR could use the scores at the
IPL 2027 auction (shortlist with Plan B, projected XI).

### Player cards
Every ranked player as a collectible-style card. The big number is his CRICQ Score (50 = average regular player);
the tier shows **ICON** (80+), **ELITE** (70–79), **RARE** (60–69) or **BASE**. Six attributes are percentiles
(1–99) against all ranked players, under pressure — batters: PRS pressure quality, LFT lift vs own level, CON
consistency, PWR boundary %, SR strike rate, SUR balls per dismissal; bowlers: PRS, LFT, CON, ECO economy, WKT balls
per wicket, DOT dot-ball %. Hover a card to tilt it; **click a card to flip it** — the back shows his numbers under
pressure against his normal level (green = better under pressure, orange = worse), pressure balls, matches, 90% range
and robustness tests; click anywhere else to flip it back. **Open profile** jumps to the full player page. Each card
shows an original pictogram for his role (batter, pace bowler, spinner). The top five
cards also appear on Home, and every Player profile starts with the player's card.

**Photos:** open the **Player Image** folder in the project. Every ranked player has a placeholder file named for
him — `viratkohliimage.pdf`, `timdavidimage.pdf`, … (`player_list.csv` lists them all). Save his photo (one you have
the right to use) with the same name: `viratkohliimage.jpg`, `.png`, `.webp`, or a PDF that contains the picture.
Refresh the dashboard and the photo appears on his card, square-cropped with the face kept near the top. An image
file always wins over a PDF. Without a photo, the card shows an animated monogram.

### Rankings
- Switch **Batters / Bowlers**. The rank is the Round 1 rank (pure pressure ranking from the Data Pack).
- Filter by **Role** (opener, finisher, death specialist…), **batting hand** or **pace/spin**, **Team**, or type a name.
- **2027 status** column — information for the auction only (retained core, traded, tipped for release…).
- **Only players RR could buy in 2027** — extra auction filter; off = the full Round 1 ranking.
- **Hide Rajasthan Royals players** — hides RR's current squad.
- **Show retired / inactive players** — off by default; they never get a rank.
- **Include players below the minimum** — shows players with too few pressure balls to be ranked (no rank, less certain).
- **Download this list (CSV)** saves exactly what is on screen.
- The chart at the bottom shows each CRICQ Score with its 90% range: overlapping lines mean those players are hard to separate.

### Situation scout — the parameters
Pick any combination of parameters — phase, setting or chasing, wickets in hand, collapse in progress, pitch / ground
type, opposition strength, knockout or league, competition, bowler type faced (batters), batter hand bowled to
(bowlers), pressure, RR home venues — plus seasons and a minimum number of balls. Players are ranked by runs added
(or saved) per 100 balls against an average player in exactly the same spot. Presets: death overs under pressure,
finishing a chase, defending at the death, rescuing a collapse, slow grounds, knockouts and more. Tick **Only players
RR could buy** to turn it into an auction search.

### Matchups
A batter against each bowler type and the individual bowlers he dominates or struggles against; a bowler against
right- and left-handers and individual batters; or any batter-vs-bowler head to head (all balls and under pressure).

### Auction board — the IPL 2027 plan for Rajasthan Royals
1. **Who RR keeps** — tick players to release. Purse (salary cap minus kept fees), open squad slots and overseas
   slots update instantly. Defaults follow news reports plus CRICQ's pressure numbers.
2. **Where RR is short** — RR's strength in each role (average CRICQ Score of its best players there) against the
   55 "proven under pressure" line. Pink = High need, gold = Medium.
3. **Auction shortlist** — one realistic target per open slot with two back-ups, overseas cap respected.
4. **Projected XI + Impact Player** — the best combination of kept players and targets (max 4 overseas).
- **Target finder** — every possible target by role, Indian/overseas and chance of being in the auction.
- **Watch list for 17 Nov** — strong fits still under contract: move them up if their team releases them.
- **Top players RR can't sign** — Tim David at RCB, Rohit-level cores, trades, retirements: don't plan around them.
- **Sources** — every status has a news source and date.

### Player
Pick **Batter** or **Bowler**, then a player. You get a plain-English summary, four normal-vs-pressure numbers,
how they perform by phase / against pace or spin / by competition, an innings-by-innings consistency chart, how they
get out (or take wickets) under pressure, and their season-by-season trend. **Score breakdown** shows Quality, Lift
and Consistency.

### Compare
Two batters, two bowlers, or a batter against a bowler (head-to-head). Head-to-heads are shown for interest only —
most pairs have met for only a few balls.

### Match replay
Choose a competition and a match (**Only tight finishes** lists the most dramatic ones). The line shows the chasing
side's chance of winning after every ball; the strip underneath shows how much pressure each ball carried (pink =
high pressure). Tables show the moments that decided the match and who handled the pressure.

### How it works
The method in plain words with the evidence: where pressure lives, how accurate the models are, whether pressure
performance repeats, and how the rankings survive different settings.

### About & privacy
What CRICQ is, the independence disclaimer, the privacy and security summary, and the full policies.

## Words used

| Term | Meaning |
|---|---|
| **Pressure Index** | 0–100 rating of the pressure on a ball: what is at stake plus how tough the scoreboard is |
| **Pressure ball** | A ball in the top 25% of the Pressure Index |
| **CRICQ Score** | How well a player performs when it matters. 50 = average ranked player, 60+ very good, 70+ elite |
| **Quality** | Runs added per pressure ball versus an average player in the same situation, adjusted for opposition |
| **Lift** | Pressure value minus the player's own normal value |
| **Consistency** | Share of pressure innings (6+ pressure balls) in which the player added value |
| **Range** | Where the score would land 90% of the time if their matches had gone slightly differently |

## Updating the results

| Task | Windows | Terminal |
|---|---|---|
| Rebuild everything from the Data Pack (~2 min) | `run_pipeline.bat` | `python pipeline.py` |
| Rebuild the PDF with your name on the cover | `build_report.bat` | `python report/build_report.py "Your Name"` |
| Refresh the Unstop entry sheet | — | `python tools/make_submission.py` |
| Run the checks | — | `pytest -q` |

Settings (what counts as pressure, eligibility, weights, "active players only", auction cap and needs) are in
`config.yaml`; re-run the pipeline after changing them.

### When the official retention lists come out (17 Nov 2026)
1. Open `data/external/player_status_2027.csv` in Excel and add a row for each player on an official list with
   `status` = `retained` or `released` and the link and date in `source` and `source_date`. Hard facts always beat
   news reports. (Other hard statuses: `traded`, `retired`, `banned`, `risk`, `opted_out`, `ineligible`.)
   New rumours or reports go in `retention_reports_2027.csv` (one row per outlet per player: `retain` or
   `release`, kind `report` / `prediction` / `opinion`).
2. In `data/external/rr_squad_2027.csv`, set RR's `projection` to `retain` or `release` to match.
3. Run `run_pipeline.bat` (or `python pipeline.py`), then `python tools/make_submission.py`, then refresh the dashboard.

## Adding an official logo

Save it as `assets/logo.png` (or `.svg` / `.jpg`) and restart the dashboard. It replaces the CRICQ mark at the top
of the sidebar. Only use a logo you have permission to use.

## Troubleshooting

| Problem | Fix |
|---|---|
| "python is not recognised" | Install Python 3.10+ from python.org and tick **Add Python to PATH**, then run `setup.bat` again |
| "No processed data yet" | Run `run_pipeline.bat` once |
| Pipeline can't find `ball_by_ball.csv` | Keep the `cricq` folder next to `CRICQ DATASET`, or copy the 6 CSVs into `data/raw/` |
| Page says "something went wrong" | Details are printed in the black terminal window (hidden from the browser on purpose) |
| Port already in use | Close the other dashboard window, or run `python -m streamlit run dashboard/app.py --server.port 8502` |
