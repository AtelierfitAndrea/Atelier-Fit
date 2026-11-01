"""Iteration 48: head_lock._match_head_colour (halo fix), QC SUIT hint, shirt-only regression render."""
import os
import sys
import time
import inspect
import numpy as np
import pytest
import requests

sys.path.insert(0, "/app/backend")
import head_lock  # noqa: E402
import tryon_quality  # noqa: E402


def _env_url():
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env_url()).rstrip("/")
API = f"{BASE_URL}/api"
SHIRT_IMG = "/tmp/photo-1596755094514-f87e34085b2c.jpg"


def _scene(bg):
    img = np.full((400, 300, 3), bg, np.uint8)
    img[150:260, 110:190] = (200, 160, 140)  # "face"
    return img


def _mask():
    m = np.zeros((400, 300), np.uint8)
    m[130:280, 95:205] = 255
    return m


# _match_head_colour unit checks
class TestMatchHeadColour:
    def test_warm_shift_is_matched(self):
        canvas, res = _scene((150, 150, 160)), _scene((180, 160, 130))
        out = head_lock._match_head_colour(canvas, res, _mask())[0]
        ring_px = out[100, 150].astype(int)  # background above the head, inside the padded box
        assert np.abs(ring_px - np.array([180, 160, 130])).max() <= 3, ring_px
        assert not np.shares_memory(out, canvas)  # input not mutated

    def test_no_shift_returns_same(self):
        c = _scene((150, 150, 160))
        assert head_lock._match_head_colour(c, c.copy(), _mask())[0] is c

    def test_gain_clipped(self):
        canvas, res = _scene((100, 100, 100)), _scene((250, 20, 100))
        out = head_lock._match_head_colour(canvas, res, _mask())[0]
        px = out[100, 150].astype(int)
        assert px[0] <= 134 and px[1] >= 74

    def test_called_in_finalize_before_blend(self):
        src = inspect.getsource(head_lock.finalize)
        assert src.index("_match_head_colour") < src.index("blendLinear")


# QC suit hint
class TestQcSuitHint:
    def test_render_adds_suit_hint(self):
        src = inspect.getsource(tryon_quality.render)
        assert "SUIT — SHIRT TUCKED IN" in src and "TUCKED INSIDE" in src

    def test_prompt_marker_matches_server_rule(self):
        import server
        assert "SUIT — SHIRT TUCKED IN" in server._tuck_rule([{"category": "suit"}])


# e2e shirt-only regression (real Gemini render ~40s)
class TestShirtOnly:
    def test_shirt_render(self):
        if not os.path.exists(SHIRT_IMG):
            pytest.skip("shirt image missing")
        s = requests.Session()
        s.headers.update({"Authorization": "Bearer pending_test_tok"})
        av = s.get(f"{API}/profile/avatar").json()["path"]
        with open(SHIRT_IMG, "rb") as f:
            gp = s.post(f"{API}/upload?kind=garment", files={"file": ("x.jpg", f, "image/jpeg")}).json()["path"]
        r = s.post(f"{API}/tryon/generate", json={"person_path": av, "garment_path": gp})
        assert r.status_code == 200, r.text
        job, t0 = r.json()["job_id"], time.time()
        while time.time() - t0 < 300:
            g = s.get(f"{API}/render-jobs/{job}")
            if g.json()["status"] != "running":
                break
            time.sleep(4)
        assert g.json()["status"] == "done", g.text
        tid = g.json()["result"]["id"]
        t = s.get(f"{API}/tryons/{tid}").json()
        assert t["garment_category"] == "top"
        img = s.get(f"{API}/files/{t['result_path']}")
        assert img.status_code == 200
        open("/tmp/shirt48.jpg", "wb").write(img.content)
        print("SHIRT TRYON", tid)
