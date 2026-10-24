# Shared size charts across customers (brand_key + group), confidence 0.98
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = "pending_test_tok"
ZARA = "https://www.zara.com/it/it/felpa-con-cappuccio-p00761403.html"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    return s


def test_analyze_requires_auth():
    r = requests.post(f"{BASE_URL}/api/product/analyze", json={"url": ZARA}, timeout=30)
    assert r.status_code == 401


def test_analyze_zara_uses_shared_chart(client):
    r = client.post(f"{BASE_URL}/api/product/analyze", json={"url": ZARA}, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    print(d)
    assert d.get("ok") is True
    assert d.get("confidence") == 0.98
    sc = d.get("saved_chart") or {}
    assert sc.get("shared") is True
    assert sc.get("brand") == "Zara"
    assert sc.get("group") == "sopra"
    assert d.get("recommended_size")
