import sys, os, asyncio, base64
sys.path.insert(0, "/app/backend"); os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
import numpy as np, cv2
import head_lock, pose_lock, tryon_quality
from emergentintegrations.llm.chat import ImageContent

D = "/app/memory/p8/"
PROMPT = (
    "IMAGE 1 is a finished fashion photo. Make ONLY ONE local edit, everything else stays pixel-identical (woman, face, red lace top with "
    "knot, sleeves, both hands, the black lace on the legs, sandals, background, light, framing, size):\n"
    "• The SOLID OPAQUE BLACK area in the middle (between the top and the legs, around and below the knot) must not look like a black "
    "bodysuit or base layer: make it the SAME transparent black floral lace as the trouser legs, skin softly visible underneath, with a "
    "thin black high waistband just under the top. No black patch, no swimsuit, no extra layer.\n"
    "Photorealistic, matte real fabric, no halo, no blur.\n"
)


async def main():
    base = cv2.cvtColor(cv2.imread(D + "final4.jpg"), cv2.COLOR_BGR2RGB)
    H, W = base.shape[:2]
    rp = D + "raw5.png"
    if os.path.exists(rp):
        raw = open(rp, "rb").read()
    else:
        raw = await tryon_quality._image_call("You are a retoucher: minimal local edits only.", PROMPT,
                                              [ImageContent(base64.b64encode(tryon_quality._png(base)).decode())], "p8-5", "9:16")
        open(rp, "wb").write(raw)
    res = np.array(head_lock._open_small(raw, max(H, W)).convert("RGB"))
    reg = head_lock._register(base, res)
    if reg is None:
        reg = cv2.resize(res, (W, H), interpolation=cv2.INTER_LANCZOS4)
    kp = pose_lock.keypoints(base)
    g = cv2.cvtColor(base, cv2.COLOR_RGB2GRAY)
    dark = (g < 45).astype(np.uint8)
    col = np.zeros((H, W), np.uint8)
    x0, x1 = int(min(kp[11, 0], kp[12, 0])) - 20, int(max(kp[11, 0], kp[12, 0])) + 20
    y0 = int(min(kp[11, 1], kp[12, 1])) - 110
    y1 = int(max(kp[13, 1], kp[14, 1])) + 10
    col[y0:y1, x0:x1] = 1
    region = cv2.morphologyEx(dark & col, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    hands, _, _ = pose_lock.seated_masks(kp, base.shape)
    for _, m in hands:
        region[m > 0] = 0
    r_, g_ = base[..., 0].astype(int), base[..., 1].astype(int)
    region[(r_ - g_ > 60)] = 0
    region = cv2.dilate(region, np.ones((5, 5), np.uint8))
    w = cv2.GaussianBlur(region.astype(np.float32), (0, 0), 1.5)
    out = cv2.blendLinear(reg, base, w, 1 - w)
    cv2.imwrite(D + "final5.jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(D + "cmp5.jpg", cv2.cvtColor(np.concatenate([base, reg, out], 1)[int(H * .5):int(H * .85)], cv2.COLOR_RGB2BGR))
    print("done", int(region.sum()))

asyncio.run(main())
