import sys, os, asyncio, base64
sys.path.insert(0, "/app/backend"); os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
import numpy as np, cv2
import head_lock, pose_lock, tryon_quality
from emergentintegrations.llm.chat import ImageContent

D = "/app/memory/p8/"
PROMPT = (
    "IMAGE 1 is a finished fashion photo. Make ONLY these two local edits, everything else stays pixel-identical (woman, face, red lace top, "
    "sleeves above the floor, arms, both hands clasped on the crossed knees, black lace trousers, background, light, framing, size):\n"
    "1. Remove the red lace fabric pieces lying on the floor on the left and on the right: clean empty studio floor there, no scraps.\n"
    "2. Replace the sandals with 2 realistic black wedge sandals (closed wedge heel, ankle strap), one on each foot, same style on both.\n"
    "Photorealistic, no halo, no blur.\n"
)


async def main():
    base = cv2.cvtColor(cv2.imread(D + "final3.jpg"), cv2.COLOR_BGR2RGB)
    H, W = base.shape[:2]
    rp = D + "raw4.png"
    if os.path.exists(rp):
        raw = open(rp, "rb").read()
    else:
        raw = await tryon_quality._image_call("You are a retoucher: minimal local edits only.", PROMPT,
                                              [ImageContent(base64.b64encode(tryon_quality._png(base)).decode())], "p8-4", "9:16")
        open(rp, "wb").write(raw)
    res = np.array(head_lock._open_small(raw, max(H, W)).convert("RGB"))
    reg = head_lock._register(base, res)
    if reg is None:
        reg = cv2.resize(res, (W, H), interpolation=cv2.INTER_LANCZOS4)
    kp = pose_lock.keypoints(base)
    r, g = base[..., 0].astype(int), base[..., 1].astype(int)
    red = ((r - g > 70) & (r > 90)).astype(np.uint8)
    # Floor lace: red outside the body column (beyond the knees) in the lower part.
    xs = [kp[i, 0] for i in (13, 14) if kp[i, 2] > 0.3]
    lo, hi = (int(min(xs)) - 10, int(max(xs)) + 10) if len(xs) == 2 else (int(W * .15), int(W * .85))
    floor = red.copy()
    floor[:int(H * 0.68)] = 0
    floor[:int(H * 0.73), lo:hi] = 0
    region = cv2.dilate(floor, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    for i in range(17, 23):
        if kp[i, 2] > 0.3:
            cv2.circle(region, tuple(np.int32(kp[i, :2])), int(W * 0.09), 1, -1)
    w = cv2.GaussianBlur(region.astype(np.float32), (0, 0), 3.0)
    out = cv2.blendLinear(reg, base, w, 1 - w)
    cv2.imwrite(D + "final4.jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 94])
    cv2.imwrite(D + "cmp4.jpg", cv2.cvtColor(np.concatenate([reg, out], 1), cv2.COLOR_RGB2BGR))
    print("done", lo, hi)

asyncio.run(main())
