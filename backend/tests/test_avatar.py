# Il Mio Avatar (single full-body photo) backend tests
import io
import json
import os

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
TOKEN = "avatar_tok_test"
FEATURES = json.dumps({"shoulder_r": 0.24, "chest_r": 0.17, "waist_r": 0.14, "hips_r": 0.19, "inseam_r": 0.46})


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return sess


def photo():
    p = "/tmp/fullbody.jpg"
    if os.path.exists(p):
        return open(p, "rb").read()
    b = io.BytesIO()
    Image.new("RGB", (400, 800), (200, 180, 160)).save(b, "JPEG")
    return b.getvalue()


def post_avatar(s, params):
    return s.post(f"{BASE_URL}/api/profile/avatar", params=params,
                  files={"photo": ("a.jpg", photo(), "image/jpeg")}, timeout=60)


class TestAvatar:
    state = {}

    def test_01_get_initial_null(self, s):
        s.delete(f"{BASE_URL}/api/profile/avatar")
        r = s.get(f"{BASE_URL}/api/profile/avatar")
        assert r.status_code == 200
        assert r.json()["path"] is None

    def test_02_unauth(self):
        r = requests.get(f"{BASE_URL}/api/profile/avatar")
        assert r.status_code == 401

    def test_03_need_height(self, s):
        m = s.get(f"{BASE_URL}/api/profile/measurements").json() or {}
        if m.get("height_cm"):
            pytest.skip("user already has height")
        r = post_avatar(s, {"features": FEATURES})
        assert r.status_code == 400
        assert r.json()["detail"] == "need_height"
        assert s.get(f"{BASE_URL}/api/profile/avatar").json()["path"] is None

    def test_04_bad_features(self, s):
        r = post_avatar(s, {"features": "{bad", "height_cm": 168})
        assert r.status_code == 400

    def test_05_invalid_photo(self, s):
        r = s.post(f"{BASE_URL}/api/profile/avatar", params={"features": FEATURES, "height_cm": 168, "weight_kg": 58},
                   files={"photo": ("a.jpg", b"notanimage", "image/jpeg")})
        assert r.status_code == 400

    def test_06_out_of_range_height(self, s):
        r = post_avatar(s, {"features": FEATURES, "height_cm": 300})
        assert r.status_code == 422

    def test_07_create_with_height(self, s):
        r = post_avatar(s, {"features": FEATURES, "height_cm": 168, "weight_kg": 58, "gender": "female"})
        assert r.status_code == 200, r.text
        d = r.json()
        path = d["avatar"]["path"]
        assert path.startswith("vfit/avatar/user_avatar_test/") and path.endswith(".bin")
        assert d["measurements"]["height_cm"] == 168
        assert d["measurements"]["weight_kg"] == 58
        assert "brand_sizes" in d and d["precision"] == 98
        TestAvatar.state["path"] = path

    def test_08_get_persisted(self, s):
        r = s.get(f"{BASE_URL}/api/profile/avatar")
        assert r.json()["path"] == TestAvatar.state["path"]
        m = s.get(f"{BASE_URL}/api/profile/measurements").json()
        assert m["height_cm"] == 168 and m.get("method") == "auto_photo"

    def test_09_weight_history(self, s):
        r = s.get(f"{BASE_URL}/api/profile/weight-history")
        if r.status_code == 404:
            pytest.skip("no weight-history endpoint")
        assert r.status_code == 200
        assert "58" in r.text

    def test_10_file_decrypted(self, s):
        r = s.get(f"{BASE_URL}/api/files/{TestAvatar.state['path']}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/jpeg")
        assert r.content[:2] == b"\xff\xd8"

    def test_11_file_private(self):
        r = requests.get(f"{BASE_URL}/api/files/{TestAvatar.state['path']}")
        assert r.status_code in (401, 403)

    def test_12_replace_marks_old_deleted(self, s):
        old = TestAvatar.state["path"]
        r = post_avatar(s, {})  # no features -> only photo, uses saved height
        assert r.status_code == 200, r.text
        new = r.json()["avatar"]["path"]
        assert new != old
        assert s.get(f"{BASE_URL}/api/files/{old}").status_code == 404
        assert s.get(f"{BASE_URL}/api/files/{new}").status_code == 200
        TestAvatar.state["path"] = new

    def test_13_resubmit_uses_saved_height(self, s):
        r = post_avatar(s, {"features": FEATURES})
        assert r.status_code == 200, r.text
        TestAvatar.state["path"] = r.json()["avatar"]["path"]

    def test_14_delete(self, s):
        p = TestAvatar.state["path"]
        r = s.delete(f"{BASE_URL}/api/profile/avatar")
        assert r.status_code == 200 and r.json()["deleted"] is True
        assert s.get(f"{BASE_URL}/api/profile/avatar").json()["path"] is None
        assert s.get(f"{BASE_URL}/api/files/{p}").status_code == 404

    def test_15_delete_all_clears_avatar(self, s):
        r = post_avatar(s, {"features": FEATURES})
        assert r.status_code == 200
        p = r.json()["avatar"]["path"]
        r = s.post(f"{BASE_URL}/api/photos/delete-all")
        assert r.status_code == 200
        assert r.json()["deleted_photos"] >= 1
        assert s.get(f"{BASE_URL}/api/profile/avatar").json()["path"] is None
        assert s.get(f"{BASE_URL}/api/files/{p}").status_code == 404
