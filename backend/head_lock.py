"""Head lock for try-ons: safe top margin, bottom canvas extension for long garments, original head pasted back."""
import gc
import logging
import io
import os
import re

import cv2
import numpy as np
from PIL import Image, ImageOps

_FACE_MODEL = os.path.join(os.path.dirname(__file__), "models", "face_yunet.onnx")
TOP_PAD_MIN_PX = 50
TOP_PAD_RATIO = 0.06
BOTTOM_PAD_RATIO = 0.20
HEAD_SAFE_ZONE = 0.15
logger = logging.getLogger(__name__)
PERSON_MAX_SIDE = 1536
PERSON_OUT_SIDE = 2048  # 2K output: lock canvas is kept at 2048, the model receives 1536
GARMENT_MAX_SIDE = 1024
LONG_WORDS = re.compile(r"\b(long|lungo|lunga|maxi|gown|abito|vestito|dress|trench|cappotto|coat|kaftan|caftano)\b", re.I)

HEAD_LOCK_RULE = (
    "HEAD LOCK — STRICT:\n"
    "• Preserve original head, face, hair 100% identical. Keep 50px safe margin from top edge. "
    "Do not crop, alter or regenerate head area.\n"
    "• The output must have EXACTLY the same width and height as IMAGE 1, with the person in the same position.\n"
    "• IMAGE 1 already includes an empty margin at the top and, for long outfits, an extended band at the bottom: "
    "if the outfit is long, expand image height at bottom only — continue the floor/background naturally into the bottom band "
    "and let the garment hem and the feet extend there. Never zoom or shift the person upwards.\n"
)


def _open_small(data: bytes, max_side: int) -> Image.Image:
    # JPEG draft decodes at reduced scale, so a 12MP photo never lands in RAM at full size.
    im = Image.open(io.BytesIO(data))
    im.draft("RGB", (max_side, max_side))
    im = ImageOps.exif_transpose(im)
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    return im


def downscale(data: bytes, max_side: int) -> bytes:
    with Image.open(io.BytesIO(data)) as probe:
        if max(probe.size) <= max_side and (probe.format in ("JPEG", "PNG")):
            return data
    im = _open_small(data, max_side)
    buf = io.BytesIO()
    if im.mode in ("RGBA", "LA", "P"):
        im.convert("RGBA").save(buf, "PNG")
    else:
        im.convert("RGB").save(buf, "JPEG", quality=90)
    del im
    return buf.getvalue()


def is_long(category: str, name: str = "") -> bool:
    return (category or "").lower() in ("dress", "suit") or bool(LONG_WORDS.search(name or ""))


def _faces(rgb: np.ndarray) -> list:
    h, w = rgb.shape[:2]
    scale = 640 / max(h, w)
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)))
    det = cv2.FaceDetectorYN.create(_FACE_MODEL, "", (small.shape[1], small.shape[0]), 0.6)
    _ok, faces = det.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
    if faces is None:
        return []
    boxes = [tuple(int(v) for v in f[:4] / scale) for f in faces]
    return sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)


def _face_box(rgb: np.ndarray):
    f = _faces(rgb)
    return f[0] if f else None


def _centre(b) -> tuple:
    return b[0] + b[2] / 2, b[1] + b[3] / 2


def _double_face(rgb: np.ndarray) -> bool:
    f = _faces(rgb)
    return len(f) > 1 and f[1][2] > 0.5 * f[0][2]


def _bg_color(rows: np.ndarray) -> tuple:
    w = rows.shape[1]
    side = np.concatenate([rows[:, : max(1, w // 4)], rows[:, -max(1, w // 4):]], axis=1).reshape(-1, 3)
    return tuple(int(v) for v in np.median(side, axis=0))


HAND_MATCH_MIN = 0.5


def _paste_hand(out: np.ndarray, canvas: np.ndarray, res: np.ndarray, box: tuple) -> bool:
    """Put the ORIGINAL hand back if the generated one sits in the same place (template match with context)."""
    H, W = out.shape[:2]
    x0, y0, x1, y1 = max(0, box[0]), max(0, box[1]), min(W, box[2]), min(H, box[3])
    bw, bh = x1 - x0, y1 - y0
    if bw < 12 or bh < 12:
        return False
    cx0, cy0 = max(0, x0 - bw // 5), max(0, y0 - bh // 5)
    cx1, cy1 = min(W, x1 + bw // 5), min(H, y1 + bh // 5)
    tpl = cv2.cvtColor(canvas[cy0:cy1, cx0:cx1], cv2.COLOR_RGB2GRAY)
    sx0, sy0 = max(0, cx0 - bw // 2), max(0, cy0 - bh // 2)
    sx1, sy1 = min(W, cx1 + bw // 2), min(H, cy1 + bh // 2)
    win = cv2.cvtColor(res[sy0:sy1, sx0:sx1], cv2.COLOR_RGB2GRAY)
    if win.shape[0] < tpl.shape[0] or win.shape[1] < tpl.shape[1]:
        return False
    _mn, score, _ml, (mx, my) = cv2.minMaxLoc(cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED))
    if score < HAND_MATCH_MIN:
        logger.info("head_lock: hand moved or covered (match %.2f), keeping generated hand", score)
        return False
    dx, dy = sx0 + mx - cx0, sy0 + my - cy0
    tx0, ty0, tx1, ty1 = x0 + dx, y0 + dy, x1 + dx, y1 + dy
    if tx0 < 0 or ty0 < 0 or tx1 > W or ty1 > H:
        return False
    m = np.zeros((bh, bw), np.uint8)
    cv2.ellipse(m, (bw // 2, bh // 2), (int(bw * 0.47), int(bh * 0.47)), 0, 0, 360, 255, -1)
    m = cv2.GaussianBlur(m, (0, 0), max(2, min(bw, bh) * 0.12)).astype(np.float32) * (1 / 255)
    # Seam check: if what surrounds the hand changed (e.g. new garment under it), a pasted patch would show edges.
    src, dst = canvas[y0:y1, x0:x1].astype(np.int16), out[ty0:ty1, tx0:tx1].astype(np.int16)
    ring = (m > 0.05) & (m < 0.5)
    seam = float(np.abs(src - dst).mean(axis=2)[ring].mean()) if ring.any() else 0.0
    if seam > 28:
        logger.info("head_lock: surroundings of the hand changed (seam %.1f), keeping generated hand", seam)
        return False
    out[ty0:ty1, tx0:tx1] = cv2.blendLinear(canvas[y0:y1, x0:x1], out[ty0:ty1, tx0:tx1], m, 1 - m)
    logger.info("head_lock: original hand restored (match %.2f, seam %.1f, shift %d,%d)", score, seam, dx, dy)
    return True


def prepare(person_bytes: bytes, long_garment: bool, hands: list = None, paste_hands=True) -> tuple:
    """paste_hands: bool for all hands, or one bool per hand box (False = the model may redraw that hand)."""
    # Returns (canvas_png_bytes, meta) with top safe margin and optional bottom extension.
    im = np.array(_open_small(person_bytes, PERSON_OUT_SIDE).convert("RGB"))
    h, w = im.shape[:2]
    top = max(TOP_PAD_MIN_PX, int(h * TOP_PAD_RATIO))
    bottom = int(h * BOTTOM_PAD_RATIO) if long_garment else 0
    # Bands are filled with the plain background colour (never the person: head/feet touching the edge must not smear).
    canvas = cv2.copyMakeBorder(im, top, bottom, 0, 0, cv2.BORDER_CONSTANT, value=_bg_color(im[:3]))
    if bottom:
        canvas[top + h:] = _bg_color(im[-3:])
    # face_lock_mask = face + hair + 50px top padding; head_safe_zone = top 15% of the photo.
    # face_lock_mask = soft ellipse over face + hair (+ chin); the whole head sits below the top safe margin.
    # Without a detectable face, fall back to head_safe_zone = top 15% of the photo.
    mask = np.zeros(canvas.shape[:2], np.uint8)
    face = _face_box(im)
    if face:
        fx, fy, fw, fh = face
        y_top, y_bot = fy - fh * 0.75 + top, fy + fh * 1.12 + top
        cv2.ellipse(mask, (int(fx + fw / 2), int((y_top + y_bot) / 2)), (int(fw * 0.95), int((y_bot - y_top) / 2)), 0, 0, 360, 255, -1)
    else:
        mask[: top + int(h * HEAD_SAFE_ZONE)] = 255
    # Hand boxes (normalised 0-1000 [ymin, xmin, ymax, xmax] on the photo) -> canvas pixels.
    hand_c, paste_c = [], []
    keep = paste_hands if isinstance(paste_hands, list) else [paste_hands] * len(hands or [])
    for b, k in zip(hands or [], keep):
        y0, x0, y1, x1 = (max(0.0, min(1000.0, float(v))) / 1000 for v in b)
        if x1 - x0 > 0.01 and y1 - y0 > 0.01:
            hand_c.append((int(x0 * w), int(y0 * h) + top, int(x1 * w), int(y1 * h) + top))
            if k:
                paste_c.append(hand_c[-1])
    # A hand/phone overlapping the chin must not be pasted back (the model may move it -> ghost bar): carve it out, eyes/nose stay locked.
    y_keep = int(face[1] + top + face[3] * 0.6) if face else 0
    for x0, y0, x1, y1 in hand_c:
        bw, bh = x1 - x0, y1 - y0
        mask[max(y_keep, int(y0 - bh * 0.8)):int(y1 + bh * 0.15), max(0, int(x0 - bw * 0.15)):int(x1 + bw * 0.15)] = 0
    mask = cv2.GaussianBlur(mask, (0, 0), max(4, h / 160))
    send = Image.fromarray(canvas)
    send.thumbnail((PERSON_MAX_SIDE, PERSON_MAX_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    send.save(buf, "PNG")
    del send
    face_c = (face[0], face[1] + top, face[2], face[3]) if face else None
    del im
    gc.collect()
    return buf.getvalue(), {"canvas": canvas, "mask": mask, "face": face_c, "hands": paste_c}


def _match_head_colour(canvas: np.ndarray, res: np.ndarray, mask: np.ndarray) -> np.ndarray:
    # Model may shift white balance: tint the pasted head to the result using the ring of background above/beside it (no halo).
    H, W = mask.shape
    ys, xs = np.where(mask > 8)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    pad = int(0.25 * max(y1 - y0, x1 - x0))
    Y0, Y1, X0, X1 = max(0, y0 - pad), min(H, y1 + pad), max(0, x0 - pad), min(W, x1 + pad)
    m = mask[Y0:Y1, X0:X1]
    ring = m < 8
    ring[(y0 + y1) // 2 - Y0:] = False  # upper half only: below the chin the garment changed
    if ring.sum() < 400:
        return canvas
    c = canvas[Y0:Y1, X0:X1]
    gain = (np.median(res[Y0:Y1, X0:X1][ring], 0) + 1) / (np.median(c[ring], 0) + 1)
    gain = np.clip(gain, 0.75, 1.33)
    if np.abs(gain - 1).max() < 0.02:
        return canvas
    canvas = canvas.copy()
    canvas[Y0:Y1, X0:X1] = np.clip(c.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    return canvas


def finalize(result_bytes: bytes, meta: dict) -> bytes:
    canvas, mask = meta["canvas"], meta["mask"]
    H, W = canvas.shape[:2]
    res = np.array(_open_small(result_bytes, max(H, W)).convert("RGB"))
    del result_bytes
    rh, rw = res.shape[:2]
    if abs(rw / rh - W / H) > 0.04:
        # Model changed the aspect: fit the full HEIGHT (head and feet never cut), then trim or pad the sides only.
        nw = int(rw * H / rh)
        res = cv2.resize(res, (nw, H), interpolation=cv2.INTER_LANCZOS4)
        if nw >= W:
            x0 = (nw - W) // 2
            res = res[:, x0:x0 + W]
        else:
            lp = (W - nw) // 2
            res = cv2.copyMakeBorder(res, 0, 0, lp, W - nw - lp, cv2.BORDER_REPLICATE)
    else:
        res = cv2.resize(res, (W, H), interpolation=cv2.INTER_LANCZOS4)
    # If the model zoomed/shifted the person, scale+move the result so its face lands exactly on the original face.
    rf, of = _face_box(res), meta.get("face")
    head_at = of  # where the ORIGINAL head will be pasted
    aligned = not of  # no detected face: only the top safe-zone band is restored
    if rf and of and 0.6 < of[2] / rf[2] < 1.6:
        aligned = True
        sc = of[2] / rf[2]
        ocx, ocy = of[0] + of[2] / 2, of[1] + of[3] / 2
        rcx, rcy = rf[0] + rf[2] / 2, rf[1] + rf[3] / 2
        if abs(sc - 1) > 0.02 or abs(ocx - rcx) > 3 or abs(ocy - rcy) > 3:
            # Keep the generated full body (hem, feet) and move the ORIGINAL head onto the generated face position.
            k = 1 / sc
            M = np.float32([[k, 0, rcx - k * ocx], [0, k, rcy - k * ocy]])
            canvas = cv2.warpAffine(canvas, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
            mask = cv2.warpAffine(mask, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            head_at = rf
            meta["hands"] = [tuple(int(v) for v in (M[0, 0] * x0 + M[0, 2], M[1, 1] * y0 + M[1, 2], M[0, 0] * x1 + M[0, 2], M[1, 1] * y1 + M[1, 2]))
                             for x0, y0, x1, y1 in meta.get("hands", [])]
    else:
        band = slice(0, int(H * 0.45))
        a = cv2.cvtColor(canvas[band], cv2.COLOR_RGB2GRAY).astype(np.float32)
        b = cv2.cvtColor(res[band], cv2.COLOR_RGB2GRAY).astype(np.float32)
        (dx, dy), resp = cv2.phaseCorrelate(a, b)
        if resp > 0.05 and abs(dx) < W * 0.08 and abs(dy) < H * 0.08:
            res = cv2.warpAffine(res, np.float32([[1, 0, -dx], [0, 1, -dy]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
            aligned = True
        del a, b
        if of and aligned:
            # Verify the generated head really sits under the pasted one, otherwise the blend shows two faces.
            rf2 = _face_box(res)
            if rf2:
                (cx, cy), (ox, oy) = _centre(rf2), _centre(of)
                aligned = abs(cx - ox) < 0.35 * of[2] and abs(cy - oy) < 0.35 * of[3]
    if not aligned:
        # Pasting the original head onto a misplaced generated one would create a double face: keep the model output.
        logger.warning("head_lock: generated head not aligned with original %s, skipping head paste", head_at)
        mask = np.zeros_like(mask)
    if mask.any():
        canvas = _match_head_colour(canvas, res, mask)
    # Per-pixel blend on uint8 images with single-channel weights (no full-size float32 RGB copies).
    w = mask.astype(np.float32) * (1 / 255)
    out = cv2.blendLinear(canvas, res, w, 1 - w)
    if aligned and of and _double_face(out):
        logger.warning("head_lock: double face after head paste, keeping model output")
        out = res
    for box in meta.get("hands", []):
        _paste_hand(out, canvas, res, box)
    del w, res, canvas, mask
    meta.clear()
    buf = io.BytesIO()
    Image.fromarray(out).save(buf, "PNG")
    del out
    gc.collect()
    return buf.getvalue()
