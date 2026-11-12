import sys, asyncio, os, base64, logging
sys.path.insert(0, "/app/backend")
os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
logging.basicConfig(level=logging.INFO)
import numpy as np, cv2
import server, head_lock, pose_lock, tryon_quality
from emergentintegrations.llm.chat import ImageContent

PERSON = "vfit/person/user_389c87aaadc6/95779ec5d7614166932a2153e02d39c8.jpg"
GARMENT = "vfit/garment/user_389c87aaadc6/86a7cf903e8b40cf97ef270cfc735659.jpg"


async def main():
    pb, _ = server.get_object(PERSON)
    pb = head_lock.crop_screenshot(pb)
    boxes, keep, txt, freeze = await server._lock_hands(PERSON, pb, False, True, ["dress"], True)
    _, lock = head_lock.prepare(pb, True, boxes, keep, True, freeze, 0.0, True)
    base = tryon_quality._snapshot(lock)
    snap = tryon_quality._snapshot(lock)
    snap["arms"] = pose_lock.arm_masks(lock["canvas"])
    out = head_lock.finalize(open("/app/memory/p6/raw1.png", "rb").read(), snap)
    gb, _ = server.get_object(GARMENT)
    gb = head_lock.downscale(gb, head_lock.GARMENT_MAX_SIDE)
    fixed = await tryon_quality._seated_legs_check(out, base["canvas"], base["seated"], [ImageContent(base64.b64encode(gb).decode())],
                                                   "tryon-user_389c87aaadc6", tryon_quality._aspect(base))
    open("/app/memory/p6/gen3.png", "wb").write(fixed)
    signed = tryon_quality.watermark(fixed, await server._mark_for("user_389c87aaadc6"))
    open("/app/memory/p6/gen3.jpg", "wb").write(signed)
    path = f"vfit/tryon/user_389c87aaadc6/{__import__('uuid').uuid4().hex}.jpg"
    server.put_object(path, signed, "image/jpeg")
    await server.db.tryons.update_one({"id": "56e1910f-4e5c-44fe-bcbd-d664490a54d9"}, {"$set": {"result_path": path}})
    print("STORED", path)
    print("DONE")

asyncio.run(main())
