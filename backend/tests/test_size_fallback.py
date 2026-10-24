# Size fallback (international average) - API + unit logic tests
import os
import sys
import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import size_fallback  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
TOKEN = "pending_test_tok"
EP = f"{BASE_URL}/api/product/size-fallback"


@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return s


# --- API ---
class TestSizeFallbackAPI:
    def test_unauth_401(self):
        r = requests.post(EP, json={"url": "https://x.com/felpa"})
        assert r.status_code == 401

    def test_default_top(self, client):
        r = client.post(EP, json={"url": "https://example.com/item"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True and d["source"] == "international_average"
        assert d["category"] == "top"
        assert d["recommended_size"] in ["S", "M", "L", "XL", "XXL"]
        assert 0.70 <= d["confidence"] <= 0.93
        assert d["explanation"].startswith("Taglia consigliata:")
        assert "media internazionale" in d["explanation"] and "Affidabilità" in d["explanation"]
        assert isinstance(d["details"], str) and d["details"]

    @pytest.mark.parametrize("url,cat", [
        ("https://shop.com/cargo-pants-123", "bottom"),
        ("https://shop.com/pantaloni-lino", "bottom"),
        ("https://shop.com/felpa-con-cappuccio", "top"),
        ("https://shop.com/hoodie-black", "top"),
    ])
    def test_category_mapping(self, client, url, cat):
        d = client.post(EP, json={"url": url}).json()
        assert d["category"] == cat
        assert d["confidence"] <= 0.93

    def test_sneakers(self, client):
        d = client.post(EP, json={"url": "https://shop.com/sneakers-air"}).json()
        assert d["category"] == "shoes"
        assert d["recommended_size"].endswith(" EU")
        assert d["recommended_size"].split()[0].isdigit()

    def test_explicit_category(self, client):
        d = client.post(EP, json={"category": "shoes"}).json()
        assert d["category"] == "shoes"


# --- unit logic ---
M = {"gender": "male", "height_cm": 178}


class TestRecommendUnit:
    def test_m_93(self):
        r = size_fallback.recommend({**M, "chest_cm": 98, "waist_cm": 84}, "t-shirt")
        assert r["size"] == "M" and r["confidence"] == 93

    def test_edge_felpa_L(self):
        r = size_fallback.recommend({**M, "chest_cm": 101.5, "waist_cm": 90}, "felpa")
        assert r["size"] == "L" and 88 <= r["confidence"] <= 90

    def test_edge_tshirt_M(self):
        r = size_fallback.recommend({**M, "chest_cm": 95.5, "waist_cm": 84}, "t-shirt")
        assert r["size"] == "M" and r["confidence"] <= 90

    def test_huge(self):
        r = size_fallback.recommend({**M, "chest_cm": 140, "waist_cm": 130}, "t-shirt")
        assert r["size"] == "XXL" and 70 <= r["confidence"] < 88

    def test_never_above_93(self):
        for c in range(80, 130):
            for kind in ["t-shirt", "felpa", "giacca", "abito", "pantaloni", "cargo"]:
                r = size_fallback.recommend({**M, "chest_cm": c, "waist_cm": c - 14, "hips_cm": c + 1}, kind)
                assert 70 <= r["confidence"] <= 93
        for f in [22, 24.0, 25.5, 27.2, 31]:
            r = size_fallback.recommend({"foot_cm": f}, "sneakers")
            assert r["confidence"] <= 93 and r["size"].endswith("EU")

    def test_female(self):
        r = size_fallback.recommend({"gender": "female", "chest_cm": 90, "waist_cm": 74, "hips_cm": 98}, "abito")
        assert r["size"] == "M"
