# Unit: head_lock scene-drift metric (_match_head_colour drift) + DRIFT_MAX + render SCENE_RULE wiring (iteration 55)
import sys, os, inspect
import numpy as np
import cv2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import head_lock
import tryon_quality


def _mask(H=400, W=300):
    m = np.zeros((H, W), np.uint8)
    cv2.ellipse(m, (150, 150), (50, 70), 0, 0, 360, 255, -1)
    return m


def test_same_scene_low_drift():
    rng = np.random.default_rng(0)
    canvas = rng.integers(80, 180, (400, 300, 3), dtype=np.uint8)
    res = np.clip(canvas.astype(int) + 4, 0, 255).astype(np.uint8)
    _c, drift = head_lock._match_head_colour(canvas, res, _mask())
    assert drift < head_lock.DRIFT_MAX


def test_new_scene_high_drift():
    rng = np.random.default_rng(1)
    canvas = rng.integers(0, 255, (400, 300, 3), dtype=np.uint8)
    res = rng.integers(0, 255, (400, 300, 3), dtype=np.uint8)
    _c, drift = head_lock._match_head_colour(canvas, res, _mask())
    assert drift > head_lock.DRIFT_MAX


def test_render_uses_scene_rule_on_drift():
    src = inspect.getsource(tryon_quality.render)
    assert "SCENE_RULE" in src and "DRIFT_MAX" in src
    assert "same background" in tryon_quality.SCENE_RULE
