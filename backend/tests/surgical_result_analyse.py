# Offline analysis of an EXISTING surgical (FASHN) try-on result vs the original avatar. Never triggers a generation.
import sys, io
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import numpy as np, cv2
from PIL import Image
import server, head_lock

ORIG = "vfit/avatar/user_389c87aaadc6/e2bf1a90a05440ab97ba1d73de3e7ecf.bin"
RES = "vfit/tryon/user_389c87aaadc6/349f217bb3d344cbbfde6699c81415dc.jpg"
HANDS = [[275, 555, 374, 696], [583, 382, 668, 458]]
LOWER = [537, 453, 642, 709]

ob, _ = server.get_object(ORIG)
rb, _ = server.get_object(RES)
mj = head_lock.downscale(ob, head_lock.PERSON_MAX_SIDE)
o = np.array(Image.open(io.BytesIO(mj)).convert("RGB"))
r = np.array(Image.open(io.BytesIO(rb)).convert("RGB"))
print("orig", o.shape, "res", r.shape)
if r.shape != o.shape:
    r = cv2.resize(r, (o.shape[1], o.shape[0]), interpolation=cv2.INTER_LANCZOS4)
H, W = o.shape[:2]
d = np.abs(o.astype(np.int16) - r.astype(np.int16)).mean(axis=2)
face = head_lock._face_box(o)
print("face", face)
fx, fy, fw, fh = face


def reg(name, y0, y1, x0, x1):
    y0, y1, x0, x1 = max(0, int(y0)), min(H, int(y1)), max(0, int(x0)), min(W, int(x1))
    dd = d[y0:y1, x0:x1]
    print(f"{name:28s} [{y0}:{y1},{x0}:{x1}] mean diff {dd.mean():6.2f}  >12: {(dd > 12).mean() * 100:5.1f}%")
    return dd


reg("face box", fy, fy + fh, fx, fx + fw)
reg("hair above face", fy - 0.5 * fh, fy, fx, fx + fw)
reg("chin->+0.3fh (bib zone)", fy + fh, fy + 1.3 * fh, fx, fx + fw)
reg("bg top-left", 0, H * 0.15, 0, W * 0.15)
reg("bg top-right", 0, H * 0.15, W * 0.85, W)
reg("bg bottom-left", H * 0.85, H, 0, W * 0.15)
for i, b in enumerate(HANDS):
    y0, x0, y1, x1 = [v / 1000 for v in b]
    reg(f"hand{i} box", y0 * H, y1 * H, x0 * W, x1 * W)
y0, x0, y1, x1 = [v / 1000 for v in LOWER]
reg("lower (trousers)", y0 * H, y1 * H, x0 * W, x1 * W)
reg("legs bottom 30%", H * 0.68, H, W * 0.2, W * 0.8)

# Skin check: new skin in result where original was not skin, and skin rectangle around hand0 inside the torso
so, sr = head_lock._skin(o) > 0, head_lock._skin(r) > 0
for i, b in enumerate(HANDS):
    y0, x0, y1, x1 = [v / 1000 for v in b]
    Y0, Y1, X0, X1 = int(y0 * H), int(y1 * H), int(x0 * W), int(x1 * W)
    print(f"hand{i}: skin orig {so[Y0:Y1, X0:X1].mean() * 100:.1f}% skin res {sr[Y0:Y1, X0:X1].mean() * 100:.1f}%  "
          f"res skin where orig not skin {(sr & ~so)[Y0:Y1, X0:X1].mean() * 100:.1f}%  skin both {(sr & so)[Y0:Y1, X0:X1].mean() * 100:.1f}%")
print("global new skin (res skin & not orig skin): %.2f%%" % ((sr & ~so).mean() * 100))

# Crops for visual review
def crop(name, y0, y1, x0, x1):
    y0, y1, x0, x1 = max(0, int(y0)), min(H, int(y1)), max(0, int(x0)), min(W, int(x1))
    side = np.concatenate([o[y0:y1, x0:x1], r[y0:y1, x0:x1]], axis=1)
    Image.fromarray(side).save(f"/tmp/sa_{name}.jpg", quality=85)

crop("full", 0, H, 0, W)
crop("head", fy - 0.6 * fh, fy + 2.2 * fh, fx - 1.0 * fw, fx + 2.0 * fw)
b = HANDS[0]; crop("hand0", b[0] / 1000 * H - 80, b[2] / 1000 * H + 80, b[1] / 1000 * W - 80, b[3] / 1000 * W + 80)
b = HANDS[1]; crop("hand1", b[0] / 1000 * H - 60, b[2] / 1000 * H + 60, b[1] / 1000 * W - 60, b[3] / 1000 * W + 60)
dm = np.clip(d * 4, 0, 255).astype(np.uint8)
Image.fromarray(dm).save("/tmp/sa_diffmap.jpg", quality=80)
