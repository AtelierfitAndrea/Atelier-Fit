import asyncio, io, sys, base64
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
import numpy as np, cv2
from PIL import Image
import server, tryon_quality, head_lock
SRC = "/app/memory/p9/shirt_fixed.jpg"
from emergentintegrations.llm.chat import ImageContent

PROMPT = ("IMAGE 1 is a square crop of a photo of ONE young woman kneeling on the beach, wearing a black long-sleeve T-shirt with a "
          "printed front and light blue jeans. The bottom HEM of the black T-shirt across the front is cut unevenly: a diagonal notch / missing "
          "piece where the jeans show through, low on the front at the hips. Rebuild the missing piece EXACTLY like the rest of the "
          "shirt: same black fabric, same texture and folds, the hem closed and continuous down to the jeans waistband. The shirt must be "
          "whole and complete, no cuts, no holes. Change NOTHING else: same jeans, same arms and hands, same body, same pose, same light, same "
          "beach. Never draw a person, a face or a miniature. "
          "No text, no frame.")

async def m():
    oid = "b9426b0d-ab36-411a-986c-f598c59bc503"
    o = await server.db.outfits.find_one({"id": oid})
    img_b = open(SRC, "rb").read()
    img = np.array(Image.open(io.BytesIO(img_b)).convert("RGB"))
    H, W = img.shape[:2]
    bx0, by0, bx1, by1 = [int(v) for v in sys.argv[1:5]]
    side = min(H, W, int(1.25 * max(bx1 - bx0, by1 - by0)))
    cx, cy = (bx0 + bx1) // 2, (by0 + by1) // 2
    sx, sy = min(max(0, cx - side // 2), W - side), min(max(0, cy - side // 2), H - side)
    crop = np.ascontiguousarray(img[sy:sy + side, sx:sx + side])
    buf = io.BytesIO(); Image.fromarray(crop).save(buf, "PNG")
    ref = head_lock.downscale(img_b, 1024)
    out = await tryon_quality._image_call("You are a high-end photo retoucher: minimal local HD repairs only.", PROMPT,
                                          [ImageContent(base64.b64encode(buf.getvalue()).decode())], "shirtfix", "1:1")
    res = np.array(Image.open(io.BytesIO(out)).convert("RGB"))
    reg = head_lock._register(crop, res, zoom=(0.8, 1.25))
    if reg is None or len(head_lock._faces(res)) > 0:
        open("/app/memory/p9/shirt_crop_raw.jpg", "wb").write(out); print("REJECTED", reg is None); return
    res = reg
    mk = np.zeros((side, side), np.float32)
    mk[by0 - sy:by1 - sy, bx0 - sx:bx1 - sx] = 1
    mk = cv2.GaussianBlur(mk, (0, 0), 6)
    img[sy:sy + side, sx:sx + side] = cv2.blendLinear(res, crop, mk, 1 - mk)
    o2 = io.BytesIO(); Image.fromarray(img).save(o2, "JPEG", quality=94)
    open("/app/memory/p9/shirt_fixed2.jpg", "wb").write(o2.getvalue())
    open("/app/memory/p9/shirt_crop_raw.jpg", "wb").write(out)
    print("DONE", sx, sy, side, reg is not None, len(head_lock._faces(res)))

asyncio.run(m())
