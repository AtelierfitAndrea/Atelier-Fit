# Copia Look: ONE link per model look (POST /api/wardrobe/looks/from-link), URL tracking cleanup, manual price fallback
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = os.environ.get("OWNER_TEST_TOKEN", "pending_test_tok")
MODEL = "/app/tests_assets/model_look.jpg"
G1 = "/app/tests_assets/garment1.jpg"
G2 = "/app/tests_assets/garment2.jpg"
CLEAN = "https://www.zalando.it/opposuits-shiny-snake-set-completo-gold-coloured-op222a042-f11.html?ssku=OP222A042-F110058000&lang=it"
AD = (CLEAN + "&amp;otid=default&amp;wmc=SEM390_NB_GO._8690582122_680648580_34341989185.&amp;opc=2211&amp;gclsrc=aw.ds"
      "&amp;gad_source=1&amp;gad_campaignid=680648580&amp;gclid=Cj0KCQjwTEST")
TRACK = ("gclid", "gad_", "wmc", "opc", "otid", "gclsrc", "&amp;")
state = {"looks": [], "garments": []}


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    ses.headers.update({"Authorization": f"Bearer {TOKEN}"})
    if ses.get(f"{BASE_URL}/api/auth/me", timeout=30).status_code != 200:
        pytest.skip("owner session invalid")
    yield ses
    for lid in state["looks"]:
        ses.delete(f"{BASE_URL}/api/wardrobe/looks/{lid}", timeout=30)
    for gid in state["garments"]:
        ses.delete(f"{BASE_URL}/api/wardrobe/garments/{gid}", timeout=30)


def _up(s, path, kind):
    with open(path, "rb") as f:
        r = s.post(f"{BASE_URL}/api/upload?kind={kind}", files={"file": ("x.jpg", f, "image/jpeg")}, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()["path"]


def test_uploads(s):
    state["model"] = _up(s, MODEL, "garment")
    state["g1"] = _up(s, G1, "garment")
    state["g2"] = _up(s, G2, "garment")


# Zalando ad link -> clean URL, brand OppoSuits, price 89.95, garments inherit link
def test_look_from_zalando_ad_link(s):
    r = s.post(f"{BASE_URL}/api/wardrobe/looks/from-link", json={
        "model_path": state["model"], "url": AD,
        "items": [{"image_path": state["g1"], "name": "TEST_Giacca", "category": "outerwear"},
                  {"image_path": state["g2"], "name": "TEST_Pantalone", "category": "bottom"}]}, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    print({k: d.get(k) for k in ("brand", "title", "price", "currency", "url", "needs_price")})
    state["looks"].append(d["id"])
    state["garments"] += [g["id"] for g in d["garments"]]
    state["zal_look"] = d["id"]
    assert "_id" not in d
    assert d["url"] == CLEAN
    assert d["brand"] == "OppoSuits"
    assert d["price"] == 89.95
    assert d["needs_price"] is False
    assert len(d["garments"]) == 2
    for g in d["garments"]:
        assert g["source_url"] == CLEAN
    cats = sorted(g["category"] for g in d["garments"])
    assert cats == ["bottom", "outerwear"]


def test_looks_list_has_zalando_look(s):
    lst = s.get(f"{BASE_URL}/api/wardrobe/looks", timeout=30).json()
    lk = next(x for x in lst if x["id"] == state["zal_look"])
    assert lk["total"] == 89.95 and lk["url"] == CLEAN and lk["brand"] == "OppoSuits"
    assert all(g["source_url"] == CLEAN for g in lk["garments"])


def test_resave_same_model_upserts(s):
    r = s.post(f"{BASE_URL}/api/wardrobe/looks/from-link", json={
        "model_path": state["model"], "url": "https://example.com/",
        "items": [{"image_path": state["g1"], "name": "TEST_Re", "category": "top"}]}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    state["garments"] += [g["id"] for g in d["garments"]]
    assert d["id"] == state["zal_look"]  # same model_path -> same look
    assert d["needs_price"] is True and d["price"] is None  # stale price must not persist
    lst = s.get(f"{BASE_URL}/api/wardrobe/looks", timeout=30).json()
    assert len([x for x in lst if x["model_path"] == state["model"]]) == 1


# Manual price fallback
def test_manual_price_flow(s):
    mp = _up(s, MODEL, "garment")
    r = s.post(f"{BASE_URL}/api/wardrobe/looks/from-link", json={
        "model_path": mp, "url": "https://example.com/",
        "items": [{"image_path": state["g1"], "name": "TEST_NoPrice", "category": "top"}]}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    state["looks"].append(d["id"])
    state["garments"] += [g["id"] for g in d["garments"]]
    state["np_look"] = d["id"]
    assert d["needs_price"] is True
    r0 = s.put(f"{BASE_URL}/api/wardrobe/looks/{d['id']}/price", json={"price": 0}, timeout=30)
    assert r0.status_code == 422
    rn = s.put(f"{BASE_URL}/api/wardrobe/looks/{d['id']}/price", json={"price": -5}, timeout=30)
    assert rn.status_code == 422
    rp = s.put(f"{BASE_URL}/api/wardrobe/looks/{d['id']}/price", json={"price": 49.9}, timeout=30)
    assert rp.status_code == 200 and rp.json()["price"] == 49.9
    lk = next(x for x in s.get(f"{BASE_URL}/api/wardrobe/looks", timeout=30).json() if x["id"] == d["id"])
    assert lk["total"] == 49.9


def test_price_other_user_404(s):
    mc = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
    lid = "TEST_" + uuid.uuid4().hex
    mc.model_looks.insert_one({"id": lid, "user_id": "someone_else", "model_path": "x", "garment_ids": [], "created_at": "2026"})
    try:
        r = s.put(f"{BASE_URL}/api/wardrobe/looks/{lid}/price", json={"price": 10}, timeout=30)
        assert r.status_code == 404
        r = s.put(f"{BASE_URL}/api/wardrobe/looks/nonexistent-{uuid.uuid4().hex}/price", json={"price": 10}, timeout=30)
        assert r.status_code == 404
        assert mc.model_looks.find_one({"id": lid}).get("price") is None
    finally:
        mc.model_looks.delete_one({"id": lid})


def test_look_validation(s):
    base = {"model_path": state["model"], "items": [{"image_path": state["g1"]}]}
    assert s.post(f"{BASE_URL}/api/wardrobe/looks/from-link", json={**base, "url": "ftp://x"}, timeout=30).status_code == 400
    assert s.post(f"{BASE_URL}/api/wardrobe/looks/from-link", json={**base, "url": CLEAN, "items": []}, timeout=30).status_code == 400
    r = s.post(f"{BASE_URL}/api/wardrobe/looks/from-link", json={**base, "url": CLEAN, "model_path": "uploads/other_user/x.jpg"}, timeout=30)
    assert r.status_code == 403


def test_garment_from_url_cleans_tracking(s):
    r = s.post(f"{BASE_URL}/api/wardrobe/garments/from-url", json={"url": AD}, timeout=150)
    print(r.status_code, r.text[:300])
    assert r.status_code == 200, r.text
    g = r.json()
    if g.get("id"):
        state["garments"].append(g["id"])
    su = g.get("source_url") or ""
    assert su == CLEAN, su
    assert not any(t in su for t in TRACK)


def test_googleadservices_unwrapped(s):
    from urllib.parse import quote
    wrapped = "https://www.googleadservices.com/pagead/aclk?sa=L&ai=XYZ&adurl=" + quote(CLEAN + "&gclid=Cj0KCQjwTEST", safe="")
    mp = _up(s, MODEL, "garment")
    r = s.post(f"{BASE_URL}/api/wardrobe/looks/from-link", json={
        "model_path": mp, "url": wrapped, "items": [{"image_path": state["g2"], "name": "TEST_Wrap", "category": "top"}]}, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    state["looks"].append(d["id"])
    state["garments"] += [g["id"] for g in d["garments"]]
    assert d["url"] == CLEAN


def test_product_analyze_cleans_url(s):
    r = s.post(f"{BASE_URL}/api/product/analyze", json={"url": AD}, timeout=150)
    print(r.status_code, r.text[:400])
    assert r.status_code == 200, r.text
    d = r.json()
    blob = str(d)
    assert "gclid" not in blob and "Cj0KCQ" not in blob
