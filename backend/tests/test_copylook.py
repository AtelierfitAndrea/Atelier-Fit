# Copia Look da Modello: extract / apply / save-garment endpoints
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = os.environ.get("OWNER_TEST_TOKEN")
MODEL = "/tmp/model.jpg"
RUN_APPLY = os.environ.get("RUN_APPLY") == "1"
state = {}


def _final_status(s, r):
    # apply is an async render job: validation errors surface when polling /render-jobs/{id}
    import time
    if r.status_code != 200 or "job_id" not in r.json():
        return r.status_code
    for _ in range(20):
        time.sleep(1.5)
        j = s.get(f"{BASE_URL}/api/render-jobs/{r.json()['job_id']}", timeout=30)
        if j.status_code != 200 or j.json()["status"] != "running":
            return j.status_code
    return 200


@pytest.fixture(scope="module")
def s():
    if not TOKEN:
        pytest.skip("OWNER_TEST_TOKEN missing")
    ses = requests.Session()
    ses.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return ses


def test_upload_model(s):
    with open(MODEL, "rb") as f:
        r = s.post(f"{BASE_URL}/api/upload?kind=garment", files={"file": ("model.jpg", f, "image/jpeg")}, timeout=60)
    assert r.status_code == 200, r.text
    state["model_path"] = r.json()["path"]
    assert "user_389c87aaadc6" in state["model_path"]


def test_extract(s):
    r = s.post(f"{BASE_URL}/api/copylook/extract", json={"model_path": state["model_path"]}, timeout=120)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) >= 1
    for it in items:
        assert it["category"] in ("top", "bottom", "dress", "outerwear", "shoes")
        assert isinstance(it["name"], str) and it["name"]
        assert it["recommended_size"]
    state["items"] = items
    with_img = [i for i in items if i["image_path"]]
    assert with_img, "no cropped images"
    img = s.get(f"{BASE_URL}/api/files/{with_img[0]['image_path']}", timeout=30)
    assert img.status_code == 200 and len(img.content) > 1000
    print("ITEMS:", [(i["name"], i["category"], i["recommended_size"]) for i in items])


def test_extract_other_user_path_403(s):
    r = s.post(f"{BASE_URL}/api/copylook/extract", json={"model_path": "vfit/garment/other_user_x/abc.jpg"}, timeout=30)
    assert r.status_code == 403


def test_extract_unauth_401():
    r = requests.post(f"{BASE_URL}/api/copylook/extract", json={"model_path": "x"}, timeout=30)
    assert r.status_code == 401


def test_apply_empty_items_400(s):
    r = s.post(f"{BASE_URL}/api/copylook/apply", json={"model_path": state["model_path"], "items": []}, timeout=30)
    assert _final_status(s, r) == 400


def test_apply_invalid_category_400(s):
    r = s.post(f"{BASE_URL}/api/copylook/apply", json={"model_path": state["model_path"], "items": [{"name": "x", "category": "hat"}]}, timeout=30)
    assert _final_status(s, r) == 400


def test_apply_other_user_403(s):
    r = s.post(f"{BASE_URL}/api/copylook/apply", json={"model_path": "vfit/garment/other_user_x/a.jpg", "items": [{"name": "x", "category": "top"}]}, timeout=30)
    assert _final_status(s, r) == 403


def test_save_garment(s):
    it = next(i for i in state["items"] if i["image_path"])
    r = s.post(f"{BASE_URL}/api/copylook/save-garment", json={"image_path": it["image_path"], "name": "TEST_" + it["name"], "category": it["category"]}, timeout=60)
    assert r.status_code == 200, r.text
    g = r.json()
    gid = g.get("id")
    assert gid
    state["garment_id"] = gid
    lst = s.get(f"{BASE_URL}/api/wardrobe/garments", timeout=30).json()
    found = [x for x in lst if x.get("id") == gid]
    assert found, "saved garment not in wardrobe"
    print("SAVED:", {k: found[0].get(k) for k in ("product_name", "brand", "category", "image_path")})


def test_save_garment_other_user_403(s):
    r = s.post(f"{BASE_URL}/api/copylook/save-garment", json={"image_path": "vfit/garment/other_user_x/a.jpg", "name": "x", "category": "top"}, timeout=30)
    assert r.status_code == 403


@pytest.mark.skipif(not RUN_APPLY, reason="costly")
def test_apply_real(s):
    chosen = [{"name": i["name"], "category": i["category"]} for i in state["items"][:2]]
    before = s.get(f"{BASE_URL}/api/subscription/status", timeout=30).json()
    r = s.post(f"{BASE_URL}/api/copylook/apply", json={"model_path": state["model_path"], "items": chosen}, timeout=180)
    assert r.status_code == 200, r.text
    import time
    for _ in range(60):
        time.sleep(4)
        j = s.get(f"{BASE_URL}/api/render-jobs/{r.json()['job_id']}", timeout=30)
        if j.status_code != 200 or j.json()["status"] != "running":
            break
    assert j.status_code == 200 and j.json()["status"] == "done", j.text
    d = j.json()["result"]
    assert d["garment_category"] == "look"
    assert len(d["copied_items"]) == len(chosen)
    assert "·" in d["recommended_size"] or len(chosen) == 1
    g = s.get(f"{BASE_URL}/api/tryons/{d['id']}", timeout=30)
    assert g.status_code == 200 and g.json()["id"] == d["id"]
    after = s.get(f"{BASE_URL}/api/subscription/status", timeout=30).json()
    print("TRYON:", d["id"], d["recommended_size"], "BEFORE:", before, "AFTER:", after)
    state["tryon_id"] = d["id"]
