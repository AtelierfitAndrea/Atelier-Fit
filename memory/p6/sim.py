import sys, asyncio, os
sys.path.insert(0, "/app/backend")
os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
import numpy as np, cv2, io
from PIL import Image
import server, head_lock, pose_lock, tryon_quality

PERSON = "vfit/person/user_389c87aaadc6/95779ec5d7614166932a2153e02d39c8.jpg"
RAW = sys.argv[1] if len(sys.argv) > 1 else "/app/memory/p6/raw.png"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/app/memory/p6/sim_out.jpg"


async def main():
    pb, _ = server.get_object(PERSON)
    pb = head_lock.crop_screenshot(pb)
    boxes, keep, txt, freeze = await server._lock_hands(PERSON, pb, False, True, ["dress"], True)
    print("boxes", boxes, "freeze", freeze)
    send, lock = head_lock.prepare(pb, True, boxes, keep, True, freeze, 0.0, True)
    open("/app/memory/p6/send.png", "wb").write(send)
    print("seated", lock.get("seated") is not None)
    snap = tryon_quality._snapshot(lock)
    snap["arms"] = pose_lock.arm_masks(lock["canvas"])
    out = head_lock.finalize(open(RAW, "rb").read(), snap)
    im = tryon_quality.watermark(out, "free")
    open(OUT, "wb").write(im)
    r = cv2.imread(OUT)
    h, w = r.shape[:2]
    cv2.imwrite(OUT.replace(".jpg", "_zoom.jpg"), cv2.resize(r[int(h * .62):int(h * .9), int(w * .2):int(w * .95)], None, fx=1.3, fy=1.3))
    print("done", r.shape)

asyncio.run(main())
