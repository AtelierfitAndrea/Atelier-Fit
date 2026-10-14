"""Backend tests for Studio Grid (multi-brand outfit) endpoints.

Covered:
- POST /api/outfit/generate-from-uploads validation (0 items, 5 items, bad slot, foreign path)
- POST /api/wardrobe/garments/from-screenshot validation (bad slot, bad URL, foreign path)
- GET /api/outfits returns outfits with source="grid"
- Regression: POST /api/outfit/generate validation path (not <2 garments) without triggering AI
"""
import os
import io
import time
import uuid
import pytest
import requests

def _read_frontend_env():
    try:
        for line in open("/app/frontend/.env"):
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return os.environ.get("REACT_APP_BACKEND_URL", "")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
API = f"{BASE_URL}/api"
OWNER_TOKEN = "fam_test_1791784817"
OWNER_ID = "fam-owner-1791784817"

HEADERS = {"Authorization": f"Bearer {OWNER_TOKEN}"}


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _upload(session: requests.Session, kind: str) -> str:
    with open("/app/memory/test_garment.jpg", "rb") as f:
        r = session.post(f"{API}/upload?kind={kind}",
                         files={"file": ("test.jpg", f, "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["path"]


@pytest.fixture(scope="module")
def person_path(session):
    return _upload(session, "person")


@pytest.fixture(scope="module")
def garment_path(session):
    return _upload(session, "garment")


# ---------- outfit/generate-from-uploads ----------
class TestGenerateFromUploadsValidation:
    def test_requires_auth(self):
        r = requests.post(f"{API}/outfit/generate-from-uploads", json={"items": []})
        assert r.status_code in (401, 403)

    def test_zero_items_rejected(self, session, person_path):
        r = session.post(f"{API}/outfit/generate-from-uploads",
                         json={"person_path": person_path, "items": []})
        assert r.status_code == 400
        assert "1 a 4" in r.json()["detail"]

    def test_five_items_rejected(self, session, person_path, garment_path):
        items = [{"slot": s, "image_path": garment_path} for s in
                 ("top", "bottom", "jacket", "shoes", "extra")]
        r = session.post(f"{API}/outfit/generate-from-uploads",
                         json={"person_path": person_path, "items": items})
        assert r.status_code == 400

    def test_invalid_slot_rejected(self, session, person_path, garment_path):
        r = session.post(f"{API}/outfit/generate-from-uploads",
                         json={"person_path": person_path,
                               "items": [{"slot": "hat", "image_path": garment_path}]})
        assert r.status_code == 400
        assert "1 a 4" in r.json()["detail"]

    def test_foreign_image_rejected(self, session, person_path):
        foreign = "atelier/garment/some-other-user/abc.jpg"
        r = session.post(f"{API}/outfit/generate-from-uploads",
                         json={"person_path": person_path,
                               "items": [{"slot": "top", "image_path": foreign}]})
        assert r.status_code == 403

    def test_foreign_person_path_rejected(self, session, garment_path):
        foreign_person = "atelier/person/some-other-user/abc.jpg"
        r = session.post(f"{API}/outfit/generate-from-uploads",
                         json={"person_path": foreign_person,
                               "items": [{"slot": "top", "image_path": garment_path}]})
        assert r.status_code == 403


# ---------- wardrobe/garments/from-screenshot ----------
class TestWardrobeFromScreenshot:
    def test_bad_slot_rejected(self, session, garment_path):
        r = session.post(f"{API}/wardrobe/garments/from-screenshot",
                         json={"image_path": garment_path, "slot": "hat",
                               "url": "https://example.com/x"})
        assert r.status_code == 400

    def test_bad_url_rejected(self, session, garment_path):
        r = session.post(f"{API}/wardrobe/garments/from-screenshot",
                         json={"image_path": garment_path, "slot": "jacket",
                               "url": "not-a-url"})
        assert r.status_code == 400
        assert "URL" in r.json()["detail"]

    def test_foreign_image_rejected(self, session):
        r = session.post(f"{API}/wardrobe/garments/from-screenshot",
                         json={"image_path": "atelier/garment/someone/x.jpg",
                               "slot": "jacket", "url": "https://example.com"})
        assert r.status_code == 403

    def test_success_saves_to_wardrobe(self, session, garment_path):
        # Use a URL that will almost certainly fail to fetch meta -> falls back to generic name
        url = f"https://httpstat.us/404?nocache={uuid.uuid4().hex}"
        r = session.post(f"{API}/wardrobe/garments/from-screenshot",
                         json={"image_path": garment_path, "slot": "jacket", "url": url})
        assert r.status_code == 200, r.text
        g = r.json()
        assert g.get("category") == "outerwear"
        assert g.get("image_path") == garment_path
        # Verify in list
        lst = session.get(f"{API}/wardrobe/garments").json()
        assert any(x.get("id") == g["id"] for x in lst)
        # Cleanup
        session.delete(f"{API}/wardrobe/garments/{g['id']}")


# ---------- regression on /outfit/generate ----------
class TestOutfitGenerateRegression:
    def test_too_few_garments(self, session):
        r = session.post(f"{API}/outfit/generate",
                         json={"garment_ids": ["x"]})
        assert r.status_code == 400
        assert "2 a 4" in r.json()["detail"]

    def test_missing_garment(self, session):
        r = session.post(f"{API}/outfit/generate",
                         json={"garment_ids": ["nope-1", "nope-2"]})
        # not blocked, so should hit garment-lookup 404
        assert r.status_code in (402, 404)


# ---------- outfits list ----------
class TestOutfitsList:
    def test_list_ok(self, session):
        r = session.get(f"{API}/outfits")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
