# FACE LOCK unit tests: head_lock.face_check (credit saver) + _pose_composite + finalize pose branch
import io
import os
import sys

import cv2
import numpy as np
import pytest
from PIL import Image, ImageEnhance, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import head_lock  # noqa: E402

POSE = "/tmp/owner_pose.jpg"
STREET = "/tmp/street.jpg"


def _jpg(im):
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=92)
    return b.getvalue()


@pytest.fixture(scope="module")
def pose_bytes():
    if not os.path.exists(POSE):
        pytest.skip("owner pose not downloaded")
    return open(POSE, "rb").read()


# Clear real photos pass the 0.75 YuNet gate
@pytest.mark.parametrize("p", [POSE, STREET])
def test_face_check_good(p):
    if not os.path.exists(p):
        pytest.skip("missing")
    ok, conf, reason = head_lock.face_check(open(p, "rb").read())
    print(p, ok, conf, reason)
    assert ok and conf >= head_lock.FACE_MIN_CONF and reason == ""


# Dark / blurry / no face / tiny face -> rejected with reason
def test_face_check_bad(pose_bytes):
    im = Image.open(io.BytesIO(pose_bytes)).convert("RGB")
    dark = ImageEnhance.Brightness(im).enhance(0.15)
    blur = im.filter(ImageFilter.GaussianBlur(12))
    noface = Image.new("RGB", (800, 1200), (180, 170, 160))
    tiny = Image.new("RGB", (3000, 4500), (200, 200, 200))
    tiny.paste(im.resize((im.width // 10, im.height // 10)), (1400, 2000))
    res = {k: head_lock.face_check(_jpg(v)) for k, v in dict(dark=dark, blur=blur, noface=noface, tiny=tiny).items()}
    print(res)
    for k, (ok, _c, reason) in res.items():
        assert ok is False, (k, res[k])
        assert reason in ("no_face", "face_small", "dark", "blurry", "low_conf")


# Composite: head pixels identical to original, background identical, only changed region taken from result
def test_pose_composite_face_lock(pose_bytes):
    _png, meta = head_lock.prepare(pose_bytes, False, pose=True)
    canvas, face = meta["canvas"], meta["face"]
    assert face is not None
    H, W = canvas.shape[:2]
    fx, fy, fw, fh = face
    res = canvas.copy()
    # Simulate "new clothes": torso region recoloured; also perturb the face (model regenerated it -> must be ignored)
    y0 = int(fy + fh * 1.6)
    res[y0:int(H * 0.7), :] = (30, 60, 200)
    res[fy:fy + fh, fx:fx + fw] = 255 - res[fy:fy + fh, fx:fx + fw]
    out, frac = head_lock._pose_composite(canvas, res, face)
    head = (slice(max(0, int(fy - fh * 0.5)), int(fy + fh)), slice(fx, fx + fw))
    hd = np.abs(out[head].astype(int) - canvas[head].astype(int)).mean()
    print("frac", frac, "head diff", hd)
    assert hd < 1.0
    # torso changed
    td = np.abs(out[y0 + 20:int(H * 0.68), W // 3:2 * W // 3].astype(int) - res[y0 + 20:int(H * 0.68), W // 3:2 * W // 3].astype(int)).mean()
    assert td < 3
    # below-torso background identical
    bd = np.abs(out[int(H * 0.75):].astype(int) - canvas[int(H * 0.75):].astype(int)).mean()
    assert bd < 1.0
    assert 0 < frac < head_lock.POSE_CHANGE_MAX


# finalize pose: totally new scene -> pose_fail True; unchanged -> pose_fail False and output == original
def test_finalize_pose_flags(pose_bytes):
    _png, meta = head_lock.prepare(pose_bytes, False, pose=True)
    canvas = meta["canvas"].copy()
    m1 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in meta.items()}
    out = head_lock.finalize(_jpg(Image.fromarray(canvas)), m1)
    assert m1["pose_fail"] is False
    o = np.array(Image.open(io.BytesIO(out)).convert("RGB"))
    assert o.shape == canvas.shape and np.abs(o.astype(int) - canvas.astype(int)).mean() < 3
    m2 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in meta.items()}
    noise = (np.random.default_rng(1).random(canvas.shape) * 255).astype(np.uint8)
    head_lock.finalize(_jpg(Image.fromarray(noise)), m2)
    assert m2["pose_fail"] is True


# render(): pose result that keeps failing the composite -> regenerated once with SCENE_RULE, then HTTPException 422 (no QC/fix, no doc)
def test_render_pose_fail_422(pose_bytes, monkeypatch):
    import asyncio
    import tryon_quality
    from fastapi import HTTPException
    from emergentintegrations.llm.chat import ImageContent
    import base64
    png, meta = head_lock.prepare(pose_bytes, False, pose=True)
    calls = []
    noise = _jpg(Image.fromarray((np.random.default_rng(2).random(meta["canvas"].shape) * 255).astype(np.uint8)))

    async def fake_call(system, prompt, contents, tag, aspect):
        calls.append(("SCENE" in prompt, tag))
        return noise

    async def fake_qc(*a, **k):
        raise AssertionError("QC must not run on a failed pose")
    monkeypatch.setattr(tryon_quality, "_image_call", fake_call)
    monkeypatch.setattr(tryon_quality, "_qc", fake_qc)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(tryon_quality.render("s", "p", [ImageContent(base64.b64encode(png).decode())], meta, "top", "t"))
    assert ei.value.status_code == 422 and "nessun credito" in ei.value.detail
    assert len(calls) == 2 and calls[1][0] is True
