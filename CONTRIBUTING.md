# Contributing to CRICQ

## Set up

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (source .venv/bin/activate on macOS/Linux)
pip install -e ".[dev]"
pre-commit install                # lint + format on every commit
```

## Daily commands

| Task | Command |
|---|---|
| Rebuild outputs | `python pipeline.py` (`--fast` skips sensitivity, `--log-level DEBUG` for detail) |
| Dashboard | `streamlit run dashboard/app.py` |
| Tests | `pytest -q` |
| Lint / format | `ruff check . && ruff format .` |
| Dependency audit | `pip-audit -r requirements-lock.txt` |

`make <task>` works too on macOS/Linux (see `Makefile`).

## Rules

1. **Every number comes from the pipeline.** The dashboard and report only read `data/processed/` and `outputs/`.
2. **Players are keyed by `player_id`.** Never join or group on names.
3. **New settings go in `config.yaml`** and get a check in `engine/validation.py`.
4. **Escape data text** before putting it in HTML (`theme.esc`, `theme.kpi`, `theme.pill`).
5. **New pages go in `dashboard/views/`** and are registered after `auth.require_login()` in `dashboard/app.py`.
6. **Tests with every change.** Unit tests use the synthetic Data Pack in `tests/conftest.py`; add a case there for
   any new data rule. CI runs lint and tests on Python 3.11 and 3.12.
7. **Re-run before committing results:** `python pipeline.py && pytest -q && python tools/make_submission.py && python tools/checksums.py`.

## Releasing

1. Update `VERSION`, `pyproject.toml` and `CHANGELOG.md`.
2. `python pipeline.py && python report/build_report.py "Your Name" && pytest -q`
3. `python tools/make_submission.py && python tools/checksums.py`
4. Zip the folder without `data/raw/*.csv`, `.streamlit/secrets.toml` and `assets/logo.*`.
