"""Player cards — collectible-style cards with an overall rating, six attributes and smooth CSS animation.

Rating (OVR) = the player's CRICQ Score, rounded (50 = average regular player, 70+ elite, 80+ icon).
Attributes are percentiles (1-99) among ranked players in the same discipline:
  batters  PRS pressure quality · LFT lift vs own level · CON consistency · PWR boundary % · SR strike rate · SUR balls per dismissal
  bowlers  PRS pressure quality · LFT lift vs own level · CON consistency · ECO economy · WKT strike rate · DOT dot-ball %
  (all under pressure; for economy and bowling strike rate, lower is better)

Photos: CRICQ ships no player photos. Put an image you have the right to use in the  Player Image  folder,
named after the player: viratkohliimage.jpg (also .jpeg, .png, .webp, or a .pdf containing the picture; up to
15 MB). The folder holds a placeholder PDF per ranked player with the exact name to use. Without a photo the
card shows an animated monogram.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from . import pictograms, theme

PHOTO_DIRS = [theme.ROOT / "Player Image", theme.ROOT / "assets" / "players"]
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_BYTES = 15 * 1024 * 1024
ATTRS = {
    "bat": [
        ("PRS", "quality", True, "Pressure quality"),
        ("LFT", "lift", True, "Lift vs own level"),
        ("CON", "consistency", True, "Consistency"),
        ("PWR", "p_bnd_pct", True, "Boundary % under pressure"),
        ("SR", "p_sr", True, "Strike rate under pressure"),
        ("SUR", "p_bpd", True, "Balls per dismissal under pressure"),
    ],
    "bowl": [
        ("PRS", "quality", True, "Pressure quality"),
        ("LFT", "lift", True, "Lift vs own level"),
        ("CON", "consistency", True, "Consistency"),
        ("ECO", "p_econ", False, "Economy under pressure"),
        ("WKT", "p_sr", False, "Balls per wicket under pressure"),
        ("DOT", "p_dot_pct", True, "Dot-ball % under pressure"),
    ],
}
POS = {
    "Opener": "OPN",
    "Top order": "TOP",
    "Middle / finisher": "FIN",
    "Lower order": "LOW",
    "Powerplay specialist": "PP",
    "Middle overs": "MID",
    "Death specialist": "DTH",
}


def key_of(text: str) -> str:
    """'Virat Kohli' → 'viratkohli'; 'viratkohliimage.pdf' / 'Virat-Kohli Image.jpg' → 'viratkohli'."""
    k = re.sub(r"[^a-z0-9]", "", str(text).lower())
    return k[: -len("image")] if k.endswith("image") and len(k) > len("image") else k


def file_name(name: str, ext: str = ".jpg") -> str:
    """The file name the dashboard looks for, e.g. 'viratkohliimage.jpg'."""
    return f"{key_of(name)}image{ext}"


@st.cache_data(show_spinner=False)
def _photo_index() -> dict:
    """{key: path} for every photo in 'Player Image/' (and the older assets/players/). Images beat PDFs."""
    out: dict[str, str] = {}
    for d in reversed(PHOTO_DIRS):  # 'Player Image' wins over assets/players
        if not d.exists():
            continue
        files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT | {".pdf"}]
        for p in sorted(files, key=lambda p: p.suffix.lower() == ".pdf", reverse=True):  # PDFs first, images override
            if p.stat().st_size <= MAX_BYTES:
                out[key_of(p.stem)] = str(p)
    return out


def _image_bytes(path: Path) -> bytes | None:
    """Raw image bytes: the file itself, or the largest picture inside a PDF (None for a placeholder PDF)."""
    if path.suffix.lower() != ".pdf":
        return path.read_bytes()
    try:
        from pypdf import PdfReader

        best = None
        for page in PdfReader(str(path)).pages[:2]:
            for im in page.images:
                if best is None or len(im.data) > len(best):
                    best = im.data
        return best
    except Exception:  # damaged or unusual PDF: fall back to the monogram
        return None


@st.cache_data(show_spinner=False)
def _data_uri(path: str, mtime: float) -> str | None:
    """Square-cropped, 360 px JPEG as a data URI (keeps pages light even with big photos)."""
    import io

    from PIL import Image, ImageOps

    raw = _image_bytes(Path(path))
    if not raw:
        return None
    try:
        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im).convert("RGB")
        w, h = im.size
        side = min(w, h)
        top = max(0, int((h - side) * 0.2))  # keep faces: crop nearer the top for portrait photos
        im = im.crop(((w - side) // 2, top, (w - side) // 2 + side, top + side)).resize((360, 360), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=86)
    except Exception:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def photo(pid, name) -> str | None:
    idx = _photo_index()
    for key in (key_of(name), str(pid)):
        if key in idx:
            p = Path(idx[key])
            return _data_uri(str(p), p.stat().st_mtime)
    return None


@st.cache_data(show_spinner=False)
def attribute_table(t: pd.DataFrame, role: str) -> pd.DataFrame:
    """Percentile (1-99) of each attribute among ranked/eligible players of this discipline."""
    base = t[t.eligible]
    out = pd.DataFrame(index=t.index)
    for code, col, higher, _ in ATTRS[role]:
        ref = base[col].dropna()
        vals = t[col]
        if not len(ref):
            out[code] = 50
            continue
        pct = vals.apply(lambda v, r=ref: (r < v).mean() if pd.notna(v) else 0.5)
        if not higher:
            pct = 1 - pct
        out[code] = (1 + pct * 98).round().astype(int)
    return out


def tier(ovr: int) -> tuple[str, str]:
    if ovr >= 80:
        return "icon", "ICON"
    if ovr >= 70:
        return "elite", "ELITE"
    if ovr >= 60:
        return "rare", "RARE"
    return "base", "BASE"


def _initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", str(name)) if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def _fmt(v, nd=1, suffix=""):
    return "—" if v is None or pd.isna(v) else f"{v:.{nd}f}{suffix}"


def _back_rows(r, role):
    """(label, pressure value, normal value, better-when-higher) for the back of the card."""
    if role == "bat":
        return [
            ("Strike rate", r.get("p_sr"), r.get("n_sr"), True, 0),
            ("Balls / out", r.get("p_bpd"), r.get("n_bpd"), True, 1),
            ("Boundary %", r.get("p_bnd_pct"), r.get("n_bnd_pct"), True, 1),
            ("Dot %", r.get("p_dot_pct"), r.get("n_dot_pct"), False, 1),
        ]
    return [
        ("Economy", r.get("p_econ"), r.get("n_econ"), False, 2),
        ("Balls / wkt", r.get("p_sr"), r.get("n_sr"), False, 1),
        ("Dot %", r.get("p_dot_pct"), r.get("n_dot_pct"), True, 1),
        ("Boundary %", r.get("p_bnd_pct"), r.get("n_bnd_pct"), False, 1),
    ]


def card_html(r, role: str, attrs: dict, delay: float = 0.0, compact: bool = False) -> str:
    """One flip card (click to turn it over). Every data-derived string is escaped."""
    ovr = int(max(1, min(99, round(float(r.clutch_score)))))
    tcls, tname = tier(ovr)
    pos = POS.get(str(r.role), "—")
    style = "PACE" if r.get("pace_spin") == "Pace" else "SPIN" if r.get("pace_spin") == "Spin" else ""
    if role == "bat":
        style = "LHB" if r.get("bat_hand") == "LHB" else "RHB"
    rank = f"#{int(r['rank'])}" if pd.notna(r.get("rank")) else ""
    img = photo(r.player_id, r.display_name)
    face = (
        f'<img src="{img}" alt="{theme.esc(r.display_name)}">'
        if img
        else f'<span class="pic">{pictograms.for_player(role, r.get("pace_spin"))}</span>'
    )
    team = theme.esc(theme.short(r.team_label) if pd.notna(r.team_label) else "—")
    tests = int(r.get("top10_in_variants", 0) or 0)
    bars = "".join(
        f'<div class="at" title="{theme.esc(lab)}"><span class="k">{code}</span><span class="v">{attrs[code]}</span>'
        f'<i style="--w:{attrs[code]}%;--d:{delay + 0.35 + i * 0.07:.2f}s"></i></div>'
        for i, (code, _, _, lab) in enumerate(ATTRS[role])
    )
    back = ""
    for lab, pv, nv, higher, nd in _back_rows(r, role):
        good = None if pv is None or nv is None or pd.isna(pv) or pd.isna(nv) else (pv >= nv) == higher
        tone = "" if good is None else (" up" if good else " down")
        arrow = "" if good is None else ("▲" if good else "▼")
        back += (
            f'<div class="br"><span class="bl">{lab}</span><span class="bv"><span class="bp{tone}">{_fmt(pv, nd)}{arrow}</span>'
            f'<span class="bn">vs {_fmt(nv, nd)}</span></span></div>'
        )
    lo, hi = r.get("score_lo"), r.get("score_hi")
    rng = f"{lo:.0f}–{hi:.0f}" if pd.notna(lo) and pd.notna(hi) else "—"
    p_balls = int(r.get("p_balls", 0) or 0)
    p_matches = int(r.get("p_matches", 0) or 0)
    sparks = (
        '<span class="sp s1"></span><span class="sp s2"></span><span class="sp s3"></span>' if tcls == "icon" else ""
    )
    return f"""
<div class="cq-flip" tabindex="0" title="Click to flip" style="--delay:{delay:.2f}s">
 <div class="cq-in">
  <div class="cq-card {tcls}{" compact" if compact else ""}">
   <div class="sheen"></div>{sparks}
   <div class="top">
    <div class="ovr"><span class="num" style="--to:{ovr};--d:{delay + 0.15:.2f}s"></span><span class="pos">{pos}</span>
      <span class="sty">{theme.esc(style)}</span></div>
    <div class="right"><span class="tier">{tname}</span><span class="rk">{rank}</span></div>
   </div>
   <div class="face">{face}</div>
   <div class="nm">{theme.esc(r.display_name)}</div>
   <div class="tm">{team} · {theme.esc(r.role)}</div>
   <div class="ats">{bars}</div>
   <div class="ft"><span>Clutch {float(r.clutch_score):.1f}</span><span class="flip-hint">tap to flip ↻</span></div>
  </div>
  <div class="cq-card back {tcls}">
   <div class="bh"><span class="bt">{theme.esc(r.display_name)}</span><span class="tier">{ovr}</span></div>
   <div class="bs">Under pressure <span>vs normal</span></div>
   {back}
   <div class="bx"><div><b>{p_balls}</b><span>pressure balls</span></div><div><b>{p_matches}</b><span>matches</span></div>
     <div><b>{rng}</b><span>90% range</span></div><div><b>{tests}/10</b><span>tests</span></div></div>
   <div class="ft"><span>{team}</span><span class="flip-hint">tap to flip back ↻</span></div>
  </div>
 </div>
</div>"""


CSS = f"""
<style>
@property --n {{ syntax: '<integer>'; initial-value: 0; inherits: false; }}
@property --a {{ syntax: '<angle>'; initial-value: 0deg; inherits: false; }}
@keyframes cqCount {{ from {{ --n: 0; }} to {{ --n: var(--to); }} }}
@keyframes cqCardIn {{ from {{ opacity: 0; transform: translateY(34px) scale(.94) rotateX(12deg); filter: blur(4px); }}
                      to {{ opacity: 1; transform: none; filter: none; }} }}
@keyframes cqFill {{ from {{ width: 0; }} to {{ width: var(--w); }} }}
@keyframes cqSheen {{ 0% {{ transform: translateX(-140%) rotate(18deg); }} 55%,100% {{ transform: translateX(260%) rotate(18deg); }} }}
@keyframes cqSpin {{ to {{ --a: 360deg; }} }}
@keyframes cqOrbit {{ to {{ transform: rotate(360deg); }} }}
@keyframes cqFloat {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-5px); }} }}
@keyframes cqBreath {{ 0%,100% {{ opacity: .45; transform: scale(.92); }} 50% {{ opacity: .9; transform: scale(1.06); }} }}
@keyframes cqTwinkle {{ 0%,100% {{ opacity: 0; transform: scale(.3) rotate(0); }} 50% {{ opacity: 1; transform: scale(1) rotate(45deg); }} }}
@keyframes cqGoldText {{ 0% {{ background-position: 0% 50%; }} 100% {{ background-position: 200% 50%; }} }}

.cq-flip {{ perspective: 1200px; outline: none; cursor: pointer; margin-bottom: 10px;
  animation: cqCardIn .8s cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--delay); }}
.cq-in {{ display: grid; transition: transform .8s cubic-bezier(.3,1.25,.4,1); transform-style: preserve-3d; }}
.cq-flip:hover .cq-in {{ transform: rotateX(6deg) rotateY(-8deg) translateY(-8px) scale(1.025); }}
.cq-flip:focus .cq-in, .cq-flip:focus:hover .cq-in {{ transform: rotateY(180deg); }}
.cq-in > .cq-card {{ grid-area: 1 / 1; backface-visibility: hidden; -webkit-backface-visibility: hidden; }}
.cq-in > .cq-card.back {{ transform: rotateY(180deg); }}

/* card body: foil border (rotating conic gradient) around a patterned face */
.cq-card {{ --c1: {theme.NEUTRAL}; --c2: {theme.ROYAL}; --c3: #8FA2D8; --glow: rgba(79,143,230,.25);
  position: relative; overflow: hidden; border-radius: 20px; padding: 14px 14px 12px; color: {theme.TEXT};
  font-family: Inter, 'Segoe UI', sans-serif; border: 2px solid transparent;
  background:
    radial-gradient(130% 70% at 50% -10%, color-mix(in srgb, var(--c2) 70%, transparent) 0%, transparent 60%) padding-box,
    repeating-linear-gradient(135deg, rgba(255,255,255,.035) 0 2px, transparent 2px 9px) padding-box,
    linear-gradient(180deg, #172457, #0C1535) padding-box,
    conic-gradient(from var(--a), var(--c1), var(--c2), var(--c3), var(--c1)) border-box;
  box-shadow: 0 10px 28px rgba(0,0,0,.35); transition: box-shadow .4s; }}
.cq-flip:hover .cq-card {{ animation: cqSpin 3s linear infinite; box-shadow: 0 24px 50px rgba(0,0,0,.5), 0 0 34px var(--glow); }}
.cq-card.icon  {{ --c1: #FFE29A; --c2: #C8871B; --c3: #FFF6D6; --glow: rgba(245,184,61,.45);
  animation: cqSpin 4s linear infinite; box-shadow: 0 12px 34px rgba(0,0,0,.4), 0 0 26px rgba(245,184,61,.28); }}
.cq-card.elite {{ --c1: {theme.PINK}; --c2: #7A1D8C; --c3: #FF8FC6; --glow: rgba(234,26,133,.4); }}
.cq-card.rare  {{ --c1: {theme.BLUE}; --c2: {theme.ROYAL}; --c3: #9CC2FF; --glow: rgba(79,143,230,.4); }}
.cq-card .sheen {{ position: absolute; top: -40%; left: 0; width: 40%; height: 180%; pointer-events: none; z-index: 3;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.18), transparent); transform: translateX(-140%) rotate(18deg); }}
.cq-flip:hover .sheen, .cq-card.icon .sheen {{ animation: cqSheen 2.8s ease-in-out infinite; }}
.cq-card .sp {{ position: absolute; width: 9px; height: 9px; z-index: 2; pointer-events: none;
  background: radial-gradient(circle, #FFF6D6 0 20%, transparent 21%), linear-gradient(#FFE29A, #FFE29A) center/100% 2px no-repeat,
              linear-gradient(#FFE29A, #FFE29A) center/2px 100% no-repeat; animation: cqTwinkle 2.4s ease-in-out infinite; }}
.cq-card .s1 {{ top: 74px; left: 22px; }} .cq-card .s2 {{ top: 46px; right: 64px; animation-delay: .8s; }}
.cq-card .s3 {{ top: 150px; right: 26px; animation-delay: 1.6s; }}

.cq-card .top {{ display: flex; justify-content: space-between; align-items: flex-start; position: relative; z-index: 1; }}
.cq-card .ovr {{ display: flex; flex-direction: column; line-height: 1; }}
.cq-card .num {{ font-size: 2.8rem; font-weight: 900; letter-spacing: -1.5px; counter-reset: n var(--n);
  animation: cqCount 1.4s cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d); --n: var(--to); }}
.cq-card .num::after {{ content: counter(n); }}
.cq-card.icon .num {{ background: linear-gradient(90deg, #FFE29A, #F5B83D, #FFF6D6, #F5B83D, #FFE29A); background-size: 200% 100%;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: cqCount 1.4s cubic-bezier(.2,.8,.2,1) both, cqGoldText 3s linear infinite; animation-delay: var(--d), 0s; }}
.cq-card.elite .num {{ color: {theme.PINK_TEXT}; text-shadow: 0 0 18px rgba(234,26,133,.45); }}
.cq-card.rare .num {{ color: #B9D1FA; }}
.cq-card .pos {{ font-size: .8rem; font-weight: 800; letter-spacing: 1.5px; margin-top: 4px; }}
.cq-card .sty {{ font-size: .68rem; font-weight: 700; letter-spacing: 1px; color: {theme.TEXT2}; margin-top: 3px; }}
.cq-card .right {{ display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }}
.cq-card .tier {{ font-size: .62rem; font-weight: 800; letter-spacing: 2px; padding: 3px 9px; border-radius: 999px;
  background: rgba(255,255,255,.08); color: {theme.TEXT2}; border: 1px solid rgba(255,255,255,.08); }}
.cq-card.icon .tier {{ background: rgba(245,184,61,.16); color: {theme.GOLD}; border-color: rgba(245,184,61,.4); }}
.cq-card.elite .tier {{ background: rgba(234,26,133,.18); color: #F7A8CF; border-color: rgba(234,26,133,.4); }}
.cq-card.rare .tier {{ background: rgba(79,143,230,.16); color: #B9D1FA; border-color: rgba(79,143,230,.35); }}
.cq-card .rk {{ font-size: 1.1rem; font-weight: 900; color: {theme.TEXT2}; }}

.cq-card .face {{ position: relative; width: 118px; height: 118px; margin: 0 auto 8px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; }}
.cq-card .face::before {{ content: ""; position: absolute; inset: -5px; border-radius: 50%;
  background: conic-gradient(var(--c1), var(--c2), var(--c3), var(--c1)); animation: cqOrbit 7s linear infinite; }}
.cq-card .face::after {{ content: ""; position: absolute; inset: 0; border-radius: 50%;
  background: radial-gradient(circle at 50% 35%, #2B3F8C 0%, #121C47 70%); box-shadow: inset 0 0 22px rgba(0,0,0,.55); }}
.cq-card .face img {{ position: relative; z-index: 1; width: 110px; height: 110px; border-radius: 50%; object-fit: cover; }}
.cq-card .face .pic {{ position: relative; z-index: 1; width: 92px; height: 92px; color: {theme.TEXT};
  animation: cqFloat 3.6s ease-in-out infinite; filter: drop-shadow(0 4px 10px rgba(0,0,0,.45)); }}
.cq-card .face .pic::before {{ content: ""; position: absolute; inset: 8px; border-radius: 50%; z-index: -1;
  background: radial-gradient(circle, var(--glow), transparent 70%); animation: cqBreath 3.6s ease-in-out infinite; }}
.cq-card.icon .face .pic {{ color: #FFE9B0; }}
.cq-card .pg {{ width: 100%; height: 100%; display: block; }}

.cq-card .nm {{ text-align: center; font-weight: 800; font-size: .98rem; line-height: 1.2; min-height: 2.4em;
  display: flex; align-items: center; justify-content: center; overflow-wrap: anywhere; position: relative; z-index: 1; }}
.cq-card .tm {{ text-align: center; color: {theme.TEXT2}; font-size: .74rem; margin: 2px 0 10px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }}
.cq-card .ats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 7px 12px; margin-bottom: 10px; }}
.cq-card .at {{ position: relative; display: flex; justify-content: space-between; font-size: .8rem; padding-bottom: 5px; }}
.cq-card .at .k {{ color: {theme.TEXT2}; font-weight: 700; letter-spacing: .8px; }}
.cq-card .at .v {{ font-weight: 800; }}
.cq-card .at::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px; border-radius: 2px; background: rgba(255,255,255,.08); }}
.cq-card .at i {{ position: absolute; left: 0; bottom: 0; height: 3px; border-radius: 2px; width: var(--w); z-index: 1;
  background: linear-gradient(90deg, var(--c2), var(--c1), var(--c3)); box-shadow: 0 0 8px var(--glow);
  animation: cqFill 1.1s cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d); }}
.cq-card.base .at i {{ background: linear-gradient(90deg, {theme.PINK}, {theme.GOLD}); }}
.cq-card {{ display: flex; flex-direction: column; }}
.cq-card .ft {{ display: flex; justify-content: space-between; margin-top: auto; padding-top: 8px; font-size: .72rem;
  color: {theme.MUTED}; border-top: 1px solid rgba(255,255,255,.08); }}
.cq-card .flip-hint {{ opacity: .75; transition: opacity .3s, color .3s; }}
.cq-flip:hover .flip-hint {{ opacity: 1; color: {theme.PINK_TEXT}; }}

/* back of the card */
.cq-card.back {{ display: flex; flex-direction: column; }}
.cq-card.back .bh {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
.cq-card.back .bt {{ font-weight: 800; font-size: .95rem; line-height: 1.2; }}
.cq-card.back .bs {{ color: {theme.TEXT2}; font-size: .66rem; margin: 4px 0 8px; letter-spacing: 1.2px; text-transform: uppercase; }}
.cq-card.back .br {{ display: flex; justify-content: space-between; align-items: baseline; gap: 6px; font-size: .76rem;
  padding: 7px 0; border-bottom: 1px dashed rgba(255,255,255,.08); white-space: nowrap; }}
.cq-card.back .bv {{ display: inline-flex; align-items: baseline; gap: 5px; }}
.cq-card.back .bs span {{ color: {theme.MUTED}; }}
.cq-card.back .bl {{ color: {theme.TEXT2}; }}
.cq-card.back .bp {{ font-weight: 800; text-align: right; }}
.cq-card.back .bp.up {{ color: {theme.GOOD}; }} .cq-card.back .bp.down {{ color: {theme.BAD}; }}
.cq-card.back .bn {{ color: {theme.MUTED}; font-size: .68rem; }}
.cq-card.back .bx {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 12px 0 4px; }}
.cq-card.back .bx div {{ background: rgba(255,255,255,.05); border-radius: 10px; padding: 6px 4px; text-align: center; }}
.cq-card.back .bx b {{ display: block; font-size: .95rem; white-space: nowrap; }}
.cq-card.back .bx span {{ font-size: .64rem; color: {theme.TEXT2}; letter-spacing: .4px; }}
.cq-card.back .ft {{ margin-top: auto; }}

.cq-card.compact .face {{ width: 96px; height: 96px; }}
.cq-card.compact .face img {{ width: 88px; height: 88px; }}
.cq-card.compact .face .pic {{ width: 74px; height: 74px; }}
@media (prefers-reduced-motion: reduce) {{
  .cq-flip, .cq-flip *, .cq-card, .cq-card * {{ animation: none !important; transition: none !important; }}
  .cq-card .num {{ --n: var(--to); }}
}}
</style>"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def grid(t: pd.DataFrame, role: str, rows: pd.DataFrame, per_row: int = 5, buttons: bool = True, key: str = "g"):
    """Render cards in rows of `per_row`, each with an 'Open profile' button."""
    inject_css()
    at = attribute_table(t, role)
    rows = rows.reset_index()
    for start in range(0, len(rows), per_row):
        cols = st.columns(per_row, gap="medium")
        for j, (_, r) in enumerate(rows.iloc[start : start + per_row].iterrows()):
            a = at.loc[r["index"]].to_dict()
            with cols[j]:
                st.markdown(card_html(r, role, a, delay=0.06 * j + 0.04 * (start // per_row)), unsafe_allow_html=True)
                if buttons and st.button(
                    "Open profile",
                    key=f"{key}_{role}_{int(r.player_id)}",
                    icon=":material/arrow_outward:",
                    use_container_width=True,
                ):
                    st.session_state.pl_role = "Batter" if role == "bat" else "Bowler"
                    st.session_state.pl_pid = int(r.player_id)
                    st.switch_page("views/player.py")
