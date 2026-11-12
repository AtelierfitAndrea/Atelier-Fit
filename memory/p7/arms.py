import sys, os, asyncio, base64, io, uuid
sys.path.insert(0, "/app/backend"); os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv(".env")
import numpy as np, cv2
from PIL import Image
import server, head_lock, pose_lock, tryon_quality
from emergentintegrations.llm.chat import ImageContent

D = "/app/memory/p7/"
PROMPT = (
    "IMAGE 1 is a finished fashion photo. Edit it MINIMALLY: the person's forearms and hands are missing. ADD ONLY the forearms and hands.\n"
    "• Arms come down naturally from the shoulders inside the red lace bell sleeves; each sleeve ends cleanly at the wrist (no trailing "
    "lace, no pieces on the floor). Below the sleeves: bare wrists and the two hands joined in front, between the crossed legs, one over "
    "the other, resting on the legs — exactly like the hands in IMAGE 2 (same skin tone, same fingers). 5 complete, real fingers per hand.\n"
    "• Change NOTHING else: the red lace top (same lace, same light, same folds), the white trousers, the red shoes, the face, hair, pose, "
    "background, framing and image size stay pixel-identical to IMAGE 1.\n"
    "• NEGATIVE: cartoon, flat, plastic, glossy fake fabric, halo around arms or hands, brown stains, extra fingers, hands hidden in sleeves.\n"
)


async def main():
    base = cv2.cvtColor(cv2.imread(D + "result.jpg"), cv2.COLOR_BGR2RGB)
    person = open(D + "person.jpg", "rb").read()
    H, W = base.shape[:2]
    if os.path.exists(D + "arms_raw.png"):
        raw = open(D + "arms_raw.png", "rb").read()
    else:
        raw = await tryon_quality._image_call("You are a retoucher: minimal local edits only.", PROMPT,
                                              [ImageContent(base64.b64encode(tryon_quality._png(base)).decode()),
                                               ImageContent(base64.b64encode(head_lock.downscale(person, 1024)).decode())],
                                              "arms-user_389c87aaadc6", "9:16")
        open(D + "arms_raw.png", "wb").write(raw)
    res = np.array(head_lock._open_small(raw, max(H, W)).convert("RGB"))
    reg = head_lock._register(base, res)
    if reg is None:
        reg = cv2.resize(res, (W, H), interpolation=cv2.INTER_LANCZOS4)
    kp = np.load(D + "kf.npy")
    zone = np.zeros((H, W), np.uint8)
    hands, _, _ = pose_lock.seated_masks(kp, base.shape)
    for _, m in hands:
        zone |= m
    for sh, el, wr in ((5, 7, 9), (6, 8, 10)):
        t = max(8, int(0.5 * np.hypot(*(kp[sh, :2] - kp[el, :2]))))
        cv2.line(zone, tuple(np.int32(kp[el, :2])), tuple(np.int32(kp[wr, :2])), 255, t, cv2.LINE_AA)
    zone = cv2.dilate(zone, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
    diff = np.abs(cv2.GaussianBlur(base, (0, 0), 1.0).astype(np.int16) - cv2.GaussianBlur(reg, (0, 0), 1.0).astype(np.int16)).mean(axis=2)
    ch = cv2.morphologyEx((diff > 22).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ch = cv2.morphologyEx(ch, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    m = ((ch > 0) & (zone > 0)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    big = st[:, 4] >= 150; big[0] = False
    m = cv2.dilate(big[lab].astype(np.uint8), np.ones((5, 5), np.uint8))
    w = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.5)
    out = cv2.blendLinear(reg, base, w, 1 - w)
    np.save(D + "arms_out.npy", out)
    cv2.imwrite(D + "arms_out.jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 94])
    cv2.imwrite(D + "arms_reg.jpg", cv2.cvtColor(reg, cv2.COLOR_RGB2BGR))
    print("changed px", int(m.sum()))

asyncio.run(main())
