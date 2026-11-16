# Security Policy — CRICQ

_Version 1.0 · 15 November 2026_

## Supported version

| Version | Supported |
|---|---|
| 1.0.x | Yes |

## Reporting a problem

Please report security issues privately to **[your contact email]** with steps to reproduce. Do not post them
publicly. You will get an acknowledgement within 7 days.

## What CRICQ is (threat model)

A read-only analytics app. It reads six CSV files you supply, writes results inside its own folder, and serves a
dashboard. It has **no uploads, no database, no user accounts, no outbound network calls** and stores no personal
information about its users. The main risks are: someone else on your network opening the dashboard, a crafted value
in the data being rendered as HTML, a crafted search freezing the app, and a downloaded CSV running formulas in a
spreadsheet. Each is addressed below.

## Built-in protections

| Area | Protection | Where |
|---|---|---|
| Network exposure | Dashboard listens on `localhost` only by default | `.streamlit/config.toml` → `server.address` |
| Access control | Optional password sign-in: salted PBKDF2-SHA256 (310,000 iterations), constant-time comparison, 5 tries then 60 s lock-out per session | `dashboard/components/auth.py` |
| Page access | Pages live in `dashboard/views/` (not an auto-discovered `pages/` folder) and are only registered after sign-in, so no page can be opened directly by URL; navigation is hidden on the sign-in screen | `dashboard/app.py`, `auth.py` |
| Secrets | Password hash kept in `.streamlit/secrets.toml`, which is git-ignored; a template is provided | `.streamlit/secrets.toml.example`, `.gitignore` |
| Cross-site attacks | Streamlit XSRF and CORS protection on; static file serving off | `config.toml` |
| HTML injection (XSS) | Every player, team, competition and result string is HTML-escaped before display | `theme.esc`, `theme.kpi`, `theme.pill` |
| Search abuse (ReDoS) | Player search is plain text (no regular expressions) and capped at 60 characters | `views/rankings.py` |
| Spreadsheet formula injection | CSV downloads prefix any cell starting with `= + - @` with `'` | `views/rankings.py` → `_safe_csv` |
| Uploads | None accepted; upload limit set to 1 MB | `config.toml` |
| Error leakage | Visitors see generic error messages; details go to the terminal only | `client.showErrorDetails = "none"` |
| Config parsing | YAML read with `yaml.safe_load` (no code execution) | `engine/config.py` |
| Telemetry | Streamlit usage statistics disabled | `browser.gatherUsageStats = false` |
| Dependencies | Version ranges in `requirements.txt`; exact tested versions in `requirements-lock.txt` | project root |
| Integrity | SHA-256 checksum of every shipped file | `CHECKSUMS.sha256` |
| Container | Docker image runs as a non-root user | `Dockerfile` |

## Turning on the password

```bash
python tools/make_password.py          # type a password (10+ characters) twice; prints a hash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # Windows  (cp on macOS/Linux)
# paste the printed password_hash line into secrets.toml, then restart the dashboard
```

To turn it off again, delete `.streamlit/secrets.toml`.

## Sharing the dashboard beyond your computer

1. Switch on the password (above).
2. Remove or change `address = "localhost"` in `.streamlit/config.toml` (for example `0.0.0.0` behind a firewall).
3. Serve it only over **HTTPS**, for example behind a reverse proxy (Caddy, nginx) or on Streamlit Community Cloud
   (put the `[auth]` block in the platform's *Secrets* settings, never in the repository).
4. Do not publish the raw Data Pack if the organisers' terms do not allow it.

## Keeping dependencies safe

```bash
pip install pip-audit
pip-audit -r requirements-lock.txt
```

Update with care: re-run `python pipeline.py` and `pytest -q` after upgrading.

## Verifying files

```bash
# macOS / Linux
sha256sum -c CHECKSUMS.sha256
# Windows PowerShell (one file)
Get-FileHash outputs\top10_batters.csv -Algorithm SHA256
```

## Known limitations

- The password is one shared password, not individual accounts, and the lock-out is per browser session. For several
  named users or audit logs, put CRICQ behind a proper identity provider (for example an SSO-enabled reverse proxy).
- CRICQ is designed for public sporting data. It is not built to hold confidential or sensitive personal data.
