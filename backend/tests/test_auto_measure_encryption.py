# Auto-measure (photo+height+weight) + Fernet encryption of personal data + B2B privacy
import json
import os
import subprocess

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0]).rstrip("/")
TOKEN = "fam_test_1791784817"
UID = "fam-owner-1791784817"
FEATS = {"shoulder_r": 0.24, "chest_r": 0.17, "waist_r": 0.14, "hips_r": 0.20, "inseam_r": 0.45}
PHOTO = "/app/memory/test_fullbody.jpg"


def mongo(js):
    out = subprocess.run(["mongosh", "--quiet", "test_database", "--eval", js], capture_output=True, text=True, timeout=30)
    return out.stdout.strip()


@pytest.fixture(scope="module")
def s():
    x = requests.Session()
    x.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return x


def _post(s, weight=60, height=165, gender="female", feats=None):
    params = {"height_cm": height, "gender": gender, "features": json.dumps(feats or FEATS)}
    if weight is not None:
        params["weight_kg"] = weight
    else:
        params["forget_weight"] = "true"  # omitted weight now falls back to the saved one
    with open(PHOTO, "rb") as f:
        return s.post(f"{BASE_URL}/api/profile/auto-measure", params=params, files={"photo": ("p.jpg", f, "image/jpeg")})


# --- auto-measure endpoint
def test_auto_measure_with_weight(s):
    r = _post(s, weight=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["precision"] == 98
    assert [b["brand"] for b in d["brand_sizes"]] == ["Zara", "H&M", "Mango", "Nike", "Adidas", "Uniqlo"]
    m = d["measurements"]
    for k in ("chest_cm", "waist_cm", "hips_cm", "shoulder_cm", "inseam_cm"):
        assert isinstance(m[k], (int, float)) and m[k] > 0
    assert m["height_cm"] == 165 and m["weight_kg"] == 60 and m["gender"] == "female"
    assert m["method"] == "auto_photo"


def test_auto_measure_without_weight(s):
    r = _post(s, weight=None)
    assert r.status_code == 200, r.text
    assert r.json()["precision"] == 85


def test_auto_measure_bad_features(s):
    assert _post(s, feats={"chest_r": 2}).status_code == 400
    with open(PHOTO, "rb") as f:
        r = s.post(f"{BASE_URL}/api/profile/auto-measure", params={"height_cm": 165, "gender": "female", "features": "notjson"},
                   files={"photo": ("p.jpg", f, "image/jpeg")})
    assert r.status_code == 400


def test_auto_measure_height_range(s):
    assert _post(s, height=100).status_code == 422
    assert _post(s, height=300).status_code == 422
    assert _post(s, gender="unisex").status_code == 422
    assert _post(s, weight=200).status_code == 422


def test_auto_measure_requires_auth():
    with open(PHOTO, "rb") as f:
        r = requests.post(f"{BASE_URL}/api/profile/auto-measure", params={"height_cm": 165, "gender": "female", "features": json.dumps(FEATS)},
                          files={"photo": ("p.jpg", f, "image/jpeg")})
    assert r.status_code == 401


# --- encryption at rest
def test_measurements_doc_encrypted(s):
    _post(s, weight=61)
    keys = mongo(f'print(JSON.stringify(Object.keys(db.measurements.findOne({{user_id:"{UID}"}},{{_id:0}}))))')
    assert set(json.loads(keys)) == {"user_id", "enc", "updated_at"}, keys
    g = s.get(f"{BASE_URL}/api/profile/measurements").json()
    assert g["weight_kg"] == 61 and g["height_cm"] == 165 and g["chest_cm"] > 0


def test_weight_history_encrypted(s):
    r = s.post(f"{BASE_URL}/api/profile/weight-history", json={"weight_kg": 62.5, "note": "TEST_enc"})
    assert r.status_code == 200 and r.json()["entry"]["weight_kg"] == 62.5
    eid = r.json()["entry"]["id"]
    doc = json.loads(mongo(f'print(JSON.stringify(db.weight_history.findOne({{id:"{eid}"}},{{_id:0}})))'))
    assert "weight_enc" in doc and "weight_kg" not in doc
    assert mongo(f'print(db.weight_history.countDocuments({{weight_kg:{{$exists:true}}}}))') == "0"
    hist = s.get(f"{BASE_URL}/api/profile/weight-history").json()["entries"]
    e = next(x for x in hist if x["id"] == eid)
    assert e["weight_kg"] == 62.5 and "weight_enc" not in e
    s.delete(f"{BASE_URL}/api/profile/weight-history/{eid}")


# --- measure photo never served
def test_measure_photo_not_served(s):
    _post(s)
    doc = json.loads(mongo(f'print(JSON.stringify(db.files.find({{user_id:"{UID}",kind:"measure"}},{{_id:0}}).sort({{created_at:-1}}).limit(1).toArray()[0]))'))
    assert doc["encrypted"] is True and doc["storage_path"].endswith(".bin")
    r = s.get(f"{BASE_URL}/api/files/{doc['storage_path']}")
    assert r.status_code == 404


# --- B2B / public privacy
def test_b2b_no_weight():
    r = requests.get(f"{BASE_URL}/api/b2b/fitting-accuracy/{UID}")
    assert r.status_code == 200
    assert "weight" not in r.json() and "weight_kg" not in r.json()


def test_public_fitting_accuracy_no_weight():
    # unauthenticated public endpoint used by brands must not leak personal weight
    r = requests.get(f"{BASE_URL}/api/fitting-accuracy/{UID}")
    assert r.status_code == 200
    assert "weight" not in r.json(), f"public endpoint leaks weight: {r.json()}"


# --- regression
def test_put_measurements_still_works(s):
    r = s.put(f"{BASE_URL}/api/profile/measurements", json={"chest_cm": 90, "height_cm": 165})
    assert r.status_code == 200 and r.json()["chest_cm"] == 90
    assert s.get(f"{BASE_URL}/api/profile/measurements").json()["chest_cm"] == 90
    for ep in ("/api/profile/fitting-accuracy", "/api/fitting-accuracy", "/api/profile/weight-history"):
        assert s.get(f"{BASE_URL}{ep}").status_code == 200, ep
