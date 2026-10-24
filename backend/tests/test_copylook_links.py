# Copia Look: "Salva link outfit modello" -> POST /api/wardrobe/garments/from-screenshot incl. slot dress
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = os.environ.get("OWNER_TEST_TOKEN", "pending_test_tok")
IMG = "/app/tests_assets/garment1.jpg"
LINK = "https://www2.hm.com/it_it/productpage.1234567001.html"
state = {"created": []}


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    ses.headers.update({"Authorization": f"Bearer {TOKEN}"})
    if ses.get(f"{BASE_URL}/api/auth/me", timeout=30).status_code != 200:
        pytest.skip("owner session invalid")
    yield ses
    for gid in state["created"]:
        ses.delete(f"{BASE_URL}/api/wardrobe/garments/{gid}", timeout=30)


def test_upload(s):
    with open(IMG, "rb") as f:
        r = s.post(f"{BASE_URL}/api/upload?kind=garment", files={"file": ("g.jpg", f, "image/jpeg")}, timeout=60)
    assert r.status_code == 200, r.text
    state["path"] = r.json()["path"]


@pytest.mark.parametrize("slot,cat", [("dress", "dress"), ("jacket", "outerwear"), ("top", "top"), ("bottom", "bottom"), ("shoes", "shoes")])
def test_save_slot(s, slot, cat):
    r = s.post(f"{BASE_URL}/api/wardrobe/garments/from-screenshot",
               json={"image_path": state["path"], "url": LINK, "slot": slot}, timeout=90)
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["category"] == cat
    assert g["source_url"] == LINK
    assert g.get("brand")
    assert "_id" not in g
    state["created"].append(g["id"])
    lst = s.get(f"{BASE_URL}/api/wardrobe/garments", timeout=30).json()
    f = [x for x in lst if x["id"] == g["id"]]
    assert f and f[0]["category"] == cat and f[0]["source_url"] == LINK
    print(slot, {k: g.get(k) for k in ("brand", "price", "currency", "product_name", "category")})


def test_invalid_slot_400(s):
    r = s.post(f"{BASE_URL}/api/wardrobe/garments/from-screenshot",
               json={"image_path": state["path"], "url": LINK, "slot": "hat"}, timeout=30)
    assert r.status_code == 400


def test_invalid_url_400(s):
    r = s.post(f"{BASE_URL}/api/wardrobe/garments/from-screenshot",
               json={"image_path": state["path"], "url": "ftp://x", "slot": "dress"}, timeout=30)
    assert r.status_code == 400


def test_other_user_path_403(s):
    r = s.post(f"{BASE_URL}/api/wardrobe/garments/from-screenshot",
               json={"image_path": "vfit/garment/other_user_x/a.jpg", "url": LINK, "slot": "dress"}, timeout=30)
    assert r.status_code == 403


def test_unauth_401():
    r = requests.post(f"{BASE_URL}/api/wardrobe/garments/from-screenshot",
                      json={"image_path": "x", "url": LINK, "slot": "dress"}, timeout=30)
    assert r.status_code == 401
