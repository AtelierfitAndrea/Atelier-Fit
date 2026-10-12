"""Backend tests for FAMILY plan sub-profiles and X-Profile-Id scoping."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://virtual-try-on-334.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

FAMILY_TOKEN = "test_fam_session_1"
FREE_TOKEN = "test_free_session_1"


def _h(token, profile_id=None):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if profile_id:
        h["X-Profile-Id"] = profile_id
    return h


@pytest.fixture(scope="module", autouse=True)
def _reset_subs():
    # Clean sub-profiles for the owner before/after module
    import pymongo
    client = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    db.users.delete_many({"owner_id": "test_family_user_1"})
    # Also clear measurements for sub-profiles / owner so tests are deterministic
    db.measurements.delete_many({"user_id": "test_family_user_1"})
    yield
    db.users.delete_many({"owner_id": "test_family_user_1"})
    db.measurements.delete_many({"user_id": "test_family_user_1"})


# ---------- Family listing ----------
def test_family_list_initial_owner_only():
    r = requests.get(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["enabled"] is True
    assert d["max_profiles"] == 4
    assert len(d["profiles"]) == 1
    assert d["profiles"][0]["is_owner"] is True


def test_family_list_free_user_not_enabled():
    r = requests.get(f"{API}/family/profiles", headers=_h(FREE_TOKEN))
    assert r.status_code == 200
    d = r.json()
    assert d["enabled"] is False
    assert len(d["profiles"]) == 1


# ---------- Create ----------
def test_family_create_forbidden_for_free():
    r = requests.post(f"{API}/family/profiles", headers=_h(FREE_TOKEN), json={"name": "Alice"})
    assert r.status_code == 403


created_ids = []


def test_family_create_three_profiles():
    for name in ["Alice", "Bob", "Carla"]:
        r = requests.post(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN), json={"name": name})
        assert r.status_code == 200, r.text
        d = r.json()
        created_ids.clear()
        created_ids.extend([p["profile_id"] for p in d["profiles"] if not p["is_owner"]])
    r = requests.get(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN))
    d = r.json()
    assert len(d["profiles"]) == 4


def test_family_create_4th_returns_400():
    r = requests.post(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN), json={"name": "Extra"})
    assert r.status_code == 400


def test_family_create_invalid_name():
    # Need to clean up to below 4 to isolate 400-name validation
    import pymongo
    client = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    # delete last sub profile
    r = requests.get(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN))
    pid = r.json()["profiles"][-1]["profile_id"]
    db.users.delete_one({"user_id": pid})
    r = requests.post(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN), json={"name": "   "})
    assert r.status_code == 400


# ---------- Rename ----------
def test_family_rename():
    r = requests.get(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN))
    subs = [p for p in r.json()["profiles"] if not p["is_owner"]]
    pid = subs[0]["profile_id"]
    r2 = requests.patch(f"{API}/family/profiles/{pid}", headers=_h(FAMILY_TOKEN), json={"name": "Renamed"})
    assert r2.status_code == 200
    names = [p["name"] for p in r2.json()["profiles"] if p["profile_id"] == pid]
    assert names == ["Renamed"]


def test_family_rename_unknown_404():
    r = requests.patch(f"{API}/family/profiles/does_not_exist", headers=_h(FAMILY_TOKEN), json={"name": "X"})
    assert r.status_code == 404


# ---------- X-Profile-Id scoping ----------
def test_profile_isolation_measurements():
    # Save measurements for owner (no header)
    r1 = requests.put(f"{API}/profile/measurements", headers=_h(FAMILY_TOKEN), json={"chest_cm": 100, "waist_cm": 80, "hips_cm": 95, "height_cm": 180})
    assert r1.status_code in (200, 201), r1.text

    # Pick a sub-profile
    r = requests.get(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN))
    subs = [p for p in r.json()["profiles"] if not p["is_owner"]]
    assert len(subs) >= 1
    sub_id = subs[0]["profile_id"]

    # Sub-profile measurements should be empty
    r2 = requests.get(f"{API}/profile/measurements", headers=_h(FAMILY_TOKEN, sub_id))
    assert r2.status_code == 200
    m = r2.json() or {}
    assert m.get("chest_cm") in (None, 0)

    # Save different data as sub-profile
    r3 = requests.put(f"{API}/profile/measurements", headers=_h(FAMILY_TOKEN, sub_id), json={"chest_cm": 85, "waist_cm": 65, "hips_cm": 90, "height_cm": 165})
    assert r3.status_code in (200, 201)

    # Owner data unchanged
    r4 = requests.get(f"{API}/profile/measurements", headers=_h(FAMILY_TOKEN))
    assert r4.status_code == 200
    assert r4.json().get("chest_cm") == 100

    # Sub data persisted
    r5 = requests.get(f"{API}/profile/measurements", headers=_h(FAMILY_TOKEN, sub_id))
    assert r5.json().get("chest_cm") == 85


def test_x_profile_id_ignored_for_non_family():
    # Free user sends X-Profile-Id; should be ignored and act as account
    r = requests.get(f"{API}/profile/measurements", headers=_h(FREE_TOKEN, "some_random_id"))
    assert r.status_code == 200


def test_x_profile_id_ignored_if_not_owned():
    # Family owner sends foreign profile id → should fall back to owner
    r = requests.get(f"{API}/profile/measurements", headers=_h(FAMILY_TOKEN, "not_my_profile_id"))
    assert r.status_code == 200
    assert r.json().get("chest_cm") == 100  # owner's data


# ---------- Subscription status shared ----------
def test_subscription_status_shared_across_profiles():
    r = requests.get(f"{API}/family/profiles", headers=_h(FAMILY_TOKEN))
    subs = [p for p in r.json()["profiles"] if not p["is_owner"]]
    sub_id = subs[0]["profile_id"]
    r2 = requests.get(f"{API}/subscription/status", headers=_h(FAMILY_TOKEN, sub_id))
    assert r2.status_code == 200
    assert r2.json().get("plan") == "FAMILY"


# ---------- Auth required ----------
def test_family_list_requires_auth():
    r = requests.get(f"{API}/family/profiles")
    assert r.status_code == 401
