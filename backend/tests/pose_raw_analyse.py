# Manual probe (not pytest): replay head_lock.finalize steps on saved raw pose outputs and dump canvas | aligned model | change mask | composite. Usage: python pose_raw_analyse.py <person_local_jpg> <long:0|1> raw1 [raw2...]
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import head_lock  # noqa: E402

_png, meta = head_lock.prepare(open(sys.argv[1], "rb").read(), sys.argv[2] == "1", pose=True)
canvas = meta["canvas"]
H, W = canvas.shape[:2]
print("canvas", W, H, "aspect", round(W / H, 3), "face", meta["face"], "pads", meta["pads_px"])
for p in sys.argv[3:]:
    res = np.array(head_lock._open_small(open(p, "rb").read(), max(H, W)).convert("RGB"))
    rh, rw = res.shape[:2]
    if abs(rw / rh - W / H) > 0.04:
        nw = int(rw * H / rh)
        res = cv2.resize(res, (nw, H), interpolation=cv2.INTER_LANCZOS4)
        res = res[:, (nw - W) // 2:(nw - W) // 2 + W] if nw >= W else cv2.copyMakeBorder(res, 0, 0, (W - nw) // 2, W - nw - (W - nw) // 2, cv2.BORDER_REPLICATE)
    else:
        res = cv2.resize(res, (W, H), interpolation=cv2.INTER_LANCZOS4)
    print("==", p, "raw aspect", round(rw / rh, 3), "faces in res", head_lock._faces(res))
    al = head_lock._align_pose(canvas, res)
    out, frac = head_lock._pose_composite(canvas, al, meta["face"], meta["pads_px"])
    d = np.abs(cv2.GaussianBlur(canvas.astype(np.float32), (0, 0), 1.2) - cv2.GaussianBlur(al.astype(np.float32), (0, 0), 1.2)).mean(2)
    print("changed frac", round(frac, 3), "diff>24 thirds", [round(float((d[i * H // 3:(i + 1) * H // 3] > 24).mean()), 3) for i in range(3)],
          "side cols diff>24", round(float((np.concatenate([d[:, :W // 8], d[:, -W // 8:]], 1) > 24).mean()), 3))
    sz = (300, int(300 * H / W))
    mk = ((d > 24) * 255).astype(np.uint8)[..., None].repeat(3, 2)
    Image.fromarray(np.concatenate([cv2.resize(x, sz) for x in (canvas, al, mk, out)], 1)).save(f"/app/test_reports/fl58/an_{os.path.basename(p).split('.')[0]}.png")
