# Manual helper (not pytest): avatar-mode try-on regression (preserve_pose false). Usage: python avatar_regression_check.py <garment_path>
import os
import sys
import time

import requests

B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
H = {"Authorization": "Bearer pending_test_tok"}
me = requests.get(f"{B}/api/auth/me", headers=H).json()
avatar = me.get("avatar_path") or "vfit/avatar/user_389c87aaadc6/e2bf1a90a05440ab97ba1d73de3e7ecf.bin"
print("avatar", avatar)
t0 = time.time()
r = requests.post(f"{B}/api/tryon/generate", headers=H, json={"person_path": avatar, "garment_path": sys.argv[1], "garment_name": "TEST_avatar"})
print("start", r.status_code, r.text, flush=True)
job = r.json()["job_id"]
while time.time() - t0 < 110:
    j = requests.get(f"{B}/api/render-jobs/{job}", headers=H)
    if j.status_code != 200 or j.json()["status"] != "running":
        break
    time.sleep(4)
print("done", j.status_code, round(time.time() - t0), j.text[:300], flush=True)
