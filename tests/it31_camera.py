import base64, json
# it31: camera zoom 1x/0.5x lens pick + wide warning, spirit level, home notes
BASE = "https://virtual-try-on-334.preview.emergentagent.com"
def durl(p):
    return "data:image/jpeg;base64," + base64.b64encode(open(p, "rb").read()).decode()
imgs = {"up": durl("/tmp/fullbody.jpg"), "full": durl("/tmp/fullbody.jpg")}
mock = open("/app/tests/cam_mock_avatar.js").read().replace("__IMGS__", json.dumps(imgs))
lens = open("/app/tests/cam_mock_lens.js").read()
pre = """window.__devs = [
 {deviceId:'back-id',kind:'videoinput',label:'Back Camera',groupId:'g'},
 {deviceId:'uw-id',kind:'videoinput',label:'Back Ultra Wide Camera',groupId:'g'},
 {deviceId:'tele-id',kind:'videoinput',label:'Back Telephoto Camera',groupId:'g'}];
window.__defaultLabel = {environment: window.localStorage.getItem('__dl') || 'Back Camera', user:'Front Camera'};
try { localStorage.setItem('atelier_owner','1'); } catch(e) {}"""
await page.set_viewport_size({"width": 390, "height": 844})
await page.context.add_cookies([{"name": "session_token", "value": "avatar_tok_test", "domain": "virtual-try-on-334.preview.emergentagent.com", "path": "/", "httpOnly": True, "secure": True, "sameSite": "None"}])
await page.add_init_script(pre + "\n" + mock + "\n" + lens)
page.on("pageerror", lambda e: print("PAGEERROR", e))
async def open_cam():
    await page.goto(BASE + "/dashboard", wait_until="networkidle")
    await page.wait_for_timeout(2000)
    btn = page.locator('[data-testid="avatar-change-btn"]')
    if await btn.count(): await btn.first.click()
    else: await page.click('[data-testid="avatar-tap-zone"]')
    await page.wait_for_selector('[data-testid="avatar-camera-video"]', timeout=8000)
    await page.wait_for_timeout(1500)
try:
    await page.goto(BASE + "/dashboard?atelier=2026", wait_until="networkidle")
    await page.wait_for_timeout(2500)
    for t in ["avatar-modes-note", "avatar-privacy-note"]:
        loc = page.locator(f'[data-testid="{t}"]')
        print(t, await loc.count(), (await loc.first.inner_text())[:200] if await loc.count() else None)
    box = page.locator('[data-testid="avatar-box"]')
    print("avatar-box", await box.count())
    if await box.count():
        txt = await box.first.inner_text()
        print("BOX TEXT:", txt[:1200])
        print("has bikini", "👙" in txt)
    await page.screenshot(path="/tmp/it31_home.jpg", quality=40, full_page=False)
    # Scenario A: default stream = Back Camera
    await open_cam()
    print("A gum", await page.evaluate("window.__gum"))
    print("A applied", await page.evaluate("window.__applied"))
    print("A warning", await page.locator('[data-testid="avatar-camera-wide-warning"]').count())
    await page.evaluate("window.__gum=[];window.__applied=[]")
    await page.click('[data-testid="avatar-camera-zoom-05"]')
    await page.wait_for_timeout(1500)
    print("A 0.5 gum", await page.evaluate("window.__gum"))
    print("A 0.5 applied", await page.evaluate("window.__applied"))
    w = page.locator('[data-testid="avatar-camera-wide-warning"]')
    print("A warning visible", await w.is_visible(), await w.inner_text() if await w.count() else None)
    print("zoom-05 class", await page.get_attribute('[data-testid="avatar-camera-zoom-05"]', "class"))
    await page.screenshot(path="/tmp/it31_wide.jpg", quality=40, full_page=False)
    await page.evaluate("window.__gum=[];window.__applied=[]")
    await page.click('[data-testid="avatar-camera-zoom-1"]')
    await page.wait_for_timeout(1500)
    print("A 1x gum", await page.evaluate("window.__gum"))
    print("A 1x applied", await page.evaluate("window.__applied"))
    print("A warning after 1x", await page.locator('[data-testid="avatar-camera-wide-warning"]').count())
    # Level
    print("level before", await page.locator('[data-testid="avatar-camera-level"]').count())
    for b, g in [(90, 0), (90, 10), (80, 0), (93, 2), (90, -4)]:
        await page.evaluate(f"window.dispatchEvent(Object.assign(new Event('deviceorientation'),{{beta:{b},gamma:{g}}}))")
        await page.wait_for_timeout(300)
        lv = page.locator('[data-testid="avatar-camera-level"]')
        print("level", b, g, await lv.is_visible(), await page.locator('[data-testid="avatar-camera-level-status"]').inner_text())
        if (b, g) == (90, 10): await page.screenshot(path="/tmp/it31_level.jpg", quality=40, full_page=False)
    # Scenario B: default stream = Ultra Wide
    await page.evaluate("localStorage.setItem('__dl','Back Ultra Wide Camera')")
    await open_cam()
    print("B gum", await page.evaluate("window.__gum"))
    print("B applied", await page.evaluate("window.__applied"))
    await page.evaluate("window.__gum=[];window.__applied=[]")
    await page.click('[data-testid="avatar-camera-zoom-05"]')
    await page.wait_for_timeout(1500)
    print("B 0.5 gum", await page.evaluate("window.__gum"))
    print("B 0.5 applied", await page.evaluate("window.__applied"))
    await page.evaluate("localStorage.removeItem('__dl')")
except Exception as e:
    print("ERR", e)
