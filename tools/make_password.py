"""Create a password hash for the optional dashboard login.

    python tools/make_password.py

Paste the printed line into .streamlit/secrets.toml under [auth] (see secrets.toml.example).
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dashboard"))
from components.auth import hash_password  # noqa: E402

pw = getpass.getpass("New dashboard password (min 10 characters): ")
if len(pw) < 10:
    sys.exit("Too short: use at least 10 characters.")
if pw != getpass.getpass("Repeat it: "):
    sys.exit("Passwords do not match.")
print("\nAdd this to .streamlit/secrets.toml:\n")
print("[auth]")
print(f'password_hash = "{hash_password(pw)}"')
