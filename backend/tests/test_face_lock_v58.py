# FACE LOCK iteration 58 retest: face selection by confidence, tightened head lock, pad bands, _align_pose, fix-pass discard, 422 re-raise, grid 400
import asyncio
import base64
import io
import os
import sys

import cv2
import numpy as np
import pytest
import requests
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import head_lock  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
H = {"Authorization": "Bearer pending_test_tok"}
POSE = "/tmp/owner_pose.jpg"  # owner b1a48272 (poster face in background)
STREET = "/tmp/street.jpg"
OWNER_PATH = "vfit/person/user_389c87aaadc6/b1a482725d9c4ea2a3b228bd487520e7.jpg"


def _jpg(a):
    b = io.BytesIO()
    Image.fromarray(a).save(b, "JPEG", quality=95)
    return b.getvalue()


@pytest.fixture(scope="module")
def pose_bytes():
    if not os.path.exists(POSE):
        pytest.skip("owner pose missing")
    return open(POSE, "rb").read()


@pytest.fixture(scope="module")
def street_bytes():
    if not os.path.exists(STREET):
        pytest.skip("street missing")
    return open(STREET, "rb").read()


# (2) face selection: owner photo -> real man's face (right, smaller, conf ~0.9), not the poster
def test_owner_face_selection(pose_bytes):
    rgb = np.array(head_lock._open_small(pose_bytes, head_lock.PERSON_OUT_SIDE).convert("RGB"))
    f = head_lock._face_box(rgb)
    print("face", f, rgb.shape)
    assert f is not None
    # poster face was at x~12 (scaled), real face at x~340 of ~800 width image
    assert f[0] > rgb.shape[1] * 0.3, f
    ok, conf, reason = head_lock.face_check(pose_bytes)
    print("face_check", ok, conf, reason)
    assert ok and conf > 0.88


# (3) tightened head: neck/collar below chin taken from model; head + above-chin zone original
def test_head_lock_tight_neck_from_model(street_bytes):
    _png, meta = head_lock.prepare(street_bytes, False, pose=True)
    canvas, face = meta["canvas"], meta["face"]
    fx, fy, fw, fh = face
    H_, W_ = canvas.shape[:2]
    res = canvas.copy()
    # model changed everything from 1.15*fh below face top (neck/collar) to 70% height
    y0 = int(fy + fh * 1.15)
    res[y0:int(H_ * 0.7), :] = (20, 30, 90)
    res[fy:fy + fh, fx:fx + fw] = 255 - res[fy:fy + fh, fx:fx + fw]  # regenerated face must be ignored
    out, frac = head_lock._pose_composite(canvas, res, face)
    head = (slice(max(0, int(fy - fh * 0.4)), int(fy + fh * 0.9)), slice(fx, fx + fw))
    hd = np.abs(out[head].astype(int) - canvas[head].astype(int)).mean()
    neck = (slice(int(fy + fh * 1.25), int(fy + fh * 1.6)), slice(int(fx), int(fx + fw)))
    nd = np.abs(out[neck].astype(int) - res[neck].astype(int)).mean()
    print("head diff", hd, "neck diff vs model", nd, "frac", frac)
    assert hd < 1.0
    assert nd < 4.0


# (4) pad bands always from the model even when model's floor ~ pad colour
def test_pad_bands_from_model(street_bytes):
    _png, meta = head_lock.prepare(street_bytes, True, pose=True)
    canvas, face, pads = meta["canvas"], meta["face"], meta["pads_px"]
    assert pads[1] > 0
    res = canvas.copy()
    res[-pads[1]:] = np.clip(res[-pads[1]:].astype(int) + 10, 0, 255).astype(np.uint8)  # near pad colour (< diff 24)
    res[:pads[0]] = np.clip(res[:pads[0]].astype(int) + 10, 0, 255).astype(np.uint8)
    out, _ = head_lock._pose_composite(canvas, res, face, pads)
    bd = np.abs(out[-pads[1] + 6:].astype(int) - res[-pads[1] + 6:].astype(int)).mean()
    td = np.abs(out[:pads[0] - 6].astype(int) - res[:pads[0] - 6].astype(int)).mean()
    print("bottom band diff vs model", bd, "top", td)
    assert bd < 1.0 and td < 1.0


# (6) _align_pose: model zoomed+shifted output -> registered back, head crop ~0 diff after finalize
def test_finalize_pose_align_zoom(street_bytes):
    _png, meta = head_lock.prepare(street_bytes, False, pose=True)
    canvas = meta["canvas"].copy()
    face = meta["face"]
    Hc, Wc = canvas.shape[:2]
    M = np.float32([[1.06, 0, -Wc * 0.03 + 8], [0, 1.06, -Hc * 0.03 - 6]])
    zoomed = cv2.warpAffine(canvas, M, (Wc, Hc), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    m = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in meta.items()}
    out = np.array(Image.open(io.BytesIO(head_lock.finalize(_jpg(zoomed), m))).convert("RGB"))
    fx, fy, fw, fh = face
    head = (slice(max(0, int(fy - fh * 0.4)), int(fy + fh * 0.9)), slice(fx, fx + fw))
    hd = np.abs(out[head].astype(int) - canvas[head].astype(int)).mean()
    inner = (slice(int(Hc * 0.1), int(Hc * 0.9)), slice(int(Wc * 0.1), int(Wc * 0.9)))
    wd = np.abs(out[inner].astype(int) - canvas[inner].astype(int)).mean()
    print("pose_fail", m.get("pose_fail"), "head diff", hd, "whole inner diff", wd)
    assert m["pose_fail"] is False
    assert hd < 1.5
    assert wd < 6


# (5) fix pass producing pose_fail is discarded: delivered image is the first (good) output
def test_fix_pass_pose_fail_discarded(pose_bytes, monkeypatch):
    import tryon_quality
    from emergentintegrations.llm.chat import ImageContent
    png, meta = head_lock.prepare(pose_bytes, False, pose=True)
    canvas = meta["canvas"]
    good = _jpg(canvas)
    noise = _jpg((np.random.default_rng(3).random(canvas.shape) * 255).astype(np.uint8))
    calls = []

    async def fake_call(system, prompt, contents, tag, aspect):
        calls.append(tag)
        return good if len(calls) == 1 else noise

    async def fake_qc(*a, **k):
        return {"ok": False, "score": 0.5, "issues": ["x"]}
    monkeypatch.setattr(tryon_quality, "_image_call", fake_call)
    monkeypatch.setattr(tryon_quality, "_qc", fake_qc)
    out = asyncio.run(tryon_quality.render("s", "p", [ImageContent(base64.b64encode(png).decode())], meta, "top", "t"))
    o = np.array(Image.open(io.BytesIO(out)).convert("RGB")).astype(np.float32)
    print("calls", calls, "out std", o.std())
    assert len(calls) == 2 and calls[1].endswith("-fix")
    # noise image std ~74; real photo much lower region-wise -> verify not noise via local smoothness
    lap = cv2.Laplacian(cv2.cvtColor(o.astype(np.uint8), cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()
    assert lap < 3000, lap


# (1) wrappers re-raise HTTPException from render (422 stays 422)
def test_render_single_reraises_422(monkeypatch):
    import server
    import tryon_quality
    from fastapi import HTTPException

    async def boom(*a, **k):
        raise HTTPException(status_code=422, detail="Non riesco a mantenere identica la tua foto in posa. nessun credito usato.")
    monkeypatch.setattr(tryon_quality, "render", boom)
    garment = "vfit/garment/user_389c87aaadc6/6a2a817775de40d396c2d4b4d3cff79e.jpg"

    async def go():
        return await server._render_single("user_389c87aaadc6", OWNER_PATH, garment, "top", "TEST", {}, server.POSE_RULE)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(go())
    print(ei.value.status_code, ei.value.detail)
    assert ei.value.status_code == 422 and "Image generation failed" not in str(ei.value.detail)


# (7) grid preserve_pose without person_path -> job error 400
def test_grid_pose_without_person_400():
    r = requests.post(f"{BASE_URL}/api/outfit/generate-from-uploads", headers=H, json={
        "items": [{"slot": "top", "image_path": "vfit/garment/user_389c87aaadc6/6a2a817775de40d396c2d4b4d3cff79e.jpg"}],
        "preserve_pose": True})
    assert r.status_code == 200, r.text
    job = r.json()["job_id"]
    import time
    for _ in range(20):
        j = requests.get(f"{BASE_URL}/api/render-jobs/{job}", headers=H)
        if j.status_code != 200 or j.json()["status"] != "running":
            break
        time.sleep(1)
    print(j.status_code, j.text)
    assert j.status_code == 400 and "foto in posa" in j.json()["detail"]
