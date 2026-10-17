# Founder admin dashboard (/api/admin/*) tests: login, session cookie, stats, logout, brute-force lockout
import os
import subprocess
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
PWD = "AtelierFondatore2026!"


def _clean_attempts():
    subprocess.run(["mongosh", "--quiet", "--eval",
                    "db=db.getSiblingDB('test_database'); db.admin_login_attempts.deleteMany({})"],
                   capture_output=True)


@pytest.fixture(autouse=True)
def clean():
    _clean_attempts()
    yield
    _clean_attempts()


# Unauthenticated access
def test_stats_without_cookie_401():
    r = requests.get(f"{BASE_URL}/api/admin/stats")
    assert r.status_code == 401


def test_wrong_password_401():
    r = requests.post(f"{BASE_URL}/api/admin/login", json={"password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Password errata"


# Login + cookie + stats + logout
def test_login_stats_logout():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/admin/login", json={"password": PWD})
    assert r.status_code == 200 and r.json()["ok"] is True
    sc = r.headers.get("set-cookie", "")
    assert "admin_token=" in sc and "HttpOnly" in sc and "Path=/api/admin" in sc
    r = s.get(f"{BASE_URL}/api/admin/stats")
    assert r.status_code == 200
    d = r.json()
    assert d["demo"] is True and d["min_views"] == 1000
    k = d["kpi"]
    for key in ("subscribers_total", "visits_today", "paying_subscribers", "revenue_total"):
        assert key in k
    assert list(d["hot_products"].keys()) == ["Maglie", "Pantaloni", "Scarpe", "Giacche"]
    names = []
    for cat, items in d["hot_products"].items():
        for p in items:
            assert p["views"] >= 1000
            assert p["conversion"] == round(p["sales"] / p["views"] * 100, 2)
            names.append(p["name"])
    for excluded in ("Camicia lino", "Chino slim", "Blazer doppiopetto"):
        assert excluded not in names
    assert len(names) == 10
    r = s.post(f"{BASE_URL}/api/admin/logout")
    assert r.status_code == 200
    # cookie removed from session -> 401
    assert s.get(f"{BASE_URL}/api/admin/stats").status_code == 401


def test_token_invalid_after_logout_server_side():
    s = requests.Session()
    s.post(f"{BASE_URL}/api/admin/login", json={"password": PWD})
    tok = s.cookies.get("admin_token")
    assert tok
    s.post(f"{BASE_URL}/api/admin/logout")
    r = requests.get(f"{BASE_URL}/api/admin/stats", cookies={"admin_token": tok})
    assert r.status_code == 401


# Brute force lockout
def test_bruteforce_lockout():
    for i in range(5):
        r = requests.post(f"{BASE_URL}/api/admin/login", json={"password": f"bad{i}"})
        assert r.status_code == 401
    r = requests.post(f"{BASE_URL}/api/admin/login", json={"password": "bad"})
    assert r.status_code == 429
    assert "Troppi tentativi" in r.json()["detail"]
    # even correct password locked
    r = requests.post(f"{BASE_URL}/api/admin/login", json={"password": PWD})
    assert r.status_code == 429
