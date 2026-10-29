# Manual helper (not pytest): compare a finished pose try-on result vs its original photo. Usage: python pose_result_diff.py <tryon_id>
import io
import os
import sys

import cv2
import numpy as np
import requests
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import head_lock  # noqa: E402

B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
H = {"Authorization": "Bearer pending_test_tok"}
t = requests.get(f"{B}/api/tryons/{sys.argv[1]}", headers=H).json()
orig = np.array(head_lock._open_small(requests.get(f"{B}/api/files/{t['person_path']}", headers=H).content, head_lock.PERSON_OUT_SIDE).convert("RGB"))
out = np.array(Image.open(io.BytesIO(requests.get(f"{B}/api/files/{t['result_path']}", headers=H).content)).convert("RGB"))
print("orig", orig.shape, "out", out.shape)
f, fo = head_lock._face_box(orig), head_lock._face_box(out)
print("face orig", f, "face out", fo)
# locate the original head crop inside the result by template matching (result may be trimmed/shifted)
fx, fy, fw, fh = f
y0 = max(0, int(fy - fh * 0.5))
tpl = orig[y0:fy + fh, fx:fx + fw]
r = cv2.matchTemplate(out, tpl, cv2.TM_SQDIFF)
_mn, _mx, (mx, my), _ = cv2.minMaxLoc(r)
b = out[my:my + tpl.shape[0], mx:mx + tpl.shape[1]]
print("head offset", mx - fx, my - y0, "head crop mean abs diff", round(float(np.abs(b.astype(int) - tpl.astype(int)).mean()), 2))
dx, dy = mx - fx, my - y0
hh = min(orig.shape[0], out.shape[0] - dy) if dy >= 0 else min(orig.shape[0] + dy, out.shape[0])
if dx == 0 and dy >= 0 and out.shape[1] == orig.shape[1]:
    d = np.abs(orig[:hh].astype(int) - out[dy:dy + hh].astype(int)).mean(axis=2)
    w = d.shape[1]
    print("whole diff", round(float(d.mean()), 2), "frac>24", round(float((d > 24).mean()), 3),
          "side bg diff", round(float(np.concatenate([d[:, : w // 8], d[:, -w // 8:]], 1).mean()), 2))
    # ring around head (halo check): pixels just outside head ellipse
    m = np.zeros(d.shape, np.uint8)
    cv2.ellipse(m, (int(fx + fw / 2), int(fy + fh * 0.38)), (int(fw * 0.82), int(fh * 0.98)), 0, 0, 360, 255, -1)
    ring = cv2.dilate(m, np.ones((25, 25), np.uint8)) - m
    print("diff in 12px ring outside head lock", round(float(d[ring > 0].mean()), 2))
side = np.concatenate([cv2.resize(orig, (400, int(400 * orig.shape[0] / orig.shape[1]))), cv2.resize(out, (400, int(400 * orig.shape[0] / orig.shape[1])))], 1)
Image.fromarray(side).save(f"/app/test_reports/fl57/cmp_{sys.argv[1][:8]}.png")
hc = (slice(max(0, fy - fh), min(orig.shape[0], fy + 2 * fh)), slice(max(0, fx - fw), min(orig.shape[1], fx + 2 * fw)))
hco = (slice(max(0, fy - fh + dy), min(out.shape[0], fy + 2 * fh + dy)), slice(max(0, fx - fw + dx), min(out.shape[1], fx + 2 * fw + dx)))
a, c = orig[hc], out[hco]
c = cv2.resize(c, (a.shape[1], a.shape[0]))
Image.fromarray(np.concatenate([a, c], 1)).save(f"/app/test_reports/fl57/head_{sys.argv[1][:8]}.png")
