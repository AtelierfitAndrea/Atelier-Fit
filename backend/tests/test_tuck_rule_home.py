# Unit tests for server._tuck_rule (untucked shirt rule) + avatar/tryons API smoke
import os, sys
import pytest
import requests

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import server  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
TOKEN = os.environ.get("OWNER_TEST_TOKEN", "pending_test_tok")


class TestTuckRule:
    def test_top_alone_untucked(self):
        r = server._tuck_rule([{"category": "top", "name": "T-shirt bianca"}])
        assert "UNTUCKED" in r

    def test_top_by_name_alone(self):
        assert "UNTUCKED" in server._tuck_rule([{"category": "", "name": "Camicia Oxford"}])

    def test_top_with_bottom(self):
        assert "UNTUCKED" in server._tuck_rule([{"category": "top", "name": "Polo"}, {"category": "bottom", "name": "Jeans"}])

    def test_top_with_outerwear_category(self):
        assert server._tuck_rule([{"category": "top", "name": "Shirt"}, {"category": "outerwear", "name": "X"}]) == ""

    def test_top_with_jacket_name(self):
        assert server._tuck_rule([{"category": "top", "name": "Shirt"}, {"category": "", "name": "Giacca lana"}]) == ""

    def test_dress_only(self):
        assert server._tuck_rule([{"category": "dress", "name": "Abito top"}]) == ""

    def test_bottom_only(self):
        assert server._tuck_rule([{"category": "bottom", "name": "Pantaloni"}]) == ""

    def test_empty(self):
        assert server._tuck_rule([]) == ""


class TestHomeApis:
    @pytest.fixture
    def s(self):
        ses = requests.Session()
        ses.headers.update({"Authorization": f"Bearer {TOKEN}"})
        r = ses.get(f"{BASE_URL}/api/auth/me")
        if r.status_code != 200:
            pytest.skip("owner session invalid")
        return ses

    def test_tryons_list(self, s):
        r = s.get(f"{BASE_URL}/api/tryons")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_subscription_status(self, s):
        r = s.get(f"{BASE_URL}/api/subscription/status")
        assert r.status_code == 200
        assert "is_blocked" in r.json()
