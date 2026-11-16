# Privacy Policy — CRICQ

_Version 1.0 · Effective 15 November 2026_

This policy explains what information CRICQ (the analytics engine, dashboard and report in this folder) uses,
why, and how it is protected. It is a plain-English policy written for an independent competition project; it is
not legal advice. If you deploy CRICQ for an organisation, have it reviewed against the laws that apply to you
(for example India's Digital Personal Data Protection Act 2023 or the EU GDPR).

**Project owner / contact:** [Your name / team name] · [your contact email]

## 1. Who we are

CRICQ is an independent project built for Rajasthan Royals' SupeRR Selector Season 2 competition. It is not
affiliated with, endorsed by or operated by Rajasthan Royals, the Indian Premier League, the BCCI or the ICC.

## 2. Information CRICQ processes

**Cricket data (the Data Pack).** CRICQ analyses the six files supplied by the competition organisers:
ball-by-ball records, matches, competitions, teams, playing XIs and squad lists for IPL and T20I cricket from 2022.
These include the **names of professional cricketers and their on-field statistics** (runs, wickets, balls, dismissals,
batting and bowling style). This is information about players' public sporting performance, already published in
match scorecards. CRICQ does not add any other information about players — no contact details, health, salary,
images or private data.

**Purpose.** Analysing sporting performance under pressure and ranking players for the competition and for
cricket-selection discussion. The data is not used for any other purpose, sold, or combined with other personal data.

**Information about people who use the dashboard.** None is collected. CRICQ has no accounts, sign-up forms,
uploads, comments or contact forms.

## 3. What happens when you open the dashboard

- The dashboard runs on **your own computer** and, by default, can only be opened from that computer (`localhost`).
- **No analytics or tracking.** CRICQ includes no analytics, advertising or tracking code, and Streamlit's own
  usage statistics are switched off (`gatherUsageStats = false`).
- **Session memory only.** Your page choices (filters, selected player) live in the browser session's memory and are
  cleared when you close the tab. Nothing is written to disk.
- **Cookies.** CRICQ sets no cookies of its own. The Streamlit framework sets one security cookie
  (`_streamlit_xsrf`) to protect against cross-site request forgery. It contains no personal information.
- **Optional password.** If the owner switches on the password, only a salted hash of that password is stored in
  `.streamlit/secrets.toml` on the host computer. Entered passwords are never logged or saved.
- **No external calls.** CRICQ does not send data to any outside service. If you deploy it on a hosting platform,
  that platform's own privacy policy also applies.

## 4. Where information is stored and for how long

All data stays inside the project folder: the raw Data Pack you supply, the processed tables in `data/processed/`,
and results in `outputs/` and `report/`. They are kept until you delete them. Deleting the folder removes everything.

## 5. Sharing

CRICQ shares nothing by itself. Files you choose to share (for example the PDF report or the top-10 lists) contain
player names and statistics derived from the Data Pack; share them only in line with the organisers' terms for the
Data Pack.

## 6. Security

See [SECURITY.md](SECURITY.md): local-only default, optional password with lock-out, hardened server settings, escaped
output, protected CSV downloads, pinned dependencies and SHA-256 checksums for outputs.

## 7. Accuracy and correction

Statistics come directly from the Data Pack. If you believe a player's record is wrong, contact the project owner;
errors traced to the source data will be noted and, where possible, corrected and the rankings re-run.

## 8. Children

CRICQ is a professional sports-analysis tool and is not directed at children.

## 9. Changes

Changes to this policy will be recorded with a new version number and date at the top of this file and in
`CHANGELOG.md`.
