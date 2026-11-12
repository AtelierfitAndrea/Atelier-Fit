import sys, os, asyncio, base64
sys.path.insert(0, "/app/backend"); os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
import numpy as np, cv2
import server, head_lock, pose_lock, tryon_quality
from emergentintegrations.llm.chat import ImageContent

D = "/app/memory/p8/"
N = sys.argv[1]
PROMPT = (
    "IMAGE 1 is a finished fashion photo. Edit ONLY the lower part (trousers and shoes); everything above the hips stays pixel-identical.\n"
    "• KEEP EXACTLY: the same woman, face, expression, hair, skin tone; the red lace top unchanged (same lace, deep V-neck, long flared "
    "sleeves, knot at the waist, same fit and colour); the pose (seated on the floor, legs crossed, hands clasped in front: 2 hands, "
    "10 fingers, unchanged); the background and light; framing and image size.\n"
    "• NEW TROUSERS: replace the white trousers with normal OPAQUE BLACK trousers: solid black fabric (NOT transparent, NOT sheer), "
    "high waist, clean realistic fit on the crossed legs with natural matte folds, waistband and hems.\n"
    "• The red lace top is real photographed fabric: never redraw it, never make it shiny, plastic, illustrated or saturated.\n"
    "• NEW SHOES: two black wedge sandals, one on each foot (2 feet, 2 shoes), same style on both, correctly placed on the feet even with "
    "crossed legs, realistic straps and wedge heel. Replace the red heels.\n"
    "• Photorealistic, soft natural studio light, high detail.\n"
)


async def main():
    base = cv2.cvtColor(cv2.imread("/app/memory/p7/baseA.jpg"), cv2.COLOR_BGR2RGB)
    H, W = base.shape[:2]
    rp = D + f"raw{N}.png"
    if os.path.exists(rp):
        raw = open(rp, "rb").read()
    else:
        raw = await tryon_quality._image_call("You are a fashion retoucher: precise local garment edits, photorealistic.", PROMPT,
                                              [ImageContent(base64.b64encode(tryon_quality._png(base)).decode())], f"p8-{N}", "9:16")
        open(rp, "wb").write(raw)
    res = np.array(head_lock._open_small(raw, max(H, W)).convert("RGB"))
    reg = head_lock._register(base, res)
    if reg is None:
        reg = cv2.resize(res, (W, H), interpolation=cv2.INTER_LANCZOS4)
    kp = pose_lock.keypoints(base)
    hip = int(min(kp[11, 1], kp[12, 1]))
    # Lower region from the edit, everything above the hips from BASE A.
    region = np.zeros((H, W), np.float32)
    region[hip - 90:] = 1
    region = cv2.GaussianBlur(region, (0, 0), 6)
    # Top pieces over the legs (knot, sleeve lace = red) and the hands stay from BASE A.
    red = ((base[..., 0].astype(int) - base[..., 1] > 70) & (base[..., 0] > 90)).astype(np.uint8)
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(red, 8)
    keepc = np.zeros(n, bool)
    for i in range(1, n):
        keepc[i] = st[i, 1] < hip + 40 and st[i, 4] > 300  # pieces of the top (knot, sleeves); shoes and floor tails go
    top = keepc[lab] & (np.arange(H)[:, None] < int(H * 0.74))
    hands, _, _ = pose_lock.seated_masks(kp, base.shape)
    hm = np.zeros((H, W), np.uint8)
    for _, m in hands:
        hm |= m
    sk = head_lock._skin(base) > 0
    hand = cv2.erode(((hm > 0) & sk).astype(np.uint8), np.ones((5, 5), np.uint8))
    prot = cv2.GaussianBlur((top | (hand > 0)).astype(np.float32), (0, 0), 1.0)
    w = np.clip(region * (1 - prot), 0, 1)
    out = cv2.blendLinear(reg, base, w, 1 - w)
    cv2.imwrite(D + f"out{N}.jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 94])
    cv2.imwrite(D + f"reg{N}.jpg", cv2.cvtColor(reg, cv2.COLOR_RGB2BGR))
    print("done", hip)

asyncio.run(main())
