# Avatar Family (per-profile avatar via X-Profile-Id) + profile_name + reminder date backend tests
import json
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
TOKEN = "avatar_tok_test"
KID = "fam_avatar_kid"
FEATURES = json.dumps({"shoulder_r": 0.24, "chest_r": 0.17, "waist_r": 0.14, "hips_r": 0.19, "inseam_r": 0.46})


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {TOKEN}"})
    yield sess
    sess.delete(f"{BASE_URL}/api/profile/avatar")
    sess.delete(f"{BASE_URL}/api/profile/avatar", headers={"X-Profile-Id": KID})


def post(s, params, kid=False):
    h = {"X-Profile-Id": KID} if kid else {}
    return s.post(f"{BASE_URL}/api/profile/avatar", params=params, headers=h,
                  files={"photo": ("a.jpg", open("/tmp/fullbody.jpg", "rb").read(), "image/jpeg")}, timeout=60)


class TestAvatarFamily:
    st = {}

    def test_01_clean_and_names(self, s):
        s.delete(f"{BASE_URL}/api/profile/avatar")
        s.delete(f"{BASE_URL}/api/profile/avatar", headers={"X-Profile-Id": KID})
        main = s.get(f"{BASE_URL}/api/profile/avatar").json()
        kid = s.get(f"{BASE_URL}/api/profile/avatar", headers={"X-Profile-Id": KID}).json()
        assert main["path"] is None and main["profile_name"] is None
        assert kid["path"] is None and kid["profile_name"] == "Giulia"

    def test_02_invalid_profile_rejected(self, s):
        r = s.get(f"{BASE_URL}/api/profile/avatar", headers={"X-Profile-Id": "user_389c87aaadc6"})
        # Backend falls back silently to the account itself (no data leak of a foreign user)
        assert r.status_code in (200, 401, 403, 404)
        if r.status_code == 200:
            assert r.json()["profile_name"] is None and r.json()["path"] is None

    def test_03_main_create(self, s):
        r = post(s, {"features": FEATURES, "height_cm": 182, "weight_kg": 78, "gender": "male"})
        assert r.status_code == 200, r.text
        p = r.json()["avatar"]["path"]
        assert "/avatar/user_avatar_test/" in p
        self.st["main"] = p

    def test_04_kid_still_empty(self, s):
        kid = s.get(f"{BASE_URL}/api/profile/avatar", headers={"X-Profile-Id": KID}).json()
        assert kid["path"] is None

    def test_05_kid_need_height(self, s):
        r = post(s, {"features": FEATURES}, kid=True)
        assert r.status_code == 400 and r.json()["detail"] == "need_height"

    def test_06_kid_create(self, s):
        r = post(s, {"features": FEATURES, "height_cm": 140, "weight_kg": 40, "gender": "female"}, kid=True)
        assert r.status_code == 200, r.text
        p = r.json()["avatar"]["path"]
        assert f"/avatar/{KID}/" in p
        self.st["kid"] = p

    def test_07_independent(self, s):
        main = s.get(f"{BASE_URL}/api/profile/avatar").json()
        kid = s.get(f"{BASE_URL}/api/profile/avatar", headers={"X-Profile-Id": KID}).json()
        assert main["path"] == self.st["main"]
        assert kid["path"] == self.st["kid"]
        assert kid["profile_name"] == "Giulia"

    def test_08_measurements_differ(self, s):
        m = s.get(f"{BASE_URL}/api/profile/measurements").json()
        k = s.get(f"{BASE_URL}/api/profile/measurements", headers={"X-Profile-Id": KID}).json()
        assert m["height_cm"] == 182 and k["height_cm"] == 140
        assert m.get("chest_cm") != k.get("chest_cm")

    def test_09_file_access(self, s):
        r = s.get(f"{BASE_URL}/api/files/{self.st['kid']}", headers={"X-Profile-Id": KID})
        assert r.status_code == 200 and len(r.content) > 1000
        r2 = requests.get(f"{BASE_URL}/api/files/{self.st['kid']}")
        assert r2.status_code in (401, 403, 404)

    def test_10_kid_delete_keeps_main(self, s):
        r = s.delete(f"{BASE_URL}/api/profile/avatar", headers={"X-Profile-Id": KID})
        assert r.status_code == 200 and r.json()["deleted"] is True
        assert s.get(f"{BASE_URL}/api/profile/avatar").json()["path"] == self.st["main"]
        assert s.get(f"{BASE_URL}/api/profile/avatar", headers={"X-Profile-Id": KID}).json()["path"] is None

    def test_11_created_at_iso(self, s):
        main = s.get(f"{BASE_URL}/api/profile/avatar").json()
        assert isinstance(main["created_at"], str) and "T" in main["created_at"]
