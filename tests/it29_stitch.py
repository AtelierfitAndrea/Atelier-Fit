import base64, json
BASE = "https://virtual-try-on-334.preview.emergentagent.com"
def durl(p):
    return "data:image/jpeg;base64," + base64.b64encode(open(p, "rb").read()).decode()
imgs = {"up": durl("/tmp/upper.jpg"), "low": durl("/tmp/lower.jpg"), "s13": durl("/tmp/lower_s13.jpg"),
        "str": durl("/tmp/lower_stretched.jpg"), "full": durl("/tmp/fullbody.jpg")}
mock = open("/app/tests/cam_mock_avatar.js").read().replace("__IMGS__", json.dumps(imgs))
lens = open("/app/tests/cam_mock_lens.js").read()
blobs = """(() => { window.__blobs = []; const o = URL.createObjectURL; URL.createObjectURL = function (b) { if (b instanceof Blob) window.__blobs.push(b); return o.call(URL, b); }; })();"""
SCEN = __SCEN__
await page.set_viewport_size({"width": 390, "height": 844})
await page.context.add_cookies([{"name": "session_token", "value": "avatar_tok_test", "domain": "virtual-try-on-334.preview.emergentagent.com", "path": "/", "httpOnly": True, "secure": True, "sameSite": "None"}])
await page.add_init_script("localStorage.setItem('atelier_owner','1');")
await page.add_init_script(mock + "\n" + lens + "\n" + blobs)
posts = []
page.on("request", lambda r: posts.append(r.method + " " + r.url) if r.method == "POST" and "/api/profile" in r.url else None)
page.on("pageerror", lambda e: print("PAGEERROR", e))
for name, low in SCEN:
    try:
        posts.clear()
        await page.goto(BASE + "/settings", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        btn = page.locator('[data-testid="avatar-change-btn"]')
        if await btn.count(): await btn.first.click()
        else: await page.click('[data-testid="avatar-tap-zone"]')
        await page.wait_for_selector('[data-testid="avatar-camera-video"]', timeout=8000)
        await page.click('[data-testid="avatar-camera-mode-double"]')
        await page.evaluate("window.__setImg('up')")
        await page.wait_for_timeout(1500)
        await page.click('[data-testid="avatar-camera-big-snap"]')
        await page.wait_for_timeout(800)
        await page.evaluate(f"window.__setImg('{low}')")
        await page.wait_for_timeout(1500)
        await page.click('[data-testid="avatar-camera-big-snap"]')
        await page.wait_for_selector('[data-testid="avatar-stitch-preview"]', timeout=60000)
        await page.wait_for_selector('[data-testid="avatar-stitch-confirm"]', timeout=60000)
        await page.wait_for_timeout(500)
        warns = await page.locator('[data-testid^="avatar-soft-warning-"]').evaluate_all("els => els.map(e => e.dataset.testid)")
        info = await page.evaluate("""async () => { const out = []; for (const b of window.__blobs) { try { const bm = await createImageBitmap(b); out.push([bm.width, bm.height, b.size]); } catch (e) { out.push(['x', b.size]); } } return out; }""")
        print(name, "warnings", warns, "blobs", info)
        # save stitched (largest non 960x1000)
        data = await page.evaluate("""async () => { const bs = window.__blobs; let pick = null; for (const b of bs) { const bm = await createImageBitmap(b); if (!(bm.width === 960 && bm.height === 1000)) pick = b; }
            if (!pick) return null; return await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(pick); }); }""")
        if data: open(f"/tmp/it29_{name}.jpg", "wb").write(base64.b64decode(data.split(",")[1]))
        await page.click('[data-testid="avatar-stitch-confirm"]')
        await page.wait_for_timeout(6000)
        toasts = await page.locator('[data-sonner-toast]').all_inner_texts()
        print(name, "toasts", toasts)
        print(name, "posts", posts)
        m = await page.evaluate("async () => (await fetch('/api/profile/measurements', {credentials: 'include'})).json()")
        print(name, "meas", {k: m.get(k) for k in ["chest_cm", "waist_cm", "hips_cm", "shoulder_cm", "inseam_cm", "method", "height_cm", "weight_kg"]})
        issues = await page.locator('[data-testid="avatar-photo-issue"]').count()
        print(name, "issues", issues)
        await page.evaluate("window.__blobs = []")
    except Exception as e:
        print(name, "ERROR", e)
