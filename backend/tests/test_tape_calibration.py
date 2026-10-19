# Taratura Metro (tape calibration): GET/POST /api/profile/tape-calibration + offsets applied on next avatar photo
import io
import json
import os
import subprocess
import time

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

UID = "TEST_tape_user"
TOK = "TEST_tape_tok"
FEAT = json.dumps({"shoulder_r": 0.22, "chest_r": 0.17, "waist_r": 0.14, "hips_r": 0.19, "inseam_r": 0.47})


def _mongo(js):
    subprocess.run(["mongosh", "--quiet", "test_database", "--eval", js], check=True, capture_output=True)


def _reset():
    _mongo(f'["users","user_sessions","measurements","files","weight_history","fitting_accuracy"].forEach(c=>db[c].deleteMany({{user_id:"{UID}"}}));')


@pytest.fixture(scope="module")
def s():
    _reset()
    # gate is by email; avatar.test@example.com is temporarily in OWNER_EMAILS
    _mongo(f'db.users.insertOne({{user_id:"{UID}",email:"avatar.test@example.com",name:"Tape",display_name:"Tape",terms_version:"1.0-2026-06",created_at:new Date().toISOString()}});'
           f'db.user_sessions.insertOne({{user_id:"{UID}",session_token:"{TOK}",expires_at:new Date(Date.now()+864e5).toISOString(),created_at:new Date().toISOString()}});')
    ss = requests.Session()
    ss.headers["Authorization"] = f"Bearer {TOK}"
    yield ss
    _reset()


def _jpg():
    b = io.BytesIO()
    Image.new("RGB", (300, 600), (200, 200, 200)).save(b, "JPEG")
    return b.getvalue()


def _avatar(s):
    r = s.post(f"{BASE_URL}/api/profile/avatar", params={"features": FEAT, "height_cm": 168, "weight_kg": 60, "gender": "female"},
               files={"photo": ("a.jpg", _jpg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["measurements"]


class TestTape:
    def test_unauth(self):
        assert requests.get(f"{BASE_URL}/api/profile/tape-calibration").status_code == 401

    def test_fresh_user_no_photo(self, s):
        d = s.get(f"{BASE_URL}/api/profile/tape-calibration").json()
        assert d["done"] is False and d["has_photo"] is False
        r = s.post(f"{BASE_URL}/api/profile/tape-calibration", json={"chest_cm": 88, "waist_cm": 70})
        assert r.status_code == 400

    def test_validation(self, s):
        for body in ({"chest_cm": 59, "waist_cm": 70}, {"chest_cm": 171, "waist_cm": 70}, {"chest_cm": 88, "waist_cm": 44}, {"chest_cm": 88}):
            assert s.post(f"{BASE_URL}/api/profile/tape-calibration", json=body).status_code == 422

    def test_calibrate_and_reapply(self, s):
        m1 = _avatar(s)
        raw_c, raw_w = m1["photo_raw_chest"], m1["photo_raw_waist"]
        assert m1["chest_cm"] == round(raw_c - 2) and m1["waist_cm"] == round(raw_w - 2)
        hips1 = m1["hips_cm"]
        d = s.get(f"{BASE_URL}/api/profile/tape-calibration").json()
        assert d["has_photo"] is True and d["done"] is False
        r = s.post(f"{BASE_URL}/api/profile/tape-calibration", json={"chest_cm": 88, "waist_cm": 70})
        assert r.status_code == 200, r.text
        assert r.json()["measurements"]["chest_cm"] == 88
        g = s.get(f"{BASE_URL}/api/profile/measurements").json()
        assert g["chest_cm"] == 88 and g["waist_cm"] == 70
        assert g["hips_cm"] == hips1
        assert "brand_sizes" in g
        d = s.get(f"{BASE_URL}/api/profile/tape-calibration").json()
        assert d["done"] is True and d["chest_cm"] == 88 and d["waist_cm"] == 70 and d["has_photo"] is True
        # same photo/features again -> offsets reproduce tape values
        m2 = _avatar(s)
        assert abs(m2["chest_cm"] - 88) <= 1 and abs(m2["waist_cm"] - 70) <= 1
        assert m2["hips_cm"] == hips1  # still generic -2
        d = s.get(f"{BASE_URL}/api/profile/tape-calibration").json()
        assert d["done"] is True
        # redo calibration after a calibrated photo uses raw, not corrected values
        r = s.post(f"{BASE_URL}/api/profile/tape-calibration", json={"chest_cm": 90, "waist_cm": 72})
        assert r.status_code == 200
        m3 = _avatar(s)
        assert abs(m3["chest_cm"] - 90) <= 1 and abs(m3["waist_cm"] - 72) <= 1
