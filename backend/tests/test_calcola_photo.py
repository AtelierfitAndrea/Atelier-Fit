# Auto-measure from photo: profile fallback for height/weight/gender, need_height, precision rules, forget_weight
import json
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

RATIOS = json.dumps({"shoulder_r": 0.23, "chest_r": 0.18, "waist_r": 0.15, "hips_r": 0.19, "inseam_r": 0.46})
PHOTO = "/app/memory/test_fullbody.jpg"


def _mongo(js):
    return subprocess.run(["mongosh", "--quiet", "--eval", "use('test_database');" + js], capture_output=True, text=True)


@pytest.fixture(scope="module")
def client():
    ts = str(int(time.time() * 1000))
    uid, tok = f"TEST_cp_{ts}", f"TEST_cp_sess_{ts}"
    _mongo(f"""db.users.insertOne({{user_id:'{uid}',email:'{uid}@example.com',name:'CP Test',terms_version:'1.0-2026-06',plan:'SINGLE',created_at:new Date().toISOString()}});
db.user_sessions.insertOne({{user_id:'{uid}',session_token:'{tok}',expires_at:new Date(Date.now()+86400000).toISOString(),created_at:new Date().toISOString()}});""")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    s.uid = uid
    yield s
    _mongo(f"['users','user_sessions','measurements','weight_history','fitting_accuracy','files'].forEach(c=>db[c].deleteMany({{user_id:'{uid}'}}));")


def post(client, **params):
    params["features"] = RATIOS
    with open(PHOTO, "rb") as f:
        return client.post(f"{BASE_URL}/api/profile/auto-measure", params=params,
                           files={"photo": ("p.jpg", f, "image/jpeg")})


class TestAutoMeasureProfileFallback:
    def test_need_height_when_none_saved(self, client):
        r = post(client)
        assert r.status_code == 400 and r.json()["detail"] == "need_height", r.text

    def test_height_no_weight_no_gender_precision_75(self, client):
        r = post(client, height_cm=170)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["precision"] == 75
        assert d["measurements"]["height_cm"] == 170
        assert d["measurements"].get("gender") in (None, "")
        assert len(d["brand_sizes"]) > 0
        g = client.get(f"{BASE_URL}/api/profile/measurements").json()
        assert g["height_cm"] == 170

    def test_saved_height_reused(self, client):
        r = post(client)
        assert r.status_code == 200, r.text
        assert r.json()["measurements"]["height_cm"] == 170

    def test_weight_no_gender_precision_88(self, client):
        r = post(client, weight_kg=72)
        assert r.status_code == 200, r.text
        assert r.json()["precision"] == 88

    def test_saved_weight_reused(self, client):
        r = post(client)
        assert r.status_code == 200
        d = r.json()
        assert d["measurements"]["weight_kg"] == 72 and d["precision"] == 88

    def test_with_gender_precision_98(self, client):
        r = post(client, gender="male")
        assert r.status_code == 200
        assert r.json()["precision"] == 98

    def test_saved_gender_reused(self, client):
        r = post(client)
        assert r.json()["precision"] == 98
        assert r.json()["measurements"]["gender"] == "male"

    def test_forget_weight(self, client):
        r = post(client, forget_weight="true")
        assert r.status_code == 200
        assert r.json()["precision"] == 85
        g = client.get(f"{BASE_URL}/api/profile/measurements").json()
        assert g.get("weight_kg") in (None,)

    def test_invalid_height_422(self, client):
        assert post(client, height_cm=100).status_code == 422

    def test_photo_stored_encrypted(self, client):
        out = _mongo(f"print(db.files.countDocuments({{user_id:'{client.uid}',kind:'measure',encrypted:true}}))").stdout.strip()
        assert int(out.splitlines()[-1]) >= 1

    def test_401(self):
        with open(PHOTO, "rb") as f:
            r = requests.post(f"{BASE_URL}/api/profile/auto-measure", params={"features": RATIOS}, files={"photo": ("p.jpg", f, "image/jpeg")})
        assert r.status_code == 401
