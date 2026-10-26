# Render jobs (background AI renders + polling): job pattern, errors propagated with original codes, ownership, 2K signed JPEG.
import io
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
OWNER = "user_389c87aaadc6"
TOKEN = "t1_render_tok"
AVATAR = "vfit/avatar/user_389c87aaadc6/e2bf1a90a05440ab97ba1d73de3e7ecf.bin"
GARMENT = "vfit/garment/user_389c87aaadc6/768957e7bf1c4ccbb3cb5bf01e90e899.jpg"
FOREIGN = "vfit/garment/someone_else/abc.jpg"

mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module")
def s():
    if not mongo.user_sessions.find_one({"session_token": TOKEN}):
        pytest.skip("no test session")
    ses = requests.Session()
    ses.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return ses


def poll(s, job_id, timeout=300):
    start = time.time()
    seen_running = False
    while time.time() - start < timeout:
        r = s.get(f"{API}/render-jobs/{job_id}")
        if r.status_code != 200:
            return r, seen_running
        if r.json()["status"] == "done":
            return r, seen_running
        assert r.json()["status"] == "running"
        seen_running = True
        time.sleep(3)
    raise AssertionError("job timeout")


def start(s, url, body):
    r = s.post(f"{API}{url}", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "running" and isinstance(d["job_id"], str)
    return d["job_id"]


# --- auth / ownership ---
class TestJobAccess:
    def test_unauthenticated_401(self):
        assert requests.get(f"{API}/render-jobs/whatever").status_code == 401

    def test_unknown_job_404(self, s):
        assert s.get(f"{API}/render-jobs/{uuid.uuid4()}").status_code == 404

    def test_other_users_job_404(self, s):
        jid = f"TEST_{uuid.uuid4()}"
        mongo.render_jobs.insert_one({"id": jid, "user_id": "someone_else", "status": "done", "result": {"x": 1}})
        try:
            assert s.get(f"{API}/render-jobs/{jid}").status_code == 404
        finally:
            mongo.render_jobs.delete_one({"id": jid})

    def test_post_unauthenticated_401(self):
        assert requests.post(f"{API}/tryon/generate", json={"person_path": AVATAR, "garment_path": GARMENT}).status_code == 401


# --- validation errors surface through GET render-jobs with original status code ---
class TestJobErrors:
    def test_outfit_one_garment_400(self, s):
        r, _ = poll(s, start(s, "/outfit/generate", {"garment_ids": ["a"]}), 30)
        assert r.status_code == 400 and "da 2 a 4" in r.json()["detail"]

    def test_outfit_unknown_garment_404(self, s):
        r, _ = poll(s, start(s, "/outfit/generate", {"garment_ids": ["TEST_nope1", "TEST_nope2"]}), 30)
        assert r.status_code == 404 and "non trovato" in r.json()["detail"]

    def test_grid_foreign_path_403(self, s):
        r, _ = poll(s, start(s, "/outfit/generate-from-uploads", {"items": [{"slot": "top", "image_path": FOREIGN}]}), 30)
        assert r.status_code == 403

    def test_grid_bad_slot_400(self, s):
        r, _ = poll(s, start(s, "/outfit/generate-from-uploads", {"items": [{"slot": "hat", "image_path": GARMENT}]}), 30)
        assert r.status_code == 400

    def test_copylook_foreign_model_403(self, s):
        r, _ = poll(s, start(s, "/copylook/apply", {"model_path": FOREIGN, "items": [{"name": "x", "category": "top"}]}), 30)
        assert r.status_code == 403

    def test_copylook_no_items_400(self, s):
        r, _ = poll(s, start(s, "/copylook/apply", {"model_path": GARMENT, "items": [{"name": "x", "category": "hat"}]}), 30)
        assert r.status_code == 400

    def test_tryon_retry_unknown_404(self, s):
        r, _ = poll(s, start(s, f"/tryons/TEST_{uuid.uuid4()}/retry", {"reason": "viso"}), 30)
        assert r.status_code == 404

    def test_outfit_retry_unknown_404(self, s):
        r, _ = poll(s, start(s, f"/outfits/TEST_{uuid.uuid4()}/retry", {"reason": "viso"}), 30)
        assert r.status_code == 404

    def test_retry_bad_reason_422(self, s):
        assert s.post(f"{API}/tryons/x/retry", json={"reason": "bogus"}).status_code == 422

    def test_quota_402_via_job(self, s):
        u = mongo.users.find_one({"user_id": OWNER}, {"_id": 0, "free_month_end": 1, "monthly_tryon_count": 1})
        month = time.strftime("%Y-%m")
        mongo.users.update_one({"user_id": OWNER}, {"$set": {"free_month_end": "2020-01-01T00:00:00+00:00",
                                                             "monthly_tryon_count": {"month": (u.get("monthly_tryon_count") or {}).get("month", month), "used": 99}}})
        try:
            r, _ = poll(s, start(s, "/tryon/generate", {"person_path": AVATAR, "garment_path": GARMENT}), 30)
            assert r.status_code == 402
        finally:
            mongo.users.update_one({"user_id": OWNER}, {"$set": {"free_month_end": u.get("free_month_end"), "monthly_tryon_count": u.get("monthly_tryon_count")}})


# --- one REAL generation (costs credits, ~60-150s) ---
@pytest.mark.skipif(os.environ.get("RUN_REAL_RENDER") != "1", reason="set RUN_REAL_RENDER=1 for a real render")
class TestRealTryon:
    def test_single_tryon_job_signed_2k_jpg(self, s):
        from PIL import Image
        t0 = time.time()
        jid = start(s, "/tryon/generate", {"person_path": AVATAR, "garment_path": GARMENT, "garment_name": "TEST_Abito nero",
                                            "garment_category": "dress"})
        assert time.time() - t0 < 10, "POST should return immediately"
        r, seen_running = poll(s, jid, 400)
        print("elapsed", time.time() - t0)
        assert r.status_code == 200, r.text
        assert seen_running
        doc = r.json()["result"]
        assert doc["result_path"].endswith(".jpg")
        f = s.get(f"{API}/files/{doc['result_path']}")
        assert f.status_code == 200 and f.headers["content-type"].startswith("image/jpeg")
        im = Image.open(io.BytesIO(f.content))
        print("size", im.size, "tryon_id", doc["id"])
        open("/tmp/real_tryon.jpg", "wb").write(f.content)
        open("/tmp/real_tryon_id.txt", "w").write(doc["id"])
        assert max(im.size) >= 1536
        # persisted
        assert any(t["id"] == doc["id"] for t in s.get(f"{API}/tryons").json())
