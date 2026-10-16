# Saved size charts per account (brand + group): _brand_key, analyze-text saves chart, marketplace/host isolation, account isolation
import asyncio
import os
import subprocess
import sys
import time
import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")


def _mongo(js):
    r = subprocess.run(["mongosh", "--quiet", "--eval", "use('test_database');" + js], capture_output=True, text=True)
    return r.stdout.strip()


@pytest.fixture(scope="module")
def client():
    ts = str(int(time.time() * 1000))
    uid, tok = f"TEST_sc_{ts}", f"TEST_sc_sess_{ts}"
    _mongo(f"""db.users.insertOne({{user_id:'{uid}',email:'{uid}@example.com',name:'SC Test',terms_version:'1.0-2026-06',plan:'SINGLE',created_at:new Date().toISOString()}});
db.user_sessions.insertOne({{user_id:'{uid}',session_token:'{tok}',expires_at:new Date(Date.now()+86400000).toISOString(),created_at:new Date().toISOString()}});""")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    s.uid = uid
    yield s
    _mongo(f"['users','user_sessions','measurements','weight_history','fitting_accuracy','files','product_analyses'].forEach(c=>db[c].deleteMany({{user_id:'{uid}'}})); db.saved_size_charts.deleteMany({{account_id:'{uid}'}});")


# --- unit: brand key / marketplace ---
def test_brand_key():
    import server
    assert server._brand_key("https://www.zara.com/it/it/giacca-p123.html") == "zara"
    assert server._brand_key("https://www2.hm.com/it_it/x") == "hm"
    assert server._brand_key("https://www.amazon.it/dp/x") == "amazon"
    assert server._brand_key("", "ZARA") == "zara"
    assert "amazon" in server._MARKETPLACES and "zalando" in server._MARKETPLACES


def test_new_user_no_measurements_rejected(client):
    r = client.post(f"{BASE_URL}/api/product/analyze-text", json={"chart_text": "S 86-90", "url": "https://www.zara.com/it/x"})
    assert r.status_code == 400


def test_analyze_text_saves_chart(client):
    r = client.put(f"{BASE_URL}/api/profile/measurements", json={"chest_cm": 92, "waist_cm": 76, "hips_cm": 96, "height_cm": 178, "gender": "male"})
    assert r.status_code == 200, r.text
    r = client.post(f"{BASE_URL}/api/product/analyze-text", json={
        "chart_text": "ZARA size chart: S chest 86-90 waist 70-74; M chest 90-94 waist 74-78; L chest 94-98 waist 78-82",
        "url": "https://www.zara.com/it/it/giacca-p123.html"}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    print("analyze-text:", d.get("ok"), d.get("recommended_size"), d.get("brand"), d.get("category"))
    assert d.get("ok") is True
    out = _mongo(f"printjson(db.saved_size_charts.find({{account_id:'{client.uid}'}},{{_id:0}}).toArray())")
    print(out)
    assert "zara" in out.lower() and "size_chart" in out


def test_saved_chart_isolation_and_marketplace(client):
    """In-process: other account never sees chart; marketplace URL never matched (no LLM call made)."""
    import server

    class U:
        def __init__(self, a):
            self.account_id = a
    # insert a chart with marketplace host for this account to prove host lookup ignored
    _mongo(f"db.saved_size_charts.insertOne({{account_id:'{client.uid}',brand_key:'amazon',group:'sopra',brand:'Amazon',size_chart:{{S:1}},host_keys:['amazon'],saved_at:new Date().toISOString()}})")

    async def run():
        other = await server._analyze_with_saved_chart(U("TEST_nobody_account"), "https://www.zara.com/it/it/maglia-p999.html", {"chest_cm": 90})
        amz = await server._analyze_with_saved_chart(U(client.uid), "https://www.amazon.it/dp/B0TEST", {"chest_cm": 90})
        found = await server.db.saved_size_charts.find_one({"account_id": client.uid, "$or": [{"brand_key": "zara"}, {"host_keys": "zara"}]}, {"_id": 0})
        return other, amz, found
    other, amz, found = asyncio.run(run())
    assert other is None
    assert amz is None
    assert found is not None
