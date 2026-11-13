"""VISO BLOCCATO ESTERNO: the external try-on output is put back on the ORIGINAL photo; only the new garment zone comes from it."""
import io
import logging

import cv2
import numpy as np
from PIL import Image

import head_lock
import pose_lock

logger = logging.getLogger(__name__)
RATIOS = {"1:1": 1.0, "3:4": 0.75, "4:3": 4 / 3, "9:16": 9 / 16, "16:9": 16 / 9}


def best_ratio(person: bytes) -> str:
    w, h = Image.open(io.BytesIO(person)).size
    return min(RATIOS, key=lambda k: abs(RATIOS[k] - w / h))


def _zone(kp: np.ndarray, shape, category: str) -> np.ndarray:
    """Where the new garment may be: legs (bottom/shoes), torso + arms (top/outerwear), both (dress/suit)."""
    H, W = shape[:2]
    z = np.zeros((H, W), np.uint8)
    ok = lambda i: kp[i, 2] > pose_lock.MIN_SCORE  # noqa: E731
    up_len = max([float(np.hypot(*(kp[a, :2] - kp[b, :2]))) for a, b in ((5, 7), (6, 8)) if ok(a) and ok(b)] or [0.12 * H])
    lower = category in ("bottom", "shoes", "dress", "suit")
    upper = category in ("top", "outerwear", "dress", "suit") or not lower
    if lower:
        z |= cv2.dilate(pose_lock.legs_mask(kp, shape), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.5 * up_len) | 1,) * 2))
    if upper:
        pts = [kp[i, :2] for i in (5, 6, 11, 12) if ok(i)]
        if len(pts) >= 3:
            cv2.fillConvexPoly(z, cv2.convexHull(np.int32(pts)), 255)
        for a, b in ((5, 7), (7, 9), (6, 8), (8, 10), (5, 6)):
            if ok(a) and ok(b):
                cv2.line(z, tuple(np.int32(kp[a, :2])), tuple(np.int32(kp[b, :2])), 255, max(8, int(0.6 * up_len)), cv2.LINE_AA)
    return cv2.dilate(z, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.25 * up_len) | 1,) * 2))


def lock_original(person: bytes, out: bytes, category: str) -> bytes:
    """Original photo everywhere (face, hair, hands, background, light); new garment pixels only inside its body zone."""
    orig = np.array(Image.open(io.BytesIO(person)).convert("RGB"))
    H, W = orig.shape[:2]
    res = np.array(head_lock._open_small(out, max(H, W)).convert("RGB"))
    reg = head_lock._register(orig, res)
    if reg is None:
        logger.warning("ext lock: registration failed, external photo kept")
        return out
    kp = pose_lock.keypoints(orig)
    if kp is None:
        return out
    zone = _zone(kp, orig.shape, category)
    diff = np.abs(cv2.GaussianBlur(orig, (0, 0), 1.5).astype(np.int16) - cv2.GaussianBlur(reg, (0, 0), 1.5).astype(np.int16)).mean(axis=2)
    ch = cv2.morphologyEx((diff > 28).astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    ch = cv2.morphologyEx(ch, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    # Floor / wall: pixels that are background-like in BOTH photos stay original (no light patches around the body).
    lab_o = cv2.cvtColor(orig, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab_r = cv2.cvtColor(reg, cv2.COLOR_RGB2LAB).astype(np.float32)
    border = np.concatenate([lab_o[:, :max(4, W // 25)].reshape(-1, 3), lab_o[:, -max(4, W // 25):].reshape(-1, 3), lab_o[-max(4, H // 30):].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    loose = lambda L: (np.abs(L[..., 0] - bg[0]) < 45) & (np.hypot(L[..., 1] - bg[1], L[..., 2] - bg[2]) < 9)  # floor, also in shadow  # noqa: E731
    both_bg = loose(lab_o) & loose(lab_r)
    sk0 = head_lock._skin(orig) > 0
    big = cv2.dilate(zone, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))) > 0
    # Old clothes (not floor, not skin) near the zone always go: never a piece of the old garment left around the new one.
    old = big & ~loose(lab_o) & ~sk0 & ((ch > 0) | loose(lab_r))
    m = ((((ch > 0) & (zone > 0)) | old) & ~both_bg).astype(np.uint8)
    # Where the old garment was but the external photo shows floor: rebuilt from the ORIGINAL floor around it (same shadows).
    fill = (old & loose(lab_r)).astype(np.uint8)
    m[fill > 0] = 0
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    m = np.zeros_like(m)
    cv2.drawContours(m, [c for c in cnts if cv2.contourArea(c) > 0.002 * H * W], -1, 1, -1)
    # Hands always original; face/head never from the external photo.
    hands, _, _ = pose_lock.seated_masks(kp, orig.shape)
    sk = head_lock._skin(orig) > 0
    for _, hm in hands:
        m[(hm > 0) & sk] = 0
    if category in ("bottom", "shoes"):
        # Bare arms are not part of a lower garment: always original.
        arms = np.zeros((H, W), np.uint8)
        for a, b in ((5, 7), (7, 9), (6, 8), (8, 10)):
            if kp[a, 2] > pose_lock.MIN_SCORE and kp[b, 2] > pose_lock.MIN_SCORE:
                cv2.line(arms, tuple(np.int32(kp[a, :2])), tuple(np.int32(kp[b, :2])), 255, max(8, int(0.09 * H)), cv2.LINE_AA)
        m[(arms > 0) & sk] = 0
    if kp[0, 2] > pose_lock.MIN_SCORE and kp[5, 2] > pose_lock.MIN_SCORE and kp[6, 2] > pose_lock.MIN_SCORE:
        neck = int((kp[5, 1] + kp[6, 1]) / 2)
        m[:max(0, neck - int(0.02 * H))] = 0
    # ORIGINAL LIGHT: the external pixels are relit with the local light ratio measured on the shared floor/wall.
    bgm = (both_bg & (m == 0)).astype(np.float32)
    sig = max(H, W) / 12
    den = cv2.GaussianBlur(bgm, (0, 0), sig) + 1e-3
    gain = np.stack([(cv2.GaussianBlur(orig[..., c].astype(np.float32) * bgm, (0, 0), sig) + 1) /
                     (cv2.GaussianBlur(reg[..., c].astype(np.float32) * bgm, (0, 0), sig) + 1) for c in range(3)], axis=2)
    gain = np.clip(np.where((den > 0.02)[..., None], gain, 1.0), 0.75, 1.33)
    reg = np.clip(reg.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    w = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 2.0)
    fin = cv2.blendLinear(reg, orig, w, 1 - w)
    if fill.any():
        fin = cv2.inpaint(fin, cv2.dilate(fill, np.ones((5, 5), np.uint8)) * 255, 9, cv2.INPAINT_TELEA)
    logger.info("ext lock: original restored, garment zone from external=%.3f", float(m.mean()))
    buf = io.BytesIO()
    Image.fromarray(fin).save(buf, "PNG")
    return buf.getvalue()
