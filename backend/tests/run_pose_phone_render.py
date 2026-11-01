# Manual REAL renders (~40-150s each, sequential): grid pose (top+bottom, no phone) and avatar single regression.
# usage: python run_pose_phone_render.py grid|avatar
import os, sys, time, requests
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
H = {"Authorization": "Bearer pending_test_tok"}


def up(p, kind):
    with open(p, "rb") as f:
        r = requests.post(f"{B}/api/upload?kind={kind}", headers=H, files={"file": (os.path.basename(p), f, "image/jpeg")})
    r.raise_for_status(); return r.json()["path"]


def wait(job, out):
    t0 = time.time()
    while True:
        time.sleep(5)
        j = requests.get(f"{B}/api/render-jobs/{job}", headers=H)
        if j.status_code != 200 or j.json()["status"] != "running":
            break
    print("elapsed", int(time.time() - t0), j.status_code, str(j.json())[:500])
    res = j.json().get("result") or {}
    rp = res.get("result_path") or res.get("result_image_path")
    if rp:
        open(out, "wb").write(requests.get(f"{B}/api/files/{rp}", headers=H).content); print("saved", out, rp)
    return res


mode = sys.argv[1]
if mode == "grid":
    pp, tp, bp = up("/tmp/pose_hip.jpg", "person"), up("/tmp/tee.jpg", "garment"), up("/tmp/shorts.jpg", "garment")
    print("person", pp)
    r = requests.post(f"{B}/api/outfit/generate-from-uploads", headers=H, json={"person_path": pp, "preserve_pose": True,
                      "items": [{"slot": "top", "image_path": tp}, {"slot": "bottom", "image_path": bp}]})
    print(r.status_code, r.text[:200]); res = wait(r.json()["job_id"], "/tmp/g2_result.jpg")
elif mode == "avatar":
    gp = up("/tmp/tee.jpg", "garment")
    av = requests.get(f"{B}/api/profile/avatar", headers=H).json().get("path")
    print("avatar", av)
    r = requests.post(f"{B}/api/tryon/generate", headers=H, json={"person_path": av, "garment_path": gp, "preserve_pose": False})
    print(r.status_code, r.text[:200]); res = wait(r.json()["job_id"], "/tmp/g3_result.jpg")
print("RESULT", {k: res.get(k) for k in ("id", "person_path", "result_path", "result_image_path")})
