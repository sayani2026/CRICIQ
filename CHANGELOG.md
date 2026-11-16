# Changelog

## 1.6.0 — 15 November 2026 · final polish

- **Cards redesigned:** original role pictograms (batter, pace bowler, spinner) floating inside a rotating tier ring;
  animated foil border (gold ICON, pink ELITE, blue RARE); pinstripe pattern; gold shimmer rating and twinkling
  sparkles on ICON cards; **click to flip** — the back shows pressure vs normal (strike rate, balls per dismissal,
  boundary %, dot %, or economy, balls per wicket, dot %, boundary %), pressure balls, matches, 90% range, tests.
- **Home hero:** animated count-up stats, a broadcast-style scrolling "Pressure rankings" ticker (pauses on hover),
  floating light orbs.
- **Whole dashboard:** slow aurora background with drifting star dust, glass tiles with a rotating gradient border on
  hover, KPI numbers that count up, growing accent bars under headings, glowing tab underline, active-page glow in
  the sidebar, pink scrollbar, charts and tables that reveal as you scroll (Chrome / Edge). Everything still turns
  off for users who ask their system for reduced motion.
- Auction board: unranked squad players show "—" instead of "None".

## 1.5.1 — 15 November 2026

- **"Player Image" folder** in the project root: one placeholder PDF per ranked player (171), named exactly as the
  dashboard expects — `viratkohliimage.pdf`, `timdavidimage.pdf`… Replace a file with the player's photo under the
  same name (`.jpg`, `.jpeg`, `.png`, `.webp`, or a PDF containing the picture, up to 15 MB) and the card shows it.
  Photos are square-cropped to 360 px for speed. `player_list.csv` lists every file name; `HOW_TO_ADD_PHOTOS.txt`
  explains the steps. `run_pipeline.bat` adds placeholders for new players and never overwrites existing files.

## 1.5.0 — 15 November 2026

- **Player cards:** every ranked player as a collectible-style card — overall rating (CRICQ Score), tier (ICON /
  ELITE / RARE / BASE), position and style, six percentile attributes, rank and robustness. New **Player cards**
  page (filters, search, Open profile), top-5 cards on Home, and a card at the top of every Player profile.
- **Photo slot:** drop images you have the right to use in `assets/players/` (by name or id) and they appear on the
  cards automatically; otherwise an animated monogram. No photos are shipped.
- **Motion:** count-up ratings, staggered card entrances, holographic sheen, 3D hover tilt, glowing ICON borders,
  rotating rating rings, animated attribute bars, animated kit stripe, title shine, a "match pulse" line on Home,
  hover lift on KPI tiles and buttons, fade-in for charts and tables. All of it switches off for users who ask
  their system for reduced motion.
- Dashboard auto-reload now also watches `assets/players/`.
- Tests: 50.

## 1.4.0 — 15 November 2026

Aligned exactly with the Round 1 problem statement ("the 10 best-performing batters under pressure and the 10
best-performing bowlers under pressure", rankings "supported by analysis of the supplied data").

- **Official lists = the pure pressure ranking from the Data Pack.** The only players left out are retired players and
  players with no match since 2024. IPL 2027 availability (retentions, trades, IPL eligibility) no longer changes the
  ranking; it is used only by the Auction board, which is labelled as an extra.
- Team shown is the 2026 team from the Data Pack (confirmed 2027 trades are kept separately for the auction board).
- Unstop sheet checks automatically: 10 players per list, ranks 1–10 in order, no repeats; report lists match it.
- Report: summary and section 8 reworded (section 8 = optional extra, does not change the rankings).
- Dashboard: Home leads with the two Round 1 lists; navigation grouped as Round 1 / Selector tools / Evidence;
  retired and inactive players never appear in Player profile, Compare, Matchups or Situation scout.

## 1.3.2 — 15 November 2026

- **Fix: a dashboard left running showed old results.** Tables were cached in memory, so after new results were
  copied in, the page showed the new layout with the previous rankings (Tim David and Kohli still ranked). The
  dashboard now fingerprints every results file and reloads automatically when anything changes; a **Reload data**
  button is in the sidebar as well.

## 1.3.1 — 15 November 2026

- **The top-10 lists now contain only players Rajasthan Royals can sign at the IPL 2027 auction** (released, tipped
  for release, mixed reports, free agents, must register). Stars their franchises keep (Tim David and Virat Kohli at
  RCB, Rohit Sharma and Bumrah at MI, Klaasen at SRH…), traded players, RR's own squad, retired and IPL-ineligible
  players never get a rank. Robustness tests use the same pool. Unstop sheet, report, home page and Rankings page
  follow (Rankings can still show everyone for comparison with "Include players RR can't sign").
- Tests: 46.

## 1.3.0 — 15 November 2026

A complete selection system: realistic availability, the cricket parameters, and a dashboard built around RR's auction.

- **Availability you can trust:** new `retention_reports_2027.csv` — 231 retain/release calls from 20+ outlets
  (Sporting News, Khel Now, MyKhel, Jago News, CricketNews, NewsBytes, PTI-sourced reports…), each with link and date.
  CRICQ weighs them (report 2 · prediction 1 · opinion 0.5, each outlet once) together with **2026 playing time
  from the Data Pack** (franchises keep their regulars) into a chance of release. Hard facts still win. Tim David,
  Rohit Sharma, Pooran and other regulars come out as core players; Ferguson, Pathirana, Green, Phillips, Shahrukh
  Khan as tipped releases. Ajinkya Rahane's retirement added. Name matching handles journalist spellings and never
  guesses a different player.
- **Cricket parameters (`engine/factors.py`):** phase, setting/chasing, wickets in hand, collapse in progress, pitch
  type (venue par), opposition strength, knockout/league, competition, bowler type faced, batter hand bowled to,
  pressure, RR home venues — per player, normal and under pressure — plus batter-vs-bowler head-to-heads.
- **Dashboard rebuilt as an RR selection system:** grouped navigation; new **Selection room** home (plan, shortlist,
  projected XI, then the Round 1 answer); new **Situation scout** and **Matchups** pages; **Parameters** section on
  every player profile; **Projected XI + Impact Player** on the Auction board; sources tabs for hard facts and
  news calls.
- **Fixes:** a player's 2027 status now uses his last match in any role (Suryakumar, Shreyas, Kohli were wrongly
  dropped from the robustness tests because they rarely bowl); sensitivity exclusions are per role.
- **Report:** auction section explains the consensus, lists the projected XI and the parameters.
- **Tests:** 45 (was 40).

## 1.2.0 — 15 November 2026

Auction-ready release: rankings now respect who can actually play, and a new **RR Auction Board** turns them into an
IPL 2027 plan.

- **Who can be ranked:** retired players (Andre Russell, Dinesh Karthik, R Ashwin, Mohit Sharma, Karn Sharma, Vijay
  Shankar), players with no match since 2024 and players who cannot play the IPL (Pakistan internationals) are no
  longer given a rank. Official lists change accordingly (batters: Russell and Karthik out; Jaiswal and Pooran in;
  bowlers: Abrar Ahmed out; Hasaranga in). Sensitivity tests apply the same rule.
- **IPL 2027 availability:** new `data/external/player_status_2027.csv` — confirmed trades (Pant, Kuldeep, Hardik,
  Arshdeep, Natarajan, Livingstone, Ellis…), likely retentions per franchise, tipped releases, retirements, bans and
  eligibility risks, each with a source and date. Simple rules cover everyone else. Each status maps to a chance of
  being in the auction pool. Teams shown reflect confirmed trades.
- **RR Auction Board (new dashboard page):** release simulator with live purse / slots / overseas slots; role-by-role
  squad strength under pressure; auction shortlist with back-ups and overseas cap; target finder; watch list for
  release day; "top players RR can't sign".
- **New engine modules:** `engine/availability.py`, `engine/auction.py`; bowling tables gain `pp_share` and
  `death_share`; pipeline writes `outputs/auction_*.csv`.
- **Rankings page:** "2027 status" column, "Only players RR could buy" and "Show retired / not IPL-eligible" filters.
  **Player page:** 2027 status with source link.
- **Report:** new section 8 "From rankings to the RR auction table". **Unstop sheet:** status column plus a
  reference list of the best players RR could buy.
- **Tests:** 40 (was 34) — availability rules, status-file validation, squad maths, needs/targets/plan, config checks.

## 1.1.0 — 15 November 2026

Engineering-quality release. **Rankings unchanged.**

- **Validation:** `config.yaml` is checked on load (ranges, weights that must sum to 1, year format) and every Data
  Pack file is schema-checked (missing files, missing columns, orphan match IDs), all with plain-English errors.
- **CLI and logging:** `python pipeline.py [--fast] [--config FILE] [--log-level LEVEL]`; timed log lines; exit
  code 2 with a readable message on bad inputs; installable entry point `cricq-pipeline`.
- **Packaging:** `pyproject.toml` (metadata, dependencies, `dev` extras, ruff and pytest settings).
- **Code quality:** whole codebase formatted and linted with ruff (pycodestyle, pyflakes, isort, bugbear, pyupgrade,
  simplify); fixed mutable default argument, files opened without context managers, length-unchecked `zip`s,
  ambiguous names.
- **Tests:** 34 tests (was 14) — new engine unit tests on a synthetic, hand-checked Data Pack covering format coding
  (IPL vs A-team events), team tiers, extras and legal balls, the scoreboard including rain-reduced innings,
  result reconciliation, win-probability terminal rules, Pressure Index bounds and monotonicity, shrinkage and
  anchoring maths, config and schema validation, and the CLI error path.
- **Tooling:** GitHub Actions CI (lint, tests on Python 3.11/3.12, dependency audit), pre-commit hooks, `.editorconfig`,
  `Makefile`.
- **Windows launchers:** `run_dashboard.bat` now opens the browser automatically; all launchers find Python via `py` or
  `python` and explain what to do if it is missing; new `open_in_vscode.bat`; VS Code tasks (`.vscode/tasks.json`)
  for running the dashboard, pipeline and tests.
- **Docs:** `ARCHITECTURE.md` (system diagram, layers, data contracts, design decisions, extension guide) and
  `CONTRIBUTING.md`.

## 1.0.0 — 15 November 2026

First complete release.

**Engine**
- Data pipeline for the six Data Pack files, with a data-quality log (revised overs stored in balls, A-team events
  sharing the IPL format code, same-name players, extras coding, super overs).
- Scoreboard rebuilt for every ball; 809 of 810 results reconcile with official margins.
- Win-probability models (chasing AUC 0.91 on unseen 2025–26 matches), Pressure Index (stakes + squeeze), expected-
  outcome models, opponent adjustment, anchored empirical-Bayes estimates, CRICQ Score, 300-sample bootstrap ranges,
  10-variant sensitivity tests, repeatability and predictive checks.

**Dashboard**
- Seven pages: Home, Rankings (auction filters), Player, Compare, Match replay, How it works, About & privacy.
- Dark theme in Royals-inspired colours (pink, royal blue, gold on navy); optional official-logo slot.

**Report**
- 11-page methodology PDF in the organisers' required structure.

**Security & privacy**
- Optional password sign-in (PBKDF2, lock-out) that guards every page URL, local-only server default, XSRF/CORS on, uploads off, generic error
  messages, HTML escaping of all data text, plain-text search, CSV formula-injection protection, pinned dependencies,
  SHA-256 checksums, non-root Docker image, privacy and security policies.
