"""Backend tests for iteration 6: terms gate, devices listing, logout-all, delete-all photos."""
import io
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient


def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip()
                    break
    assert v
    return v.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

TERMS_VERSION = "1.0-2026-06"


@pytest.fixture(scope="module")
def mdb():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


def _mk_user(mdb, suffix="", plan="FREE", terms=False, ua="Mozilla/5.0 (Macintosh) Chrome/120 Safari/537"):
    uid = f"TEST_user_{suffix}_{uuid.uuid4().hex[:6]}"
    tok = f"TEST_sess_{suffix}_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id": uid, "email": f"{uid}@example.com", "name": "TEST U",
        "plan": plan, "created_at": now,
    }
    if terms:
        doc["terms_version"] = TERMS_VERSION
        doc["terms_accepted_at"] = now
    mdb.users.insert_one(doc)
    mdb.user_sessions.insert_one({
        "user_id": uid, "session_token": tok,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": now, "user_agent": ua,
    })
    return uid, tok


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def _cleanup(mdb, uid):
    mdb.users.delete_many({"user_id": uid})
    mdb.user_sessions.delete_many({"user_id": uid})
    mdb.terms_acceptances.delete_many({"user_id": uid})
    mdb.files.delete_many({"user_id": uid})
    mdb.tryons.delete_many({"user_id": uid})
    mdb.outfits.delete_many({"user_id": uid})
    mdb.measurements.delete_many({"user_id": uid})


# --- Terms gate ---

class TestTerms:
    def test_me_returns_terms_fields(self, mdb):
        uid, tok = _mk_user(mdb, "me")
        try:
            r = requests.get(f"{API}/auth/me", headers=_auth(tok))
            assert r.status_code == 200
            d = r.json()
            assert d["terms_current_version"] == TERMS_VERSION
            assert d.get("terms_version") in (None, "")
            assert d.get("terms_accepted_at") in (None, "")
        finally:
            _cleanup(mdb, uid)

    def test_accept_persists(self, mdb):
        uid, tok = _mk_user(mdb, "acc")
        try:
            r = requests.post(f"{API}/terms/accept",
                              json={"version": TERMS_VERSION, "accepted": True},
                              headers=_auth(tok))
            assert r.status_code == 200
            u = mdb.users.find_one({"user_id": uid})
            assert u["terms_version"] == TERMS_VERSION
            assert u.get("terms_accepted_at")
            assert mdb.terms_acceptances.count_documents({"user_id": uid}) == 1
            # /me reflects it
            me = requests.get(f"{API}/auth/me", headers=_auth(tok)).json()
            assert me["terms_version"] == TERMS_VERSION
        finally:
            _cleanup(mdb, uid)

    def test_accept_wrong_version_400(self, mdb):
        uid, tok = _mk_user(mdb, "wv")
        try:
            r = requests.post(f"{API}/terms/accept",
                              json={"version": "0.0-wrong", "accepted": True},
                              headers=_auth(tok))
            assert r.status_code == 400
        finally:
            _cleanup(mdb, uid)

    def test_accept_false_400(self, mdb):
        uid, tok = _mk_user(mdb, "af")
        try:
            r = requests.post(f"{API}/terms/accept",
                              json={"version": TERMS_VERSION, "accepted": False},
                              headers=_auth(tok))
            assert r.status_code == 400
        finally:
            _cleanup(mdb, uid)

    def test_accept_requires_auth(self):
        r = requests.post(f"{API}/terms/accept",
                          json={"version": TERMS_VERSION, "accepted": True})
        assert r.status_code == 401


# --- Devices ---

class TestDevices:
    def test_list_includes_current(self, mdb):
        uid, tok = _mk_user(mdb, "dev", ua="Mozilla/5.0 (iPhone; CPU iPhone OS 17) Safari/605")
        try:
            r = requests.get(f"{API}/auth/devices", headers=_auth(tok))
            assert r.status_code == 200
            arr = r.json()
            assert isinstance(arr, list) and len(arr) >= 1
            cur = [x for x in arr if x.get("current")]
            assert len(cur) == 1
            assert "Safari" in cur[0]["label"] or "iPhone" in cur[0]["label"]
        finally:
            _cleanup(mdb, uid)

    def test_logout_all_removes_all_sessions(self, mdb):
        uid, tok = _mk_user(mdb, "la")
        # Add a second session for same user
        tok2 = f"TEST_sess2_{uuid.uuid4().hex[:6]}"
        mdb.user_sessions.insert_one({
            "user_id": uid, "session_token": tok2,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_agent": "Mozilla/5.0 (Windows) Firefox/120",
        })
        try:
            assert mdb.user_sessions.count_documents({"user_id": uid}) == 2
            r = requests.post(f"{API}/auth/logout-all", headers=_auth(tok))
            assert r.status_code == 200
            assert r.json().get("signed_out") == 2
            assert mdb.user_sessions.count_documents({"user_id": uid}) == 0
            # /me returns 401
            me = requests.get(f"{API}/auth/me", headers=_auth(tok))
            assert me.status_code == 401
        finally:
            _cleanup(mdb, uid)


# --- Delete all photos ---

def _upload(tok, kind="person", profile_id=None):
    img = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    headers = _auth(tok)
    if profile_id:
        headers["X-Profile-Id"] = profile_id
    r = requests.post(f"{API}/upload?kind={kind}",
                      files={"file": ("t.png", img, "image/png")}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["path"]


class TestDeleteAllPhotos:
    def test_requires_auth(self):
        r = requests.post(f"{API}/photos/delete-all")
        assert r.status_code == 401

    def test_delete_wipes_person_tryons_outfits_keeps_garments_and_measurements(self, mdb):
        uid, tok = _mk_user(mdb, "del", terms=True)
        try:
            # Seed: upload a person file and a garment
            person_path = _upload(tok, "person")
            garment_path = _upload(tok, "garment")
            # Seed measurements
            mdb.measurements.insert_one({"user_id": uid, "height_cm": 170, "weight_kg": 65})
            # Seed tryons / outfits docs with paths "owned" by uid
            fake_tryon_path = f"vfit/tryons/{uid}/{uuid.uuid4().hex}.png"
            mdb.tryons.insert_one({
                "id": f"t_{uuid.uuid4().hex[:8]}", "user_id": uid,
                "person_path": person_path, "result_path": fake_tryon_path,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            fake_outfit_path = f"vfit/outfits/{uid}/{uuid.uuid4().hex}.png"
            mdb.outfits.insert_one({
                "id": f"o_{uuid.uuid4().hex[:8]}", "user_id": uid,
                "result_path": fake_outfit_path, "person_path": person_path,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            # Confirm garments endpoint works BEFORE
            w = requests.get(f"{API}/wardrobe/garments", headers=_auth(tok))
            assert w.status_code == 200

            # Call delete-all
            r = requests.post(f"{API}/photos/delete-all", headers=_auth(tok))
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["deleted_tryons"] >= 1
            assert data["deleted_outfits"] >= 1
            assert data["deleted_photos"] >= 1

            # tryons / outfits removed
            assert mdb.tryons.count_documents({"user_id": uid}) == 0
            assert mdb.outfits.count_documents({"user_id": uid}) == 0

            # person file marked deleted and GET returns 404
            f = mdb.files.find_one({"storage_path": person_path})
            assert f and f.get("is_deleted") is True
            g_file = requests.get(f"{API}/files/{person_path}", headers=_auth(tok))
            assert g_file.status_code == 404

            # measurements still intact
            assert mdb.measurements.count_documents({"user_id": uid}) == 1

            # garment file still accessible
            g_get = requests.get(f"{API}/files/{garment_path}", headers=_auth(tok))
            assert g_get.status_code == 200
            # wardrobe still lists it
            w2 = requests.get(f"{API}/wardrobe/garments", headers=_auth(tok))
            assert w2.status_code == 200
            # garment file is NOT marked deleted
            gf = mdb.files.find_one({"storage_path": garment_path})
            assert gf is None or gf.get("is_deleted") is not True
        finally:
            _cleanup(mdb, uid)

    def test_family_subprofile_scope(self, mdb):
        # Owner (FAMILY), sub-profile; deletion with X-Profile-Id removes only sub data
        owner_uid, owner_tok = _mk_user(mdb, "famowner", plan="FAMILY", terms=True)
        sub_id = f"TEST_sub_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        mdb.users.insert_one({
            "user_id": sub_id, "owner_id": owner_uid, "is_family_profile": True,
            "name": "TEST Sub", "plan": "FAMILY", "created_at": now,
        })
        try:
            # Upload for owner (no profile header) and for sub (with header)
            owner_person = _upload(owner_tok, "person")
            sub_person = _upload(owner_tok, "person", profile_id=sub_id)
            assert f"/{sub_id}/" in sub_person
            # Tryons for each
            mdb.tryons.insert_one({"id": f"to_{uuid.uuid4().hex[:6]}", "user_id": owner_uid,
                                    "person_path": owner_person, "result_path": owner_person})
            mdb.tryons.insert_one({"id": f"ts_{uuid.uuid4().hex[:6]}", "user_id": sub_id,
                                    "person_path": sub_person, "result_path": sub_person})

            # Delete-all for SUB only
            r = requests.post(f"{API}/photos/delete-all",
                              headers={**_auth(owner_tok), "X-Profile-Id": sub_id})
            assert r.status_code == 200, r.text

            # Sub data gone
            assert mdb.tryons.count_documents({"user_id": sub_id}) == 0
            # Owner data intact
            assert mdb.tryons.count_documents({"user_id": owner_uid}) == 1
            # Owner person file not deleted
            of = mdb.files.find_one({"storage_path": owner_person})
            assert of is None or of.get("is_deleted") is not True
            # Owner can still fetch own file
            g = requests.get(f"{API}/files/{owner_person}", headers=_auth(owner_tok))
            assert g.status_code == 200
            # Sub file marked deleted
            sf = mdb.files.find_one({"storage_path": sub_person})
            assert sf and sf.get("is_deleted") is True
        finally:
            mdb.users.delete_one({"user_id": sub_id})
            mdb.files.delete_many({"user_id": sub_id})
            mdb.tryons.delete_many({"user_id": sub_id})
            mdb.outfits.delete_many({"user_id": sub_id})
            _cleanup(mdb, owner_uid)
