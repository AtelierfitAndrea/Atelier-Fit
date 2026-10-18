import base64, json
# it30: 2-shot two_shot param + -2cm calib, single-shot no two_shot, stitched seam export
BASE = "https://virtual-try-on-334.preview.emergentagent.com"
def durl(p):
    return "data:image/jpeg;base64," + base64.b64encode(open(p, "rb").read()).decode()
imgs = {"up": durl("/tmp/upper.jpg"), "low": durl("/tmp/lower.jpg"), "full": durl("/tmp/fullbody.jpg")}
mock = open("/app/tests/cam_mock_avatar.js").read().replace("__IMGS__", json.dumps(imgs))
lens = open("/app/tests/cam_mock_lens.js").read()
blobs = """(() => { window.__blobs = []; const o = URL.createObjectURL; URL.createObjectURL = function (b) { if (b instanceof Blob) window.__blobs.push(b); return o.call(URL, b); }; })();"""
await page.set_viewport_size({"width": 390, "height": 844})
await page.context.add_cookies([{"name": "session_token", "value": "avatar_tok_test", "domain": "virtual-try-on-334.preview.emergentagent.com", "path": "/", "httpOnly": True, "secure": True, "sameSite": "None"}])
await page.add_init_script(mock + "\n" + lens + "\n" + blobs)
posts = []
page.on("request", lambda r: posts.append(r.method + " " + r.url) if r.method == "POST" and "/api/profile" in r.url else None)
page.on("pageerror", lambda e: print("PAGEERROR", e))
for name in ["good_form", "good", "single"]:
    try:
        posts.clear()
        await page.goto(BASE + "/settings", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        btn = page.locator('[data-testid="avatar-change-btn"]')
        if await btn.count(): await btn.first.click()
        else: await page.click('[data-testid="avatar-tap-zone"]')
        await page.wait_for_selector('[data-testid="avatar-camera-video"]', timeout=8000)
        if name == "single":
            await page.evaluate("window.__setImg('full')")
            await page.wait_for_timeout(1500)
            await page.click('[data-testid="avatar-camera-big-snap"]')
            await page.wait_for_timeout(8000)
        else:
            await page.click('[data-testid="avatar-camera-mode-double"]')
            await page.evaluate("window.__setImg('up')")
            await page.wait_for_timeout(1500)
            await page.click('[data-testid="avatar-camera-big-snap"]')
            await page.wait_for_timeout(800)
            await page.evaluate("window.__setImg('low')")
            await page.wait_for_timeout(1500)
            await page.click('[data-testid="avatar-camera-big-snap"]')
            await page.wait_for_selector('[data-testid="avatar-stitch-confirm"]', timeout=60000)
            await page.wait_for_timeout(500)
            warns = await page.locator('[data-testid^="avatar-soft-warning-"]').evaluate_all("els => els.map(e => e.dataset.testid)")
            print(name, "warnings", warns)
            data = await page.evaluate("""async () => { let pick = null; for (const b of window.__blobs) { try { const bm = await createImageBitmap(b); if (!(bm.width === 960 && bm.height === 1000)) pick = b; } catch (e) {} }
                if (!pick) return null; return await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(pick); }); }""")
            if data: open(f"/tmp/it30_{name}.jpg", "wb").write(base64.b64decode(data.split(",")[1]))
            await page.click('[data-testid="avatar-stitch-confirm"]')
            await page.wait_for_timeout(3000)
        if await page.locator('[data-testid="avatar-body-form"]').count():
            print(name, "BODY FORM shown")
            await page.fill('[data-testid="avatar-height-input"]', "168")
            await page.fill('[data-testid="avatar-weight-input"]', "60")
            await page.click('[data-testid="avatar-gender-female"]')
            await page.click('[data-testid="avatar-body-submit"]')
        await page.wait_for_timeout(6000)
        toasts = await page.locator('[data-sonner-toast]').all_inner_texts()
        print(name, "toasts", toasts)
        for p in posts: print(name, "POST", p)
        m = await page.evaluate("async () => (await fetch('/api/profile/measurements', {credentials: 'include'})).json()")
        print(name, "meas", {k: m.get(k) for k in ["chest_cm", "waist_cm", "hips_cm", "shoulder_cm", "inseam_cm", "method", "height_cm", "weight_kg"]})
        await page.evaluate("window.__blobs = []")
    except Exception as e:
        print(name, "ERROR", e)
        await page.screenshot(path=f"/tmp/it30_err_{name}.jpg", quality=40, full_page=False)
