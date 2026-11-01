# Surgical FASHN try-on: synthetic unit tests for head_lock._pose_composite (chin/bib fix, hand-skin lock, no-new-skin)
# and offline checks of the owner gating / one-submit / no-retry / 422 rules. NEVER calls the real engine.
import asyncio
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import head_lock  # noqa: E402
import fashn  # noqa: E402

SKIN_A = (224, 172, 140)   # original skin
SKIN_B = (190, 140, 110)   # generated skin (different shade, still skin)
BG = (200, 200, 200)
BLACK = (15, 15, 15)
H, W = 1000, 800
FACE = (350, 150, 100, 130)  # fx, fy, fw, fh
FX, FY, FW, FH = FACE
CX = FX + FW // 2


def _px(img, y, x):
    return img[y, x].astype(int)


def _close(a, b, tol=6):
    return np.abs(np.asarray(a, int) - np.asarray(b, int)).max() <= tol


@pytest.fixture
def scene():
    canvas = np.full((H, W, 3), BG, np.uint8)
    canvas[FY:FY + FH, FX:FX + FW] = SKIN_A                 # face
    canvas[FY + FH:FY + FH + 60, CX - 40:CX + 40] = SKIN_A   # neck/upper chest under the chin (bare)
    canvas[FY + FH + 60:700, 250:550] = SKIN_A               # bare torso
    canvas[450:560, 420:520] = SKIN_A                        # hand on the chest (same colour as chest)
    res = canvas.copy()
    res[FY:FY + FH, FX:FX + FW] = (120, 90, 80)              # model changed the face -> must stay original
    res[FY + FH:FY + FH + 60, CX - 40:CX + 40] = BLACK       # new collar right under the chin
    res[FY + FH + 60:700, 250:550] = BLACK                   # new black t-shirt
    res[450:560, 420:520] = SKIN_B                           # generated hand (slightly different)
    # ghost hair beside the head (above the chin, outside the head ellipse)
    res[FY + 20:FY + 80, FX + FW + 20:FX + FW + 60] = (60, 50, 40)
    return canvas, res


def _freeze_hand():
    # hand box with top_free -1 + global no-new-skin box
    return [(420, 450, 520, 560, -1.0), (0, 0, W, H, 1.0)]


class TestPoseCompositeSynthetic:
    def test_face_stays_original(self, scene):
        canvas, res = scene
        out, _ = head_lock._pose_composite(canvas, res, FACE, (0, 0), _freeze_hand())
        # up to 0.90fh fully original (transition to the result is a ~3px blur around 0.98fh = chin)
        y1 = int(FY + 0.90 * FH)
        assert np.abs(out[FY + 5:y1, FX + 10:FX + FW - 10].astype(int) - canvas[FY + 5:y1, FX + 10:FX + FW - 10]).max() <= 1

    def test_below_chin_takes_result(self, scene):
        canvas, res = scene
        out, _ = head_lock._pose_composite(canvas, res, FACE, (0, 0), _freeze_hand())
        # fy + 1.05fh: inside the OLD ellipse (ended at fy+1.10fh), outside the new one (fy+0.98fh)
        y = int(FY + 1.05 * FH)
        assert _close(_px(out, y, CX), BLACK, 20), f"bib: {_px(out, y, CX)}"
        y2 = int(FY + 1.25 * FH)
        assert _close(_px(out, y2, CX), BLACK, 6)

    def test_ghost_hair_beside_head_locked(self, scene):
        canvas, res = scene
        out, _ = head_lock._pose_composite(canvas, res, FACE, (0, 0), _freeze_hand())
        assert _close(_px(out, FY + 50, FX + FW + 40), BG, 4)

    def test_hand_skin_locked_chest_not_pasted(self, scene):
        canvas, res = scene
        out, _ = head_lock._pose_composite(canvas, res, FACE, (0, 0), _freeze_hand())
        assert _close(_px(out, 505, 470), SKIN_A, 4), "hand must be original pixels"
        # inside the hand box (with padding) but outside the hand: chest skin in original, tee in result -> tee
        assert _close(_px(out, 448, 470), BLACK, 40) or _close(_px(out, 445, 470), BLACK, 10)
        assert _close(_px(out, 600, 300), BLACK, 4)

    def test_old_behaviour_top_free_zero_would_paste_rectangle(self, scene):
        # Sanity: a top_free 0 box freezes the whole box (the old chest rectangle bug) - confirms test sensitivity.
        canvas, res = scene
        pad_canvas = canvas.copy()
        pad_canvas[430:450, 420:520] = SKIN_A
        out, _ = head_lock._pose_composite(pad_canvas, res, FACE, (0, 0), [(400, 430, 540, 580, 0.0)])
        assert _close(_px(out, 435, 410), SKIN_A, 4)
        out2, _ = head_lock._pose_composite(pad_canvas, res, FACE, (0, 0), [(400, 430, 540, 580, -1.0)])
        assert _close(_px(out2, 435, 410), BLACK, 10)

    def test_held_phone_inside_hand_box_kept(self, scene):
        # Rule "only clothing changes": a phone (non-skin) held in the hand box must keep original pixels.
        canvas, res = scene
        canvas, res = canvas.copy(), res.copy()
        canvas[400:500, 440:480] = (120, 90, 50)   # brown phone over chest, partly above the hand
        res[400:450, 440:480] = BLACK              # model paints the tee over the lower part of the phone
        out, _ = head_lock._pose_composite(canvas, res, FACE, (0, 0), [(420, 395, 520, 560, -1.0), (0, 0, W, H, 1.0)])
        assert _close(_px(out, 430, 460), (120, 90, 50), 10), f"phone overwritten by garment: {_px(out, 430, 460)}"


    def test_no_new_skin_holes(self, scene):
        canvas, res = scene
        canvas = canvas.copy()
        canvas[FY + FH + 60:700, 250:550] = (40, 40, 120)  # original wears a blue shirt
        canvas[450:560, 420:520] = SKIN_A
        res = res.copy()
        res[600:680, 300:400] = SKIN_B                      # model opens a skin hole in the new tee
        out, _ = head_lock._pose_composite(canvas, res, FACE, (0, 0), _freeze_hand())
        assert _close(_px(out, 640, 350), (40, 40, 120), 4), "new bare skin must not appear"
        assert _close(_px(out, 620, 500), BLACK, 4)


class TestGatingAndEngine:
    def test_non_owner_gets_no_surgical(self):
        import server
        u = server.User(user_id="x", email="nobody@example.com", name="n", account_id="x") if "account_id" in server.User.model_fields else server.User(user_id="x", email="nobody@example.com", name="n")
        assert server._owner_extra(u, True) == ""
        assert server._owner_extra(u, False) == ""

    def test_owner_gets_surgical(self):
        import server
        owner = [e.strip() for e in os.environ["OWNER_EMAILS"].split(",") if e.strip()][0]
        kw = dict(user_id="x", email=owner.upper(), name="n")
        if "account_id" in server.User.model_fields:
            kw["account_id"] = "x"
        u = server.User(**kw)
        assert server.SURGICAL_RULE in server._owner_extra(u, False)

    def test_fashn_single_submit_no_retry_on_error(self, monkeypatch):
        calls = {"post": 0}

        class R:
            status_code = 500
            text = "boom"

        def post(*a, **k):
            calls["post"] += 1
            return R()
        monkeypatch.setattr(fashn.requests, "post", post)
        with pytest.raises(fashn.TryOnError):
            fashn.tryon(b"x", b"y", "top")
        assert calls["post"] == 1

    def test_fashn_402_insufficient(self, monkeypatch):
        class R:
            status_code = 402
            text = ""
        monkeypatch.setattr(fashn.requests, "post", lambda *a, **k: R())
        with pytest.raises(fashn.InsufficientCredits):
            fashn.tryon(b"x", b"y", "top")

    def test_fashn_untrusted_queue_url(self, monkeypatch):
        class R:
            status_code = 200
            text = ""
            def json(self):
                return {"status_url": "https://evil.com/x", "response_url": "https://evil.com/y"}
        monkeypatch.setattr(fashn.requests, "post", lambda *a, **k: R())
        with pytest.raises(fashn.TryOnError):
            fashn.tryon(b"x", b"y", "top")

    def test_fashn_render_422_shoes_bag_only(self, monkeypatch):
        import server
        from fastapi import HTTPException
        called = {"n": 0}
        monkeypatch.setattr(fashn, "tryon", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
        with pytest.raises(HTTPException) as e:
            asyncio.run(server._fashn_render("u", "p", [("g1", "shoes"), ("g2", "bag")], ["shoes", "bag"]))
        assert e.value.status_code == 422
        assert called["n"] == 0

    def test_fashn_render_one_call_per_garment_and_error_maps_502(self, monkeypatch):
        import server
        from fastapi import HTTPException
        n = {"tryon": 0, "put": 0}
        monkeypatch.setattr(server, "get_object", lambda p: (b"img", "image/jpeg"))
        monkeypatch.setattr(server, "put_object", lambda *a, **k: n.__setitem__("put", n["put"] + 1))

        async def hi(*a, **k):
            return {"boxes": [], "phone": [], "lower": None, "shoes": None}
        monkeypatch.setattr(server, "_hand_info", hi)
        monkeypatch.setattr(head_lock, "downscale", lambda b, s: b)

        def boom(*a, **k):
            n["tryon"] += 1
            raise fashn.TryOnError("x")
        monkeypatch.setattr(fashn, "tryon", boom)
        with pytest.raises(HTTPException) as e:
            asyncio.run(server._fashn_render("u", "p", [("g1", "top"), ("g2", "bottom")], ["top", "bottom"]))
        assert e.value.status_code == 502
        assert n["tryon"] == 1 and n["put"] == 0

    def test_fashn_poll_http_error_is_not_tryon_error(self, monkeypatch):
        # Code review probe: a 5xx on the STATUS poll raises requests.HTTPError (not TryOnError) -> generic 500 upstream.
        import requests as rq

        class P:
            status_code = 200
            text = ""
            def json(self):
                return {"status_url": fashn.QUEUE_BASE + "/s", "response_url": fashn.QUEUE_BASE + "/r"}

        class S:
            status_code = 503
            def raise_for_status(self):
                raise rq.HTTPError("503")
        monkeypatch.setattr(fashn.requests, "post", lambda *a, **k: P())
        monkeypatch.setattr(fashn.requests, "get", lambda *a, **k: S())
        with pytest.raises(Exception) as e:
            fashn.tryon(b"x", b"y", "top", timeout_s=5)
        print("poll error type:", type(e.value).__name__)
        assert isinstance(e.value, fashn.TryOnError), "status-poll HTTP error escapes as requests.HTTPError -> 500 instead of 502"
