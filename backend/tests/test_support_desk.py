# Support desk (support.py): customer tickets, AI auto-reply, owner inbox, cron poll.
# NOTE: real emails are sent (CC andremo2014@gmail.com). Keep sends minimal (~3 per run).
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER_TOKEN = os.environ.get("SUP_OWNER_TOKEN")
NONOWNER_TOKEN = os.environ.get("SUP_NONOWNER_TOKEN")
CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET")

STATE = {}


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def wait_status(tid, want, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = requests.get(f"{BASE_URL}/api/admin/support/tickets/{tid}", headers=H(OWNER_TOKEN))
        d = r.json()
        if d.get("status") in want:
            return d
        time.sleep(3)
    return d


# --- Auth gating ---
class TestAuthGating:
    @pytest.mark.parametrize("method,path", [
        ("get", "/api/admin/support/tickets"), ("get", "/api/admin/support/tickets/x"),
        ("post", "/api/admin/support/tickets/x/reply"), ("post", "/api/admin/support/tickets/x/ai-draft"),
        ("patch", "/api/admin/support/tickets/x"), ("put", "/api/admin/support/settings"),
        ("post", "/api/admin/support/sync"), ("get", "/api/support/tickets")])
    def test_unauth_401(self, method, path):
        r = getattr(requests, method)(f"{BASE_URL}{path}", json={})
        assert r.status_code == 401, r.text

    @pytest.mark.parametrize("method,path,body", [
        ("get", "/api/admin/support/tickets", None), ("get", "/api/admin/support/tickets/x", None),
        ("post", "/api/admin/support/tickets/x/reply", {"message": "hi"}), ("post", "/api/admin/support/tickets/x/ai-draft", None),
        ("patch", "/api/admin/support/tickets/x", {"status": "open"}), ("put", "/api/admin/support/settings", {"auto_reply": True}),
        ("post", "/api/admin/support/sync", None)])
    def test_nonowner_403(self, method, path, body):
        r = getattr(requests, method)(f"{BASE_URL}{path}", json=body, headers=H(NONOWNER_TOKEN))
        assert r.status_code == 403, r.text


# --- Cron endpoint ---
class TestCron:
    def test_no_bearer(self):
        assert requests.post(f"{BASE_URL}/api/cron/support-poll", json={}).status_code == 401

    def test_wrong_bearer(self):
        assert requests.post(f"{BASE_URL}/api/cron/support-poll", json={}, headers=H("wrong")).status_code == 401

    def test_accepted_then_duplicate(self):
        wid = f"TEST_{uuid.uuid4()}"
        h = {**H(CRON_SECRET), "X-Webhook-Id": wid}
        r1 = requests.post(f"{BASE_URL}/api/cron/support-poll", json={"run_id": wid}, headers=h)
        assert r1.status_code in (200, 202) and r1.json()["status"] == "accepted", r1.text
        r2 = requests.post(f"{BASE_URL}/api/cron/support-poll", json={"run_id": wid}, headers=h)
        assert r2.status_code in (200, 202) and r2.json()["status"] == "duplicate", r2.text

    def test_invalid_body(self):
        r = requests.post(f"{BASE_URL}/api/cron/support-poll", data="notjson", headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 400


# --- Customer + owner flows ---
class TestFlows:
    def test_validation(self):
        r = requests.post(f"{BASE_URL}/api/support/tickets", json={"category": "bogus", "subject": "abc", "message": "hello"}, headers=H(OWNER_TOKEN))
        assert r.status_code == 422

    def test_01_relevant_ticket_ai_answered(self):
        r = requests.post(f"{BASE_URL}/api/support/tickets", headers=H(OWNER_TOKEN), json={
            "category": "giacche", "subject": "TEST_ Taglia giacca tra due misure",
            "message": "Buongiorno, sono tra la M e la L per una giacca di lana. Quale taglia mi consigliate di scegliere?"})
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["status"] == "open" and t["category"] == "giacche" and t["source"] == "app"
        STATE["t1"] = t["id"]
        d = wait_status(t["id"], ("answered", "needs_human"))
        assert d["status"] == "answered", d
        ai = [m for m in d["messages"] if m["author"] == "ai"]
        assert ai and ai[-1]["sent"] is True and not ai[-1].get("draft")
        print("AI REPLY:", ai[-1]["body"])
        assert "My Atelier" in ai[-1]["body"]

    def test_02_user_list_own_only(self):
        r = requests.get(f"{BASE_URL}/api/support/tickets", headers=H(OWNER_TOKEN))
        assert r.status_code == 200
        items = r.json()
        assert all(t["user_id"] == "user_389c87aaadc6" for t in items)
        t1 = next(t for t in items if t["id"] == STATE["t1"])
        assert len(t1["messages"]) >= 2
        assert all("email_message_id" not in m for m in t1["messages"])

    def test_03_followup_triggers_ai(self):
        r = requests.post(f"{BASE_URL}/api/support/tickets/{STATE['t1']}/messages", headers=H(OWNER_TOKEN),
                          json={"message": "Grazie. E per i pantaloni aderenti invece?"})
        assert r.status_code == 200 and r.json()["author"] == "user"
        time.sleep(4)
        d = wait_status(STATE["t1"], ("answered", "needs_human"))
        ai = [m for m in d["messages"] if m["author"] == "ai"]
        assert d["status"] == "answered" and len(ai) >= 2, d
        print("FOLLOWUP REPLY:", ai[-1]["body"])

    def test_04_followup_foreign_ticket_404(self):
        r = requests.post(f"{BASE_URL}/api/support/tickets/e933a7ab-1caf-44a5-ba88-92ef01ce202d/messages", headers=H(OWNER_TOKEN), json={"message": "x"})
        assert r.status_code == 404

    def test_05_irrelevant_needs_human(self):
        r = requests.post(f"{BASE_URL}/api/support/tickets", headers=H(OWNER_TOKEN), json={
            "category": "altro", "subject": "TEST_ Fattura abbonamento",
            "message": "Vorrei una fattura per il mio abbonamento, intestata alla mia azienda con partita IVA."})
        assert r.status_code == 200
        STATE["t2"] = r.json()["id"]
        d = wait_status(STATE["t2"], ("answered", "needs_human"))
        assert d["status"] == "needs_human", d
        assert not [m for m in d["messages"] if m["author"] == "ai"]

    def test_06_autoreply_off_draft(self):
        r = requests.put(f"{BASE_URL}/api/admin/support/settings", headers=H(OWNER_TOKEN), json={"auto_reply": False})
        assert r.status_code == 200 and r.json()["auto_reply"] is False
        try:
            r = requests.post(f"{BASE_URL}/api/support/tickets", headers=H(OWNER_TOKEN), json={
                "category": "foto", "subject": "TEST_ Foto scura",
                "message": "La foto del mio avatar risulta troppo scura e sfocata, come posso migliorarla?"})
            STATE["t3"] = r.json()["id"]
            d = wait_status(STATE["t3"], ("answered", "needs_human"))
            assert d["status"] == "needs_human", d
            drafts = [m for m in d["messages"] if m.get("draft")]
            assert drafts and drafts[0]["author"] == "ai" and not drafts[0].get("sent")
            items = requests.get(f"{BASE_URL}/api/support/tickets", headers=H(OWNER_TOKEN)).json()
            t3 = next(t for t in items if t["id"] == STATE["t3"])
            assert all(not m.get("draft") for m in t3["messages"]) and all(m["author"] == "user" for m in t3["messages"])
        finally:
            r = requests.put(f"{BASE_URL}/api/admin/support/settings", headers=H(OWNER_TOKEN), json={"auto_reply": True})
            assert r.json()["auto_reply"] is True

    def test_07_admin_list(self):
        r = requests.get(f"{BASE_URL}/api/admin/support/tickets", headers=H(OWNER_TOKEN))
        assert r.status_code == 200
        d = r.json()
        assert set(d["counts"]) == {"open", "answered", "needs_human", "closed"}
        assert "auto_reply" in d["settings"] and all("preview" in t for t in d["tickets"])
        r = requests.get(f"{BASE_URL}/api/admin/support/tickets", params={"status": "needs_human"}, headers=H(OWNER_TOKEN))
        assert all(t["status"] == "needs_human" for t in r.json()["tickets"])

    def test_08_ai_draft_endpoint(self):
        r = requests.post(f"{BASE_URL}/api/admin/support/tickets/{STATE['t3']}/ai-draft", headers=H(OWNER_TOKEN), timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["draft"] and d["relevant"] is True

    def test_09_manual_reply(self):
        r = requests.post(f"{BASE_URL}/api/admin/support/tickets/{STATE['t3']}/reply", headers=H(OWNER_TOKEN), timeout=90,
                          json={"message": "Gentile cliente,\nla invitiamo a scattare con luce naturale frontale.\n\nUn caro saluto,\nIl team My Atelier"})
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["author"] == "admin" and m["sent"] is True
        d = requests.get(f"{BASE_URL}/api/admin/support/tickets/{STATE['t3']}", headers=H(OWNER_TOKEN)).json()
        assert d["status"] == "answered" and not [x for x in d["messages"] if x.get("draft")]

    def test_10_patch_status(self):
        r = requests.patch(f"{BASE_URL}/api/admin/support/tickets/{STATE['t2']}", headers=H(OWNER_TOKEN), json={"status": "closed"})
        assert r.status_code == 200 and r.json()["status"] == "closed"
        assert requests.get(f"{BASE_URL}/api/admin/support/tickets/{STATE['t2']}", headers=H(OWNER_TOKEN)).json()["status"] == "closed"
        assert requests.patch(f"{BASE_URL}/api/admin/support/tickets/{STATE['t2']}", headers=H(OWNER_TOKEN), json={"status": "bad"}).status_code == 422
        assert requests.patch(f"{BASE_URL}/api/admin/support/tickets/nope", headers=H(OWNER_TOKEN), json={"status": "open"}).status_code == 404

    def test_11_sync(self):
        r = requests.post(f"{BASE_URL}/api/admin/support/sync", headers=H(OWNER_TOKEN), timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        print("SYNC:", d)
        assert "new" in d and "error" not in d
