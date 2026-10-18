# Quick estimate (height+weight+sex, no tape), tape calibration, logo/favicon assets
import os
import subprocess
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")


@pytest.fixture(scope="module")
def client():
    ts = str(int(time.time() * 1000))
    uid, tok = f"TEST_qe_{ts}", f"TEST_qe_sess_{ts}"
    js = f"""use('test_database');
db.users.insertOne({{user_id:'{uid}',email:'{uid}@example.com',name:'QE Test',terms_version:'1.0-2026-06',plan:'SINGLE',created_at:new Date().toISOString()}});
db.user_sessions.insertOne({{user_id:'{uid}',session_token:'{tok}',expires_at:new Date(Date.now()+86400000).toISOString(),created_at:new Date().toISOString()}});"""
    subprocess.run(["mongosh", "--quiet", "--eval", js], check=True, capture_output=True)
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    yield s
    js2 = f"use('test_database'); ['users','user_sessions','measurements','weight_history','fitting_accuracy'].forEach(c=>db[c].deleteMany({{user_id:'{uid}'}}));"
    subprocess.run(["mongosh", "--quiet", "--eval", js2], capture_output=True)


class TestQuickEstimateValidation:
    @pytest.mark.parametrize("body", [
        {"height_cm": 100, "weight_kg": 70, "gender": "male"},
        {"height_cm": 240, "weight_kg": 70, "gender": "male"},
        {"height_cm": 180, "weight_kg": 30, "gender": "male"},
        {"height_cm": 180, "weight_kg": 160, "gender": "male"},
        {"height_cm": 180, "weight_kg": 70, "gender": "unisex"},
        {"height_cm": 180, "weight_kg": 70},
    ])
    def test_422(self, client, body):
        r = client.post(f"{BASE_URL}/api/profile/quick-estimate", json=body)
        assert r.status_code == 422, r.text

    def test_401_no_auth(self):
        r = requests.post(f"{BASE_URL}/api/profile/quick-estimate", json={"height_cm": 180, "weight_kg": 75, "gender": "male"})
        assert r.status_code == 401


class TestQuickEstimateFlow:
    def test_estimate_stored(self, client):
        r = client.post(f"{BASE_URL}/api/profile/quick-estimate", json={"height_cm": 182, "weight_kg": 75, "gender": "male"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["kept_precise"] is False
        m = d["measurements"]
        assert m["method"] == "height_weight"
        for k in ("chest_cm", "waist_cm", "hips_cm", "shoulder_cm", "inseam_cm"):
            assert isinstance(m[k], (int, float)) and m[k] > 0
        g = client.get(f"{BASE_URL}/api/profile/measurements").json()
        assert g["method"] == "height_weight" and g["height_cm"] == 182 and g["weight_kg"] == 75
        assert g["chest_cm"] == m["chest_cm"]
        assert "brand_sizes" in g
        print("estimate", {k: m[k] for k in ("chest_cm", "waist_cm", "hips_cm", "shoulder_cm", "inseam_cm")})

    def test_female_differs(self, client):
        r = client.post(f"{BASE_URL}/api/profile/quick-estimate", json={"height_cm": 165, "weight_kg": 58, "gender": "female"})
        assert r.status_code == 200
        m = r.json()["measurements"]
        assert m["gender"] == "female" and m["method"] == "height_weight"
        assert m["hips_cm"] >= m["waist_cm"]

    def test_tape_kept(self, client):
        p = client.put(f"{BASE_URL}/api/profile/measurements", json={"chest_cm": 111, "waist_cm": 77, "hips_cm": 99, "shoulder_cm": 44, "method": "tape"})
        assert p.status_code == 200
        g = client.get(f"{BASE_URL}/api/profile/measurements").json()
        assert g["method"] == "tape" and g["chest_cm"] == 111
        r = client.post(f"{BASE_URL}/api/profile/quick-estimate", json={"height_cm": 165, "weight_kg": 60, "gender": "female"})
        assert r.status_code == 200
        assert r.json()["kept_precise"] is True
        g = client.get(f"{BASE_URL}/api/profile/measurements").json()
        assert g["chest_cm"] == 111 and g["waist_cm"] == 77 and g["hips_cm"] == 99 and g["shoulder_cm"] == 44
        assert g["method"] == "tape"
        assert g["weight_kg"] == 60

    def test_tape_overwritten_when_height_changes(self, client):
        r = client.post(f"{BASE_URL}/api/profile/quick-estimate", json={"height_cm": 175, "weight_kg": 60, "gender": "female"})
        assert r.status_code == 200
        assert r.json()["kept_precise"] is False
        g = client.get(f"{BASE_URL}/api/profile/measurements").json()
        assert g["method"] == "height_weight" and g["chest_cm"] != 111


class TestAssets:
    @pytest.mark.parametrize("path", ["/logo.png", "/logo-white.png", "/favicon.ico", "/favicon.png", "/apple-touch-icon.png"])
    def test_asset(self, path):
        r = requests.get(f"{BASE_URL}{path}")
        assert r.status_code == 200
        assert "image" in r.headers.get("content-type", "") or path.endswith(".ico"), r.headers.get("content-type")

    def test_index_links_favicon(self):
        html = requests.get(f"{BASE_URL}/").text
        assert "favicon.ico" in html or "favicon.png" in html
        assert "apple-touch-icon" in html


# Weight history: quick-estimate logs a weight_history entry only when weight changes (iteration 23).
# Uses the owner test account user_avatar_test (prelaunch gate blocks non-owner emails); added entries are removed afterwards.
class TestQuickEstimateWeightHistory:
    @pytest.fixture(scope="class")
    def wclient(self):
        s = requests.Session()
        s.headers.update({"Authorization": "Bearer avatar_tok_test"})
        r = s.get(f"{BASE_URL}/api/profile/measurements")
        if r.status_code != 200 or not r.json().get("weight_kg"):
            pytest.skip("avatar test user not onboarded")
        before = {e["id"] for e in s.get(f"{BASE_URL}/api/profile/weight-history").json()["entries"]}
        s.base_profile = r.json()
        yield s
        b = s.base_profile
        s.post(f"{BASE_URL}/api/profile/quick-estimate", json={"height_cm": b["height_cm"], "weight_kg": b["weight_kg"], "gender": b["gender"]})
        ids = [e["id"] for e in s.get(f"{BASE_URL}/api/profile/weight-history").json()["entries"] if e["id"] not in before]
        js = "use('test_database'); db.weight_history.deleteMany({id:{$in:%s}})" % str(ids)
        subprocess.run(["mongosh", "--quiet", "--eval", js], capture_output=True)

    def _hist(self, c):
        r = c.get(f"{BASE_URL}/api/profile/weight-history")
        assert r.status_code == 200
        return r.json()["entries"]

    def test_same_weight_no_new_entry(self, wclient):
        b = wclient.base_profile
        n = len(self._hist(wclient))
        r = wclient.post(f"{BASE_URL}/api/profile/quick-estimate", json={"height_cm": b["height_cm"], "weight_kg": b["weight_kg"], "gender": b["gender"]})
        assert r.status_code == 200
        assert len(self._hist(wclient)) == n

    def test_changed_weight_new_entry_and_photo_kept(self, wclient):
        b = wclient.base_profile
        n = len(self._hist(wclient))
        r = wclient.post(f"{BASE_URL}/api/profile/quick-estimate", json={"height_cm": b["height_cm"], "weight_kg": b["weight_kg"] + 2, "gender": b["gender"]})
        assert r.status_code == 200
        h = self._hist(wclient)
        assert len(h) == n + 1 and (b["weight_kg"] + 2) in [e["weight_kg"] for e in h]
        if b.get("method") == "auto_photo":
            assert r.json()["kept_precise"] is True

    def test_weight_encrypted_in_db(self, wclient):
        out = subprocess.run(["mongosh", "--quiet", "--eval", "use('test_database'); print(db.weight_history.countDocuments({user_id:'user_avatar_test', weight_kg:{$exists:true}}))"], capture_output=True, text=True).stdout.strip()
        assert out.endswith("0")
