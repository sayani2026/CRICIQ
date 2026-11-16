"""Player cards: rating, tiers, attribute percentiles, escaping and the photo slot."""

import pandas as pd

from dashboard.components import cards


def _t():
    return pd.DataFrame(
        {
            "player_id": [1, 2, 3],
            "display_name": ["<b>Evil</b> Name", "Mid Player", "Low Player"],
            "eligible": [True, True, True],
            "clutch_score": [84.6, 63.0, 41.0],
            "quality": [0.3, 0.2, 0.1],
            "lift": [0.1, 0.0, -0.1],
            "consistency": [0.9, 0.6, 0.4],
            "p_bnd_pct": [25.0, 20.0, 10.0],
            "p_sr": [180.0, 140.0, 110.0],
            "p_bpd": [22.0, 15.0, 9.0],
            "role": ["Middle / finisher", "Opener", "Top order"],
            "bat_hand": ["RHB", "LHB", "RHB"],
            "team_label": ["Royal Challengers Bengaluru", "Mumbai Indians", None],
            "rank": [1.0, 2.0, None],
            "top10_in_variants": [10, 6, 0],
        }
    )


def test_tiers():
    assert cards.tier(85)[0] == "icon" and cards.tier(75)[0] == "elite"
    assert cards.tier(64)[0] == "rare" and cards.tier(41)[0] == "base"


def test_attributes_are_percentiles():
    a = cards.attribute_table.__wrapped__(_t(), "bat")
    assert a.values.min() >= 1 and a.values.max() <= 99
    assert a.loc[0, "PRS"] > a.loc[2, "PRS"]


def test_card_escapes_names_and_shows_rating():
    t = _t()
    a = cards.attribute_table.__wrapped__(t, "bat")
    h = cards.card_html(t.iloc[0], "bat", a.loc[0].to_dict())
    assert "<b>Evil</b>" not in h and "&lt;b&gt;Evil" in h
    assert "--to:85" in h and "ICON" in h and "RCB" in h


def _png(path, color=(200, 30, 120)):
    from PIL import Image

    Image.new("RGB", (40, 60), color).save(path)


def test_photo_names_and_formats(tmp_path, monkeypatch):
    from reportlab.pdfgen import canvas

    monkeypatch.setattr(cards, "PHOTO_DIRS", [tmp_path])
    assert cards.key_of("viratkohliimage.pdf".removesuffix(".pdf")) == "viratkohli"
    assert cards.key_of("Virat Kohli") == "viratkohli" and cards.file_name("Tim David") == "timdavidimage.jpg"
    _png(tmp_path / "midplayerimage.png")
    # a text-only placeholder PDF must not count as a photo
    c = canvas.Canvas(str(tmp_path / "lowplayerimage.pdf"))
    c.drawString(50, 50, "placeholder")
    c.save()
    # a PDF that contains a picture does count
    _png(tmp_path / "pic.png")
    c = canvas.Canvas(str(tmp_path / "evilnameimage.pdf"))
    c.drawImage(str(tmp_path / "pic.png"), 10, 10, 120, 180)
    c.save()
    cards._photo_index.clear()
    cards._data_uri.clear()
    assert cards.photo(2, "Mid Player").startswith("data:image/jpeg;base64,")
    assert cards.photo(3, "Low Player") is None
    assert cards.photo(1, "Evil Name").startswith("data:image/jpeg;base64,")
    cards._photo_index.clear()
    cards._data_uri.clear()
