# FACE LOCK credit saver API: /api/pose/check + 422 guard on pose try-on / grid outfit (no AI call, quota unchanged)
import io
import os
import time

import pytest
import requests
from PIL import Image, ImageEnhance

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER = {"Authorization": "Bearer pending_test_tok"}
GOOD = "vfit/person/user_389c87aaadc6/b1a482725d9c4ea2a3b228bd487520e7.jpg"
GARMENT = "vfit/garment/user_389c87aaadc6/6a2a817775de40d396c2d4b4d3cff79e.jpg"


def _upload(img, kind="person"):
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=90)
    r = requests.post(f"{BASE_URL}/api/upload?kind={kind}", headers=OWNER, files={"file": ("x.jpg", b.getvalue(), "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["path"]


def _status():
    return requests.get(f"{BASE_URL}/api/subscription/status", headers=OWNER).json()


def _wait(job_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{BASE_URL}/api/render-jobs/{job_id}", headers=OWNER)
        if r.status_code != 200 or r.json().get("status") != "running":
            return r
        time.sleep(1.5)
    raise AssertionError("job still running")


@pytest.fixture(scope="module")
def bad_paths():
    pose = requests.get(f"{BASE_URL}/api/files/{GOOD}", headers=OWNER).content
    im = Image.open(io.BytesIO(pose))
    dark = _upload(ImageEnhance.Brightness(im).enhance(0.15))
    noface = _upload(Image.new("RGB", (800, 1200), (180, 170, 160)))
    yield {"dark": dark, "noface": noface}
    for p in (dark, noface):
        requests.delete(f"{BASE_URL}/api/files/{p}", headers=OWNER)


def test_pose_check_auth():
    assert requests.post(f"{BASE_URL}/api/pose/check", json={"path": GOOD}).status_code == 401


def test_pose_check_foreign_path():
    r = requests.post(f"{BASE_URL}/api/pose/check", headers=OWNER, json={"path": "vfit/person/someone_else/x.jpg"})
    assert r.status_code in (403, 404)


def test_pose_check_good():
    r = requests.post(f"{BASE_URL}/api/pose/check", headers=OWNER, json={"path": GOOD})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True and d["confidence"] >= 0.75 and d["reason"] == "" and "_id" not in d


def test_pose_check_bad(bad_paths):
    for k, p in bad_paths.items():
        d = requests.post(f"{BASE_URL}/api/pose/check", headers=OWNER, json={"path": p}).json()
        assert d["ok"] is False, (k, d)
        assert d["message"] and ("luminosa" in d["message"] or "viso" in d["message"].lower()), d
        # cached: second call identical
        d2 = requests.post(f"{BASE_URL}/api/pose/check", headers=OWNER, json={"path": p}).json()
        assert d2 == d


def test_tryon_pose_guard_422(bad_paths):
    before = _status()
    n_before = len(requests.get(f"{BASE_URL}/api/tryons", headers=OWNER).json() or [])
    r = requests.post(f"{BASE_URL}/api/tryon/generate", headers=OWNER, json={
        "person_path": bad_paths["dark"], "garment_path": GARMENT, "garment_name": "TEST_shirt", "garment_category": "top", "preserve_pose": True})
    assert r.status_code == 200, r.text
    t0 = time.time()
    j = _wait(r.json()["job_id"])
    assert j.status_code == 422, j.text
    assert "luminosa" in j.json()["detail"]
    assert time.time() - t0 < 15  # no AI call
    after = _status()
    assert {k: after.get(k) for k in ("tryons_used_today", "tryons_used_this_month", "tryons_remaining", "boost_credits", "extra_credits", "plan")} == {k: before.get(k) for k in ("tryons_used_today", "tryons_used_this_month", "tryons_remaining", "boost_credits", "extra_credits", "plan")}
    assert len(requests.get(f"{BASE_URL}/api/tryons", headers=OWNER).json() or []) == n_before


def test_grid_pose_guard_422(bad_paths):
    before = _status()
    r = requests.post(f"{BASE_URL}/api/outfit/generate-from-uploads", headers=OWNER, json={
        "person_path": bad_paths["noface"], "items": [{"slot": "top", "image_path": GARMENT}], "preserve_pose": True})
    assert r.status_code == 200, r.text
    j = _wait(r.json()["job_id"])
    assert j.status_code in (400, 422), j.text
    if j.status_code == 422:
        assert "viso" in j.json()["detail"].lower() or "luminosa" in j.json()["detail"]
    after = _status()
    assert {k: after.get(k) for k in ("tryons_used_today", "tryons_used_this_month", "tryons_remaining", "boost_credits", "extra_credits", "plan")} == {k: before.get(k) for k in ("tryons_used_today", "tryons_used_this_month", "tryons_remaining", "boost_credits", "extra_credits", "plan")}
