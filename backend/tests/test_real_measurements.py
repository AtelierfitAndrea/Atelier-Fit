# Iteration 33: real tape measurements (no photo estimation), size gating, reminder popup backend
import os, io, json
from datetime import datetime, timezone, timedelta
import pytest, requests
from pymongo import MongoClient
from cryptography.fernet import Fernet
from dotenv import dotenv_values

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]
BASE_URL = BASE_URL.rstrip("/")
ENV = dotenv_values("/app/backend/.env")
TOKEN = os.environ["T1_TOKEN"]
UID = "user_389c87aaadc6"
db = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
F = Fernet(ENV["DATA_ENCRYPTION_KEY"].encode())

VALID = {"height_cm": 172, "chest_cm": 94, "waist_cm": 78, "hips_cm": 98, "shoulder_cm": 44, "inseam_cm": 80}


def write_meas(data, updated_at=None):
    db.measurements.update_one({"user_id": UID}, {"$set": {"enc": F.encrypt(json.dumps(data).encode()).decode(),
                                                          "updated_at": updated_at or datetime.now(timezone.utc).isoformat()}}, upsert=True)


@pytest.fixture(scope="module")
def s():
    x = requests.Session()
    x.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return x


class TestValidation:
    @pytest.mark.parametrize("field", list(VALID))
    def test_missing_required(self, s, field):
        body = {k: v for k, v in VALID.items() if k != field}
        assert s.put(f"{BASE_URL}/api/profile/real-measurements", json=body).status_code == 422

    @pytest.mark.parametrize("field,val", [("height_cm", 50), ("chest_cm", 300), ("shoulder_cm", 10), ("inseam_cm", 200),
                                           ("weight_kg", 10), ("age", 5)])
    def test_out_of_range(self, s, field, val):
        assert s.put(f"{BASE_URL}/api/profile/real-measurements", json={**VALID, field: val}).status_code == 422

    def test_bad_gender(self, s):
        assert s.put(f"{BASE_URL}/api/profile/real-measurements", json={**VALID, "gender": "x"}).status_code == 422


class TestIncompleteGating:
    def test_photo_method_incomplete(self, s):
        write_meas({**VALID, "method": "auto_photo"})
        r = s.get(f"{BASE_URL}/api/profile/measurements").json()
        assert r["complete"] is False
        assert s.get(f"{BASE_URL}/api/size/recommend?category=top").json()["size"] == "Completa le tue misure"
        assert s.get(f"{BASE_URL}/api/size/recommend?category=bottom").json()["size"] == "Completa le tue misure"
        r = s.post(f"{BASE_URL}/api/product/analyze", json={"url": "https://example.com/p"})
        assert r.status_code == 400 and r.json()["detail"] == "Completa le tue misure"
        r = s.post(f"{BASE_URL}/api/product/analyze-text", json={"chart_text": "S 88 M 96", "url": ""})
        assert r.status_code == 400 and r.json()["detail"] == "Completa le tue misure"

    def test_missing_field_incomplete(self, s):
        write_meas({**{k: v for k, v in VALID.items() if k != "inseam_cm"}, "method": "tape"})
        assert s.get(f"{BASE_URL}/api/profile/measurements").json()["complete"] is False


class TestSave:
    def test_save_success_and_persist(self, s):
        r = s.put(f"{BASE_URL}/api/profile/real-measurements", json={**VALID, "weight_kg": 70, "age": 35, "gender": "male"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["method"] == "tape" and d["complete"] is True and d["measured_at"]
        assert isinstance(d["brand_sizes"], list) and len(d["brand_sizes"]) > 0
        assert d["weight_kg"] == 70 and d["age"] == 35 and d["gender"] == "male"
        g = s.get(f"{BASE_URL}/api/profile/measurements").json()
        assert g["complete"] is True and g["height_cm"] == 172 and g["inseam_cm"] == 80
        size = s.get(f"{BASE_URL}/api/size/recommend?category=top").json()["size"]
        assert size != "Completa le tue misure" and len(size) <= 4, size

    def test_save_without_optional_removes_them(self, s):
        d = s.put(f"{BASE_URL}/api/profile/real-measurements", json=VALID).json()
        assert d["complete"] is True and "weight_kg" not in d and "age" not in d


class TestRemovedEndpoints:
    @pytest.mark.parametrize("path", ["/api/profile/quick-estimate", "/api/profile/auto-measure", "/api/profile/tape-calibration"])
    def test_removed(self, s, path):
        assert s.post(f"{BASE_URL}{path}", json={}).status_code in (404, 405)


class TestReminder:
    def test_reminder_flow(self, s):
        old = (datetime.now(timezone.utc) - timedelta(days=70)).isoformat()
        cur = s.get(f"{BASE_URL}/api/profile/measurements").json()
        cur.pop("complete", None); cur.pop("updated_at", None)
        hist = list(db.weight_history.find({"user_id": UID}))
        db.weight_history.update_many({"user_id": UID}, {"$set": {"recorded_at": old}})
        try:
            write_meas({**cur, "measured_at": old}, old)
            db.users.update_one({"user_id": UID}, {"$unset": {"reminder_snoozed_until": ""}})
            assert s.get(f"{BASE_URL}/api/profile/avatar").json()["reminder_due"] is True
            sn = s.post(f"{BASE_URL}/api/profile/reminder/snooze").json()
            until = datetime.fromisoformat(sn["snoozed_until"])
            assert 6.9 < (until - datetime.now(timezone.utc)).total_seconds() / 86400 <= 7.01
            assert s.get(f"{BASE_URL}/api/profile/avatar").json()["reminder_due"] is False
            # saving real measurements clears snooze
            s.put(f"{BASE_URL}/api/profile/real-measurements", json=VALID)
            u = db.users.find_one({"user_id": UID}, {"reminder_snoozed_until": 1})
            assert "reminder_snoozed_until" not in u
            assert s.get(f"{BASE_URL}/api/profile/avatar").json()["reminder_due"] is False  # fresh
        finally:
            for h in hist:
                db.weight_history.update_one({"_id": h["_id"]}, {"$set": {"recorded_at": h["recorded_at"]}})


class TestAvatarUpload:
    def test_avatar_returns_only_avatar(self, s):
        from PIL import Image
        before_user = db.users.find_one({"user_id": UID}, {"avatar_path": 1, "avatar_at": 1})
        before_meas = s.get(f"{BASE_URL}/api/profile/measurements").json()
        buf = io.BytesIO(); Image.new("RGB", (300, 600), (180, 160, 140)).save(buf, "JPEG")
        # detach owner avatar so the upload does NOT erase the real one
        db.users.update_one({"user_id": UID}, {"$unset": {"avatar_path": ""}})
        r = s.post(f"{BASE_URL}/api/profile/avatar", files={"photo": ("a.jpg", buf.getvalue(), "image/jpeg")})
        try:
            assert r.status_code == 200, r.text
            assert list(r.json().keys()) == ["avatar"]
            after = s.get(f"{BASE_URL}/api/profile/measurements").json()
            assert {k: after.get(k) for k in VALID} == {k: before_meas.get(k) for k in VALID}
            assert after.get("method") == "tape"
        finally:
            # restore original owner avatar (un-delete old file record)
            new_path = r.json().get("avatar", {}).get("path") if r.ok else None
            db.users.update_one({"user_id": UID}, {"$set": {"avatar_path": before_user["avatar_path"], "avatar_at": before_user.get("avatar_at")}})
            if new_path:
                db.files.update_one({"storage_path": new_path}, {"$set": {"is_deleted": True}})
