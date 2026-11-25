"""LACE ONLY FROM THE EXTERNAL SERVER: the system result (complete garment, solid parts, lining, sleeves) stays the base; the external
try-on only gives the lace / transparent texture, inside the system garment and never on its solid parts."""
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


def _ok(kp, i):
    return kp[i, 2] > pose_lock.MIN_SCORE


def _up_len(kp, H):
    return max([float(np.hypot(*(kp[a, :2] - kp[b, :2]))) for a, b in ((5, 7), (6, 8)) if _ok(kp, a) and _ok(kp, b)] or [0.12 * H])


def _zone(kp: np.ndarray, shape, category: str) -> np.ndarray:
    """Where the new garment may be: legs (bottom/shoes), torso + arms (top/outerwear), both (dress/suit)."""
    H, W = shape[:2]
    z = np.zeros((H, W), np.uint8)
    up_len = _up_len(kp, H)
    lower = category in ("bottom", "shoes", "dress", "suit")
    upper = category in ("top", "outerwear", "dress", "suit") or not lower
    if lower:
        z |= cv2.dilate(pose_lock.legs_mask(kp, shape), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.5 * up_len) | 1,) * 2))
    if upper:
        pts = [kp[i, :2] for i in (5, 6, 11, 12) if _ok(kp, i)]
        if len(pts) >= 3:
            cv2.fillConvexPoly(z, cv2.convexHull(np.int32(pts)), 255)
        for a, b in ((5, 7), (7, 9), (6, 8), (8, 10), (5, 6)):
            if _ok(kp, a) and _ok(kp, b):
                cv2.line(z, tuple(np.int32(kp[a, :2])), tuple(np.int32(kp[b, :2])), 255, max(8, int(0.6 * up_len)), cv2.LINE_AA)
    return cv2.dilate(z, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.25 * up_len) | 1,) * 2))


def _solid(kp: np.ndarray, shape, category: str) -> np.ndarray:
    """Parts always built by the system in opaque fabric: waistband + hips (bottoms), shoulder seams where sleeves attach (tops)."""
    H, W = shape[:2]
    s = np.zeros((H, W), np.uint8)
    up_len = _up_len(kp, H)
    if category in ("bottom", "dress", "suit") and _ok(kp, 11) and _ok(kp, 12):
        hip = int((kp[11, 1] + kp[12, 1]) / 2)
        thigh = max([float(np.hypot(*(kp[a, :2] - kp[b, :2]))) for a, b in ((11, 13), (12, 14)) if _ok(kp, a) and _ok(kp, b)] or [up_len])
        if category == "bottom":
            s[max(0, hip - int(0.45 * thigh)):min(H, hip + int(0.3 * thigh))] = 255
    if category in ("top", "outerwear", "dress", "suit"):
        for i in (5, 6):
            if _ok(kp, i):
                cv2.circle(s, tuple(np.int32(kp[i, :2])), int(0.35 * up_len), 255, -1)
    return s


def _blur_diff(a, b):
    return np.abs(cv2.GaussianBlur(a, (0, 0), 1.5).astype(np.int16) - cv2.GaussianBlur(b, (0, 0), 1.5).astype(np.int16)).mean(axis=2)


def _tight_body(kp: np.ndarray, shape) -> np.ndarray:
    """Narrow pose strips (limbs, torso, head): pixels here are always body / worn garment, never debris."""
    H, W = shape[:2]
    up = _up_len(kp, H)
    m = np.zeros((H, W), np.uint8)
    pts = [kp[i, :2] for i in (5, 6, 11, 12) if _ok(kp, i)]
    if len(pts) >= 3:
        cv2.fillConvexPoly(m, cv2.convexHull(np.int32(pts)), 255)
    for a, b in ((5, 7), (7, 9), (6, 8), (8, 10), (11, 13), (13, 15), (12, 14), (14, 16), (5, 6), (11, 12)):
        if _ok(kp, a) and _ok(kp, b):
            cv2.line(m, tuple(np.int32(kp[a, :2])), tuple(np.int32(kp[b, :2])), 255, max(6, int(0.3 * up)), cv2.LINE_AA)
    head = [kp[i, :2] for i in range(5) if _ok(kp, i)]
    if head:
        cv2.circle(m, tuple(np.int32(np.mean(head, axis=0))), int(0.6 * up), 255, -1)
    return m > 0


def clean_floor(result: bytes, person: bytes, boxes=()):
    """GLOBAL RULE: inset/phone frame cropped; everything changed OUTSIDE the body (scraps, lace pieces, props, their shadows) gets the
    ORIGINAL floor back, relit to the result. Body, garment, model and pose untouched. None when nothing to clean."""
    cropped = head_lock.crop_screenshot(result)
    G = np.array(Image.open(io.BytesIO(cropped)).convert("RGB"))
    H, W = G.shape[:2]
    O = head_lock._register(G, np.array(head_lock._open_small(person, max(H, W)).convert("RGB")))
    kp = pose_lock.keypoints(G)
    if O is None or kp is None:
        logger.warning("floor clean: registration/pose failed")
        return cropped if cropped is not result else None
    up_len = _up_len(kp, H)
    core = _zone(kp, G.shape, "suit")
    head = [kp[i, :2] for i in range(5) if _ok(kp, i)]
    if head:
        c = np.mean(head, axis=0)
        cv2.circle(core, tuple(np.int32(c)), int(0.9 * up_len), 255, -1)
    near = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.7 * up_len) | 1,) * 2)) > 0
    ch = cv2.morphologyEx((_blur_diff(G, O) > 28).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # SAFE CLEANING: the wide protected zone (whole body + garments + margin) is never touched, whatever the AI boxes say.
    protect = near | cv2.dilate(_tight_body(kp, G.shape).astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
    debris = (ch > 0) & ~protect
    soft = cv2.dilate((_blur_diff(G, O) > 10).astype(np.uint8), np.ones((5, 5), np.uint8))  # AI-flagged boxes: faint outlines go too
    for y0, x0, y1, x1 in boxes:
        ys, xs = slice(int(y0 * H / 1000), int(y1 * H / 1000) + 1), slice(int(x0 * W / 1000), int(x1 * W / 1000) + 1)
        debris[ys, xs] |= (soft[ys, xs] > 0) & ~protect[ys, xs]
    debris[int(0.9 * H):, int(0.5 * W):] = False  # signature
    debris = cv2.dilate(debris.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    debris[protect] = 0
    # Only SMALL spots: a large changed area is never floor debris, it is left as it is.
    n, lab, stats, _ = cv2.connectedComponentsWithStats(debris)
    small = np.zeros(n, bool)
    small[1:] = stats[1:, cv2.CC_STAT_AREA] <= 0.005 * H * W
    debris = small[lab].astype(np.uint8)
    if debris.sum() < 0.0005 * H * W:
        return cropped if cropped is not result else None
    bgm = ((ch == 0) & ~near).astype(np.float32)
    sig = max(H, W) / 12
    den = cv2.GaussianBlur(bgm, (0, 0), sig) + 1e-3
    gain = np.stack([(cv2.GaussianBlur(G[..., c].astype(np.float32) * bgm, (0, 0), sig) + 1) /
                     (cv2.GaussianBlur(O[..., c].astype(np.float32) * bgm, (0, 0), sig) + 1) for c in range(3)], axis=2)
    gain = np.clip(np.where((den > 0.02)[..., None], gain, 1.0), 0.8, 1.25)
    O = np.clip(O.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    w = cv2.GaussianBlur(debris.astype(np.float32), (0, 0), 2.0)
    fin = cv2.blendLinear(O, G, w, 1 - w)
    # Where the ORIGINAL photo had the body (e.g. a bare foot moved), the original is no floor: rebuilt from the floor around it.
    fill = ((debris > 0) & cv2.dilate((head_lock._skin(O) > 0).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)).astype(np.uint8)
    if fill.any():
        fin = cv2.inpaint(fin, cv2.dilate(fill, np.ones((5, 5), np.uint8)) * 255, 9, cv2.INPAINT_TELEA)
    logger.info("floor clean: %.4f of the photo restored from the original floor", float(debris.mean()))
    buf = io.BytesIO()
    Image.fromarray(fin).save(buf, "JPEG", quality=94)
    return buf.getvalue()


def lace_layer(base: bytes, person: bytes, ext: bytes, category: str) -> bytes:
    """System result everywhere; external lace pixels only where BOTH photos show the new garment, colours agree, never skin
    (lace holes show the system lining), never on solid parts, hands, background or the signature."""
    G = np.array(Image.open(io.BytesIO(base)).convert("RGB"))
    H, W = G.shape[:2]
    O = head_lock._register(G, np.array(head_lock._open_small(person, max(H, W)).convert("RGB")))
    F = head_lock._register(G, np.array(head_lock._open_small(ext, max(H, W)).convert("RGB")))
    kp = pose_lock.keypoints(G)
    if O is None or F is None or kp is None:
        logger.warning("lace layer: registration/pose failed, system result kept")
        return base
    zone = _zone(kp, G.shape, category) > 0
    lab_o = cv2.cvtColor(O, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab_g = cv2.cvtColor(cv2.GaussianBlur(G, (0, 0), 2), cv2.COLOR_RGB2LAB).astype(np.float32)
    lab_f = cv2.cvtColor(cv2.GaussianBlur(F, (0, 0), 2), cv2.COLOR_RGB2LAB).astype(np.float32)
    border = np.concatenate([lab_o[:, :max(4, W // 25)].reshape(-1, 3), lab_o[:, -max(4, W // 25):].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    bg_f = (np.abs(lab_f[..., 0] - bg[0]) < 45) & (np.hypot(lab_f[..., 1] - bg[1], lab_f[..., 2] - bg[2]) < 9)
    gem = zone & (_blur_diff(G, O) > 28)
    extg = zone & (_blur_diff(F, O) > 28) & (head_lock._skin(F) == 0) & ~bg_f
    agree = np.hypot(lab_g[..., 1] - lab_f[..., 1], lab_g[..., 2] - lab_f[..., 2]) < 20
    m = (gem & extg & agree & (_solid(kp, G.shape, category) == 0)).astype(np.uint8)
    hands, _, _ = pose_lock.seated_masks(kp, G.shape)
    for _, hm in hands:
        m[cv2.dilate(hm, np.ones((9, 9), np.uint8)) > 0] = 0
    m[int(0.9 * H):, int(0.5 * W):] = 0  # signature corner
    if kp[0, 2] > pose_lock.MIN_SCORE and _ok(kp, 5) and _ok(kp, 6):
        m[:max(0, int((kp[5, 1] + kp[6, 1]) / 2) - int(0.02 * H))] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] > 0.001 * H * W
    m = keep[lab].astype(np.uint8)
    if not m.any():
        logger.info("lace layer: no shared lace zone, system result kept")
        return base
    sel = m > 0
    gain = np.clip(G[sel].reshape(-1, 3).mean(0) / (F[sel].reshape(-1, 3).mean(0) + 1), 0.85, 1.18)
    F = np.clip(F.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    w = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.2)
    fin = cv2.blendLinear(F, G, w, 1 - w)
    logger.info("lace layer: %s lace from external=%.3f", category, float(m.mean()))
    buf = io.BytesIO()
    Image.fromarray(fin).save(buf, "JPEG", quality=94)
    return buf.getvalue()
