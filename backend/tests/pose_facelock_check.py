# Manual helper (not pytest): real pose try-on render + head/background pixel diff vs original. Usage: python pose_facelock_check.py <person_path> <garment_path>
import io
import os
import sys
import time

import numpy as np
import requests
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import head_lock  # noqa: E402

B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
H = {"Authorization": "Bearer pending_test_tok"}
person, garment = sys.argv[1], sys.argv[2]
before = requests.get(f"{B}/api/subscription/status", headers=H).json()
t0 = time.time()
r = requests.post(f"{B}/api/tryon/generate", headers=H, json={"person_path": person, "garment_path": garment, "preserve_pose": True, "garment_name": "TEST_pose"})
print("start", r.status_code, r.text, flush=True)
job = r.json()["job_id"]
while True:
    j = requests.get(f"{B}/api/render-jobs/{job}", headers=H)
    if j.status_code != 200 or j.json()["status"] != "running":
        break
    time.sleep(5)
print("done", j.status_code, round(time.time() - t0), j.text[:400], flush=True)
after = requests.get(f"{B}/api/subscription/status", headers=H).json()
print("quota before", {k: before.get(k) for k in ("used", "remaining")}, "after", {k: after.get(k) for k in ("used", "remaining")})
if j.status_code != 200:
    sys.exit()
res = j.json()["result"]
print("TRYON_ID", res["id"], res["result_path"])
orig = np.array(head_lock._open_small(requests.get(f"{B}/api/files/{person}", headers=H).content, head_lock.PERSON_OUT_SIDE).convert("RGB"))
out = np.array(Image.open(io.BytesIO(requests.get(f"{B}/api/files/{res['result_path']}", headers=H).content)).convert("RGB"))
print("orig", orig.shape, "out", out.shape)
Image.fromarray(out).save("/tmp/pose_out.jpg")
f, fo = head_lock._face_box(orig), head_lock._face_box(out)
print("face orig", f, "face out", fo)
if f and fo:
    sc = fo[2] / f[2]
    print("scale", round(sc, 3))
    fx, fy, fw, fh = f
    dx, dy = fo[0] - fx, fo[1] - fy
    a = orig[max(0, int(fy - fh * 0.5)):fy + fh, fx:fx + fw].astype(int)
    b = out[max(0, int(fy - fh * 0.5)) + dy:fy + fh + dy, fx + dx:fx + fw + dx].astype(int)
    if a.shape == b.shape:
        print("offset", dx, dy, "head crop diff", round(float(np.abs(a - b).mean()), 2))
    if abs(sc - 1) < 0.02 and dx == 0:
        ho = min(orig.shape[0], out.shape[0] - dy)
        o2, r2 = orig[:ho], out[dy:dy + ho, :orig.shape[1]]
        if o2.shape == r2.shape:
            d = np.abs(o2.astype(int) - r2.astype(int)).mean(axis=2)
            print("whole diff", round(float(d.mean()), 2), "changed>24 frac", round(float((d > 24).mean()), 3))
            # background columns (outer 12%) diff
            w = o2.shape[1]
            print("side bg diff", round(float(np.concatenate([d[:, : w // 8], d[:, -w // 8:]], 1).mean()), 2))
