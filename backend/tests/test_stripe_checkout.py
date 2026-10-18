# Stripe checkout / payment status regression tests (owner account, test mode)
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = "owner_tok_test"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    r = s.get(f"{BASE_URL}/api/subscription/status")
    if r.status_code != 200:
        pytest.skip(f"owner auth failed {r.status_code}")
    return s


# Checkout creation for each plan option
@pytest.mark.parametrize("option", ["extra", "single", "family"])
def test_checkout_creates_session(client, option):
    r = client.post(f"{BASE_URL}/api/subscription/checkout", json={"option": option, "origin_url": BASE_URL})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["checkout_url"].startswith("https://checkout.stripe.com")
    assert d["session_id"].startswith("cs_test_")
    # status for unpaid session is pending (unauthenticated)
    s = requests.get(f"{BASE_URL}/api/payments/status/{d['session_id']}")
    assert s.status_code == 200
    sd = s.json()
    assert sd["payment_status"] == "pending"
    assert sd["status"] == "initiated"
    assert sd["option"] == option


def test_checkout_invalid_option(client):
    r = client.post(f"{BASE_URL}/api/subscription/checkout", json={"option": "gold", "origin_url": BASE_URL})
    assert r.status_code == 400


def test_checkout_requires_auth():
    r = requests.post(f"{BASE_URL}/api/subscription/checkout", json={"option": "single", "origin_url": BASE_URL})
    assert r.status_code == 401


def test_checkout_missing_fields(client):
    r = client.post(f"{BASE_URL}/api/subscription/checkout", json={"option": "single"})
    assert r.status_code == 422


def test_status_unknown_session():
    r = requests.get(f"{BASE_URL}/api/payments/status/cs_test_doesnotexist123")
    assert r.status_code == 404


def test_webhook_invalid_signature():
    r = requests.post(f"{BASE_URL}/api/stripe/webhook", data=b"{}", headers={"stripe-signature": "bad"})
    assert r.status_code == 400
