# Legs pass: bottom garments never keep original (bare skin) pixels inside the trouser zone; skin stays allowed only for shorts/skirts.
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import head_lock  # noqa: E402
import tryon_quality  # noqa: E402

H, W = 640, 400
SKIN = (205, 150, 125)
BG = np.full((H, W, 3), (120, 120, 125), np.uint8)
LEGS = np.zeros((H, W), bool)
LEGS[110:600, 90:180] = True
LEGS[110:600, 220:310] = True
CROP = BG.copy()
CROP[LEGS] = SKIN
ZONE = cv2.dilate((head_lock._skin(CROP) > 0).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
INNER = cv2.erode(LEGS.astype(np.uint8), np.ones((13, 13), np.uint8)) > 0


def _generated_share(colour, force):
    res = BG.copy()
    res[LEGS] = colour
    out, _ = head_lock._pose_composite(CROP, res, None, (0, 0), [], None, force)
    return float((np.abs(out.astype(int) - res.astype(int)).max(axis=2) <= 3)[INNER].mean())


def test_faded_skin_toned_pants_were_dropped_without_force():
    # the bug: a wash close to the skin tone is "unchanged" for the colour-distance rule -> original bare legs come back
    assert _generated_share((215, 180, 150), None) < 0.05


def test_force_uses_generated_pants_everywhere():
    for colour in ((215, 180, 150), (45, 70, 130), (25, 25, 28), (150, 175, 205)):
        assert _generated_share(colour, ZONE.astype(np.uint8) * 255) > 0.99


def test_skin_left_metric_flags_bare_legs_and_ignores_dressed_legs():
    bare = CROP.copy()
    dressed = CROP.copy()
    dressed[LEGS] = (45, 70, 130)
    assert tryon_quality.legs_skin_left(bare, CROP, ZONE) > 0.9
    assert tryon_quality.legs_skin_left(dressed, CROP, ZONE) < 0.05
    # person already in trousers in the photo: nothing to judge
    assert tryon_quality.legs_skin_left(dressed, dressed, ZONE) == -1.0


def test_skin_allowed_only_for_short_garments():
    os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
    os.environ.setdefault("DB_NAME", "test")
    import server
    g = lambda name: [{"category": "bottom", "name": name}]  # noqa: E731
    assert not server._skin_allowed(g("Moorer slim jeans"))
    assert not server._skin_allowed(g("ICON black faded jeans"))
    assert not server._skin_allowed(g("washed bleached acid wash jeans"))
    assert not server._skin_allowed(g("ICON ripped black jeans"))
    assert not server._skin_allowed(g("Jeans strappati"))
    assert not server._skin_allowed(g("distressed destroyed jeans"))
    assert server._skin_allowed(g("ripped denim shorts"))
    assert server._skin_allowed(g("Gonna strappata"))
    assert server._skin_allowed(g("Denim shorts"))
    assert server._bare_legs_by_design(g("Bermuda cotone")) and not server._bare_legs_by_design(g("ripped jeans"))


def test_band_skin_left_keypoint_free_variant():
    dressed = CROP.copy()
    dressed[LEGS] = (45, 70, 130)
    assert tryon_quality.band_skin_left(CROP, CROP) > 0.9          # model left the legs bare -> fails
    assert tryon_quality.band_skin_left(CROP, dressed) < 0.05      # dressed -> passes
    assert tryon_quality.band_skin_left(dressed, dressed) == -1.0  # nothing to judge


def test_log_legs_outcome_sink_and_never_raises():
    seen = []
    tryon_quality.metric_sink = seen.append
    tryon_quality.log_legs_outcome("multipass", "pass", skin_left=0.0)
    tryon_quality.metric_sink = lambda ev: 1 / 0
    tryon_quality.log_legs_outcome("multipass", "blocked")  # a broken sink must not break a render
    tryon_quality.metric_sink = None
    assert seen[0]["outcome"] == "pass" and seen[0]["path"] == "multipass"
