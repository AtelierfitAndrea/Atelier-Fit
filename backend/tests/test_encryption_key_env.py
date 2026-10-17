# Regression: encryption key quoting in .env — backend up, measurements/weight decrypt, round trip, auto-measure
import os, json, pytest, requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
TOKEN = "fam_test_1791784817"
H = {"Authorization": f"Bearer {TOKEN}"}
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def uid():
    return db.user_sessions.find_one({"session_token": TOKEN})["user_id"]


# NOTE: test_auto_measure runs last on purpose so the test user ends in the auto_photo state (UI shows result panel)


def test_root():
    r = requests.get(f"{BASE_URL}/api/")
    assert r.status_code == 200


def test_measurements_decrypt():
    r = requests.get(f"{BASE_URL}/api/profile/measurements", headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    d = d.get("measurements", d) if isinstance(d, dict) else d
    print(d)
    for k in ("chest_cm", "height_cm", "weight_kg"):
        assert isinstance(d.get(k), (int, float)), k
    # brand_sizes is cleared by a manual PUT (by design); it is asserted after auto-measure in test_auto_measure


def test_weight_history_decrypt():
    r = requests.get(f"{BASE_URL}/api/profile/weight-history", headers=H)
    assert r.status_code == 200
    e = r.json()["entries"]
    assert e and all(isinstance(x.get("weight_kg"), (int, float)) for x in e)
    assert all("weight_enc" not in x for x in e)


def test_roundtrip_inseam():
    r = requests.put(f"{BASE_URL}/api/profile/measurements", headers=H, json={"inseam_cm": 75})
    assert r.status_code == 200, r.text
    g = requests.get(f"{BASE_URL}/api/profile/measurements", headers=H).json()
    g = g.get("measurements", g)
    assert g["inseam_cm"] == 75
    doc = db.measurements.find_one({"user_id": uid()}, {"_id": 0})
    assert "enc" in doc
    assert not ({"inseam_cm", "chest_cm", "height_cm", "weight_kg"} & set(doc))


def test_auto_measure():
    feats = json.dumps({"shoulder_r": 0.19, "chest_r": 0.18, "waist_r": 0.15, "hips_r": 0.2, "inseam_r": 0.45})
    with open("/app/memory/test_fullbody.jpg", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/profile/auto-measure", headers=H,
                          params={"features": feats, "height_cm": 165, "gender": "female"},
                          files={"photo": ("p.jpg", f, "image/jpeg")})
    assert r.status_code == 200, r.text
    assert "precision" in json.dumps(r.json())
    doc = db.measurements.find_one({"user_id": uid()}, {"_id": 0})
    assert "enc" in doc and "chest_cm" not in doc
    g = requests.get(f"{BASE_URL}/api/profile/measurements", headers=H).json()
    assert g["method"] == "auto_photo" and isinstance(g["precision"], (int, float)) and g["brand_sizes"]
