"""Universal Pose Lock (DWPose, local ONNX, free): skeleton of the original photo as a pose guide + rejection of results whose pose moved."""
import io
import logging
import threading
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

logger = logging.getLogger(__name__)
MODEL = str(Path(__file__).parent / "models" / "dw-ll_ucoco_384.onnx")
IN_W, IN_H = 288, 384
MEAN, STD = np.array([123.675, 116.28, 103.53], np.float32), np.array([58.395, 57.12, 57.375], np.float32)
# COCO body: shoulders, elbows, wrists, hips, knees, ankles + 6 foot points (17-22).
JOINTS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
BONES = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
         (15, 17), (15, 19), (16, 20), (16, 22), (0, 5), (0, 6)]
POSE_DEV_MAX = 0.30  # max limb-joint shift, as a fraction of the torso length
MIN_SCORE = 0.45
_lock = threading.Lock()
_sess = None


MODEL_URL = "https://huggingface.co/yzd-v/DWPose/resolve/main/dw-ll_ucoco_384.onnx"


def _session():
    global _sess
    if _sess is None:
        if not Path(MODEL).exists():
            # Model is too large for the repo: fetched once on first use.
            import requests
            tmp = MODEL + ".part"
            with requests.get(MODEL_URL, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            Path(tmp).rename(MODEL)
            logger.info("pose_lock: DWPose model downloaded")
        _sess = ort.InferenceSession(MODEL, providers=["CPUExecutionProvider"])
    return _sess


def _run(rgb: np.ndarray, box) -> np.ndarray:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = (x1 - x0) * 1.25, (y1 - y0) * 1.25
    if w / h > IN_W / IN_H:
        h = w * IN_H / IN_W
    else:
        w = h * IN_W / IN_H
    src = np.float32([[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx - w / 2, cy + h / 2]])
    dst = np.float32([[0, 0], [IN_W, 0], [0, IN_H]])
    crop = cv2.warpAffine(rgb, cv2.getAffineTransform(src, dst), (IN_W, IN_H), flags=cv2.INTER_LINEAR)
    x = ((crop.astype(np.float32) - MEAN) / STD).transpose(2, 0, 1)[None]
    with _lock:
        sx, sy = _session().run(None, {"input": x})
    px, py = sx[0].argmax(1) / 2.0, sy[0].argmax(1) / 2.0
    score = np.minimum(sx[0].max(1), sy[0].max(1))
    return np.stack([cx - w / 2 + px * w / IN_W, cy - h / 2 + py * h / IN_H, score], 1)


def keypoints(rgb: np.ndarray):
    """(133, 3) array [x_px, y_px, score] (COCO-WholeBody), or None when no body is found."""
    H, W = rgb.shape[:2]
    kp = _run(rgb, (0, 0, W, H))
    good = kp[:23][kp[:23, 2] > MIN_SCORE]
    if len(good) < 6:
        return None
    # Second pass on the person box for precision.
    x0, y0 = good[:, :2].min(0)
    x1, y1 = good[:, :2].max(0)
    pad = 0.15 * max(x1 - x0, y1 - y0)
    return _run(rgb, (max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)))


def skeleton_png(img_bytes: bytes):
    """Pose guide image (white bones on black, same framing as the photo), or None."""
    rgb = np.array(Image.open(io.BytesIO(img_bytes)).convert("RGB"))
    kp = keypoints(rgb)
    if kp is None:
        return None
    out = np.zeros_like(rgb)
    th = max(3, rgb.shape[1] // 120)
    for a, b in BONES:
        if kp[a, 2] > MIN_SCORE and kp[b, 2] > MIN_SCORE:
            cv2.line(out, (int(kp[a, 0]), int(kp[a, 1])), (int(kp[b, 0]), int(kp[b, 1])), (255, 255, 255), th, cv2.LINE_AA)
    for i in JOINTS:
        if kp[i, 2] > MIN_SCORE:
            cv2.circle(out, (int(kp[i, 0]), int(kp[i, 1])), th * 2, (0, 200, 255), -1, cv2.LINE_AA)
    buf = io.BytesIO()
    Image.fromarray(out).save(buf, "PNG")
    return buf.getvalue()


def is_half_body(img_bytes: bytes) -> bool:
    """True when the feet are not in the photo (portrait / half figure): no visible ankle inside the frame."""
    rgb = np.array(Image.open(io.BytesIO(img_bytes)).convert("RGB"))
    kp = keypoints(rgb)
    if kp is None:
        return False
    ank = kp[[15, 16]]
    return bool(((ank[:, 2] < MIN_SCORE) | (ank[:, 1] > rgb.shape[0] * 0.97)).all())


def deviation(orig: np.ndarray, res: np.ndarray, upper_only: bool = False):
    """Largest limb-joint shift between original and result (fraction of torso length); None if not measurable."""
    ko = keypoints(orig)
    if ko is None:
        return None
    kr = keypoints(res)
    if kr is None:
        return 1.0
    torso = max(np.hypot(*(ko[5, :2] - ko[11, :2])), np.hypot(*(ko[6, :2] - ko[12, :2])), 1.0)
    idx = [i for i in (JOINTS[:6] if upper_only else JOINTS) if ko[i, 2] > MIN_SCORE and kr[i, 2] > 0.2]
    if len(idx) < 3:
        return None
    # Compare pose SHAPE, not framing: the result skeleton is first fitted (scale/rotation/shift) onto the original one.
    src, dst = kr[idx, :2].astype(np.float32), ko[idx, :2].astype(np.float32)
    M, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
    fit = src @ M[:, :2].T + M[:, 2] if M is not None else src
    devs = np.hypot(*(fit - dst).T) / torso
    return float(devs.max())


def arm_masks(rgb: np.ndarray):
    """(sleeve_force, hand_keep) full-size masks: sleeve strip shoulder->elbow->near wrist, hand = hull of the finger points."""
    kp = keypoints(rgb)
    if kp is None:
        return None
    H, W = rgb.shape[:2]
    force, hands = np.zeros((H, W), np.uint8), np.zeros((H, W), np.uint8)
    for sh, el, wr in ((5, 7, 9), (6, 8, 10)):
        if kp[sh, 2] < MIN_SCORE or kp[el, 2] < MIN_SCORE:
            continue
        upper = float(np.hypot(*(kp[sh, :2] - kp[el, :2])))
        pts = [kp[sh, :2], kp[el, :2]]
        if kp[wr, 2] >= MIN_SCORE:
            pts.append(kp[el, :2] + 0.85 * (kp[wr, :2] - kp[el, :2]))
        cv2.polylines(force, [np.int32(pts)], False, 255, max(6, int(0.45 * upper)), cv2.LINE_AA)
    for lo in (92, 113):  # finger points of each hand (wrist root excluded: the cuff covers it)
        pts = kp[lo:lo + 20]
        pts = pts[pts[:, 2] > 0.3]
        if len(pts) < 6:
            continue
        hull = cv2.convexHull(np.int32(pts[:, :2]))
        cv2.fillConvexPoly(hands, hull, 255)
        span = max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1]))
        hands = cv2.dilate(hands, np.ones((max(3, int(0.12 * span)),) * 2, np.uint8))
    force[hands > 0] = 0
    return force, hands
