# Iteration 54: QC phone veto, _fix_prompt phone text, FIX_SYSTEM alignment, _retry_extra phone drop, _paste_hand skin-only, grid desc names
import asyncio
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import server  # noqa: E402
import head_lock  # noqa: E402
import tryon_quality  # noqa: E402


def _fake_chat(reply):
    class C:
        def __init__(self, *a, **k): pass
        def with_model(self, *a): return self
        async def send_message(self, m): return reply
    return C


IMG = head_lock.downscale(__import__("io").BytesIO().getvalue() or b"", 10) if False else None


def _jpeg():
    import io
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (64, 64), (200, 200, 200)).save(b, "JPEG"); return b.getvalue()


# QC: phone veto only when phone removal active
@pytest.mark.parametrize("phone,exp_ok,exp_score", [(True, False, -1), (False, True, 8)])
def test_qc_phone_veto(monkeypatch, phone, exp_ok, exp_score):
    monkeypatch.setattr(tryon_quality, "LlmChat", _fake_chat('{"face_same":true,"hands_ok":true,"garments_ok":true,"phone_present":true,"issues":""}'))
    r = asyncio.run(tryon_quality._qc("AAAA", _jpeg(), "white tee", phone))
    assert r["ok"] is exp_ok and r["score"] == exp_score
    if phone:
        assert "smartphone" in r["issues"]


def test_qc_no_phone_passes(monkeypatch):
    monkeypatch.setattr(tryon_quality, "LlmChat", _fake_chat('{"face_same":true,"hands_ok":false,"garments_ok":true,"phone_present":false,"issues":"bad fingers"}'))
    r = asyncio.run(tryon_quality._qc("AAAA", _jpeg(), "white tee", True))
    assert r["ok"] is False and r["score"] == 6  # phone-free bad fingers beats any phone candidate (-1)


def test_fix_prompt_phone_and_system():
    p = tryon_quality._fix_prompt("hands", "white tee", phone=True)
    assert "NEVER copy the phone" in p and "face identity reference" in p and "NO smartphone" in p
    assert "smartphone" not in tryon_quality._fix_prompt("hands", "white tee", phone=False).split("FIX ONLY")[0]
    assert "never change, add or remove any clothing" not in tryon_quality.FIX_SYSTEM
    assert "FIX list" in tryon_quality.FIX_SYSTEM
    assert "Never invent new garments or shoes" in p and "never copy clothing from IMAGE 2" in p


def test_retry_extra_drops_phone_when_posed():
    posed = server._retry_extra({"preserve_pose": True}, "mani_viso")
    assert "phone held" not in posed and posed.startswith(server.POSE_RULE)
    assert "phone held as in IMAGE 1" in server._retry_extra({"preserve_pose": False}, "mani_viso")


def test_paste_hand_refuses_skin_over_garment():
    # original: skin hand on bare skin; result: same layout but region now white tee (not skin)
    skin = (200, 150, 120)
    canvas = np.full((300, 300, 3), (60, 60, 60), np.uint8)
    canvas[100:200, 100:200] = skin
    canvas[140:160, 120:180] = (90, 40, 30)  # texture for template match
    res = canvas.copy()
    res[100:200, 100:200] = (245, 245, 245)
    res[140:160, 120:180] = (90, 40, 30)
    out = res.copy()
    ok = head_lock._paste_hand(out, canvas, res, (100, 100, 200, 200))
    assert ok is False
    assert (out == res).all()


def test_skin_mask():
    a = np.zeros((2, 2, 3), np.uint8); a[0, 0] = (200, 150, 120); a[1, 1] = (245, 245, 245)
    s = head_lock._skin(a)
    assert s[0, 0] == 255 and s[1, 1] == 0


def test_grid_uses_desc(monkeypatch):
    async def fake_info(p):
        return {"category": "bottom", "desc": "light-blue ripped denim shorts"} if "b" in p else {"category": "top", "desc": "white crew tee"}
    captured = {}

    async def fake_compose(user, pp, items, text, extra):
        captured["items"] = items; captured["extra"] = extra
        return pp, "res"

    async def fake_status(a): return {"is_blocked": False}

    class FakeColl:
        async def insert_one(self, d): captured["doc"] = d
    monkeypatch.setattr(server, "_garment_info", fake_info)
    monkeypatch.setattr(server, "_compose_outfit", fake_compose)
    monkeypatch.setattr(server, "get_subscription_status", fake_status)
    monkeypatch.setattr(server, "_path_owner", lambda p: "u1")
    async def fake_consume(*a): return None
    monkeypatch.setattr(server, "consume_tryon_quota", fake_consume)
    monkeypatch.setattr(server.db, "outfits", FakeColl(), raising=False)
    user = type("U", (), {"user_id": "u1", "account_id": "a1"})()
    req = server.GridOutfitRequest(person_path="p", preserve_pose=True, items=[{"slot": "top", "image_path": "t"}, {"slot": "bottom", "image_path": "b"}])
    try:
        asyncio.run(server._outfit_generate_from_uploads(req, user))
    except Exception:
        pass
    names = {i["slot"]: i["name"] for i in captured["items"]}
    assert names["bottom"] == "light-blue ripped denim shorts" and names["top"] == "white crew tee"
    assert captured["extra"] == server.POSE_RULE
