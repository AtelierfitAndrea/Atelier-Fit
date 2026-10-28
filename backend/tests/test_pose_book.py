# Foto in Posa / Il Mio Book: /api/book CRUD, auth, ownership, /files 404 after delete, quota untouched
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
OWNER = {"Authorization": "Bearer pending_test_tok"}
OTHER = {"Authorization": "Bearer test_book_other_tok"}
POSE = "/tmp/pose.jpg"


def _upload(headers, kind="person", path=POSE, name="pose.jpg", ct="image/jpeg"):
    with open(path, "rb") as f:
        r = requests.post(f"{BASE_URL}/api/upload?kind={kind}", headers=headers, files={"file": (name, f, ct)})
    assert r.status_code == 200, r.text
    return r.json()["path"]


def _status(headers):
    return requests.get(f"{BASE_URL}/api/subscription/status", headers=headers).json()


@pytest.fixture(scope="module")
def created():
    ids = []
    yield ids
    for h, i in ids:
        requests.delete(f"{BASE_URL}/api/book/{i}", headers=h)


# Auth required
@pytest.mark.parametrize("method,url", [("get", "/api/book"), ("post", "/api/book"), ("delete", "/api/book/x")])
def test_book_requires_auth(method, url):
    r = getattr(requests, method)(f"{BASE_URL}{url}", json={"path": "a/b/c/d"} if method == "post" else None)
    assert r.status_code == 401


# Create -> list -> idempotent -> delete -> 404 file
def test_book_crud_and_file_404(created):
    before = _status(OWNER)
    path = _upload(OWNER)
    r = requests.post(f"{BASE_URL}/api/book", headers=OWNER, json={"path": path})
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["path"] == path and isinstance(doc["id"], str) and "_id" not in doc
    created.append((OWNER, doc["id"]))
    # idempotent
    r2 = requests.post(f"{BASE_URL}/api/book", headers=OWNER, json={"path": path})
    assert r2.json()["id"] == doc["id"]
    lst = requests.get(f"{BASE_URL}/api/book", headers=OWNER).json()["photos"]
    assert [p["id"] for p in lst].count(doc["id"]) == 1
    assert requests.get(f"{BASE_URL}/api/files/{path}", headers=OWNER).status_code == 200
    # other user can't delete -> 404, can't see file
    assert requests.delete(f"{BASE_URL}/api/book/{doc['id']}", headers=OTHER).status_code == 404
    assert requests.get(f"{BASE_URL}/api/files/{path}", headers=OTHER).status_code in (403, 404)
    d = requests.delete(f"{BASE_URL}/api/book/{doc['id']}", headers=OWNER)
    assert d.status_code == 200 and d.json()["deleted"] is True
    assert doc["id"] not in [p["id"] for p in requests.get(f"{BASE_URL}/api/book", headers=OWNER).json()["photos"]]
    assert requests.get(f"{BASE_URL}/api/files/{path}", headers=OWNER).status_code == 404
    assert requests.delete(f"{BASE_URL}/api/book/{doc['id']}", headers=OWNER).status_code == 404
    after = _status(OWNER)
    assert after["tryons_used_today"] == before["tryons_used_today"]
    assert after["tryons_used_this_month"] == before["tryons_used_this_month"]


# Ownership: other user's path rejected
def test_book_rejects_foreign_path(created):
    path = _upload(OWNER)
    r = requests.post(f"{BASE_URL}/api/book", headers=OTHER, json={"path": path})
    assert r.status_code == 403
    assert requests.post(f"{BASE_URL}/api/book", headers=OWNER, json={"path": "garbage"}).status_code == 403
    assert requests.post(f"{BASE_URL}/api/book", headers=OWNER, json={}).status_code == 422


# Isolation: other user's list doesn't contain owner's entries
def test_book_list_isolated(created):
    path = _upload(OWNER)
    doc = requests.post(f"{BASE_URL}/api/book", headers=OWNER, json={"path": path}).json()
    created.append((OWNER, doc["id"]))
    other = requests.get(f"{BASE_URL}/api/book", headers=OTHER).json()["photos"]
    assert doc["id"] not in [p["id"] for p in other]


# preserve_pose accepted by tryon + grid models (validation only, no render)
def test_preserve_pose_field_validation():
    r = requests.post(f"{BASE_URL}/api/tryon/generate", headers=OWNER,
                      json={"person_path": "x", "garment_path": "y", "preserve_pose": "notabool"})
    assert r.status_code == 422
    r = requests.post(f"{BASE_URL}/api/outfit/generate-from-uploads", headers=OWNER,
                      json={"items": [], "preserve_pose": "notabool"})
    assert r.status_code == 422
