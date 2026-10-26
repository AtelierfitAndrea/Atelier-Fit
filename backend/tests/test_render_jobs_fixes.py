# Iteration 42: render-job fixes — IDOR on tryon/outfit paths, 1 running job per user (409), TTL index, pad-band trim.
import io
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import numpy as np
import pytest
import requests
from PIL import Image
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
OWNER = "user_389c87aaadc6"
TOKEN = "t1_render_tok"
AVATAR = "vfit/avatar/user_389c87aaadc6/e2bf1a90a05440ab97ba1d73de3e7ecf.bin"
GARMENT = "vfit/garment/user_389c87aaadc6/768957e7bf1c4ccbb3cb5bf01e90e899.jpg"
FOREIGN_PERSON = "vfit/avatar/someone_else/abc.bin"
FOREIGN_GARMENT = "vfit/garment/someone_else/abc.jpg"
BUSY = "Hai già una foto in preparazione: attendi che finisca."

mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module")
def s():
    if not mongo.user_sessions.find_one({"session_token": TOKEN}):
        pytest.skip("no test session")
    ses = requests.Session()
    ses.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return ses


def poll(s, job_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = s.get(f"{API}/render-jobs/{job_id}")
        if r.status_code != 200 or r.json()["status"] == "done":
            return r
        time.sleep(1.5)
    raise AssertionError("job timeout")


def wait_idle(timeout=30):
    t0 = time.time()
    while mongo.render_jobs.find_one({"user_id": OWNER, "status": "running"}) and time.time() - t0 < timeout:
        time.sleep(0.5)


# --- Fix 1: IDOR ---
class TestIdor:
    @pytest.mark.parametrize("body", [
        {"person_path": FOREIGN_PERSON, "garment_path": GARMENT},
        {"person_path": AVATAR, "garment_path": FOREIGN_GARMENT},
    ])
    def test_tryon_foreign_path_403(self, s, body):
        wait_idle()
        r = s.post(f"{API}/tryon/generate", json=body)
        assert r.status_code == 200, r.text
        g = poll(s, r.json()["job_id"])
        assert g.status_code == 403 and g.json()["detail"] == "Accesso negato"

    def test_outfit_foreign_person_403(self, s):
        wait_idle()
        r = s.post(f"{API}/outfit/generate", json={"garment_ids": ["TEST_a", "TEST_b"], "person_path": FOREIGN_PERSON})
        assert r.status_code == 200, r.text
        g = poll(s, r.json()["job_id"])
        assert g.status_code == 403 and g.json()["detail"] == "Accesso negato"

    def test_outfit_own_person_passes_ownership(self, s):
        # own avatar passes the ownership check -> next failure is unknown garments (404), not 403
        wait_idle()
        r = s.post(f"{API}/outfit/generate", json={"garment_ids": ["TEST_a", "TEST_b"], "person_path": AVATAR})
        g = poll(s, r.json()["job_id"])
        assert g.status_code == 404, g.text


# --- Fix 2: one running job per user ---
class TestBusy:
    def _fake_running(self, minutes_ago=0):
        jid = f"TEST_{uuid.uuid4()}"
        now = datetime.now(timezone.utc)
        mongo.render_jobs.insert_one({"id": jid, "user_id": OWNER, "status": "running",
                                      "started_at": now - timedelta(minutes=minutes_ago), "expires_at": now + timedelta(hours=1)})
        return jid

    @pytest.mark.parametrize("url,body", [
        ("/tryon/generate", {"person_path": AVATAR, "garment_path": GARMENT}),
        ("/outfit/generate", {"garment_ids": ["TEST_a", "TEST_b"]}),
        ("/outfit/generate-from-uploads", {"items": [{"slot": "top", "image_path": GARMENT}]}),
        ("/copylook/apply", {"model_path": GARMENT, "items": [{"name": "x", "category": "top"}]}),
        ("/tryons/TEST_x/retry", {"reason": "viso"}),
        ("/outfits/TEST_x/retry", {"reason": "viso"}),
    ])
    def test_second_job_409(self, s, url, body):
        wait_idle()
        jid = self._fake_running()
        try:
            r = s.post(f"{API}{url}", json=body)
            assert r.status_code == 409, r.text
            assert r.json()["detail"] == BUSY
        finally:
            mongo.render_jobs.delete_one({"id": jid})

    def test_accepted_after_finish(self, s):
        wait_idle()
        jid = self._fake_running()
        mongo.render_jobs.update_one({"id": jid}, {"$set": {"status": "done"}})
        try:
            r = s.post(f"{API}/tryon/generate", json={"person_path": FOREIGN_PERSON, "garment_path": GARMENT})
            assert r.status_code == 200
            assert poll(s, r.json()["job_id"]).status_code == 403
        finally:
            mongo.render_jobs.delete_one({"id": jid})

    def test_stale_running_over_10min_does_not_block(self, s):
        wait_idle()
        jid = self._fake_running(minutes_ago=11)
        try:
            r = s.post(f"{API}/tryon/generate", json={"person_path": FOREIGN_PERSON, "garment_path": GARMENT})
            assert r.status_code == 200
            poll(s, r.json()["job_id"])
        finally:
            mongo.render_jobs.delete_one({"id": jid})

    def test_concurrent_posts_only_one_accepted(self, s):
        # race: N simultaneous POSTs; the slow-path job is kept running by a 2s-ish 404 garment lookup is too fast,
        # so we just count how many were accepted in the same instant.
        wait_idle()
        body = {"person_path": FOREIGN_PERSON, "garment_path": GARMENT}
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda _: s.post(f"{API}/tryon/generate", json=body), range(8)))
        codes = [r.status_code for r in res]
        print("concurrent codes", codes)
        for r in res:
            if r.status_code == 200:
                poll(s, r.json()["job_id"])
        assert codes.count(200) == 1, f"race: {codes.count(200)} jobs accepted in parallel: {codes}"


# --- Fix 3: TTL index + job docs ---
class TestTtl:
    def test_ttl_index(self):
        idx = {i["name"]: i for i in mongo.render_jobs.list_indexes()}
        assert idx["expires_at_1"]["expireAfterSeconds"] == 0

    def test_new_job_has_expires_at(self, s):
        wait_idle()
        r = s.post(f"{API}/tryon/generate", json={"person_path": FOREIGN_PERSON, "garment_path": GARMENT})
        jid = r.json()["job_id"]
        poll(s, jid)
        d = mongo.render_jobs.find_one({"id": jid})
        assert isinstance(d["expires_at"], datetime)
        assert timedelta(hours=23) < d["expires_at"] - d["started_at"] <= timedelta(days=1, minutes=1)


# --- Fix 4: pad-band trim (unit) ---
sys.path.insert(0, "/app/backend")


class TestTrim:
    def _photo(self, W=600, H=1000, top=0, bot=0):
        rng = np.random.default_rng(0)
        yy, xx = np.mgrid[0:H, 0:W]
        a = np.stack([(xx * 255 // W), (yy * 255 // H), ((xx + yy) % 255)], -1).astype(np.int16)
        a = np.clip(a + rng.integers(-20, 20, a.shape), 0, 255).astype(np.uint8)
        a[:top] = 128
        if bot:
            a[H - bot:] = 128
        return Image.fromarray(a)

    def test_no_bands_untouched(self):
        from tryon_quality import _trim_pad_bands
        assert _trim_pad_bands(self._photo()).size == (600, 1000)

    def test_bands_removed(self):
        from tryon_quality import _trim_pad_bands
        out = _trim_pad_bands(self._photo(top=60, bot=150))
        assert out.size[0] == 600 and 780 <= out.size[1] <= 800, out.size

    def test_watermark_on_banded_image(self):
        from tryon_quality import watermark
        buf = io.BytesIO()
        self._photo(top=60, bot=150).save(buf, "PNG")
        im = Image.open(io.BytesIO(watermark(buf.getvalue())))
        assert im.format == "JPEG" and im.size[1] < 820
        bottom = np.asarray(im.convert("L"))[-40:]
        assert bottom.std() > 10  # bottom strip is photo, not flat band
