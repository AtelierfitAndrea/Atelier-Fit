# Stripe webhook (signature, paid/failed logging, idempotency), admin payments ledger, renewal-reminder cron.
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

ENV = dotenv_values("/app/backend/.env")
FENV = dotenv_values("/app/frontend/.env")
BASE_URL = FENV["REACT_APP_BACKEND_URL"].rstrip("/")
WH_SECRET = ENV["STRIPE_LIVE_WEBHOOK_SECRET"]
CRON_SECRET = ENV["WEBHOOK_CRON_SECRET"]
OWNER_TOK = "pending_test_tok"
db = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
TAG = uuid.uuid4().hex[:8]
NONOWNER_UID, NONOWNER_TOK = f"TEST_pay_user_{TAG}", f"TEST_pay_tok_{TAG}"
NONOWNER_EMAIL = f"test.pay.{TAG}@example.com"
SESSION_ID = f"cs_TEST_{TAG}"
PI_ID = f"pi_TEST_{TAG}"
INV_ID = f"in_TEST_{TAG}"
REN_UID, FAR_UID = f"TEST_ren_{TAG}", f"TEST_far_{TAG}"


def signed_post(event: dict):
    payload = json.dumps(event)
    ts = int(time.time())
    sig = hmac.new(WH_SECRET.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return requests.post(f"{BASE_URL}/api/stripe/webhook", data=payload,
                         headers={"Content-Type": "application/json", "Stripe-Signature": f"t={ts},v1={sig}"}, timeout=30)


def event(t, obj, eid=None):
    return {"id": eid or f"evt_TEST_{uuid.uuid4().hex[:10]}", "object": "event", "api_version": "2024-06-20",
            "created": int(time.time()), "livemode": True, "type": t, "data": {"object": obj}}


@pytest.fixture(scope="module", autouse=True)
def seed():
    now = datetime.now(timezone.utc)
    db.users.insert_many([
        {"user_id": NONOWNER_UID, "email": NONOWNER_EMAIL, "name": "Test Pay", "plan": "FREE", "terms_version": "1.0-2026-06",
         "created_at": now.isoformat()},
        {"user_id": REN_UID, "email": f"test.ren.{TAG}@example.com", "name": "Ren Tester", "plan": "SINGLE",
         "plan_expires_at": (now + timedelta(days=2.5)).isoformat(), "created_at": now.isoformat()},
        {"user_id": FAR_UID, "email": f"test.far.{TAG}@example.com", "name": "Far Tester", "plan": "SINGLE",
         "plan_expires_at": (now + timedelta(days=10)).isoformat(), "created_at": now.isoformat()},
    ])
    db.user_sessions.insert_one({"user_id": NONOWNER_UID, "session_token": NONOWNER_TOK,
                                 "expires_at": (now + timedelta(days=1)).isoformat(), "created_at": now.isoformat()})
    db.payment_transactions.insert_one({"session_id": SESSION_ID, "user_id": NONOWNER_UID, "option": "single", "lookup_key": "x",
                                        "amount": 2.99, "currency": "eur", "status": "initiated", "payment_status": "pending",
                                        "applied": False, "livemode": True, "created_at": now.isoformat(), "updated_at": now.isoformat()})
    yield
    uids = [NONOWNER_UID, REN_UID, FAR_UID]
    db.users.delete_many({"user_id": {"$in": uids}})
    db.user_sessions.delete_many({"user_id": {"$in": uids}})
    db.payment_transactions.delete_many({"session_id": SESSION_ID})
    db.payments.delete_many({"id": {"$in": [SESSION_ID, PI_ID, INV_ID]}})
    db.renewal_reminders.delete_many({"user_id": {"$in": uids}})
    db.referrals.delete_many({"user_id": {"$in": uids}}) if "referrals" in db.list_collection_names() else None
    db.cron_runs.delete_many({"run_id": {"$regex": f"TEST_{TAG}"}})


# --- Webhook signature ---
def test_unsigned_webhook_returns_200_not_received():
    r = requests.post(f"{BASE_URL}/api/stripe/webhook", json=event("checkout.session.completed", {"id": "x"}), timeout=30)
    assert r.status_code == 200
    assert r.json()["received"] is False


def test_bad_signature_returns_200_not_received():
    r = requests.post(f"{BASE_URL}/api/stripe/webhook", data="{}", headers={"Stripe-Signature": "t=1,v1=deadbeef"}, timeout=30)
    assert r.status_code == 200 and r.json()["received"] is False


def test_signed_testmode_event_ignored():
    ev = event("checkout.session.completed", {"id": "cs_none", "payment_status": "paid"})
    ev["livemode"] = False
    r = signed_post(ev)
    assert r.status_code == 200 and r.json()["received"] is True and r.json()["status"] == "ignored"


# --- checkout.session.completed (1 alert) ---
def test_checkout_completed_applies_plan_and_logs_once():
    obj = {"id": SESSION_ID, "object": "checkout.session", "payment_status": "paid", "amount_total": 299,
           "payment_intent": f"pi_paid_{TAG}", "customer_details": {"email": NONOWNER_EMAIL}}
    ev = event("checkout.session.completed", obj)
    r1 = signed_post(ev)
    assert r1.status_code == 200 and r1.json()["received"] is True and r1.json()["status"] == "ok"
    r2 = signed_post(ev)
    assert r2.status_code == 200 and r2.json()["received"] is True
    time.sleep(4)
    u = db.users.find_one({"user_id": NONOWNER_UID})
    assert u["plan"] == "SINGLE"
    exp = datetime.fromisoformat(u["plan_expires_at"])
    assert timedelta(days=29) < exp - datetime.now(timezone.utc) < timedelta(days=31)
    rows = list(db.payments.find({"id": SESSION_ID}, {"_id": 0}))
    assert len(rows) == 1
    assert rows[0]["status"] == "success" and rows[0]["type"] == "PRO"
    assert rows[0]["email"] == NONOWNER_EMAIL and rows[0]["amount"] == 2.99
    tx = db.payment_transactions.find_one({"session_id": SESSION_ID})
    assert tx["applied"] is True and tx["payment_status"] == "paid"


# --- failures (2 alerts) ---
def test_payment_intent_failed_logged_once():
    obj = {"id": PI_ID, "object": "payment_intent", "amount": 299, "receipt_email": NONOWNER_EMAIL,
           "last_payment_error": {"message": "TEST carta rifiutata"}}
    ev = event("payment_intent.payment_failed", obj)
    assert signed_post(ev).json()["received"] is True
    assert signed_post(ev).json()["received"] is True
    time.sleep(1)
    rows = list(db.payments.find({"id": PI_ID}, {"_id": 0}))
    assert len(rows) == 1
    assert rows[0]["status"] == "failed" and rows[0]["email"] == NONOWNER_EMAIL
    assert rows[0]["reason"] == "TEST carta rifiutata" and rows[0]["amount"] == 2.99


def test_invoice_failed_logged_once():
    obj = {"id": INV_ID, "object": "invoice", "amount_due": 499, "customer_email": NONOWNER_EMAIL, "status": "open"}
    ev = event("invoice.payment_failed", obj)
    assert signed_post(ev).json()["received"] is True
    assert signed_post(ev).json()["received"] is True
    time.sleep(1)
    rows = list(db.payments.find({"id": INV_ID}, {"_id": 0}))
    assert len(rows) == 1
    assert rows[0]["status"] == "failed" and rows[0]["email"] == NONOWNER_EMAIL and rows[0]["amount"] == 4.99
    assert rows[0]["reason"] == "Pagamento fattura non riuscito"
    assert db.stripe_events.find_one({"object_id": INV_ID}) is not None
    db.stripe_events.delete_many({"object_id": INV_ID})


# --- admin payments ---
def test_admin_payments_owner_list_and_filters():
    h = {"Authorization": f"Bearer {OWNER_TOK}"}
    r = requests.get(f"{BASE_URL}/api/admin/payments", headers=h, timeout=30)
    assert r.status_code == 200
    rows = r.json()["payments"]
    assert len(rows) <= 50
    dates = [p["createdAt"] for p in rows]
    assert dates == sorted(dates, reverse=True)
    ids = {p["id"] for p in rows}
    assert {SESSION_ID, PI_ID, INV_ID} <= ids
    assert all("_id" not in p for p in rows)
    s = requests.get(f"{BASE_URL}/api/admin/payments", params={"status": "success"}, headers=h, timeout=30).json()["payments"]
    assert s and all(p["status"] == "success" for p in s)
    f = requests.get(f"{BASE_URL}/api/admin/payments", params={"status": "failed"}, headers=h, timeout=30).json()["payments"]
    assert f and all(p["status"] == "failed" for p in f)


def test_admin_payments_non_owner_403_and_anon_401():
    r = requests.get(f"{BASE_URL}/api/admin/payments", headers={"Authorization": f"Bearer {NONOWNER_TOK}"}, timeout=30)
    assert r.status_code == 403
    assert requests.get(f"{BASE_URL}/api/admin/payments", timeout=30).status_code == 401


# --- cron check-renewals ---
def test_cron_requires_bearer():
    url = f"{BASE_URL}/api/cron/check-renewals"
    assert requests.post(url, json={}, timeout=30).status_code == 401
    assert requests.post(url, json={}, headers={"Authorization": "Bearer wrong"}, timeout=30).status_code == 401


def test_cron_sends_once_and_dedupes():
    url = f"{BASE_URL}/api/cron/check-renewals"
    h = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": f"TEST_{TAG}_1"}
    r = requests.post(url, json={}, headers=h, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert requests.post(url, json={}, headers=h, timeout=30).json()["status"] == "duplicate"
    time.sleep(8)
    assert db.renewal_reminders.count_documents({"user_id": REN_UID}) == 1
    assert db.renewal_reminders.count_documents({"user_id": FAR_UID}) == 0
    sent_at = db.renewal_reminders.find_one({"user_id": REN_UID})["sent_at"]
    h2 = {**h, "X-Webhook-Id": f"TEST_{TAG}_2"}
    assert requests.post(url, json={}, headers=h2, timeout=30).json()["status"] == "accepted"
    time.sleep(6)
    rows = list(db.renewal_reminders.find({"user_id": REN_UID}))
    assert len(rows) == 1 and rows[0]["sent_at"] == sent_at
