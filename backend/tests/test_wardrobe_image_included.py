"""Backend tests for iteration 8:
- PUT /api/wardrobe/garments/{id}/image (wardrobe_set_image): ownership + 404
- GET /api/subscription/status: honeymoon flag used by IncludedNote (SINGLE plan user visible)
- POST /api/wardrobe/garments/from-screenshot persists price/brand/source_url for grid-total
"""
import os
import io
import uuid
import time
import datetime as dt
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0]).rstrip("/")
API = f"{BASE_URL}/api"

OWNER_TOKEN = "fam_test_1791784817"
OWNER_ID = "fam-owner-1791784817"
HEADERS = {"Authorization": f"Bearer {OWNER_TOKEN}"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update(HEADERS)
    return sess


@pytest.fixture(scope="module")
def garment_path(s):
    with open("/app/memory/test_garment.jpg", "rb") as f:
        r = s.post(f"{API}/upload?kind=garment",
                   files={"file": ("test.jpg", f, "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["path"]


# ---------- /subscription/status ----------
class TestSubscriptionStatusForIncludedNote:
    def test_single_user_has_honeymoon_or_single(self, s):
        r = s.get(f"{API}/subscription/status")
        assert r.status_code == 200, r.text
        d = r.json()
        # IncludedNote visibility rule: honeymoon_active OR plan in {SINGLE,FAMILY}
        assert d["plan"] in ("SINGLE", "FAMILY") or d.get("honeymoon_active") is True
        assert "is_blocked" in d


# ---------- PUT /wardrobe/garments/{id}/image ----------
class TestWardrobeSetImage:
    def test_404_unknown_garment(self, s, garment_path):
        r = s.put(f"{API}/wardrobe/garments/nope-{uuid.uuid4().hex[:8]}/image",
                  json={"image_path": garment_path})
        assert r.status_code == 404

    def test_403_foreign_path(self, s):
        # First create a real placeholder garment via from-url (invalid short URL -> amazon placeholder)
        r = s.post(f"{API}/wardrobe/garments/from-url",
                   json={"url": f"https://a.co/d/invalid{uuid.uuid4().hex[:6]}"})
        if r.status_code != 200:
            pytest.skip(f"could not create placeholder: {r.status_code} {r.text}")
        g = r.json()
        gid = g["id"]
        try:
            foreign = "atelier/garment/other-user-xyz/abc.jpg"
            r2 = s.put(f"{API}/wardrobe/garments/{gid}/image",
                       json={"image_path": foreign})
            assert r2.status_code == 403
        finally:
            s.delete(f"{API}/wardrobe/garments/{gid}")

    def test_success_updates_image_and_clears_placeholder(self, s, garment_path):
        # Create placeholder garment via from-url (amazon short)
        r = s.post(f"{API}/wardrobe/garments/from-url",
                   json={"url": f"https://a.co/d/placeholder{uuid.uuid4().hex[:6]}"})
        if r.status_code != 200:
            pytest.skip(f"could not create placeholder: {r.status_code} {r.text}")
        g = r.json()
        gid = g["id"]
        try:
            # Place image
            r2 = s.put(f"{API}/wardrobe/garments/{gid}/image",
                       json={"image_path": garment_path})
            assert r2.status_code == 200, r2.text
            g2 = r2.json()
            assert g2["image_path"] == garment_path
            assert g2.get("is_placeholder") is False
            # Verify persisted via GET list
            lst = s.get(f"{API}/wardrobe/garments").json()
            found = next((x for x in lst if x["id"] == gid), None)
            assert found is not None
            assert found["image_path"] == garment_path
            assert found.get("is_placeholder") is False
        finally:
            s.delete(f"{API}/wardrobe/garments/{gid}")

    def test_requires_auth(self, garment_path):
        r = requests.put(f"{API}/wardrobe/garments/anything/image",
                         json={"image_path": garment_path})
        assert r.status_code in (401, 403)


# ---------- from-screenshot persists brand & source_url for grid-total ----------
class TestFromScreenshotFieldsForGridTotal:
    def test_persists_brand_and_source_url(self, s, garment_path):
        url = f"https://httpstat.us/404?x={uuid.uuid4().hex}"
        r = s.post(f"{API}/wardrobe/garments/from-screenshot",
                   json={"image_path": garment_path, "slot": "jacket", "url": url})
        assert r.status_code == 200, r.text
        g = r.json()
        try:
            assert g["source_url"] == url
            assert g.get("brand")  # non-empty
            # price may be None when meta extraction fails — frontend shows "prezzo non disponibile"
            assert "price" in g
            assert "currency" in g
        finally:
            s.delete(f"{API}/wardrobe/garments/{g['id']}")
