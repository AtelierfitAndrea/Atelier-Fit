"""Suit tuck rule + AI garment classification (Studio no longer sends category).

Uses owner session pending_test_tok. Generations run sequentially (~40 s each).
"""
import os
import sys
import time
import subprocess
import pytest
import requests

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")
import server  # noqa: E402


def _env_url():
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env_url()).rstrip("/")
API = f"{BASE_URL}/api"
TOKEN = "pending_test_tok"
SUIT_IMG = "/tmp/photo-1594938298603-c8148c4dae35.jpg"
SHIRT_IMG = "/tmp/photo-1596755094514-f87e34085b2c.jpg"
BAG_IMG = "/tmp/photo-1584917865442-de89df76afd3.jpg"
STATE = {}
import asyncio
LOOP = asyncio.new_event_loop()


def mongo(js):
    return subprocess.run(["mongosh", "--quiet", "--eval", f"use('test_database'); {js}"], capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope="module")
def s():
    x = requests.Session()
    x.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return x


def upload(s, path):
    with open(path, "rb") as f:
        r = s.post(f"{API}/upload?kind=garment", files={"file": ("x.jpg", f, "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()["path"]


def poll(s, job, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        g = s.get(f"{API}/render-jobs/{job}")
        if g.status_code != 200 or g.json()["status"] != "running":
            return g
        time.sleep(4)
    pytest.fail("render job timeout")


# _tuck_rule unit checks
class TestTuckRuleUnit:
    def test_suit_tucked(self):
        r = server._tuck_rule([{"category": "suit"}])
        assert "SUIT" in r and "TUCKED INSIDE" in r and "tie" in r.lower()

    def test_top_untucked(self):
        assert "UNTUCKED" in server._tuck_rule([{"category": "top"}])

    def test_top_with_outerwear_empty(self):
        assert server._tuck_rule([{"category": "top"}, {"category": "outerwear"}]) == ""

    def test_suit_with_top_still_suit(self):
        assert "SUIT" in server._tuck_rule([{"category": "top"}, {"category": "suit"}])

    def test_is_long_suit(self):
        import head_lock
        assert head_lock.is_long("suit") and head_lock.is_long("dress") and not head_lock.is_long("top")


# _classify_garment via real Gemini + db cache
class TestClassify:
    @pytest.mark.parametrize("img,expected", [(SUIT_IMG, "suit"), (SHIRT_IMG, "top"), (BAG_IMG, "bag")])
    def test_classify(self, s, img, expected):
        p = upload(s, img)
        STATE[expected] = p
        # run in a fresh loop (motor client bound to loop at first use)
        cat = LOOP.run_until_complete(server._classify_garment(p, None))
        assert cat == expected, f"{img} -> {cat}"
        cached = mongo(f"JSON.stringify(db.garment_class.findOne({{path:'{p}'}},{{_id:0,category:1}}))")
        assert expected in cached


# End-to-end single try-on (no category) — suit
class TestSuitTryon:
    def test_generate_suit_without_category(self, s):
        av = s.get(f"{API}/profile/avatar").json()["path"]
        gp = upload(s, SUIT_IMG)
        r = s.post(f"{API}/tryon/generate", json={"person_path": av, "garment_path": gp, "garment_category": None,
                                                  "garment_name": None, "chosen_size": None})
        assert r.status_code == 200, r.text
        g = poll(s, r.json()["job_id"])
        assert g.status_code == 200, g.text
        res = g.json()["result"]
        tid = res["id"]
        STATE["suit_tryon"] = tid
        doc = mongo(f"JSON.stringify(db.tryons.findOne({{id:'{tid}'}},{{_id:0,garment_category:1,result_path:1}}))")
        print("TRYON DOC", doc)
        assert '"garment_category":"suit"' in doc
        t = s.get(f"{API}/tryons/{tid}")
        assert t.status_code == 200
        rp = t.json()["result_path"]
        img = s.get(f"{API}/files/{rp}")
        assert img.status_code == 200
        open("/tmp/suit_result.jpg", "wb").write(img.content)
