"""Shared try-on render pipeline: Nano Banana Pro 2K, quality check with up to 2 fix passes, signature watermark."""
import base64
import gc
import io
import json
import logging
import os
import re
import uuid

import numpy as np

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from starlette.concurrency import run_in_threadpool
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

import head_lock

logger = logging.getLogger(__name__)
MODELS = ("gemini-3-pro-image-preview", "gemini-3.1-flash-image-preview")
QC_MODEL = "gemini-3.8-flash"
MAX_FIXES = 2
SIGNATURE = "myatelierapp.it"
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "PlayfairDisplay.ttf")
_RATIOS = {"1:1": 1, "2:3": 2 / 3, "3:2": 1.5, "3:4": 0.75, "4:3": 4 / 3, "4:5": 0.8, "5:4": 1.25, "9:16": 9 / 16, "16:9": 16 / 9}

QUALITY_RULES = (
    "\nQUALITY — NON-NEGOTIABLE:\n"
    "• POSITIVE: photorealistic try-on, keep original identity 100%, same face, same person, same skin, same body, same background, "
    "same hair, preserve garment color and logo exactly, multibrand multi-outfit, natural fabric draping, realistic shadows, "
    "ultra sharp high resolution, perfect hands with 5 fingers.\n"
    "• NEGATIVE: face changed, second face, double face, deformed hands, 6 fingers, extra fingers, mutated hands, blurred, plastic skin, "
    "cartoon, illustration, logo distorted, color changed, low quality, bad anatomy, extra limbs, halo effect.\n"
    "• Every garment keeps its ORIGINAL colour, logo, print and pattern exactly — no invented colours, no gradients, no distorted logos; "
    "real fabric folds and shadows.\n"
    "• Hands: if a hand is visible, it has exactly 5 perfect fingers. If you are not 100% sure you can draw a hand perfectly, "
    "hide it naturally (in a pocket, behind the body or the garment) — a hidden hand is better than a wrong hand.\n"
)

FIX_SYSTEM = ("You are a retoucher for virtual try-on photos. You make minimal, local corrections to face and hands only, "
              "and never change, add or remove any clothing.")


def _fix_prompt(issues: str, garments_txt: str) -> str:
    return (
        "IMAGE 1 is a virtual try-on result. IMAGE 2 is the original photo of the SAME person. Edit IMAGE 1 minimally.\n"
        "KEEP EXACTLY AS IN IMAGE 1 (do not touch):\n"
        f"• Every clothing item currently worn — {garments_txt} — plus any other clothing visible in IMAGE 1, INCLUDING the trousers/pants/"
        "skirt, shoes and outerwear: same items, colours, logos, patterns, fit, length and folds. Never remove, add or swap a garment.\n"
        "• Background, lighting, pose, body, framing and image size.\n"
        f"FIX ONLY: {issues or 'face and hands'}.\n"
        "• If the issues mention a tucked-in shirt/t-shirt, pull it OUT so its hem hangs outside the trousers — the only garment change allowed.\n"
        "• Face: identical to IMAGE 2 (same person, same features, skin tone and hair), a single face, no ghost face, no halo.\n"
        "• Hands: exactly 5 natural, well-formed fingers per hand, no fused or extra fingers. If a hand cannot be made perfect, "
        "hide it naturally (in a pocket, behind the body or the garment).\n"
    )


def _snapshot(lock: dict) -> dict:
    return {"canvas": lock["canvas"].copy(), "mask": lock["mask"].copy(), "face": lock["face"], "hands": list(lock["hands"])}


def _aspect(lock: dict) -> str:
    h, w = lock["canvas"].shape[:2]
    return min(_RATIOS, key=lambda k: abs(_RATIOS[k] - w / h))


async def _image_call(system: str, prompt: str, contents: list, tag: str, aspect: str) -> bytes:
    last = None
    for model in MODELS:
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"{tag}-{uuid.uuid4().hex[:8]}", system_message=system)
        chat.with_model("gemini", model).with_params(modalities=["image", "text"], image_config={"image_size": "2K", "aspect_ratio": aspect})
        try:
            _t, images = await chat.send_message_multimodal_response(UserMessage(text=prompt, file_contents=contents))
        except Exception as e:
            logger.warning(f"{tag}: {model} failed: {e}")
            last = e
            continue
        if images:
            return base64.b64decode(images[0]["data"])
        last = RuntimeError("no image")
    raise RuntimeError(f"Image generation failed: {last}")


def _extract(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


async def _qc(person_b64: str, result: bytes, garments_txt: str) -> dict:
    small = await run_in_threadpool(head_lock.downscale, result, head_lock.GARMENT_MAX_SIDE)
    prompt = (
        "IMAGE 1 is the original photo of a person. IMAGE 2 is an AI virtual try-on of that person. Inspect IMAGE 2 very strictly.\n"
        f"Expected garments worn in IMAGE 2: {garments_txt}.\n"
        "Return ONLY JSON: {\"face_same\": bool, \"hands_ok\": bool, \"garments_ok\": bool, \"issues\": \"short English list of defects\"}\n"
        "face_same: same person with the same facial features as IMAGE 1, exactly one face, no ghost/second face, no halo, not blurred.\n"
        "hands_ok: every visible hand has exactly 5 well-formed fingers, no fused/extra/missing fingers (true if no hand is visible).\n"
        "garments_ok: every expected garment is worn with its colour, logo and pattern intact and no expected garment is missing."
    )
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"qc-{uuid.uuid4().hex[:8]}",
                   system_message="You are a strict photo quality inspector. Reply with JSON only.")
    chat.with_model("gemini", QC_MODEL)
    try:
        reply = await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(person_b64), ImageContent(base64.b64encode(small).decode())]))
    except Exception as e:
        logger.warning(f"qc failed, accepting image: {e}")
        return {"ok": True, "score": 8, "issues": ""}
    d = _extract(reply)
    face, hands, garments = (d.get(k) is not False for k in ("face_same", "hands_ok", "garments_ok"))
    return {"ok": face and hands and garments, "score": 3 * garments + 3 * face + 2 * hands, "issues": str(d.get("issues") or "")[:400]}


def _trim_pad_bands(im: Image.Image) -> Image.Image:
    # Remove leftover flat head_lock padding the model did not fill (letterbox look), so the photo ends where the scene ends.
    W, H = im.size
    small = np.asarray(im.convert("L").resize((256, max(1, int(256 * H / W)))), dtype=np.float32)
    sh = small.shape[0]
    flat = small.std(axis=1) < 3.5
    means = small.mean(axis=1)

    def run(rows):
        n = 0
        for r in rows:
            if not flat[r] or abs(means[r] - means[rows[0]]) > 4:
                break
            n += 1
        return n
    top = run(list(range(int(sh * 0.08))))
    bot = run(list(range(sh - 1, sh - 1 - int(sh * 0.18), -1)))
    if top < 3 and bot < 3:
        return im
    k = H / sh
    return im.crop((0, int(top * k) if top >= 3 else 0, W, H - int(bot * k) if bot >= 3 else H))


def watermark(img_bytes: bytes) -> bytes:
    im = _trim_pad_bands(Image.open(io.BytesIO(img_bytes)).convert("RGB"))
    W, H = im.size
    font = ImageFont.truetype(FONT_PATH, max(16, int(min(W, H) * 0.034)))
    try:
        font.set_variation_by_name("Medium")
    except Exception:
        pass
    x0, y0, x1, y1 = ImageDraw.Draw(im).textbbox((0, 0), SIGNATURE, font=font)
    tw, th = x1 - x0, y1 - y0
    margin, pad = int(min(W, H) * 0.035), max(6, th // 2)
    px, py = W - margin - tw - pad, H - margin - th - pad
    # Work on a small patch only: no full-size RGBA layers in memory.
    patch = im.crop((px - pad, py - pad, px + tw + 2 * pad, py + th + 2 * pad)).convert("RGBA")
    shadow = Image.new("RGBA", patch.size, (0, 0, 0, 0))
    off = max(1, th // 18)
    ImageDraw.Draw(shadow).text((2 * pad - x0 + off, 2 * pad - y0 + off), SIGNATURE, font=font, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(1, th // 10)))
    text = Image.new("RGBA", patch.size, (0, 0, 0, 0))
    ImageDraw.Draw(text).text((2 * pad - x0, 2 * pad - y0), SIGNATURE, font=font, fill=(255, 255, 255, 215))
    patch = Image.alpha_composite(Image.alpha_composite(patch, shadow), text)
    im.paste(patch.convert("RGB"), (px - pad, py - pad))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=94, subsampling=0, optimize=True)
    del im, patch
    gc.collect()
    return buf.getvalue()


async def render(system: str, prompt: str, contents: list, lock: dict, garments_txt: str, tag: str) -> bytes:
    """Generate -> head/hand lock -> QC; up to MAX_FIXES face/hands-only fixes that keep all garments. Returns signed JPEG."""
    person_b64 = contents[0].file_content_base64
    if "UNTUCKED TOP" in prompt:
        garments_txt += " — the shirt/t-shirt must be worn UNTUCKED, hanging outside the trousers (tucked in = garments_ok false)"
    aspect = _aspect(lock)
    base = _snapshot(lock)
    lock.clear()
    raw = await _image_call(system, prompt + QUALITY_RULES, contents, tag, aspect)
    out = await run_in_threadpool(head_lock.finalize, raw, _snapshot(base))
    del raw, contents
    best, best_score = out, -1
    for attempt in range(MAX_FIXES + 1):
        qc = await _qc(person_b64, out, garments_txt)
        if qc["score"] > best_score:
            best, best_score = out, qc["score"]
        if qc["ok"] or attempt == MAX_FIXES:
            break
        logger.info(f"{tag}: quality check failed (attempt {attempt + 1}): {qc['issues']} — fixing face/hands only")
        src = await run_in_threadpool(head_lock.downscale, out, head_lock.PERSON_MAX_SIDE)
        try:
            raw = await _image_call(FIX_SYSTEM, _fix_prompt(qc["issues"], garments_txt),
                                    [ImageContent(base64.b64encode(src).decode()), ImageContent(person_b64)], f"{tag}-fix", aspect)
        except Exception as e:
            logger.warning(f"{tag}: fix pass failed: {e}")
            break
        del src
        out = await run_in_threadpool(head_lock.finalize, raw, _snapshot(base))
        del raw
    del base
    return await run_in_threadpool(watermark, best)
