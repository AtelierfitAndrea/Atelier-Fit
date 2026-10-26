# Invita un'Amica (referral) + share tracking + owner stats: HTTP + direct reward-logic tests
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER_ID = "user_389c87aaadc6"
OWNER_TOK = "pending_test_tok"

import server  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


def run(coro_fn):
    async def wrap():
        server.db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        try:
            return await coro_fn(server.db)
        finally:
            await cleanup(server.db)
    return asyncio.run(wrap())


async def cleanup(db):
    ids = await db.users.distinct("user_id", {"email": {"$regex": "^test_ref_"}})
    await db.users.delete_many({"user_id": {"$in": ids}})
    await db.referrals.delete_many({"$or": [{"invitee_id": {"$in": ids}}, {"inviter_id": {"$in": ids}}]})
    await db.tryons.delete_many({"user_id": {"$in": ids}})
    await db.share_events.delete_many({"user_id": {"$in": ids}})


async def mk_user(db, days_old=0, **extra):
    uid = "test_ref_" + uuid.uuid4().hex[:8]
    doc = {"user_id": uid, "email": f"{uid}@example.com", "name": "T", "terms_version": "1.0-2026-06",
           "created_at": (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat(), **extra}
    await db.users.insert_one(doc)
    doc.pop("_id", None)
    return doc


def owner_session():
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {OWNER_TOK}"
    return s


# ---- HTTP (owner session; non-owners are blocked by prelaunch gate) ----
class TestHTTP:
    def test_referral_me_stable(self):
        s = owner_session()
        a, b = s.get(f"{BASE_URL}/api/referral/me"), s.get(f"{BASE_URL}/api/referral/me")
        assert a.status_code == 200, a.text
        d = a.json()
        assert d["code"] == b.json()["code"] and len(d["code"]) == 7
        assert d["top_at"] == 3 and isinstance(d["is_top"], bool)
        for k in ("invited", "qualified", "paid"):
            assert isinstance(d[k], int)

    def test_claim_self_400(self):
        s = owner_session()
        code = s.get(f"{BASE_URL}/api/referral/me").json()["code"]
        r = s.post(f"{BASE_URL}/api/referral/claim", json={"code": code.lower()})
        assert r.status_code == 400, r.text

    def test_claim_invalid_404(self):
        r = owner_session().post(f"{BASE_URL}/api/referral/claim", json={"code": "ZZZZZZZ"})
        assert r.status_code == 404, r.text

    def test_claim_validation_422(self):
        r = owner_session().post(f"{BASE_URL}/api/referral/claim", json={"code": "ab"})
        assert r.status_code == 422

    def test_unauth(self):
        assert requests.get(f"{BASE_URL}/api/referral/me").status_code == 401
        assert requests.post(f"{BASE_URL}/api/share-events", json={"channel": "whatsapp"}).status_code == 401
        assert requests.get(f"{BASE_URL}/api/admin/stats").status_code == 401

    def test_share_event_and_admin_stats(self):
        s = owner_session()
        r = s.post(f"{BASE_URL}/api/share-events", json={"channel": "WhatsApp"})
        assert r.status_code == 200 and r.json()["ok"] is True
        st = s.get(f"{BASE_URL}/api/admin/stats")
        assert st.status_code == 200
        d = st.json()
        assert len(d["daily_shares"]) == 30
        assert d["daily_shares"][-1]["date"] == datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert set(d["referrals"]) == {"invited", "qualified", "paid"}
        # cleanup owner event
        asyncio.run(_del_owner_shares())


async def _del_owner_shares():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await db.share_events.delete_many({"user_id": OWNER_ID})


# ---- Direct function tests (reward logic) ----
class TestRewardLogic:
    def test_claim_rules(self):
        async def sc(db):
            inviter = await mk_user(db, days_old=60)
            code = await server._referral_code(inviter["user_id"])
            assert code == await server._referral_code(inviter["user_id"])
            new = await mk_user(db)
            r = await server.referral_claim(server.ReferralClaimIn(code=code.lower()), server.User(**new))
            assert r == {"ok": True}
            ref = await db.referrals.find_one({"invitee_id": new["user_id"]})
            assert ref["status"] == "joined" and ref["inviter_id"] == inviter["user_id"]
            assert (await db.users.find_one({"user_id": new["user_id"]}))["referred_by"] == inviter["user_id"]
            r2 = await server.referral_claim(server.ReferralClaimIn(code=code), server.User(**new))
            assert r2.get("already") is True
            old = await mk_user(db, days_old=20)
            with pytest.raises(server.HTTPException) as e:
                await server.referral_claim(server.ReferralClaimIn(code=code), server.User(**old))
            assert e.value.status_code == 409
            tried = await mk_user(db)
            await db.tryons.insert_one({"id": "x", "user_id": tried["user_id"]})
            with pytest.raises(server.HTTPException) as e:
                await server.referral_claim(server.ReferralClaimIn(code=code), server.User(**tried))
            assert e.value.status_code == 409
            with pytest.raises(server.HTTPException) as e:
                await server.referral_claim(server.ReferralClaimIn(code=code), server.User(**inviter))
            assert e.value.status_code == 400
        run(sc)

    def test_qualify_free_inviter_once(self):
        async def sc(db):
            inviter = await mk_user(db, days_old=60, extra_tryon_credits=1)
            code = await server._referral_code(inviter["user_id"])
            new = await mk_user(db)
            await server.referral_claim(server.ReferralClaimIn(code=code), server.User(**new))
            st = await server.get_subscription_status(new["user_id"])
            await server.consume_tryon_quota(new["user_id"], st)
            await server.consume_tryon_quota(new["user_id"], st)
            inv = await db.users.find_one({"user_id": inviter["user_id"]})
            me = await db.users.find_one({"user_id": new["user_id"]})
            assert inv["extra_tryon_credits"] == 6, inv.get("extra_tryon_credits")
            assert me["extra_tryon_credits"] == 5  # honeymoon -> not decremented
            ref = await db.referrals.find_one({"invitee_id": new["user_id"]})
            assert ref["status"] == "qualified" and ref["inviter_reward"] == "5 prove extra"
        run(sc)

    def test_qualify_paying_inviter_plus7(self):
        async def sc(db):
            exp = datetime.now(timezone.utc) + timedelta(days=10)
            inviter = await mk_user(db, days_old=60, plan="SINGLE", plan_expires_at=exp.isoformat())
            code = await server._referral_code(inviter["user_id"])
            new = await mk_user(db)
            await server.referral_claim(server.ReferralClaimIn(code=code), server.User(**new))
            await server.consume_tryon_quota(new["user_id"], await server.get_subscription_status(new["user_id"]))
            inv = await db.users.find_one({"user_id": inviter["user_id"]})
            new_exp = server._parse_dt(inv["plan_expires_at"])
            assert abs((new_exp - exp) - timedelta(days=7)) < timedelta(seconds=2)
            assert int(inv.get("extra_tryon_credits", 0) or 0) == 0
            me = await db.users.find_one({"user_id": new["user_id"]})
            assert me["extra_tryon_credits"] == 5
        run(sc)

    def test_payment_reward_once(self):
        async def sc(db):
            free_inv = await mk_user(db, days_old=60)
            exp = datetime.now(timezone.utc) + timedelta(days=5)
            paying_inv = await mk_user(db, days_old=60, plan="FAMILY", plan_expires_at=exp.isoformat())
            for inviter in (free_inv, paying_inv):
                code = await server._referral_code(inviter["user_id"])
                new = await mk_user(db)
                await server.referral_claim(server.ReferralClaimIn(code=code), server.User(**new))
                await server._referral_on_payment(new["user_id"])
                after1 = await db.users.find_one({"user_id": inviter["user_id"]})
                await server._referral_on_payment(new["user_id"])
                after2 = await db.users.find_one({"user_id": inviter["user_id"]})
                assert after1["plan_expires_at"] == after2["plan_expires_at"]
                e1 = server._parse_dt(after1["plan_expires_at"])
                if inviter is free_inv:
                    assert after1["plan"] == "SINGLE"
                    assert abs(e1 - datetime.now(timezone.utc) - timedelta(days=30)) < timedelta(seconds=10)
                else:
                    assert after1["plan"] == "FAMILY"
                    assert abs((e1 - exp) - timedelta(days=30)) < timedelta(seconds=2)
                assert (await db.referrals.find_one({"invitee_id": new["user_id"]})).get("paid_at")
        run(sc)

    def test_is_top_after_3(self):
        async def sc(db):
            inviter = await mk_user(db, days_old=60)
            code = await server._referral_code(inviter["user_id"])
            for i in range(3):
                new = await mk_user(db)
                await server.referral_claim(server.ReferralClaimIn(code=code), server.User(**new))
                await server.consume_tryon_quota(new["user_id"], await server.get_subscription_status(new["user_id"]))
                me = await server.referral_me(server.User(**inviter))
                assert me["qualified"] == i + 1 and me["is_top"] == (i == 2)
            assert (await db.users.find_one({"user_id": inviter["user_id"]}))["extra_tryon_credits"] == 15
        run(sc)

    def test_shares_exclude_owner(self):
        async def sc(db):
            u = await mk_user(db)
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            now = datetime.now(timezone.utc)
            excl = await server._owner_user_ids()
            before = (await server._daily_shares(now, excl))[-1]["count"]
            await server.share_event(server.ShareEventIn(channel="Telegram"), server.User(**u))
            await db.share_events.insert_one({"user_id": OWNER_ID, "channel": "x", "day": day, "created_at": now.isoformat()})
            after = (await server._daily_shares(now, excl))[-1]["count"]
            await db.share_events.delete_many({"user_id": OWNER_ID})
            assert after == before + 1
            ev = await db.share_events.find_one({"user_id": u["user_id"]})
            assert ev["channel"] == "telegram" and ev["day"] == day
        run(sc)
