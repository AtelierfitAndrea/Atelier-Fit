# Freemium v2: FREE 3/day (Rome midnight reset), BOOST today-only, permanent referral extras, PRO/FAMILY unlimited,
# watermark free/pro, checkout options, owner-room top referrers. No real AI, no real Stripe sessions.
import asyncio
import io
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import requests
from dotenv import load_dotenv
from PIL import Image

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER_ID = "user_389c87aaadc6"
H = {"Authorization": "Bearer pending_test_tok"}

import server  # noqa: E402
import tryon_quality  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pymongo import MongoClient  # noqa: E402

sdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
FIELDS = ("created_at", "free_month_end", "plan", "plan_expires_at", "extra_tryon_credits", "boost", "daily_tryon_count")


def run(fn):
    async def wrap():
        server.db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        try:
            return await fn(server.db)
        finally:
            ids = await server.db.users.distinct("user_id", {"email": {"$regex": "^test_frm_"}})
            await server.db.users.delete_many({"user_id": {"$in": ids}})
            await server.db.referrals.delete_many({"$or": [{"invitee_id": {"$in": ids}}, {"inviter_id": {"$in": ids}}]})
            await server.db.payment_transactions.delete_many({"user_id": {"$in": ids}})
    return asyncio.run(wrap())


async def mk(db, days_old=40, **extra):
    uid = "test_frm_" + uuid.uuid4().hex[:8]
    await db.users.insert_one({"user_id": uid, "email": f"{uid}@example.com", "name": "T",
                               "created_at": (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat(), **extra})
    return uid


def today():
    return server._rome_day(datetime.now(timezone.utc))


def yesterday():
    return server._rome_day(datetime.now(timezone.utc) - timedelta(days=1))


@pytest.fixture(scope="module")
def owner_backup():
    doc = sdb.users.find_one({"user_id": OWNER_ID}, {"_id": 0})
    yield
    sdb.users.update_one({"user_id": OWNER_ID}, {"$set": {k: doc[k] for k in FIELDS if k in doc},
                                                 "$unset": {k: "" for k in FIELDS if k not in doc}})


def owner_set(**kv):
    sdb.users.update_one({"user_id": OWNER_ID}, {"$set": kv})


def owner_unset(*keys):
    sdb.users.update_one({"user_id": OWNER_ID}, {"$unset": {k: "" for k in keys}})


def status():
    r = requests.get(f"{BASE_URL}/api/subscription/status", headers=H)
    assert r.status_code == 200, r.text
    return r.json()


# ---- HTTP status for owner in different states ----
@pytest.mark.usefixtures("owner_backup")
class TestStatusHTTP:
    def test_free_past_honeymoon(self):
        old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        owner_set(created_at=old, plan="FREE", extra_tryon_credits=0)
        owner_unset("free_month_end", "boost", "daily_tryon_count", "plan_expires_at")
        s = status()
        assert s["honeymoon_active"] is False
        assert s["tryons_limit"] == 3 and s["tryons_remaining"] == 3 and s["tryons_used_today"] == 0
        assert s["boost_credits"] == 0 and s["extra_credits"] == 0 and s["is_blocked"] is False
        assert s["watermark"] == "free"
        exp = server._next_rome_midnight(datetime.now(timezone.utc)).isoformat()
        assert s["resets_at"] == exp
        r = datetime.fromisoformat(s["resets_at"]).astimezone(server.ROME)
        assert (r.hour, r.minute) == (0, 0)

    def test_free_blocked_and_boost(self):
        owner_set(daily_tryon_count={"day": today(), "used": 3})
        s = status()
        assert s["tryons_remaining"] == 0 and s["is_blocked"] is True
        owner_set(boost={"day": today(), "credits": 3})
        s = status()
        assert s["boost_credits"] == 3 and s["is_blocked"] is False

    def test_stale_boost_and_daily_ignored(self):
        owner_set(daily_tryon_count={"day": yesterday(), "used": 3}, boost={"day": yesterday(), "credits": 3})
        s = status()
        assert s["tryons_remaining"] == 3 and s["boost_credits"] == 0

    def test_honeymoon_unlimited(self):
        owner_set(created_at=datetime.now(timezone.utc).isoformat())
        s = status()
        assert s["honeymoon_active"] is True and s["tryons_limit"] is None and s["watermark"] == "free" and s["is_blocked"] is False

    @pytest.mark.parametrize("plan", ["SINGLE", "FAMILY"])
    def test_paid_unlimited_pro(self, plan):
        owner_set(created_at=(datetime.now(timezone.utc) - timedelta(days=40)).isoformat(), plan=plan,
                  plan_expires_at=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
                  daily_tryon_count={"day": today(), "used": 3})
        s = status()
        assert s["plan"] == plan and s["tryons_limit"] is None and s["is_blocked"] is False and s["watermark"] == "pro"

    def test_expired_plan_reverts_free(self):
        owner_set(plan="SINGLE", plan_expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
        s = status()
        assert s["plan"] == "FREE" and s["watermark"] == "free" and s["tryons_limit"] == 3

    def test_checkout_family_rejected(self):
        r = requests.post(f"{BASE_URL}/api/subscription/checkout", headers=H,
                          json={"option": "family", "origin_url": BASE_URL})
        assert r.status_code == 400 and r.json()["detail"] == "Invalid option"

    def test_upload_blocked_402(self):
        owner_set(plan="FREE", daily_tryon_count={"day": today(), "used": 3}, extra_tryon_credits=0)
        owner_unset("boost", "plan_expires_at")
        png = io.BytesIO()
        Image.new("RGB", (4, 4)).save(png, "PNG")
        r = requests.post(f"{BASE_URL}/api/upload?kind=person", headers=H, files={"file": ("t.png", png.getvalue(), "image/png")})
        assert r.status_code == 402, r.text


# ---- consume order ----
def test_consume_order():
    async def go(db):
        uid = await mk(db, extra_tryon_credits=2)
        seq = []
        for _ in range(9):
            st = await server.get_subscription_status(uid)
            seq.append((st["tryons_remaining"], st["boost_credits"], st["extra_credits"], st["is_blocked"]))
            if st["is_blocked"]:
                break
            if len(seq) == 4:  # after daily is used up, buy a BOOST
                await db.users.update_one({"user_id": uid}, {"$set": {"boost": {"day": today(), "credits": 3}}})
                st = await server.get_subscription_status(uid)
                seq[-1] = (st["tryons_remaining"], st["boost_credits"], st["extra_credits"], st["is_blocked"])
            await server.consume_tryon_quota(uid, st)
        return seq
    seq = run(go)
    assert seq == [(3, 0, 2, False), (2, 0, 2, False), (1, 0, 2, False), (0, 3, 2, False),
                   (0, 2, 2, False), (0, 1, 2, False), (0, 0, 2, False), (0, 0, 1, False), (0, 0, 0, True)], seq


def test_consume_noop_for_pro_and_honeymoon():
    async def go(db):
        a = await mk(db, plan="SINGLE", plan_expires_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat())
        b = await mk(db, days_old=1)
        for u in (a, b):
            await server.consume_tryon_quota(u, await server.get_subscription_status(u))
        return [await db.users.find_one({"user_id": u}, {"_id": 0, "daily_tryon_count": 1}) for u in (a, b)]
    assert all("daily_tryon_count" not in d for d in run(go))


def test_reset_previous_day():
    async def go(db):
        uid = await mk(db, daily_tryon_count={"day": yesterday(), "used": 3}, boost={"day": yesterday(), "credits": 2})
        st = await server.get_subscription_status(uid)
        await server.consume_tryon_quota(uid, st)
        return st, await db.users.find_one({"user_id": uid}, {"_id": 0})
    st, doc = run(go)
    assert st["tryons_remaining"] == 3 and st["boost_credits"] == 0
    assert doc["daily_tryon_count"] == {"day": today(), "used": 1}


# ---- paid BOOST ----
def test_apply_paid_boost():
    async def go(db):
        uid = await mk(db, boost={"day": today(), "credits": 1})
        sid = "cs_test_frm_" + uuid.uuid4().hex
        await db.payment_transactions.insert_one({"session_id": sid, "user_id": uid, "option": "extra", "payment_status": "paid",
                                                  "applied": False, "receipt_status": "skip", "livemode": False})
        await server._apply_paid_session(sid)
        await server._apply_paid_session(sid)  # idempotent
        await asyncio.sleep(0.2)
        st = await server.get_subscription_status(uid)
        d = await db.users.find_one({"user_id": uid}, {"_id": 0})
        return st, d
    st, d = run(go)
    assert d["boost"] == {"day": today(), "credits": 4}
    assert st["boost_credits"] == 4 and st["plan"] == "FREE"


def test_apply_paid_boost_over_stale():
    async def go(db):
        uid = await mk(db, boost={"day": yesterday(), "credits": 2})
        sid = "cs_test_frm_" + uuid.uuid4().hex
        await db.payment_transactions.insert_one({"session_id": sid, "user_id": uid, "option": "extra", "payment_status": "paid",
                                                  "applied": False, "receipt_status": "skip", "livemode": False})
        await server._apply_paid_session(sid)
        return await db.users.find_one({"user_id": uid}, {"_id": 0})
    assert run(go)["boost"] == {"day": today(), "credits": 3}


# ---- watermark mark selection ----
def test_mark_for():
    async def go(db):
        free = await mk(db)
        pro = await mk(db, plan="SINGLE", plan_expires_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat())
        fam = await mk(db, plan="FAMILY", plan_expires_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat())
        child = await mk(db, owner_id=fam, is_family_profile=True)
        return [await server._mark_for(u) for u in (free, pro, fam, child)]
    assert run(go) == ["free", "pro", "pro", "pro"]


def _img(w=800, h=1000, top=None, bot=None, seed=1):
    rng = np.random.default_rng(seed)
    a = rng.integers(40, 220, (h, w, 3), dtype=np.uint8)
    if top is not None:
        a[:60] = top
    if bot is not None:
        a[-100:] = bot
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, "PNG")
    return buf.getvalue(), a


def _corner_diff(mark):
    raw, a = _img()
    out = np.asarray(Image.open(io.BytesIO(tryon_quality.watermark(raw, mark))).convert("RGB")).astype(int)
    base = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")).astype(int)
    d = np.abs(out - base).sum(axis=2) > 120
    ys, xs = np.nonzero(d)
    return out.shape, ys, xs


def test_watermark_free_vs_pro():
    shp, ys, xs = _corner_diff("free")
    shp2, ys2, xs2 = _corner_diff("pro")
    assert shp[:2] == (1000, 800) and shp2[:2] == (1000, 800)
    assert len(ys) > 0 and ys.min() > 800 and xs.min() > 300  # bottom-right
    assert len(ys2) > 0 and ys2.min() > 850
    w_free, w_pro = xs.max() - xs.min(), xs2.max() - xs2.min()
    assert w_pro < w_free * 0.7, (w_free, w_pro)
    assert len(ys2) < len(ys)
    assert tryon_quality.MARKS["free"][0] == "Creato con My Atelier" and tryon_quality.MARKS["pro"][0] == "myatelierapp.it"
    assert tryon_quality.MARKS["pro"][2] < tryon_quality.MARKS["free"][2]


def test_trim_pad_bands():
    raw, _ = _img(top=128, bot=90)
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    assert tryon_quality._trim_pad_bands(im, None).size == (800, 1000)
    t = tryon_quality._trim_pad_bands(im, (128.0, 90.0)).size
    assert t[0] == 800 and 830 <= t[1] <= 850, t
    # flat band with different grey than the pad: not trimmed
    assert tryon_quality._trim_pad_bands(im, (200.0, 30.0)).size == (800, 1000)
    # no flat band at all
    raw2, _ = _img()
    assert tryon_quality._trim_pad_bands(Image.open(io.BytesIO(raw2)), (128.0, 90.0)).size == (800, 1000)


# ---- owner room top referrers ----
def test_top_referrers_and_admin_stats():
    async def go(db):
        a = await mk(db, name="Alfa")
        b = await mk(db, name="Beta")
        now = datetime.now(timezone.utc).isoformat()
        rows = [(a, "qualified"), (a, "joined"), (b, "joined"), (b, "joined"), (b, "joined")]
        for inv, stt in rows:
            await db.referrals.insert_one({"id": str(uuid.uuid4()), "inviter_id": inv, "invitee_id": "test_frm_inv_" + uuid.uuid4().hex[:6],
                                           "status": stt, "created_at": now})
        # old month row must not count
        await db.referrals.insert_one({"id": str(uuid.uuid4()), "inviter_id": b, "invitee_id": "test_frm_inv_old",
                                       "status": "qualified", "created_at": "2020-01-01T00:00:00+00:00"})
        top = await server._top_referrers(datetime.now(timezone.utc).strftime("%Y-%m"), [OWNER_ID])
        http = requests.get(f"{BASE_URL}/api/admin/stats", headers=H)
        return a, b, top, http
    a, b, top, http = run(go)
    mine = [t for t in top if t["email"].startswith("test_frm_")]
    assert len(top) <= 10
    assert mine[0]["name"] == "Alfa" and mine[0]["invited"] == 2 and mine[0]["qualified"] == 1
    assert mine[1]["name"] == "Beta" and mine[1]["invited"] == 3 and mine[1]["qualified"] == 0
    assert http.status_code == 200 and isinstance(http.json().get("top_referrers"), list)
    names = [t["name"] for t in http.json()["top_referrers"]]
    assert "Alfa" in names and "Beta" in names
