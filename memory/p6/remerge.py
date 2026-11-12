import sys, asyncio, os, logging
sys.path.insert(0, "/app/backend")
os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
import numpy as np, cv2
from PIL import Image
import server, head_lock, pose_lock, tryon_quality
import io

PERSON = "vfit/person/user_389c87aaadc6/95779ec5d7614166932a2153e02d39c8.jpg"


async def main():
    pb, _ = server.get_object(PERSON)
    pb = head_lock.crop_screenshot(pb)
    boxes, keep, txt, freeze = await server._lock_hands(PERSON, pb, False, True, ["dress"], True)
    _, lock = head_lock.prepare(pb, True, boxes, keep, True, freeze, 0.0, True)
    base = tryon_quality._snapshot(lock)
    snap = tryon_quality._snapshot(lock)
    snap["arms"] = pose_lock.arm_masks(lock["canvas"])
    out = head_lock.finalize(open("/app/memory/p6/raw1.png", "rb").read(), snap)
    fin = np.array(Image.open(io.BytesIO(out)).convert("RGB"))
    seated = base["seated"]
    sk = head_lock._skin(fin) > 0
    grey = cv2.dilate(((seated["bare"] > 0) & sk).astype(np.uint8), np.ones((7, 7), np.uint8))
    protect = cv2.dilate((sk & (seated["bare"] == 0) & (grey == 0)).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    grey[protect] = 0
    H, W = fin.shape[:2]
    res = np.array(head_lock._open_small(open("/app/memory/p6/seatfix3.png", "rb").read(), max(H, W)).convert("RGB"))
    reg = head_lock._register(fin, res)
    np.save("/app/memory/p6/fin.npy", fin); np.save("/app/memory/p6/reg.npy", reg); np.save("/app/memory/p6/grey.npy", grey); np.save("/app/memory/p6/protect.npy", protect)
    np.save("/app/memory/p6/bare.npy", seated["bare"]); np.save("/app/memory/p6/canvas.npy", base["canvas"])
    print("saved")

asyncio.run(main())
