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
    # The person is the most CONFIDENT sizeable face (a big faded poster face in the background must not win on area).
    big = max(f[2] * f[3] for f in faces)
    faces = sorted([f for f in faces if f[2] * f[3] >= 0.15 * big], key=lambda f: f[14], reverse=True)
    return [tuple(int(v) for v in f[:4] / scale) for f in faces]


FACE_MIN_CONF = 0.75  # YuNet score: clear real photos measure 0.80-0.95


def face_check(person_bytes: bytes) -> tuple:
    """Credit saver for posed photos: (ok, confidence, reason). Face re-detected on a zoomed crop so small full-body faces score fairly."""
    rgb = np.array(_open_small(person_bytes, PERSON_MAX_SIDE).convert("RGB"))
    h, w = rgb.shape[:2]
    scale = 640 / max(h, w)
    small = cv2.resize(rgb, (int(w * scale), int(h * scale)))
    det = cv2.FaceDetectorYN.create(_FACE_MODEL, "", (small.shape[1], small.shape[0]), 0.5)
    _ok, faces = det.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
    if faces is None:
        return False, 0.0, "no_face"
    big = max(r[2] * r[3] for r in faces)
    f = max((r for r in faces if r[2] * r[3] >= 0.15 * big), key=lambda r: r[14])
    x, y, fw, fh = (f[:4] / scale).astype(int)
    conf = float(f[14])
    side = int(max(fw, fh) * 3)
    cx, cy = x + fw // 2, y + fh // 2
    x0, y0 = max(0, cx - side // 2), max(0, cy - side // 2)
    crop = rgb[y0:min(h, y0 + side), x0:min(w, x0 + side)]
    if crop.size:
        cs = 640 / max(crop.shape[:2])
        c2 = cv2.resize(crop, (int(crop.shape[1] * cs), int(crop.shape[0] * cs)))
        det2 = cv2.FaceDetectorYN.create(_FACE_MODEL, "", (c2.shape[1], c2.shape[0]), 0.5)
        _ok, f2 = det2.detect(cv2.cvtColor(c2, cv2.COLOR_RGB2BGR))
        if f2 is not None:
            conf = max(conf, float(max(f2, key=lambda r: r[14])[14]))
    face = cv2.cvtColor(rgb[max(0, y):y + fh, max(0, x):x + fw], cv2.COLOR_RGB2GRAY)
    bright = float(face.mean()) if face.size else 0.0
    sharp = float(cv2.Laplacian(cv2.resize(face, (128, 128)), cv2.CV_64F).var()) if face.size else 0.0
    if fw < 40 or fh < 40:
        return False, conf, "face_small"
    if bright < 55:
        return False, conf, "dark"
    if sharp < 25:
        return False, conf, "blurry"
    if conf < FACE_MIN_CONF:
        return False, conf, "low_conf"
    return True, conf, ""


def _largest(m: np.ndarray) -> np.ndarray:
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    if n <= 1:
        return np.zeros_like(m, np.uint8)
    return (lab == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)


def _head_zones(head: np.ndarray, zone: np.ndarray, face: tuple) -> None:
    fx, fy, fw, fh = face
    cx = int(fx + fw / 2)
    # Head (hair, ears, glasses, face) down to the chin always stays original; hoods/collars/neck below the chin come from the model.
    cv2.ellipse(head, (cx, int(fy + fh * 0.30)), (int(fw * 0.78), int(fh * 0.68)), 0, 0, 360, 255, -1)
    # Around the head ABOVE the chin, changes are the model's misplaced head/hair (ghost silhouette): keep the original there too.
    cv2.ellipse(zone, (cx, int(fy + fh * 0.30)), (int(fw * 1.15), int(fh * 1.15)), 0, 0, 360, 255, -1)
    zone[int(fy + fh * 0.95):] = 0


def _pose_composite(canvas: np.ndarray, res: np.ndarray, face: tuple, pads: tuple = (0, 0), freeze: list = (), arms=None, force: np.ndarray = None):
    """FACE LOCK for posed photos: original pixels everywhere, generated pixels ONLY where the clothes changed.
    Head (hair, ears, glasses, face) is never taken from the model. Returns (image, changed_fraction).
    `force` (uint8 mask, same size): pixels that are ALWAYS the generated ones, whatever the colour distance says
    (bottom garments: a faded / skin-toned pair must never fall back to the original bare legs)."""
    H, W = canvas.shape[:2]
    s = 512 / max(H, W)
    sw, sh = int(W * s), int(H * s)
    cs = cv2.resize(canvas, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32)
    rs = cv2.resize(res, (sw, sh), interpolation=cv2.INTER_AREA).astype(np.float32)
    gain = np.clip((np.median(rs.reshape(-1, 3), 0) + 1) / (np.median(cs.reshape(-1, 3), 0) + 1), 0.8, 1.25)
    d = np.abs(cv2.GaussianBlur(cs * gain, (0, 0), 1.2) - cv2.GaussianBlur(rs, (0, 0), 1.2)).mean(axis=2)
    ch = (d > 24).astype(np.uint8)
    ch = cv2.morphologyEx(ch, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ch = cv2.morphologyEx(ch, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ch, 8)
    keep = stats[:, cv2.CC_STAT_AREA] >= 0.002 * sw * sh
    keep[0] = False
    ch = keep[lab].astype(np.uint8) * 255
    # CLEAN EDGES: thin changed lines (strong edges like mirror frames / door jambs shifted by a pixel) are not clothes: drop them.
    ch = cv2.morphologyEx(ch, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    # Unchanged islands enclosed by new clothes (skin-coloured prints, labels, hem gap) are fabric, never original skin: fill them.
    cnts, _ = cv2.findContours(ch, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(ch, cnts, -1, 255, -1)
    del cs, rs, d, lab
    frac = float((ch > 0).mean())
    ch = cv2.dilate(ch, np.ones((7, 7), np.uint8))
    ch = cv2.resize(ch, (W, H), interpolation=cv2.INTER_LINEAR)
    head = np.zeros((H, W), np.uint8)
    zone = np.zeros((H, W), np.uint8)
    if face:  # face hidden (e.g. behind the phone): the unchanged-pixel rule alone keeps the original head
        _head_zones(head, zone, face)
    ch[(head > 0) | (zone > 0)] = 0
    # Garments not being tried on (e.g. white paint-splash trousers when only a top is tested) keep the original pixels:
    # no skin holes, same pattern. Only their top band may show the new top's hem, and never as new bare skin there.
    for x0, y0, x1, y1, top_free in freeze:
        px, py = max(2, int((x1 - x0) * 0.04)), max(2, int((y1 - y0) * 0.03))
        X0, Y0, X1, Y1 = max(0, x0 - px), max(0, y0 - py), min(W, x1 + px), min(H, y1 + py)
        if top_free < 0:
            # Hand box: lock only the hand itself (largest skin-in-both blob, eroded so no chest skin/tattoo halo comes back),
            # plus, for a phone hand (-2), the held phone (largest non-skin blob of the original inside the box).
            box = ch[Y0:Y1, X0:X1]
            co, ro = canvas[Y0:Y1, X0:X1], res[Y0:Y1, X0:X1]
            so = _skin(co)
            # Only pixels the model left where they were (the hand/phone itself): chest/tattoo behind it that got new fabric never comes back.
            same = (cv2.GaussianBlur(np.abs(co.astype(np.int16) - ro.astype(np.int16)).mean(axis=2).astype(np.float32), (0, 0), 1.5) < 30).astype(np.uint8)
            lock = _largest(cv2.erode((_skin(ro) > 0).astype(np.uint8) & (so > 0).astype(np.uint8) & same, np.ones((5, 5), np.uint8)))
            if top_free <= -2:
                lock |= cv2.dilate(_largest(cv2.morphologyEx((so == 0).astype(np.uint8) & same, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))), np.ones((3, 3), np.uint8))
            box[lock > 0] = 0
            continue
        yf = Y0 + int((Y1 - Y0) * top_free)
        if yf > Y0:
            band = ch[Y0:yf, X0:X1]
            band[(_skin(res[Y0:yf, X0:X1]) > 0) & (_skin(canvas[Y0:yf, X0:X1]) == 0)] = 0
        ch[yf:Y1, X0:X1] = 0
    if arms is not None:
        # SLEEVE LOCK per arm segment: if the model kept the segment as in the photo (bare forearm, short sleeve) it stays the
        # ORIGINAL skin/tattoos (no invented tattoos); if it put a new sleeve there, the whole segment is the new sleeve (no holes).
        segs, hands = arms
        diff = np.abs(cv2.GaussianBlur(canvas, (0, 0), 1.5).astype(np.int16) - cv2.GaussianBlur(res, (0, 0), 1.5).astype(np.int16)).mean(axis=2)
        for kind, m in segs:
            sel = m > 0
            if not sel.any():
                continue
            same = float((diff[sel] < 20).mean())
            if same > 0.5:
                if kind == "fore":  # bare forearm: only the arm skin itself (skin in photo and result), never the shirt beside it
                    ch[sel & (_skin(canvas) > 0) & (_skin(res) > 0)] = 0
            else:
                ch[sel] = 255
        del diff
        # The hand stays original only where the result still shows that hand (a bag or new grip there comes from the model).
        hand_here = (hands > 0) & (_skin(canvas) > 0) & ((_skin(res) > 0) | (np.abs(canvas.astype(np.int16) - res.astype(np.int16)).mean(axis=2) < 40))
        ch[hand_here | (head > 0) | (zone > 0)] = 0
    if force is not None:
        ch[(force > 0) & (head == 0) & (zone == 0)] = 255
    # Top/bottom pad bands are not part of the photo: always the model's continuation of the scene.
    if pads[0]:
        ch[:pads[0]] = 255
    if pads[1]:
        ch[H - pads[1]:] = 255
    w = cv2.GaussianBlur(ch, (0, 0), 2.0).astype(np.float32) * (1 / 255)
    out = cv2.blendLinear(res, canvas, w, 1 - w)
    del w, ch, head, zone
    return out, frac


def _align_pose(canvas: np.ndarray, res: np.ndarray) -> np.ndarray:
    """Register the generated image onto the original by matching background features (similarity transform, RANSAC)."""
    H, W = canvas.shape[:2]
    s = 0.5
    g1 = cv2.cvtColor(cv2.resize(canvas, (int(W * s), int(H * s))), cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(cv2.resize(res, (int(W * s), int(H * s))), cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(2000)
    k1, d1 = orb.detectAndCompute(g1, None)
    k2, d2 = orb.detectAndCompute(g2, None)
    if d1 is None or d2 is None:
        return res
    m = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d2, d1), key=lambda x: x.distance)[:500]
    if len(m) < 30:
        return res
    src = np.float32([k2[x.queryIdx].pt for x in m])
    dst = np.float32([k1[x.trainIdx].pt for x in m])
    M, inl = cv2.estimateAffinePartial2D(src, dst, ransacReprojThreshold=3.0)
    if M is None or inl is None or int(inl.sum()) < 20:
        return res
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    rot = abs(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    if not (0.8 < scale < 1.25) or rot > 3:
        return res
    M[:, 2] /= s
    if abs(scale - 1) < 0.004 and abs(M[0, 2]) < 1 and abs(M[1, 2]) < 1:
        return res
    logger.info("head_lock: pose align scale=%.3f shift=(%.1f, %.1f) inliers=%d", scale, M[0, 2], M[1, 2], int(inl.sum()))
    return cv2.warpAffine(res, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)


POSE_CHANGE_MAX = 0.75


def surgical_merge(orig_jpeg: bytes, result_bytes: bytes, freeze: list) -> bytes:
    """Dedicated try-on output -> original pixels everywhere except the changed clothing (face/hair/hands/skin/background locked)."""
    orig = np.array(Image.open(io.BytesIO(orig_jpeg)).convert("RGB"))
    H, W = orig.shape[:2]
    res = Image.open(io.BytesIO(result_bytes)).convert("RGB")
    rw, rh = res.size
    if abs(rw / rh - W / H) > 0.02:
        # Engine changed the aspect: fit by width/height (centre), then feature registration fixes the rest.
        sc = max(W / rw, H / rh)
        res = res.resize((int(rw * sc), int(rh * sc)), Image.LANCZOS)
        l, t = (res.width - W) // 2, (res.height - H) // 2
        res = res.crop((l, t, l + W, t + H))
    else:
        res = res.resize((W, H), Image.LANCZOS)
    res = _align_pose(orig, np.array(res))
    face = _face_box(orig)
    if not face:
        raise ValueError("no face in original")
    fz = []
    for z in freeze:
        y0, x0, y1, x1 = (max(0.0, min(1000.0, float(v))) / 1000 for v in z["box"])
        fz.append((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H), float(z.get("top_free", 0))))
    out, frac = _pose_composite(orig, res, face, (0, 0), fz)
    logger.info("head_lock: surgical merge changed=%.2f", frac)
    buf = io.BytesIO()
    Image.fromarray(out).save(buf, "PNG")
    return buf.getvalue()


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


DRIFT_MAX = 28.0


def _skin(a: np.ndarray) -> np.ndarray:
    return cv2.inRange(cv2.cvtColor(np.ascontiguousarray(a), cv2.COLOR_RGB2YCrCb), (0, 133, 77), (255, 173, 127))


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
    cv2.ellipse(m, (bw // 2, bh // 2), (int(bw * 0.40), int(bh * 0.40)), 0, 0, 360, 255, -1)
    m = cv2.GaussianBlur(m, (0, 0), max(2, min(bw, bh) * 0.08)).astype(np.float32) * (1 / 255)
    # Seam check: if what surrounds the hand changed (e.g. new garment under it), a pasted patch would show edges.
    src, dst = canvas[y0:y1, x0:x1].astype(np.int16), out[ty0:ty1, tx0:tx1].astype(np.int16)
    ring = (m > 0.05) & (m < 0.5)
    seam = float(np.abs(src - dst).mean(axis=2)[ring].mean()) if ring.any() else 0.0
    if seam > 28:
        logger.info("head_lock: surroundings of the hand changed (seam %.1f), keeping generated hand", seam)
        return False
    # Paste only where the model kept roughly the same pixel (the hand): never drag original body pixels over a new garment.
    near = (np.abs(src - dst).mean(axis=2) < 38).astype(np.uint8) * 255
    core = m > 0.5
    if near[core].mean() / 255 < 0.45:
        logger.info("head_lock: generated hand area differs from the original, keeping generated hand")
        return False
    near = cv2.GaussianBlur(cv2.morphologyEx(near, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)), (0, 0), max(1.5, min(bw, bh) * 0.03))
    m = m * near.astype(np.float32) * (1 / 255)
    out[ty0:ty1, tx0:tx1] = cv2.blendLinear(canvas[y0:y1, x0:x1], out[ty0:ty1, tx0:tx1], m, 1 - m)
    logger.info("head_lock: original hand restored (match %.2f, seam %.1f, shift %d,%d)", score, seam, dx, dy)
    return True


def prepare(person_bytes: bytes, long_garment: bool, hands: list = None, paste_hands=True, pose: bool = False, freeze: list = None, extend: float = 0.0) -> tuple:
    """paste_hands: bool for all hands, or one bool per hand box (False = the model may redraw that hand)."""
    # Returns (canvas_png_bytes, meta) with top safe margin and optional bottom extension.
    im = np.array(_open_small(person_bytes, PERSON_OUT_SIDE).convert("RGB"))
    h, w = im.shape[:2]
    top = max(TOP_PAD_MIN_PX, int(h * TOP_PAD_RATIO))
    bottom = int(h * extend) if extend else (int(h * BOTTOM_PAD_RATIO) if long_garment else 0)
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
    # Frozen garment zones (normalised boxes) -> canvas pixels; the top part may be covered by the new top's hem.
    freeze_c = []
    for z in freeze or []:
        y0, x0, y1, x1 = (max(0.0, min(1000.0, float(v))) / 1000 for v in z["box"])
        if x1 - x0 > 0.02 and y1 - y0 > 0.02:
            freeze_c.append((int(x0 * w), int(y0 * h) + top, int(x1 * w), int(y1 * h) + top, float(z.get("top_free", 0))))
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
    return buf.getvalue(), {"canvas": canvas, "mask": mask, "face": face_c, "hands": paste_c, "pose": pose, "pads_px": (top, bottom), "freeze": freeze_c}


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
        return canvas, 0.0
    c = canvas[Y0:Y1, X0:X1]
    r = res[Y0:Y1, X0:X1][ring].astype(np.float32)
    gain = (np.median(r, 0) + 1) / (np.median(c[ring], 0) + 1)
    gain = np.clip(gain, 0.75, 1.33)
    # Scene drift: how different the background around the head still is after the colour match (new scene -> halo risk).
    drift = float(np.median(np.abs(c[ring].astype(np.float32) * gain - r).mean(axis=1)))
    if np.abs(gain - 1).max() < 0.02:
        return canvas, drift
    canvas = canvas.copy()
    canvas[Y0:Y1, X0:X1] = np.clip(c.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    return canvas, drift


def _register(canvas: np.ndarray, res: np.ndarray):
    """Map the generated image onto the original framing from background features, whatever size/aspect/zoom the model used."""
    H, W = canvas.shape[:2]
    rh, rw = res.shape[:2]
    sc, sr = 1024 / max(H, W), 1024 / max(rh, rw)
    g1 = cv2.cvtColor(cv2.resize(canvas, (int(W * sc), int(H * sc))), cv2.COLOR_RGB2GRAY)
    g2 = cv2.cvtColor(cv2.resize(res, (int(rw * sr), int(rh * sr))), cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(4000)
    k1, d1 = orb.detectAndCompute(g1, None)
    k2, d2 = orb.detectAndCompute(g2, None)
    if d1 is None or d2 is None or len(k1) < 30 or len(k2) < 30:
        return None
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d2, d1, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < 0.8 * p[1].distance]
    if len(good) < 30:
        return None
    src = np.float32([k2[m.queryIdx].pt for m in good]) / sr
    dst = np.float32([k1[m.trainIdx].pt for m in good]) / sc
    M, inl = cv2.estimateAffinePartial2D(src, dst, ransacReprojThreshold=4.0 / sc)
    if M is None or inl is None or int(inl.sum()) < 25:
        return None
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    ref = max(W / rw, H / rh)  # the model may answer at any resolution: judge the zoom relative to a plain fit
    if not (0.4 < scale / ref < 2.5) or abs(np.degrees(np.arctan2(M[1, 0], M[0, 0]))) > 4:
        return None
    logger.info("head_lock: registered result scale=%.3f shift=(%.0f, %.0f) inliers=%d", scale, M[0, 2], M[1, 2], int(inl.sum()))
    out = cv2.warpAffine(res, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE)
    # Where the generated image does not reach (model framed tighter), keep the original photo: never stretched edge stripes.
    cover = cv2.warpAffine(np.full((rh, rw), 255, np.uint8), M, (W, H), flags=cv2.INTER_NEAREST, borderValue=0)
    cover = cv2.erode(cover, np.ones((3, 3), np.uint8))
    out[cover == 0] = canvas[cover == 0]
    return out


def finalize(result_bytes: bytes, meta: dict) -> bytes:
    canvas, mask = meta["canvas"], meta["mask"]
    H, W = canvas.shape[:2]
    res = np.array(_open_small(result_bytes, max(H, W)).convert("RGB"))
    del result_bytes
    rh, rw = res.shape[:2]
    reg = _register(canvas, res) if meta.get("pose") else None
    if reg is not None:
        # Posed photo registered on the background: composite directly (face position no longer needed for alignment).
        out, frac = _pose_composite(canvas, reg, meta.get("face"), meta.get("pads_px", (0, 0)), meta.get("freeze", ()), meta.get("arms"))
        logger.info("head_lock: pose composite (registered) changed=%.2f", frac)
        meta.clear()
        meta["drift"] = 0.0
        meta["pose_fail"] = frac > POSE_CHANGE_MAX
        buf = io.BytesIO()
        Image.fromarray(out).save(buf, "PNG")
        return buf.getvalue()
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
    of = meta.get("face")
    # Match the generated face to the ORIGINAL one by position (not by detector rank: a poster/mirror face must not win).
    cand = _faces(res)
    rf = min(cand, key=lambda b: (_centre(b)[0] - _centre(of)[0]) ** 2 + (_centre(b)[1] - _centre(of)[1]) ** 2) if (cand and of) else (cand[0] if cand else None)
    head_at = of  # where the ORIGINAL head will be pasted
    aligned = not of  # no detected face: only the top safe-zone band is restored
    if rf and of and 0.6 < of[2] / rf[2] < 1.6:
        aligned = True
        sc = of[2] / rf[2]
        ocx, ocy = of[0] + of[2] / 2, of[1] + of[3] / 2
        rcx, rcy = rf[0] + rf[2] / 2, rf[1] + rf[3] / 2
        if meta.get("pose"):
            # Posed photo: original pixels stay untouched; the generated image is moved onto the original framing.
            res = _align_pose(canvas, res)
        elif abs(sc - 1) > 0.02 or abs(ocx - rcx) > 3 or abs(ocy - rcy) > 3:
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
    if meta.get("pose"):
        # Posed photo: never keep a generated face. Misaligned or new scene -> flag so the render loop regenerates.
        out, frac = (_pose_composite(canvas, res, head_at, meta.get("pads_px", (0, 0)), meta.get("freeze", ()), meta.get("arms")) if aligned and head_at else (res, 1.0))
        logger.info("head_lock: pose composite changed=%.2f aligned=%s", frac, aligned)
        del res, canvas, mask
        meta.clear()
        meta["drift"] = 0.0
        meta["pose_fail"] = frac > POSE_CHANGE_MAX
        buf = io.BytesIO()
        Image.fromarray(out).save(buf, "PNG")
        del out
        gc.collect()
        return buf.getvalue()
    if not aligned:
        # Pasting the original head onto a misplaced generated one would create a double face: keep the model output.
        logger.warning("head_lock: generated head not aligned with original %s, skipping head paste", head_at)
        mask = np.zeros_like(mask)
    drift = 0.0
    if mask.any():
        canvas, drift = _match_head_colour(canvas, res, mask)
        logger.info("head_lock: background drift around head %.1f", drift)
        if drift > DRIFT_MAX and head_at:
            # Background around the head changed: paste only a tight face oval so no old scene shows as a halo.
            fx, fy, fw, fh = head_at
            tight = np.zeros_like(mask)
            cv2.ellipse(tight, (int(fx + fw / 2), int(fy + fh * 0.52)), (int(fw * 0.6), int(fh * 0.78)), 0, 0, 360, 255, -1)
            tight = cv2.GaussianBlur(tight, (0, 0), max(3, fw / 14))
            mask = np.minimum(mask, tight)
            logger.info("head_lock: scene drift %.1f around the head, tight face paste only", drift)
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
    meta["drift"] = drift
    buf = io.BytesIO()
    Image.fromarray(out).save(buf, "PNG")
    del out
    gc.collect()
    return buf.getvalue()


def has_face(jpeg: bytes) -> bool:
    return _face_box(np.array(Image.open(io.BytesIO(jpeg)).convert("RGB"))) is not None


def crop_screenshot(data: bytes) -> bytes:
    """Phone screenshot of an app showing the photo (UI bars, text, buttons): keep only the embedded photo."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    # Letterbox bars (flat black/white rows or columns at the edges) are not part of the photo.
    a = np.asarray(img.convert("L"), np.float32)
    # A bar row/column is flat, or almost all black/white (phone navigation bar with tiny icons).
    bar = lambda v: (v.std() < 4) or ((v < 25).mean() > 0.85) or ((v > 235).mean() > 0.97)  # noqa: E731
    rows = np.array([bar(r) for r in a])
    cols = np.array([bar(c) for c in a.T])
    t = int(np.argmin(rows)) if rows.any() else 0
    b = len(rows) - int(np.argmin(rows[::-1])) if rows.any() else len(rows)
    lft = int(np.argmin(cols)) if cols.any() else 0
    rgt = len(cols) - int(np.argmin(cols[::-1])) if cols.any() else len(cols)
    if (t or b < len(rows) or lft or rgt < len(cols)) and (b - t) > 0.3 * len(rows) and (rgt - lft) > 0.3 * len(cols):
        logger.info("head_lock: letterbox trimmed to x=%d-%d y=%d-%d", lft, rgt, t, b)
        img = img.crop((lft, t, rgt, b))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=95)
        data = buf.getvalue()
    W, H = img.size
    small = np.array(img.resize((max(1, W // 2), max(1, H // 2))))
    g = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    edges = cv2.dilate(cv2.Canny(g, 30, 100), np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sh, sw = g.shape
    best = None
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if 0.18 * sw * sh < w * h < 0.85 * sw * sh and w > 0.6 * sw and cv2.contourArea(cv2.convexHull(c)) > 0.9 * w * h:
            if best is None or w * h > best[2] * best[3]:
                best = (x, y, w, h)
    if best is None:
        return data
    x, y, w, h = best
    # The UI around the photo must be mostly flat (white/grey bars), otherwise this is a normal photo.
    ring = np.ones((sh, sw), bool)
    ring[y:y + h, x:x + w] = False
    if g[ring].std() > 45 and (np.abs(g[ring].astype(int) - int(np.median(g[ring]))) < 12).mean() < 0.7:
        return data
    box = (2 * x + 6, 2 * y + 6, 2 * (x + w) - 6, 2 * (y + h) - 6)
    logger.info("head_lock: screenshot detected, using embedded photo %s of %sx%s", box, W, H)
    buf = io.BytesIO()
    img.crop(box).save(buf, "JPEG", quality=95)
    return buf.getvalue()
