# Manual REAL renders (sequential): pose single try-on with phone selfie -> free retry (phone must stay removed); grid outfit retry flag check.
# usage: python run_pose_retry_render.py single|retry <tryon_id> [reason]
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
    print("elapsed", int(time.time() - t0), j.status_code, str(j.json())[:600])
    res = j.json().get("result") or {}
    rp = res.get("result_path") or res.get("result_image_path")
    if rp:
        open(out, "wb").write(requests.get(f"{B}/api/files/{rp}", headers=H).content); print("saved", out, rp)
    return res


mode = sys.argv[1]
if mode == "single":
    pp, gp = up("/tmp/phone_selfie.jpg", "person"), up("/tmp/tee.jpg", "garment")
    r = requests.post(f"{B}/api/tryon/generate", headers=H, json={"person_path": pp, "garment_path": gp, "preserve_pose": True, "garment_category": "top", "garment_name": "T-shirt bianca"})
    print(r.status_code, r.text[:200]); res = wait(r.json()["job_id"], "/tmp/r1_first.jpg")
    print("RESULT", {k: res.get(k) for k in ("id", "preserve_pose", "person_path", "result_path")})
elif mode == "retry":
    tid, reason = sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "mani_viso")
    print("state", requests.get(f"{B}/api/tryons/{tid}/retry", headers=H).json())
    r = requests.post(f"{B}/api/tryons/{tid}/retry", headers=H, json={"reason": reason})
    print(r.status_code, r.text[:200]); res = wait(r.json()["job_id"], "/tmp/r1_retry.jpg")
    print("RESULT", {k: res.get(k) for k in ("id", "preserve_pose", "retry_used", "retry_reason", "previous_result_path", "result_path")})
elif mode == "oretry":
    oid, reason = sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "capo")
    r = requests.post(f"{B}/api/outfits/{oid}/retry", headers=H, json={"reason": reason})
    print(r.status_code, r.text[:200]); res = wait(r.json()["job_id"], "/tmp/g_retry.jpg")
    print("RESULT", {k: res.get(k) for k in ("id", "preserve_pose", "retry_used", "result_path")})
