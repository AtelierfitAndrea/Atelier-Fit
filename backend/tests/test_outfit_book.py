# Outfit Book (AI-only outfits) + Le mie Pose regression tests (iteration 56)
import os
import uuid
import subprocess
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
OWNER = "user_389c87aaadc6"
TOKEN = "pending_test_tok"
OTHER_UID = "TEST_other_" + uuid.uuid4().hex[:6]
OTHER_TRYON = "TEST_tryon_" + uuid.uuid4().hex[:6]


def mongo(js):
    return subprocess.run(["mongosh", "--quiet", "test_database", "--eval", js], capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope="module")
def s():
    x = requests.Session()
    x.headers["Authorization"] = f"Bearer {TOKEN}"
    if x.get(f"{BASE_URL}/api/auth/me").status_code != 200:
        pytest.skip("owner session invalid")
    mongo(f'db.tryons.insertOne({{id:"{OTHER_TRYON}",user_id:"{OTHER_UID}",result_path:"vfit/tryon/{OTHER_UID}/x.jpg",created_at:new Date().toISOString()}})')
    yield x
    mongo(f'db.tryons.deleteMany({{id:"{OTHER_TRYON}"}}); db.book_outfits_my_atelier.deleteMany({{user_id:"{OWNER}"}})')


def ids(name, col):
    out = mongo(f'print(JSON.stringify(db.{col}.find({{user_id:"{OWNER}", result_path:{{$exists:true}}}},{{_id:0,id:1,result_path:1}}).sort({{created_at:-1}}).limit(2).toArray()))')
    return __import__("json").loads(out)


# Auth required
@pytest.mark.parametrize("method,path", [("get", "/api/outfit-book"), ("post", "/api/outfit-book"), ("delete", "/api/outfit-book/x")])
def test_auth_required(method, path):
    r = getattr(requests, method)(f"{BASE_URL}{path}", json={"kind": "tryon", "ref_id": "x"})
    assert r.status_code == 401


def test_list_shape(s):
    r = s.get(f"{BASE_URL}/api/outfit-book")
    assert r.status_code == 200 and isinstance(r.json()["outfits"], list)


def test_add_tryon_dedupe_delete(s):
    t = ids("t", "tryons")[0]
    r = s.post(f"{BASE_URL}/api/outfit-book", json={"kind": "tryon", "ref_id": t["id"]})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["kind"] == "tryon" and e["ref_id"] == t["id"] and e["result_path"] == t["result_path"] and "_id" not in e
    r2 = s.post(f"{BASE_URL}/api/outfit-book", json={"kind": "tryon", "ref_id": t["id"]})
    assert r2.json()["id"] == e["id"]
    rows = s.get(f"{BASE_URL}/api/outfit-book").json()["outfits"]
    assert sum(1 for x in rows if x["result_path"] == t["result_path"]) == 1
    # image of book entry is viewable
    assert s.get(f"{BASE_URL}/api/files/{e['result_path']}?thumb=640").status_code == 200
    d = s.delete(f"{BASE_URL}/api/outfit-book/{e['id']}")
    assert d.status_code == 200 and d.json()["deleted"] is True
    assert all(x["id"] != e["id"] for x in s.get(f"{BASE_URL}/api/outfit-book").json()["outfits"])
    assert s.delete(f"{BASE_URL}/api/outfit-book/{e['id']}").status_code == 404
    # source try-on remains in history
    assert s.get(f"{BASE_URL}/api/tryons/{t['id']}").status_code == 200


def test_add_outfit(s):
    o = ids("o", "outfits")[0]
    r = s.post(f"{BASE_URL}/api/outfit-book", json={"kind": "outfit", "ref_id": o["id"]})
    assert r.status_code == 200 and r.json()["result_path"] == o["result_path"]
    s.delete(f"{BASE_URL}/api/outfit-book/{r.json()['id']}")


def test_wrong_kind_for_id_404(s):
    t = ids("t", "tryons")[0]
    assert s.post(f"{BASE_URL}/api/outfit-book", json={"kind": "outfit", "ref_id": t["id"]}).status_code == 404


def test_reject_other_user_and_missing(s):
    assert s.post(f"{BASE_URL}/api/outfit-book", json={"kind": "tryon", "ref_id": OTHER_TRYON}).status_code == 404
    assert s.post(f"{BASE_URL}/api/outfit-book", json={"kind": "tryon", "ref_id": "nope"}).status_code == 404


def test_invalid_kind_and_gallery_path(s):
    assert s.post(f"{BASE_URL}/api/outfit-book", json={"kind": "gallery", "ref_id": "x"}).status_code == 422
    assert s.post(f"{BASE_URL}/api/outfit-book", json={"kind": "tryon", "path": "vfit/person/x.jpg"}).status_code == 422


def test_pose_book_list(s):
    r = s.get(f"{BASE_URL}/api/book")
    assert r.status_code == 200 and isinstance(r.json()["photos"], list)
