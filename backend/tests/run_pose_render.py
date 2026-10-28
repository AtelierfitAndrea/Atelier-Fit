# One real single try-on with preserve_pose:true (manual run; ~40-110s)
import os, time, requests, sys
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
H = {"Authorization": "Bearer pending_test_tok"}
def up(p, kind):
    with open(p, "rb") as f:
        r = requests.post(f"{B}/api/upload?kind={kind}", headers=H, files={"file": (os.path.basename(p), f, "image/jpeg")})
    r.raise_for_status(); return r.json()["path"]
before = requests.get(f"{B}/api/subscription/status", headers=H).json()
pp, gp = up("/tmp/pose.jpg", "person"), up("/tmp/garment.jpg", "garment")
print("paths", pp, gp)
r = requests.post(f"{B}/api/tryon/generate", headers=H, json={"person_path": pp, "garment_path": gp, "garment_category": "outerwear", "garment_name": "bomber jacket", "preserve_pose": True})
print(r.status_code, r.text); job = r.json()["job_id"]
t0 = time.time()
while True:
    time.sleep(5)
    j = requests.get(f"{B}/api/render-jobs/{job}", headers=H)
    if j.status_code != 200 or j.json()["status"] != "running":
        break
print("elapsed", int(time.time() - t0), j.status_code, str(j.json())[:600])
res = j.json().get("result") or {}
rp = res.get("result_path") or res.get("result_image_path")
if rp:
    img = requests.get(f"{B}/api/files/{rp}", headers=H)
    open("/tmp/pose_result.jpg", "wb").write(img.content); print("saved", len(img.content))
after = requests.get(f"{B}/api/subscription/status", headers=H).json()
print("used today", before["tryons_used_today"], "->", after["tryons_used_today"])
