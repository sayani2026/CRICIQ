"""Security checks: escaping, password hashing, CSV formula protection, hardened config."""

import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))

from components import auth, theme  # noqa: E402


def test_kpi_and_pill_escape_html():
    bad = '<img src=x onerror="alert(1)">'
    for out in (theme.kpi(bad, bad, bad), theme.kpi("a", "b", [bad, bad]), theme.pill(bad)):
        assert "<img" not in out and "&lt;img" in out


def test_password_hash_roundtrip_and_salt():
    h1, h2 = auth.hash_password("correct horse battery"), auth.hash_password("correct horse battery")
    assert h1 != h2  # random salt
    assert auth.verify_password("correct horse battery", h1)
    assert not auth.verify_password("wrong password!!", h1)
    assert not auth.verify_password("x", "garbage")  # malformed hash never verifies
    assert "correct horse" not in h1


def test_csv_formula_injection_neutralised():
    import pandas as pd

    src = (ROOT / "dashboard" / "views" / "rankings.py").read_text(encoding="utf-8")
    ns = {"pd": pd}
    exec(src[src.index("def _safe_csv") : src.index("st.download_button")], ns)
    out = ns["_safe_csv"](pd.DataFrame({"Player": ['=HYPERLINK("x")', "+1", "Tim David"]})).decode("utf-8-sig")
    assert "'=HYPERLINK" in out and "'+1" in out and "Tim David" in out


def test_search_is_literal():
    src = (ROOT / "dashboard" / "views" / "rankings.py").read_text(encoding="utf-8")
    assert "regex=False" in src and "max_chars=60" in src


def test_hardened_streamlit_config():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["server"]["address"] == "localhost"
    assert cfg["server"]["enableXsrfProtection"] is True
    assert cfg["server"]["enableCORS"] is True
    assert cfg["server"]["maxUploadSize"] <= 1
    assert cfg["client"]["showErrorDetails"] == "none"
    assert cfg["browser"]["gatherUsageStats"] is False


def test_secrets_not_shipped_and_ignored():
    assert not (ROOT / ".streamlit" / "secrets.toml").exists()
    assert ".streamlit/secrets.toml" in (ROOT / ".gitignore").read_text()


def test_no_auto_discovered_pages_folder():
    """A dashboard/pages folder would let Streamlit list and open pages before the password check."""
    assert not (ROOT / "dashboard" / "pages").exists()
