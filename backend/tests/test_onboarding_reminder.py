# Onboarding (display name) + 60-day update reminder (avatar/weight) backend tests
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
TOKEN = "avatar_tok_test"
UID = "user_avatar_test"
FEATURES = json.dumps({"shoulder_r": 0.24, "chest_r": 0.17, "waist_r": 0.14, "hips_r": 0.19, "inseam_r": 0.46})


def mongo(js):
    out = subprocess.run(["mongosh", "test_database", "--quiet", "--eval", js], capture_output=True, text=True, timeout=30)
    return out.stdout.strip()


def ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return sess


# --- Display name ---
class TestDisplayName:
    def test_empty_name_rejected(self, s):
        r = s.put(f"{BASE_URL}/api/profile/display-name", json={"name": ""})
        assert r.status_code in (400, 422)

    def test_whitespace_name_rejected(self, s):
        r = s.put(f"{BASE_URL}/api/profile/display-name", json={"name": "   "})
        assert r.status_code in (400, 422)

    def test_too_long_rejected(self, s):
        r = s.put(f"{BASE_URL}/api/profile/display-name", json={"name": "x" * 41})
        assert r.status_code == 422

    def test_unauth(self):
        r = requests.put(f"{BASE_URL}/api/profile/display-name", json={"name": "A"})
        assert r.status_code == 401

    def test_set_and_persist(self, s):
        r = s.put(f"{BASE_URL}/api/profile/display-name", json={"name": "  Marta  "})
        assert r.status_code == 200
        assert r.json()["display_name"] == "Marta"
        me = s.get(f"{BASE_URL}/api/auth/me").json()
        assert me["display_name"] == "Marta"


# --- Reminder ---
class TestReminder:
    def test_no_avatar_not_due(self, s):
        d = s.get(f"{BASE_URL}/api/profile/avatar").json()
        if d["path"]:
            pytest.skip("avatar already exists")
        assert d["reminder_due"] is False

    def test_create_avatar_not_due(self, s):
        r = s.post(f"{BASE_URL}/api/profile/avatar",
                   params={"features": FEATURES, "height_cm": 168, "weight_kg": 60, "gender": "female"},
                   files={"photo": ("a.jpg", open("/tmp/fullbody.jpg", "rb").read(), "image/jpeg")}, timeout=60)
        assert r.status_code == 200, r.text
        d = s.get(f"{BASE_URL}/api/profile/avatar").json()
        assert d["path"]
        assert d["reminder_due"] is False

    def test_aged_avatar_and_weight_due(self, s):
        old = ago(70)
        mongo(f'db.users.updateOne({{user_id:"{UID}"}},{{$set:{{avatar_at:"{old}"}},$unset:{{reminder_snoozed_until:""}}}});'
              f'db.weight_history.updateMany({{user_id:"{UID}"}},{{$set:{{recorded_at:"{old}"}}}})')
        assert s.get(f"{BASE_URL}/api/profile/avatar").json()["reminder_due"] is True

    def test_recent_weight_keeps_not_due(self, s):
        mongo(f'db.weight_history.insertOne({{id:"TEST_w",user_id:"{UID}",recorded_at:"{ago(5)}"}})')
        try:
            assert s.get(f"{BASE_URL}/api/profile/avatar").json()["reminder_due"] is False
        finally:
            mongo('db.weight_history.deleteOne({id:"TEST_w"})')
        assert s.get(f"{BASE_URL}/api/profile/avatar").json()["reminder_due"] is True

    def test_snooze(self, s):
        r = s.post(f"{BASE_URL}/api/profile/reminder/snooze")
        assert r.status_code == 200
        until = datetime.fromisoformat(r.json()["snoozed_until"])
        delta = until - datetime.now(timezone.utc)
        assert timedelta(days=6, hours=23) < delta <= timedelta(days=7)
        assert s.get(f"{BASE_URL}/api/profile/avatar").json()["reminder_due"] is False

    def test_expired_snooze_due_again(self, s):
        mongo(f'db.users.updateOne({{user_id:"{UID}"}},{{$set:{{reminder_snoozed_until:"{ago(1)}"}}}})')
        assert s.get(f"{BASE_URL}/api/profile/avatar").json()["reminder_due"] is True

    def test_snooze_unauth(self):
        assert requests.post(f"{BASE_URL}/api/profile/reminder/snooze").status_code == 401
