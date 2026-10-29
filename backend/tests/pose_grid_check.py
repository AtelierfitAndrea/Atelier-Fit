# Manual helper (not pytest): real pose GRID render (outfit/generate-from-uploads preserve_pose). Usage: python pose_grid_check.py <person_path> slot=path [slot=path...]
import os
import sys
import time

import requests

B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
H = {"Authorization": "Bearer pending_test_tok"}
items = [{"slot": a.split("=")[0], "image_path": a.split("=", 1)[1]} for a in sys.argv[2:]]
t0 = time.time()
r = requests.post(f"{B}/api/outfit/generate-from-uploads", headers=H, json={"person_path": sys.argv[1], "items": items, "preserve_pose": True})
print("start", r.status_code, r.text, flush=True)
job = r.json()["job_id"]
while True:
    j = requests.get(f"{B}/api/render-jobs/{job}", headers=H)
    if j.status_code != 200 or j.json()["status"] != "running":
        break
    time.sleep(5)
print("done", j.status_code, round(time.time() - t0), j.text[:600], flush=True)
