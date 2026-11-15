import asyncio, io, sys, base64
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
import numpy as np, cv2
from PIL import Image
import server, tryon_quality, head_lock
from emergentintegrations.llm.chat import ImageContent

PROMPT = ("IMAGE 1 is a square crop of a photo of ONE young woman kneeling on the beach, wearing a black lace dress. Her ONLY two arms are "
          "raised, holding her hair (they are outside / at the top edge of this crop). In this crop there are EXTRA arms and hands resting on "
          "her knees: they are an error. Remove them COMPLETELY: no arms, no hands, no fingers on the knees or in front of the body. Where they "
          "were, show ONLY the same black lace dress continuing naturally over the torso, hips and thighs, and the empty knees. NEVER add hands, "
          "arms, legs or feet. Keep identical framing, scale, pose, dress pattern, colours and light. IMAGE 2 is the whole photo, reference only: "
          "return the crop of IMAGE 1. No text, no frame.")

async def m():
    oid = "38b3cc55-d7b0-4ace-80cc-941edaa239e4"
    o = await server.db.outfits.find_one({"id": oid})
    src = o["result_path"]
    img_b = server.get_object(src)[0]
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
                                          [ImageContent(base64.b64encode(buf.getvalue()).decode()), ImageContent(base64.b64encode(ref).decode())], "armsfix", "1:1")
    res = np.array(Image.open(io.BytesIO(out)).convert("RGB"))
    reg = head_lock._register(crop, res)
    res = reg if reg is not None else cv2.resize(res, (side, side), interpolation=cv2.INTER_LANCZOS4)
    mk = np.zeros((side, side), np.float32)
    mk[by0 - sy:by1 - sy, bx0 - sx:bx1 - sx] = 1
    mk = cv2.GaussianBlur(mk, (0, 0), 6)
    img[sy:sy + side, sx:sx + side] = cv2.blendLinear(res, crop, mk, 1 - mk)
    o2 = io.BytesIO(); Image.fromarray(img).save(o2, "JPEG", quality=94)
    open("/app/memory/p9/arms_fixed.jpg", "wb").write(o2.getvalue())
    open("/app/memory/p9/arms_crop_raw.jpg", "wb").write(out)
    print("DONE", sx, sy, side, reg is not None)

asyncio.run(m())
