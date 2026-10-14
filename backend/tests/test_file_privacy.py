"""Backend tests for private files and outfit sharing (iteration 5)."""
import io
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not set"
    return v.rstrip("/")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

OWNER_SESSION = "fam_test_1791784817"
OWNER_UID = "fam-owner-1791784817"
OTHER_SESSION = "TEST_other_sess_1"
OTHER_UID = "TEST_otheruser_1"


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _upload(session, kind="person"):
    img = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    r = requests.post(
        f"{API}/upload?kind={kind}",
        files={"file": ("t.png", img, "image/png")},
        headers=_auth(session),
    )
    assert r.status_code == 200, r.text
    return r.json()["path"]


# --- Files privacy ---

class TestFilesPrivacy:
    def test_get_file_requires_auth(self):
        path = _upload(OWNER_SESSION)
        r = requests.get(f"{API}/files/{path}")  # no auth
        assert r.status_code == 401, r.text

    def test_owner_can_read_own_file(self):
        path = _upload(OWNER_SESSION)
        r = requests.get(f"{API}/files/{path}", headers=_auth(OWNER_SESSION))
        assert r.status_code == 200
        assert r.content[:4] == b"\x89PNG"

    def test_other_user_cannot_read(self):
        path = _upload(OWNER_SESSION)
        r = requests.get(f"{API}/files/{path}", headers=_auth(OTHER_SESSION))
        assert r.status_code == 403

    def test_family_owner_can_read_sub_profile_file(self, db):
        # Create a sub-profile owned by OWNER_UID
        sub_id = f"TEST_sub_{uuid.uuid4().hex[:8]}"
        db.users.insert_one({
            "user_id": sub_id,
            "owner_id": OWNER_UID,
            "is_family_profile": True,
            "name": "TEST Sub",
            "plan": "FAMILY",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            # Upload as sub-profile (X-Profile-Id header routes to sub)
            img = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
            r = requests.post(
                f"{API}/upload?kind=person",
                files={"file": ("s.png", img, "image/png")},
                headers={**_auth(OWNER_SESSION), "X-Profile-Id": sub_id},
            )
            assert r.status_code == 200, r.text
            path = r.json()["path"]
            assert f"/{sub_id}/" in path
            # Account owner (without X-Profile-Id) should still be able to read
            r2 = requests.get(f"{API}/files/{path}", headers=_auth(OWNER_SESSION))
            assert r2.status_code == 200
            # Other independent user cannot
            r3 = requests.get(f"{API}/files/{path}", headers=_auth(OTHER_SESSION))
            assert r3.status_code == 403
        finally:
            db.users.delete_one({"user_id": sub_id})
            db.files.delete_many({"user_id": sub_id})

    def test_delete_own_then_get_404(self):
        path = _upload(OWNER_SESSION)
        d = requests.delete(f"{API}/files/{path}", headers=_auth(OWNER_SESSION))
        assert d.status_code == 200
        assert d.json().get("deleted") is True
        g = requests.get(f"{API}/files/{path}", headers=_auth(OWNER_SESSION))
        assert g.status_code == 404

    def test_delete_by_non_owner_forbidden(self):
        path = _upload(OWNER_SESSION)
        d = requests.delete(f"{API}/files/{path}", headers=_auth(OTHER_SESSION))
        assert d.status_code == 403


# --- Outfit sharing ---

class TestOutfitSharing:
    def test_share_flow_and_public_image(self, db):
        # Create a result file directly (shared via outfit)
        result_path = _upload(OWNER_SESSION, kind="person")  # reuse endpoint to get a real stored file
        outfit_id = f"TEST_outfit_{uuid.uuid4().hex[:8]}"
        db.outfits.insert_one({
            "id": outfit_id,
            "user_id": OWNER_UID,
            "result_path": result_path,
            "shared": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            # Before share: public endpoint 404
            r = requests.get(f"{API}/outfits/share/{outfit_id}")
            assert r.status_code == 404
            # Image public access: forbidden (not shared yet)
            r_img = requests.get(f"{API}/files/{result_path}")
            assert r_img.status_code == 401  # no auth

            # Mark shared
            s = requests.post(f"{API}/outfits/{outfit_id}/share", headers=_auth(OWNER_SESSION))
            assert s.status_code == 200
            assert s.json().get("shared") is True

            # After share: public endpoint 200, redacted (no user_id)
            r2 = requests.get(f"{API}/outfits/share/{outfit_id}")
            assert r2.status_code == 200
            data = r2.json()
            assert "user_id" not in data
            assert data.get("id") == outfit_id
            assert data.get("shared") is True

            # Shared image accessible without auth
            r_img2 = requests.get(f"{API}/files/{result_path}")
            assert r_img2.status_code == 200, r_img2.text
        finally:
            db.outfits.delete_one({"id": outfit_id})

    def test_share_non_owner_404(self, db):
        outfit_id = f"TEST_outfit_{uuid.uuid4().hex[:8]}"
        db.outfits.insert_one({
            "id": outfit_id,
            "user_id": OWNER_UID,
            "result_path": "vfit/person/x/y.png",
            "shared": False,
        })
        try:
            r = requests.post(f"{API}/outfits/{outfit_id}/share", headers=_auth(OTHER_SESSION))
            assert r.status_code == 404
        finally:
            db.outfits.delete_one({"id": outfit_id})
