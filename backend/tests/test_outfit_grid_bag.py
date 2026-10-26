"""Outfit grid BORSA (bag) slot tests: validation, bag-only AI generation, free-tier quota consumption.

Uses owner session pending_test_tok (prelaunch gate). Honeymoon is temporarily expired for the quota test and restored.
"""
import os
import time
import subprocess
import pytest
import requests


def _env_url():
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env_url()).rstrip("/")
API = f"{BASE_URL}/api"
TOKEN = "pending_test_tok"
OWNER_ID = "user_389c87aaadc6"
BAG_IMG = os.environ.get("BAG_IMG", "/tmp/bag_61f184.jpg")
PERSON_IMG = "/app/memory/test_fullbody.jpg"
RESULTS = {}


def mongo(js):
    return subprocess.run(["mongosh", "--quiet", "--eval", f"use('test_database'); {js}"], capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def s():
    x = requests.Session()
    x.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return x


def upload(s, kind, path):
    with open(path, "rb") as f:
        r = s.post(f"{API}/upload?kind={kind}", files={"file": ("x.jpg", f, "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["path"]


def run_job(s, payload, timeout=300):
    r = s.post(f"{API}/outfit/generate-from-uploads", json=payload)
    assert r.status_code == 200, r.text
    job = r.json()["job_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        g = s.get(f"{API}/render-jobs/{job}")
        if g.status_code != 200 or g.json()["status"] != "running":
            return g
        time.sleep(4)
    pytest.fail("render job timeout")


@pytest.fixture(scope="module")
def paths(s):
    return {"bag": upload(s, "garment", BAG_IMG), "person": upload(s, "person", PERSON_IMG)}


# Validation (no AI)
class TestValidation:
    def test_unknown_slot_400(self, s, paths):
        g = run_job(s, {"person_path": paths["person"], "items": [{"slot": "hat", "image_path": paths["bag"]}]})
        assert g.status_code == 400 and "da 1 a 5" in g.json()["detail"]

    def test_zero_items_400(self, s, paths):
        g = run_job(s, {"person_path": paths["person"], "items": []})
        assert g.status_code == 400

    def test_foreign_path_403(self, s, paths):
        g = run_job(s, {"person_path": paths["person"], "items": [{"slot": "bag", "image_path": "vfit/garment/someone_else/x.jpg"}]})
        assert g.status_code == 403

    def test_bag_rule_in_prompt(self):
        import sys
        sys.path.insert(0, "/app/backend")
        import server
        assert server._GRID_SLOTS["bag"] == ("bag", "Borsa")
        assert server._GRID_ORDER[-1] == "bag"
        assert "BAG — MANDATORY" in server._bag_rule([{"category": "bag"}])
        assert server._bag_rule([{"category": "top"}]) == ""

    def test_from_screenshot_accepts_bag_slot(self, s, paths):
        # bad URL -> 400 'URL non valido' proves the slot passed validation
        r = s.post(f"{API}/wardrobe/garments/from-screenshot", json={"image_path": paths["bag"], "url": "notaurl", "slot": "bag"})
        assert r.status_code == 400 and r.json()["detail"] == "URL non valido"


# Bag-only generation + FREE quota consumption (honeymoon expired temporarily)
class TestBagOnlyGeneration:
    def test_bag_only_consumes_free_quota(self, s, paths):
        orig = mongo(f"print(db.users.findOne({{user_id:'{OWNER_ID}'}}).free_month_end)").strip()
        mongo(f"db.users.updateOne({{user_id:'{OWNER_ID}'}},{{$set:{{free_month_end:'2026-10-01T00:00:00+00:00'}},$unset:{{daily_tryon_count:''}}}})")
        try:
            st0 = s.get(f"{API}/subscription/status").json()
            assert st0["honeymoon_active"] is False and st0["tryons_remaining"] == 3
            g = run_job(s, {"person_path": paths["person"], "items": [{"slot": "bag", "image_path": paths["bag"]}]})
            assert g.status_code == 200, g.text
            res = g.json()["result"]
            assert res["source"] == "grid" and res["result_path"]
            assert [i["slot"] for i in res["items"]] == ["bag"] and res["items"][0]["category"] == "bag"
            RESULTS["bag_only"] = res["result_path"]
            img = s.get(f"{API}/files/{res['result_path']}")
            assert img.status_code == 200 and len(img.content) > 10000
            open("/tmp/result_bag_only.jpg", "wb").write(img.content)
            st1 = s.get(f"{API}/subscription/status").json()
            assert st1["tryons_used_today"] == 1 and st1["tryons_remaining"] == 2, st1
            # persisted in outfits list
            lst = s.get(f"{API}/outfits").json()
            lst = lst if isinstance(lst, list) else lst.get("outfits", lst.get("items", []))
            assert any(o.get("id") == res["id"] for o in lst)
        finally:
            mongo(f"db.users.updateOne({{user_id:'{OWNER_ID}'}},{{$set:{{free_month_end:'{orig}'}},$unset:{{daily_tryon_count:''}}}})")
