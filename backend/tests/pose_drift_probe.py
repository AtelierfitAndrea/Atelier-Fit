# Manual probe: how robust is the pose changed-fraction to tiny model drift (zoom / shift / aspect padding / noise)?
import io
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import head_lock  # noqa: E402
import logging; logging.basicConfig(level=logging.INFO, format="  %(message)s")
import tryon_quality  # noqa: E402

pb = open("/tmp/owner_pose.jpg", "rb").read()
_png, meta = head_lock.prepare(pb, False, pose=True)
canvas = meta["canvas"]
H, W = canvas.shape[:2]
print("canvas", W, H, "aspect sent", tryon_quality._aspect(meta), "face", meta["face"])


def run(name, res):
    m = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in meta.items()}
    b = io.BytesIO()
    Image.fromarray(res).save(b, "JPEG", quality=90)
    head_lock.finalize(b.getvalue(), m)
    print(f"{name:28s} pose_fail={m['pose_fail']}")


run("identical", canvas)
# model returns 9:16 by outpainting the sides (person same size)
nw = int(H * 9 / 16)
lp = (nw - W) // 2
run("9:16 side outpaint", cv2.copyMakeBorder(canvas, 0, 0, lp, nw - W - lp, cv2.BORDER_REFLECT))
for z in (1.01, 1.02, 1.04):
    M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, z)
    run(f"zoom {z}", cv2.warpAffine(canvas, M, (W, H), borderMode=cv2.BORDER_REFLECT))
for s in (2, 5, 10):
    run(f"shift {s}px", cv2.warpAffine(canvas, np.float32([[1, 0, s], [0, 1, s]]), (W, H), borderMode=cv2.BORDER_REFLECT))
noisy = np.clip(canvas.astype(np.float32) * 1.05 + np.random.default_rng(0).normal(0, 6, canvas.shape), 0, 255).astype(np.uint8)
run("noise + 5% brighter", noisy)
