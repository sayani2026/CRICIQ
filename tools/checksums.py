"""Write CHECKSUMS.sha256 for every file in the project (excluding secrets and caches)."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"CHECKSUMS.sha256", "secrets.toml"}
lines = []
for p in sorted(ROOT.rglob("*")):
    rel = p.relative_to(ROOT).as_posix()
    if (
        not p.is_file()
        or p.name in SKIP
        or "__pycache__" in rel
        or ".pytest_cache" in rel
        or ".ruff_cache" in rel
        or rel.startswith("Player Image/")  # your photos: expected to change
        or p.suffix == ".zip"
        or (rel.startswith("data/raw/") and p.suffix == ".csv")
    ):
        continue
    lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}")
(ROOT / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote CHECKSUMS.sha256 ({len(lines)} files)")
