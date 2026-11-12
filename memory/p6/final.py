import sys, asyncio, os, io, uuid
sys.path.insert(0, "/app/backend"); os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
import numpy as np, cv2
from PIL import Image
import server, head_lock, pose_lock, tryon_quality
PERSON = "vfit/person/user_389c87aaadc6/95779ec5d7614166932a2153e02d39c8.jpg"
async def main():
    pb, _ = server.get_object(PERSON); pb = head_lock.crop_screenshot(pb)
    boxes, keep, txt, freeze = await server._lock_hands(PERSON, pb, False, True, ["dress"], True)
    _, lock = head_lock.prepare(pb, True, boxes, keep, True, freeze, 0.0, True)
    base = tryon_quality._snapshot(lock); snap = tryon_quality._snapshot(lock)
    snap["arms"] = pose_lock.arm_masks(lock["canvas"])
    out = head_lock.finalize(open("/app/memory/p6/raw1.png", "rb").read(), snap)
    fin = np.array(Image.open(io.BytesIO(out)).convert("RGB")); seated = base["seated"]
    sk = head_lock._skin(fin) > 0
    grey = cv2.dilate(((seated["bare"] > 0) & sk).astype(np.uint8), np.ones((7, 7), np.uint8))
    p = cv2.morphologyEx((sk & (seated["bare"] == 0) & (grey == 0)).astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(p, 8); big = st[:, cv2.CC_STAT_AREA] >= 0.002 * p.size; big[0] = False
    protect = big[lab]; grey[protect] = 0
    fixed = tryon_quality.seated_cover_merge(fin, open("/app/memory/p6/seatfix3.png", "rb").read(), base["canvas"], seated, grey, protect)
    print("skin_left", tryon_quality.legs_skin_left(fixed, base["canvas"], seated["bare"]))
    signed = tryon_quality.watermark(tryon_quality._png(fixed), await server._mark_for("user_389c87aaadc6"))
    open("/app/memory/p6/final.jpg", "wb").write(signed)
    path = f"vfit/tryon/user_389c87aaadc6/{uuid.uuid4().hex}.jpg"
    server.put_object(path, signed, "image/jpeg")
    await server.db.tryons.update_one({"id": "56e1910f-4e5c-44fe-bcbd-d664490a54d9"}, {"$set": {"result_path": path}})
    print("STORED", path)
asyncio.run(main())
