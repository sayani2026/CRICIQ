"""Optional password protection for the dashboard.

Off by default (local use). To turn it on:
    1. python tools/make_password.py            -> prints a password hash
    2. copy .streamlit/secrets.toml.example to .streamlit/secrets.toml and paste the hash
    3. restart the dashboard
The plain password is never stored: only a salted PBKDF2-SHA256 hash, compared in constant time.
After 5 wrong attempts the form locks for 60 seconds (per browser session).
"""

import base64
import hashlib
import hmac
import time

import streamlit as st

MAX_TRIES, LOCK_SECONDS = 5, 60


def hash_password(password, salt=None, iterations=310_000):
    import os

    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password, stored):
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False


def _configured_hash():
    try:
        return st.secrets.get("auth", {}).get("password_hash")
    except Exception:  # no secrets file -> protection off
        return None


def enabled():
    return bool(_configured_hash())


def require_login():
    """Stop the page until the right password is entered (only when a hash is configured)."""
    stored = _configured_hash()
    if not stored or st.session_state.get("cq_auth_ok"):
        return
    st.markdown("<style>[data-testid='stSidebarNav']{display:none}</style>", unsafe_allow_html=True)
    ss = st.session_state
    ss.setdefault("cq_tries", 0)
    ss.setdefault("cq_locked_until", 0.0)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("### Sign in to CRICQ")
        st.caption("This dashboard is password protected.")
        locked = time.time() < ss.cq_locked_until
        with st.form("cq_login", clear_on_submit=True):
            pw = st.text_input("Password", type="password", disabled=locked)
            ok = st.form_submit_button("Sign in", disabled=locked, use_container_width=True)
        if locked:
            st.error(f"Too many attempts. Try again in {int(ss.cq_locked_until - time.time()) + 1} seconds.")
        elif ok:
            if verify_password(pw or "", stored):
                ss.cq_auth_ok, ss.cq_tries = True, 0
                st.rerun()
            ss.cq_tries += 1
            if ss.cq_tries >= MAX_TRIES:
                ss.cq_locked_until, ss.cq_tries = time.time() + LOCK_SECONDS, 0
            st.error("Wrong password.")
    st.stop()


def logout_button():
    signed_in = enabled() and st.session_state.get("cq_auth_ok")
    if signed_in and st.button("Sign out", icon=":material/logout:", use_container_width=True):
        st.session_state.cq_auth_ok = False
        st.rerun()
