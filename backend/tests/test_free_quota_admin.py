# FREE quota (5/month after honeymoon) 402 enforcement + real admin stats
import io
import os
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
UID = "user_389c87aaadc6"
H = {"Authorization": "Bearer owner_tok_test"}
ORIG_CREATED = "2026-10-03T05:40:30.312552+00:00"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5f0000000049454e44ae426082")


def set_user(created_at, used, extra=0):
    db.users.update_one({"user_id": UID}, {"$set": {
        "created_at": created_at, "monthly_tryon_count": {"month": "2026-10", "used": used},
        "extra_tryon_credits": extra, "plan": "FREE"}, "$unset": {"plan_expires_at": ""}})


@pytest.fixture(scope="class")
def restore():
    yield
    set_user(ORIG_CREATED, 0, 0)


def status():
    r = requests.get(f"{BASE_URL}/api/subscription/status", headers=H)
    assert r.status_code == 200
    return r.json()


def upload(kind="person"):
    return requests.post(f"{BASE_URL}/api/upload?kind={kind}", headers=H,
                         files={"file": ("t.png", io.BytesIO(PNG), "image/png")})


@pytest.mark.usefixtures("restore")
class TestBlocked:
    def test_status_blocked(self):
        set_user("2026-08-01T00:00:00+00:00", 5)
        s = status()
        assert s["honeymoon_active"] is False and s["is_blocked"] is True
        assert s["tryons_remaining"] == 0 and s["plan"] == "FREE"

    def test_upload_person_402(self):
        r = upload("person")
        assert r.status_code == 402, r.text

    def test_upload_garment_402(self):
        r = upload("garment")
        assert r.status_code == 402, r.text

    def test_generate_402(self):
        r = requests.post(f"{BASE_URL}/api/tryon/generate", headers=H, json={
            "person_path": "x/p.png", "garment_path": "x/g.png", "garment_category": "top"})
        assert r.status_code == 402, r.text

    def test_extra_credit_unblocks(self):
        set_user("2026-08-01T00:00:00+00:00", 5, extra=1)
        s = status()
        assert s["is_blocked"] is False and s["extra_credits"] == 1

    # Non-blocked FREE + honeymoon (same class: shares owner user state; loadscope keeps it on one worker)
    def test_used2_remaining3_upload_ok(self):
        set_user("2026-08-01T00:00:00+00:00", 2)
        s = status()
        assert s["tryons_remaining"] == 3 and s["is_blocked"] is False
        r = upload("person")
        assert r.status_code == 200, r.text
        assert "path" in r.json()

    def test_honeymoon_unlimited(self):
        set_user(ORIG_CREATED, 5)
        s = status()
        assert s["honeymoon_active"] is True and s["is_blocked"] is False
        assert s["tryons_remaining"] is None


class TestAdminStats:
    def test_unauth_401(self):
        assert requests.get(f"{BASE_URL}/api/admin/stats").status_code == 401

    def test_wrong_password_401(self):
        r = requests.post(f"{BASE_URL}/api/admin/login", json={"password": "wrong"})
        assert r.status_code == 401
        db.admin_login_attempts.delete_many({})

    def test_stats_real(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/admin/login", json={"password": "AtelierFondatore2026!"})
        assert r.status_code == 200
        d = s.get(f"{BASE_URL}/api/admin/stats").json()
        assert d["demo"] is False
        paid = list(db.payment_transactions.find({"payment_status": "paid"}, {"_id": 0}))
        total = round(sum(p["amount"] for p in paid), 2)
        month = round(sum(p["amount"] for p in paid if p["created_at"][:7] == "2026-10"), 2)
        assert d["kpi"]["revenue_total"] == total
        assert d["kpi"]["revenue_month"] == month
        assert d["kpi"]["subscribers_total"] == db.users.count_documents({"is_family_profile": {"$ne": True}})
        bp = {b["label"]: b["count"] for b in d["by_plan"]}
        assert bp["Una Tantum"] == sum(1 for p in paid if p["option"] == "extra")
        assert bp["Single"] == sum(1 for p in paid if p["option"] == "single")
        assert len(d["last_payments"]) == min(10, len(paid))
        assert set(d["hot_products"]) == {"Maglie", "Pantaloni", "Scarpe", "Giacche"}
        print(d)
