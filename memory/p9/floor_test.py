import asyncio, sys, io, importlib.util
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
import numpy as np, cv2
from PIL import Image
import server, ext_lock, head_lock, pose_lock

spec = importlib.util.spec_from_file_location("ext_old", "/tmp/ext_lock_old.py")
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)


async def m():
    person = head_lock.downscale(await server._person_cropped("vfit/person/user_389c87aaadc6/95779ec5d7614166932a2153e02d39c8.jpg"), 2048)
    G = np.array(Image.open("/app/memory/p9/red3.jpg").convert("RGB"))
    H, W = G.shape[:2]
    kp = pose_lock.keypoints(G)
    near = ext_lock._zone(kp, G.shape, "suit") > 0
    # synthetic debris: small red scrap far on the floor + big blob far away
    far = np.argwhere(~cv2.dilate(near.astype(np.uint8), np.ones((int(0.9 * ext_lock._up_len(kp, H)),) * 2, np.uint8)).astype(bool))
    far = far[(far[:, 0] > 0.4 * H) & (far[:, 0] < 0.88 * H)]
    y, x = far[len(far) // 2]
    cv2.circle(G, (int(x), int(y)), int(0.012 * W), (200, 20, 30), -1)
    print("small scrap at", y, x)
    buf = io.BytesIO(); Image.fromarray(G).save(buf, "JPEG", quality=95); res = buf.getvalue()
    # bad AI boxes covering the thighs/legs (what broke 0d1d720f)
    legs = pose_lock.legs_mask(kp, G.shape) > 0
    ys, xs = np.where(legs)
    box = (int(ys.min() * 1000 / H), int(xs.min() * 1000 / W), int(ys.max() * 1000 / H), int(xs.max() * 1000 / W))
    small_box = (int((y - 0.03 * H) * 1000 / H), int((x - 0.03 * W) * 1000 / W), int((y + 0.03 * H) * 1000 / H), int((x + 0.03 * W) * 1000 / W))
    for name, mod in (("OLD", old), ("NEW", ext_lock)):
        out = mod.clean_floor(res, person, [box, small_box])
        if out is None:
            print(name, "nothing cleaned"); continue
        R = np.array(Image.open(io.BytesIO(out)).convert("RGB"))
        d = np.abs(R.astype(int) - G.astype(int)).max(axis=2) > 12
        print(name, "changed total=%.4f  inside body zone=%.4f  on legs=%.4f  scrap removed=%s" % (
            d.mean(), (d & near).sum() / near.sum(), (d & legs).sum() / legs.sum(), bool(d[y, x])))
        Image.fromarray(np.hstack([G, R])).resize((W, H // 2)).save(f"/app/memory/p9/floor_{name}.jpg", quality=70)

asyncio.run(m())
