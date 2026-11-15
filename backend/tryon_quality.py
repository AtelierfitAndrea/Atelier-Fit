"""Shared try-on render pipeline: Nano Banana Pro 2K, quality check with up to 2 fix passes, signature watermark."""
import asyncio
import base64
import gc
import io
import json
import logging
import os
import re
import time
import uuid

import cv2
import numpy as np

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from starlette.concurrency import run_in_threadpool
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

import fal_tryon
import head_lock
import pose_lock

logger = logging.getLogger(__name__)
# 3 parallel variants: their API calls overlap, the heavy pixel merge runs one at a time (memory).
_HEAVY = asyncio.Semaphore(1)


async def _heavy(fn, *a):
    async with _HEAVY:
        return await run_in_threadpool(fn, *a)


def _pose_dev(canvas: np.ndarray, out_png: bytes, upper_only: bool = False):
    res = np.array(Image.open(io.BytesIO(out_png)).convert("RGB"))
    if res.shape[:2] != canvas.shape[:2]:
        res = np.array(Image.fromarray(res).resize((canvas.shape[1], canvas.shape[0])))
    return pose_lock.deviation(canvas, res, upper_only)


MODELS = ("gemini-3-pro-image-preview", "gemini-3.1-flash-image-preview")
QC_MODEL = "gemini-3.8-flash"
MAX_FIXES = 2
MARKS = {"free": ("Creato con My Atelier", 0.034, 215), "pro": ("myatelierapp.it", 0.024, 140)}
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

FIX_SYSTEM = ("You are a retoucher for virtual try-on photos. You make minimal, local corrections to face and hands, "
              "and change clothing only when the FIX list explicitly names a clothing defect.")


SCENE_RULE = ("\n\nSCENE — STRICT: keep EXACTLY the same background, room, objects, props held in the hands, pose, framing and camera angle "
              "as IMAGE 1. Change ONLY the requested clothes.")


def _fix_prompt(issues: str, garments_txt: str, phone: bool = False) -> str:
    phone_txt = ("• IMAGE 2 shows the person holding a smartphone: use IMAGE 2 ONLY as the face identity reference. NEVER copy the phone, that hand's grip "
                 "or any clothing from IMAGE 2. The output must contain NO smartphone: that hand stays empty, relaxed, 5 fingers.\n") if phone else ""
    return (
        "IMAGE 1 is a virtual try-on result. IMAGE 2 is the original photo of the SAME person. Edit IMAGE 1 minimally.\n"
        "IMAGE 2 is a reference for the face only: never copy clothing from IMAGE 2.\n"
        f"{phone_txt}"
        "KEEP EXACTLY AS IN IMAGE 1 (do not touch), unless the FIX list below names that item:\n"
        f"• The requested clothing — {garments_txt} — plus any other clothing visible in IMAGE 1, INCLUDING the trousers/pants/"
        "skirt, shoes and outerwear: same items, colours, logos, patterns, fit, length and folds. Never invent new garments or shoes.\n"
        "• Background, lighting, pose, body, framing and image size.\n"
        f"FIX ONLY: {issues or 'face and hands'}.\n"
        "• If the issues mention a tucked-in shirt/t-shirt, pull it OUT so its hem hangs outside the trousers.\n"
        "• If the issues mention a requested garment that is missing or not applied (e.g. the old trousers still worn instead of the new shorts), "
        "replace that item with the requested garment from the list above; if they mention a leftover old garment layer, remove it. "
        "These are the only garment changes allowed.\n"
        "• If the issues mention a smartphone, remove it completely and leave that hand empty and relaxed with 5 fingers.\n"
        "• Face: identical to IMAGE 2 (same person, same features, skin tone and hair), a single face, no ghost face, no halo.\n"
        "• Hands: exactly 5 natural, well-formed fingers per hand, no fused or extra fingers. If a hand cannot be made perfect, "
        "hide it naturally (in a pocket, behind the body or the garment).\n"
    )


SEATED_SKIN_MAX = 0.3  # share of the original bare-leg skin still skin: ~0.2 = covered (toes, warm shadows), ~0.4 = a bare leg


def _png(rgb: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "PNG")
    return buf.getvalue()


SEATED_FIX_PROMPT = (
    "IMAGE 1 is a finished virtual try-on photo of a SEATED person. The FLAT GREY areas on the legs are bare skin that the garment must cover "
    "(SEATED RULE: no leg may peek out from under a long garment). Fill EVERY grey area with the SAME garment fabric worn in IMAGE 1 "
    "(IMAGE 2 is the product shot): same colour, sheen and weight, continuing the existing folds naturally over the crossed / bent legs down to "
    "the ankles, so BOTH legs are fully and symmetrically covered. Only the feet / toes may show below the hem.\n"
    "Change NOTHING else: face, hair, hands, fingers, arms, feet, background, floor, framing and image size stay pixel-identical to IMAGE 1. "
    "Never draw skin in the grey areas, never leave any grey, no slit, no hole, no halo.\n"
)


async def _seated_legs_check(out: bytes, canvas: np.ndarray, seated: dict, garment: list, tag: str, aspect: str) -> bytes:
    """SEATED RULE 3 (permanent): bare leg skin left under a long garment (free pixel check) -> ONE cover pass that only fills those
    areas with the same fabric; everything else stays the first result. Never more than this single extra generation."""
    fin = np.array(Image.open(io.BytesIO(out)).convert("RGB"))
    if fin.shape[:2] != canvas.shape[:2]:
        return out
    left = legs_skin_left(fin, canvas, seated["bare"])
    if left <= SEATED_SKIN_MAX:
        log_legs_outcome("seated", "pass", tag=tag, skin_left=round(left, 3))
        return out
    sk = head_lock._skin(fin) > 0
    grey = cv2.dilate(((seated["bare"] > 0) & sk).astype(np.uint8), np.ones((7, 7), np.uint8))
    # Hands, feet, arms, face: only big real skin areas (a red/grey anti-aliased hem edge looks skin-toned but is not protected).
    p = cv2.morphologyEx((sk & (seated["bare"] == 0) & (grey == 0)).astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(p, 8)
    big = st[:, cv2.CC_STAT_AREA] >= 0.002 * p.size
    big[0] = False
    protect = big[lab]
    grey[protect] = 0
    send = fin.copy()
    send[grey > 0] = head_lock.SEATED_GREY
    small = Image.fromarray(send)
    small.thumbnail((head_lock.PERSON_MAX_SIDE, head_lock.PERSON_MAX_SIDE), Image.LANCZOS)
    logger.info(f"{tag}: seated legs show skin ({left:.0%}), one cover pass")
    try:
        raw = await _image_call("You are a retoucher: you only fill the marked grey areas with the garment fabric.", SEATED_FIX_PROMPT,
                                [ImageContent(base64.b64encode(_png(np.array(small))).decode()), *garment], f"{tag}-seatfix", aspect)
    except Exception as e:
        logger.warning(f"{tag}: seated cover pass failed, first result kept: {e}")
        log_legs_outcome("seated", "delivered_with_warning", tag=tag, skin_left=round(left, 3))
        return out
    with open(f"/tmp/seatfix_raw_{tag}_{uuid.uuid4().hex[:6]}.png", "wb") as f:  # kept for free offline re-merge checks
        f.write(raw)
    fixed = await run_in_threadpool(seated_cover_merge, fin, raw, canvas, seated, grey, protect)
    left2 = legs_skin_left(fixed, canvas, seated["bare"])
    log_legs_outcome("seated", "corrected" if left2 <= SEATED_SKIN_MAX else "delivered_with_warning", tag=tag,
                     first={"skin_left": round(left, 3)}, second={"skin_left": round(left2, 3)})
    return _png(fixed) if left2 < left else out


def seated_cover_merge(fin: np.ndarray, raw: bytes, canvas: np.ndarray, seated: dict, grey: np.ndarray, protect: np.ndarray) -> np.ndarray:
    """The whole lower garment comes from the cover pass (grey areas + legs + every pixel either image changed below the hips),
    wide feather on the floor where both images match: no patch, no double hem edge. Hands/feet stay from the first result."""
    H, W = fin.shape[:2]
    res = np.array(head_lock._open_small(raw, max(H, W)).convert("RGB"))
    reg = head_lock._register(fin, res)
    if reg is None:
        reg = cv2.resize(res, (W, H), interpolation=cv2.INTER_LANCZOS4)
    bl = lambda a: cv2.GaussianBlur(a, (0, 0), 1.0).astype(np.int16)  # noqa: E731
    chg = ((np.abs(bl(fin) - bl(canvas)).mean(axis=2) > 20) | (np.abs(bl(reg) - bl(canvas)).mean(axis=2) > 20)).astype(np.uint8)
    chg = cv2.morphologyEx(chg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    kp = seated["kp"]
    chg[:int(min(kp[11, 1], kp[12, 1]))] = 0
    region = ((cv2.dilate(seated["force"], cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))) > 0) | (cv2.dilate(grey, np.ones((9, 9), np.uint8)) > 0)
              | (cv2.dilate(chg, np.ones((21, 21), np.uint8)) > 0))
    wgt = cv2.GaussianBlur(region.astype(np.float32), (0, 0), 6.0) * (1 - cv2.GaussianBlur(protect.astype(np.float32), (0, 0), 1.0))
    return cv2.blendLinear(reg, fin, wgt, 1 - wgt)


def _snapshot(lock: dict) -> dict:
    return {"canvas": lock["canvas"].copy(), "mask": lock["mask"].copy(), "face": lock["face"], "hands": list(lock["hands"]), "pose": lock.get("pose", False),
            "pads_px": lock.get("pads_px", (0, 0)), "freeze": list(lock.get("freeze", [])), "seated": lock.get("seated")}


def _aspect(lock: dict) -> str:
    h, w = lock["canvas"].shape[:2]
    return min(_RATIOS, key=lambda k: abs(_RATIOS[k] - w / h))


# REGOLA ASSOLUTA MY ATELIER (owner, non modificabile): fixed system prompt of EVERY image-model call.
REGOLA_FISSA_MY_ATELIER = """
1. PRENDI la foto base caricata dall'utente.
2. RIMUOVI COMPLETAMENTE i vestiti della foto base.
   - Elimina al 100% il costume, body, reggiseno, mutande, o qualsiasi capo presente nella foto base.
   - Non deve rimanere NESSUNA traccia del vestito originale.
   - Non deve essere visibile NESSUN vestito sotto il nuovo vestito.
3. METTI SOLO i vestiti caricati dall'utente negli slot.
   - SLOT 1 = capo superiore
   - SLOT 2 = capo inferiore
   - SLOT 3 = scarpe
   - SLOT 4 = giacca / accessorio
   - SLOT 5 = borsa
   - Usa SOLO questi. Non inventare altri capi. Non aggiungere strati.
4. VIETATO LAYERING:
   - Vietato mostrare il vestito base sotto il vestito nuovo.
   - Vietato mostrare tessuto nero sotto tessuto rosso.
   - Vietato mostrare body sotto pantaloni.
   - Il nuovo vestito deve stare DIRETTAMENTE sul corpo.
5. MANTIENI invariati: stessa donna, stessa faccia, stessa posa, stesso corpo, stesso sfondo, stessa luce.
   Cambia SOLO i vestiti.
6. Se il vestito originale è ancora visibile, il risultato è SBAGLIATO e deve essere rigenerato.
"""
OLD_CLOTHES_MAX_REGEN = 2


async def old_clothes_qc(person_bytes: bytes, result: bytes, garments_txt: str) -> dict:
    """REGOLA FISSA check (cheap text model): old clothes of the base photo still visible? garments not in the slots? double layer?"""
    a = await run_in_threadpool(head_lock.downscale, person_bytes, head_lock.GARMENT_MAX_SIDE)
    b = await run_in_threadpool(head_lock.downscale, result, head_lock.GARMENT_MAX_SIDE)
    prompt = (
        "IMAGE 1 is the base photo of a person wearing her ORIGINAL clothes. IMAGE 2 is a virtual try-on of the same person.\n"
        f"The ONLY garments allowed in IMAGE 2: {garments_txt}.\n"
        "Return ONLY JSON: {\"old_clothes_visible\": bool, \"extra_garments\": bool, \"double_layer\": bool, \"solid_parts_not_solid\": bool, "
        "\"sleeves_detached\": bool, \"pants_incomplete\": bool, \"coverage_wrong\": bool, \"not_fitting_pose\": bool, \"edge_artifacts\": bool, "
        "\"outfit_incomplete\": bool, \"local_artifacts\": bool, "
        "\"issues\": \"short English list\"}\n"
        "solid_parts_not_solid: waistband, hips, seams, buttons or hems are see-through or missing (a garment made only of transparency).\n"
        "sleeves_detached: a sleeve is floating, cut or not continuous with the top at the shoulder, or does not follow the arm.\n"
        "pants_incomplete: trousers without a solid opaque waist/hips, or with missing parts of the legs.\n"
        "coverage_wrong: through lace / sheer fabric you see bare skin instead of an opaque lining, a separate bra or detached / floating black "
        "straps are visible, or the original underwear of IMAGE 1 is visible.\n"
        "outfit_incomplete: a requested garment is not fully worn (no trousers / bare legs where trousers were requested, missing top), "
        "the figure is not full body head to feet, feet or shoes are cut / touch the photo edge, or the photo is zoomed, cropped or an inset "
        "(phone screen, frame, rounded card).\n"
        "local_artifacts: black or dark blurred smudges, local blur, doubled / ghost parts, double fingers or toes, deformed feet or hands, "
        "shoes / sandals fused with the floor — check feet, hands, shoes and the floor right around them.\n"
        "IGNORE fabric scraps, debris or objects on the floor outside the body: they are cleaned afterwards, never flag them.\n"
        "not_fitting_pose: the garment does not drape on the real pose (seated/standing), floats or is pasted flat.\n"
        "edge_artifacts: white patches, colour smudges or halos ON or right around the body (not on the floor).\n"
        "old_clothes_visible: any piece of the ORIGINAL clothing of IMAGE 1 (bodysuit, swimsuit, bra, underwear, tank, old trousers...) is "
        "still visible in IMAGE 2 — under, through (see-through fabric), around or instead of the new garments.\n"
        "extra_garments: IMAGE 2 shows a garment layer that is neither in the allowed list nor original skin (invented base layer, extra top).\n"
        "double_layer: one garment shows another fabric under it that is not in the allowed list (e.g. black fabric under a red lace top, "
        "a body under the trousers). A nude or black OPAQUE LINING under a lace / sheer garment belongs to the new garment (correct, "
        "not a double layer); a bra or separate straps are NOT allowed.\n"
        "Do NOT flag parts of an allowed garment: a solid waistband, lined panel or darker lace of allowed black trousers belongs to the "
        "trousers. Flag only what clearly is ANOTHER garment, typically the original one of IMAGE 1 continuing where no allowed garment "
        "is (e.g. black bodysuit fabric on the belly, chest or under the neckline, straps on the shoulders, swimsuit edges on the hips).\n"
    )
    try:
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"oldc-{uuid.uuid4().hex[:8]}",
                       system_message="You are a strict fashion photo inspector. Reply with JSON only.")
        chat.with_model("gemini", QC_MODEL)
        reply = await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(base64.b64encode(a).decode()),
                                                                               ImageContent(base64.b64encode(b).decode())]))
    except Exception as e:
        logger.warning(f"old clothes qc failed, not blocking: {e}")
        return {"ok": True, "bad": 0, "incomplete": 0, "issues": ""}
    d = _extract(reply)
    bad = sum(d.get(k) is True for k in ("old_clothes_visible", "extra_garments", "double_layer", "solid_parts_not_solid", "sleeves_detached",
                                          "pants_incomplete", "coverage_wrong", "not_fitting_pose", "edge_artifacts", "outfit_incomplete", "local_artifacts"))
    # COMPLETE outfit first (top + trousers worn, full body, no inset): an incomplete photo always ranks below a complete one.
    inc = int(any(d.get(k) is True for k in ("outfit_incomplete", "pants_incomplete", "solid_parts_not_solid")))
    return {"ok": bad == 0, "bad": bad, "incomplete": inc, "artifacts": d.get("local_artifacts") is True, "issues": str(d.get("issues") or "")[:400]}


async def transparent_qc(garment: bytes) -> str:
    """Emergent fallback for the transparency detection (cheap text model) -> none|light|high."""
    small = await run_in_threadpool(head_lock.downscale, garment, 768)
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"transp-{uuid.uuid4().hex[:8]}", system_message="Reply with one word.")
    chat.with_model("gemini", QC_MODEL)
    reply = await chat.send_message(UserMessage(text=fal_tryon.TRANSP_PROMPT, file_contents=[ImageContent(base64.b64encode(small).decode())]))
    return fal_tryon.level(reply)


def coverage_rule(level: str, category: str, name: str) -> str:
    """COVERAGE (owner rule): every transparent garment over an OPAQUE lining; never a bra added, never detached straps."""
    if level not in ("light", "high"):
        return ""
    cat = (category or "").lower()
    head = f"\nCOVERAGE — TRANSPARENT GARMENT ({name or cat}):\n"
    if cat == "bottom":
        return head + ("• Waistband and hips SOLID OPAQUE fabric. The lace / sheer parts lie ON TOP of an OPAQUE lining "
                       f"({'nude skin-tone' if level == 'light' else 'same colour as the garment'}) that fully covers the legs under it: "
                       "no see-through to skin, underwear or old clothes.\n")
    return head + ("• Under the lace an OPAQUE LINING fully covers the body (nude skin-tone, or black where the product shows black under the "
                   "lace): no see-through to skin, nothing of IMAGE 1 under it.\n"
                   "• NEVER add a bra or any underwear. NO separate or detached black straps, NO floating straps: the top's own straps / "
                   "shoulders rest ON the shoulders, attached to the top, neckline exactly as the product.\n")


async def debris_boxes(img: bytes) -> list:
    """GLOBAL RULE helper (cheap text model): boxes of fabric scraps / smudges / props OUTSIDE the person, normalised 0-1000."""
    small = await run_in_threadpool(head_lock.downscale, img, 1024)
    prompt = ("Virtual try-on photo of ONE person. Find every defect OUTSIDE the person: fabric scraps, lace or red pieces, colour smudges or "
              "stains, white / grey patches, blurred blobs, props or objects on the floor or the wall that are NOT the person's body, hair, "
              "hands, feet, shoes or the clothes she wears. Look ALSO right next to the body edges (shoulders, sleeves, knees, legs): darker or lighter "
              "patches of floor / wall that do not match the surrounding floor, smears and ghost outlines. Return ONLY JSON: {\"debris\": [{\"box_2d\": [ymin, xmin, ymax, xmax]}]} "
              "normalised 0-1000, each box tight around one defect. Empty list if the floor and background are clean.")
    try:
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"debris-{uuid.uuid4().hex[:8]}",
                       system_message="You are a precise photo retouch inspector. Reply with JSON only.")
        chat.with_model("gemini", QC_MODEL)
        reply = await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(base64.b64encode(small).decode())]))
    except Exception as e:
        logger.warning(f"debris detection failed: {e}")
        return []
    d = _extract(reply)
    return [b["box_2d"] for b in (d.get("debris") or [])[:12] if isinstance(b, dict) and isinstance(b.get("box_2d"), list) and len(b["box_2d"]) == 4]


async def artifact_boxes(img: bytes) -> list:
    """ANTI-ARTEFATTO: boxes (0-1000) of local defects on feet, hands, shoes and the floor around them."""
    small = await run_in_threadpool(head_lock.downscale, img, 1024)
    prompt = ("Virtual try-on photo of ONE person. Find every LOCAL DEFECT: black or dark blurred smudges, locally blurred areas, doubled or "
              "ghost parts, double fingers or toes, deformed feet or hands, shoes / sandals fused with the floor. Check feet, hands, shoes "
              "and the floor right around them first. Return ONLY JSON: {\"defects\": [{\"box_2d\": [ymin, xmin, ymax, xmax]}]} "
              "normalised 0-1000, each box tight around one defect. Empty list if the photo is clean.")
    try:
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"artef-{uuid.uuid4().hex[:8]}",
                       system_message="You are a precise photo retouch inspector. Reply with JSON only.")
        chat.with_model("gemini", QC_MODEL)
        reply = await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(base64.b64encode(small).decode())]))
    except Exception as e:
        logger.warning(f"artifact detection failed: {e}")
        return []
    d = _extract(reply)
    return [b["box_2d"] for b in (d.get("defects") or [])[:4] if isinstance(b, dict) and isinstance(b.get("box_2d"), list) and len(b["box_2d"]) == 4]


ZONE_FIX_PROMPT = (
    "IMAGE 1 is a square crop of a fashion photo. Inside it there is a LOCAL DEFECT (black blurred smudge, local blur, doubled or deformed "
    "foot / hand / shoe, shoe fused with the floor). Return the SAME crop: identical framing, scale, pose, garments, colours and light. "
    "Rebuild ONLY the defect cleanly in HD: one natural foot / hand per side with real shape and 5 toes / fingers, shoes with a clear "
    "outline standing on the floor with a soft natural contact shadow, as sharp as the rest of the photo. Never hide anything with a dark "
    "patch or blur. Change nothing else. No text, no frame.")


async def fix_zone(crop: bytes, tag: str) -> bytes:
    return await _image_call("You are a high-end photo retoucher: minimal local HD repairs only.", ZONE_FIX_PROMPT,
                             [ImageContent(base64.b64encode(crop).decode())], tag, "1:1")


def old_clothes_note(issues: str) -> str:
    return ("\nPREVIOUS ATTEMPT REJECTED (FINAL CHECK): " + issues +
            ". Fix it: remove 100% of the original clothes, rebuild every solid part (waistband, hips, seams, buttons, hems) in opaque fabric, "
            "sleeves and shoulder straps attached to the top, trousers complete, opaque lining under every lace part, no bra, no detached straps, "
            "full body head to feet, nothing on the floor, "
            "garment fitted to the live pose.\n")


async def _image_call(system: str, prompt: str, contents: list, tag: str, aspect: str) -> bytes:
    last = None
    system = REGOLA_FISSA_MY_ATELIER + "\n" + system
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


async def _qc(person_b64: str, result: bytes, garments_txt: str, phone: bool = False) -> dict:
    small = await run_in_threadpool(head_lock.downscale, result, head_lock.GARMENT_MAX_SIDE)
    prompt = (
        "IMAGE 1 is the original photo of a person. IMAGE 2 is an AI virtual try-on of that person. Inspect IMAGE 2 very strictly.\n"
        f"Expected garments worn in IMAGE 2: {garments_txt}.\n"
        "Return ONLY JSON: {\"face_same\": bool, \"hands_ok\": bool, \"garments_ok\": bool, \"phone_present\": bool, \"issues\": \"short English list of defects\"}\n"
        "phone_present: a smartphone is visible anywhere in IMAGE 2.\n"
        "face_same: same person with the same facial features as IMAGE 1, exactly one face, no ghost/second face, no halo, not blurred.\n"
        "hands_ok: every visible hand has exactly 5 well-formed fingers, no fused/extra/missing fingers (true if no hand is visible).\n"
        "garments_ok: every expected garment is worn with its colour, logo and pattern intact and no expected garment is missing. "
        "False if IMAGE 2 still shows the ORIGINAL garment of IMAGE 1 where an expected garment should be (e.g. old long jeans instead of the expected shorts) — "
        "name it in issues as 'missing garment: ...'. "
        "ALSO False if a long trouser/jeans garment is expected but bare skin shows anywhere between the waist and the ankles "
        "(faded or washed denim is fabric, not skin) — unless the expected garment is shorts or a skirt. Ripped, frayed or distressed LONG trousers must still be fully covered: "
        "holes or rips showing skin are bare legs; "
        "name it in issues as 'bare legs: ...'."
    )
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"qc-{uuid.uuid4().hex[:8]}",
                   system_message="You are a strict photo quality inspector. Reply with JSON only.")
    chat.with_model("gemini", QC_MODEL)
    files = [ImageContent(person_b64), ImageContent(base64.b64encode(small).decode())]
    try:
        try:
            reply = await chat.send_message(UserMessage(text=prompt, file_contents=files))
        except Exception as e:
            logger.warning(f"qc call failed, retrying once: {e}")
            chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"qc-{uuid.uuid4().hex[:8]}",
                           system_message="You are a strict photo quality inspector. Reply with JSON only.")
            chat.with_model("gemini", QC_MODEL)
            reply = await chat.send_message(UserMessage(text=prompt, file_contents=files))
    except Exception as e:
        if phone:
            # Unchecked image in phone-removal mode might still show the phone: never accept it blindly.
            logger.warning(f"qc failed twice in phone mode: {e}")
            return {"ok": False, "score": 0, "issues": "smartphone may still be visible — remove it"}
        logger.warning(f"qc failed, accepting image: {e}")
        return {"ok": True, "score": 8, "issues": ""}
    d = _extract(reply)
    face, hands, garments = (d.get(k) is not False for k in ("face_same", "hands_ok", "garments_ok"))
    issues = str(d.get("issues") or "")[:400]
    if phone and d.get("phone_present") is True:
        # Phone removal requested: a candidate still showing a phone is never acceptable.
        return {"ok": False, "score": -1, "issues": ("smartphone still visible — remove it; " + issues)[:400]}
    return {"ok": face and hands and garments, "score": 3 * garments + 3 * face + 2 * hands, "issues": issues}


RIPPED_WORDS = re.compile(r"\b(rip(ped)?|distress(ed)?|destroyed|torn|strappat\w*|strappi|rott[oi]|stracciat\w*)\b", re.I)
BARE_LEG_WORDS = re.compile(r"\b(shorts?|bermuda|pantaloncin\w*|hot ?pants|skirt|gonna|minigonna|mini ?skirt|culottes?)\b", re.I)
metric_sink = None  # set by server: callable(dict) that stores the event (legs_qc_events collection)


def log_legs_outcome(path: str, outcome: str, **kw) -> None:
    """One structured line (+ DB event when a sink is set) per legs-QC decision, to tune the thresholds later.
    outcome: pass | corrected | blocked | delivered_with_warning. path: multipass | fallback | half_body."""
    ev = {"path": path, "outcome": outcome, "at": time.time(), **kw}
    logger.info("LEGS_QC " + json.dumps(ev, default=str))
    if metric_sink:
        try:
            metric_sink(ev)
        except Exception as e:  # metrics never break a render
            logger.warning(f"legs qc metric sink failed: {e}")


def band_skin_left(orig: np.ndarray, result: np.ndarray, top: float = 0.5) -> float:
    """Keypoint-free variant of legs_skin_left for photos without readable legs: lower part of the frame only.
    Returns -1.0 when the original shows too little skin there to judge."""
    H = orig.shape[0]
    y0 = int(H * top)
    zone = np.zeros(orig.shape[:2], bool)
    zone[y0:] = True
    sk = (head_lock._skin(orig) > 0) & zone
    if sk.sum() < LEGS_BAND_MIN_SKIN * zone.sum():
        return -1.0
    return float(((head_lock._skin(result) > 0) & sk).sum() / sk.sum())


LEGS_BAND_MIN_SKIN = 0.08  # original skin must cover this share of the lower half before the keypoint-free check judges
LEGS_BAND_SKIN_MAX = 0.5   # looser than the keypoint check (0.2): hands and bare feet also count as skin in a plain band


def legs_skin_left(final: np.ndarray, base: np.ndarray, zone: np.ndarray, hold: np.ndarray = None) -> float:
    """Deterministic, free check: share of the original bare-leg skin (inside `zone`) that is still skin in the result.
    Returns -1.0 when the original had too little bare skin there to judge (person already in trousers)."""
    sk_base = (head_lock._skin(base) > 0) & (zone > 0)
    if hold is not None:
        sk_base &= ~(hold > 0)
    if sk_base.sum() < 0.03 * max(1, int((zone > 0).sum())):
        return -1.0
    return float(((head_lock._skin(final) > 0) & sk_base).sum() / sk_base.sum())


async def legs_qc(crop_png: bytes, expect_untucked: bool, skin_ok: bool, garments_txt: str) -> dict:
    """Blocking QC for the legs pass: skin between waist and ankle, tucked-in shirt. A QC outage never blocks."""
    prompt = (
        f"IMAGE 1 is a crop (waist to feet) of an AI virtual try-on. Expected bottom/shoes: {garments_txt}.\n"
        "Return ONLY JSON: {\"bare_legs\": bool, \"shirt_tucked\": bool, \"issues\": \"short English list\"}\n"
        "bare_legs: true if bare skin is visible anywhere between the waistband and the ankles, i.e. the trousers are missing, transparent, "
        "cut off or have holes. Faded, washed, bleached, acid-wash, painted or printed fabric is NOT skin (false). "
        + ("Shorts and skirts may legitimately show skin: answer false for them. Long trousers or jeans, even ripped or distressed, must never show skin through rips: answer true if they do.\n" if skin_ok else "\n")
        + "shirt_tucked: true if the shirt/top hem is tucked INSIDE the trousers (false if it hangs outside or no shirt is visible)."
    )
    try:
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"legsqc-{uuid.uuid4().hex[:8]}",
                       system_message="You are a strict photo quality inspector. Reply with JSON only.")
        chat.with_model("gemini", QC_MODEL)
        d = _extract(await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(base64.b64encode(crop_png).decode())])))
    except Exception as e:
        logger.warning(f"legs qc failed, not blocking: {e}")
        return {"bare_legs": False, "shirt_tucked": False, "issues": ""}
    return {"bare_legs": d.get("bare_legs") is True and not skin_ok,
            "shirt_tucked": d.get("shirt_tucked") is True and expect_untucked,
            "issues": str(d.get("issues") or "")[:300]}


def _trim_pad_bands(im: Image.Image, pads=None) -> Image.Image:
    # Remove leftover flat head_lock padding the model did not fill (letterbox look), so the photo ends where the scene ends.
    W, H = im.size
    small = np.asarray(im.convert("L").resize((256, max(1, int(256 * H / W)))), dtype=np.float32)
    sh = small.shape[0]
    flat = small.std(axis=1) < 3.5
    means = small.mean(axis=1)

    def run(rows, ref):
        n = 0
        for r in rows:
            if ref is None or not flat[r] or abs(means[r] - ref) > 4:
                break
            n += 1
        return n
    # The model may re-tint the pad: a perfectly flat edge band (std < 1.2) is trimmed whatever its colour.
    top = max(run(list(range(int(sh * 0.08))), pads[0] if pads else None),
              run(list(range(int(sh * 0.08))), means[0] if small[0].std() < 1.2 else None))
    bot = max(run(list(range(sh - 1, sh - 1 - int(sh * 0.18), -1)), pads[1] if pads else None),
              run(list(range(sh - 1, sh - 1 - int(sh * 0.18), -1)), means[-1] if small[-1].std() < 1.2 else None))
    if top < 3 and bot < 3:
        return im
    k = H / sh
    im = im.crop((0, int(top * k) if top >= 3 else 0, W, H))
    if bot < 3:
        return im
    # FRAMING 1:1: the bottom pad is never cut (feet keep their margin): it becomes floor, mirrored from the rows above it.
    a = np.array(im)
    n = int(bot * k)
    src = a[-2 * n:-n] if a.shape[0] > 2 * n else a[:-n]
    fill = cv2.GaussianBlur(cv2.resize(src[::-1], (a.shape[1], n)), (0, 0), 3)
    a[-n:] = fill
    return Image.fromarray(a)


def watermark(img_bytes: bytes, mark: str = "free", pads=None) -> bytes:
    signature, size_k, alpha = MARKS.get(mark, MARKS["free"])
    im = _trim_pad_bands(Image.open(io.BytesIO(img_bytes)).convert("RGB"), pads)
    W, H = im.size
    font = ImageFont.truetype(FONT_PATH, max(14, int(min(W, H) * size_k)))
    try:
        font.set_variation_by_name("Medium")
    except Exception:
        pass
    x0, y0, x1, y1 = ImageDraw.Draw(im).textbbox((0, 0), signature, font=font)
    tw, th = x1 - x0, y1 - y0
    margin, pad = int(min(W, H) * 0.035), max(6, th // 2)
    px, py = W - margin - tw - pad, H - margin - th - pad
    # Work on a small patch only: no full-size RGBA layers in memory.
    patch = im.crop((px - pad, py - pad, px + tw + 2 * pad, py + th + 2 * pad)).convert("RGBA")
    shadow = Image.new("RGBA", patch.size, (0, 0, 0, 0))
    off = max(1, th // 18)
    ImageDraw.Draw(shadow).text((2 * pad - x0 + off, 2 * pad - y0 + off), signature, font=font, fill=(0, 0, 0, int(alpha * 0.55)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(1, th // 10)))
    text = Image.new("RGBA", patch.size, (0, 0, 0, 0))
    ImageDraw.Draw(text).text((2 * pad - x0, 2 * pad - y0), signature, font=font, fill=(255, 255, 255, alpha))
    patch = Image.alpha_composite(Image.alpha_composite(patch, shadow), text)
    im.paste(patch.convert("RGB"), (px - pad, py - pad))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=94, subsampling=0)
    del im, patch
    gc.collect()
    return buf.getvalue()


async def render(system: str, prompt: str, contents: list, lock: dict, garments_txt: str, tag: str, mark: str = "free") -> bytes:
    """Generate -> head/hand lock -> QC; up to MAX_FIXES face/hands-only fixes that keep all garments. Returns signed JPEG."""
    person_b64 = contents[0].file_content_base64
    if "UNTUCKED TOP" in prompt:
        garments_txt += " — the top must NOT be tucked in: its hem rests cleanly on the waistband (tucked in = garments_ok false)"
    if "SUIT — SHIRT TUCKED IN" in prompt:
        garments_txt += " — complete suit: the shirt must be TUCKED INSIDE the trousers, tie straight inside the jacket (shirt hanging out = garments_ok false)"
    phone = "SMARTPHONE REMOVAL" in prompt
    if "NO INVENTED TATTOOS" in prompt:
        garments_txt += " — arms and legs must show NO tattoo that is not in IMAGE 1, and no beard may be added (invented tattoo/beard = garments_ok false)"
    if phone:
        garments_txt += " — NO smartphone may remain in any hand or anywhere in the image; the former phone hand must be empty and relaxed (phone visible = garments_ok false)"
    aspect = _aspect(lock)
    base = _snapshot(lock)
    # Grey levels of the head_lock padding bands: only rows still showing exactly that pad get trimmed.
    lum = np.array([0.299, 0.587, 0.114], np.float32)
    pads = (float((base["canvas"][0] @ lum).mean()), float((base["canvas"][-1] @ lum).mean()))
    lock.clear()
    surgical = "SURGICAL TRY-ON" in prompt
    if surgical:
        # UNIVERSAL POSE LOCK: the original skeleton (local DWPose, free) is sent as a guide image after all the others.
        # Seated cover: IMAGE 1 has grey legs, the skeleton is read on the original photo.
        skel_src = _png(base["canvas"]) if base.get("seated") else base64.b64decode(person_b64)
        skel = await run_in_threadpool(pose_lock.skeleton_png, skel_src)
        if skel:
            contents = [*contents, ImageContent(base64.b64encode(skel).decode())]
            prompt += ("\nPOSE SKELETON — the LAST image is the body skeleton extracted from IMAGE 1 (white bones, orange joints), same framing. "
                       "The output body MUST overlay this skeleton EXACTLY: every shoulder, elbow, wrist, hip, knee, ankle and foot in the same place. "
                       "It is a guide only: NEVER draw lines, dots or the skeleton in the output.\n")
    raw = await _image_call(system, prompt + QUALITY_RULES, contents, tag, aspect)
    snap = _snapshot(base)
    if surgical and snap["pose"]:
        snap["arms"] = await run_in_threadpool(pose_lock.arm_masks, base["canvas"])
        if snap["arms"] is not None and "BAG IN HAND" in prompt:
            # Carrying a bag is the one case where hand and forearm may change: no original hand/forearm pasted (no ghost hand).
            segs, hands = snap["arms"]
            snap["arms"] = ([sg for sg in segs if sg[0] == "upper"], np.zeros_like(hands))
    out = await _heavy(head_lock.finalize, raw, snap)
    if surgical:
        # STOP rule: exactly ONE generation, no regeneration, no automatic fix loop. Not usable -> error, no credit.
        raw_file = f"/tmp/surgical_raw_{tag}_{uuid.uuid4().hex[:6]}.png"
        with open(raw_file, "wb") as f:  # model output kept for free offline merge checks
            f.write(raw)
        # Half-body photos: legs are invented by design, only shoulders/arms are checked.
        dev = await run_in_threadpool(_pose_dev, base["canvas"], out, "HALF-BODY PHOTO" in prompt)
        logger.info(f"{tag}: pose lock deviation {dev} raw={raw_file}")
        seated_meta = base.get("seated")
        if seated_meta:
            out = await _seated_legs_check(out, base["canvas"], seated_meta, contents[1:len(contents) - (1 if skel else 0)], tag, aspect)
        del raw, contents, base
        # Owner request: no automatic rejection on pose/scene checks, values are only logged.
        logger.info(f"{tag}: pose_fail={snap.get('pose_fail')} (not blocking)")
        if "HALF-BODY PHOTO" in prompt and re.search(r"\bbottom:", garments_txt):
            # Half-body: the photo has no legs, so there is no original skin to compare with (free check impossible).
            # AI check only, one-shot rule kept: it is logged, never blocks, never regenerates.
            try:
                skin_ok = bool(BARE_LEG_WORDS.search(garments_txt))
                q = await legs_qc(await run_in_threadpool(head_lock.downscale, out, head_lock.GARMENT_MAX_SIDE), False, skin_ok, garments_txt)
                log_legs_outcome("half_body", "delivered_with_warning" if q["bare_legs"] else "pass", tag=tag, ai_bare=q["bare_legs"], issues=q["issues"], skin_ok=skin_ok)
            except Exception as e:
                logger.warning(f"{tag}: half-body legs qc skipped: {e}")
        logger.info(f"{tag}: surgical one-shot render delivered")
        if mark is None:  # multi-pass: un-signed PNG of the canvas, the caller finishes it
            return out
        return await run_in_threadpool(watermark, out, mark, pads)
    if snap.get("drift", 0) > head_lock.DRIFT_MAX or snap.get("pose_fail"):
        # The model invented a new scene: one fresh generation that must keep IMAGE 1's background.
        logger.info(f"{tag}: {'pose lock failed (scene/face changed)' if snap.get('pose_fail') else 'background drift %.1f' % snap['drift']}, regenerating once")
        del raw
        try:
            raw = await _image_call(system, prompt + SCENE_RULE + QUALITY_RULES, contents, f"{tag}-scene", aspect)
            snap2 = _snapshot(base)
            out2 = await _heavy(head_lock.finalize, raw, snap2)
            if snap2.get("drift", 0) < snap["drift"] or (snap.get("pose_fail") and not snap2.get("pose_fail")):
                out, snap = out2, snap2
            del out2
        except Exception as e:
            logger.warning(f"{tag}: scene regeneration failed, keeping first result: {e}")
            raw = None
    if snap.get("pose_fail"):
        # SHOW ALWAYS (owner rule): never blocked, delivered as it came out; only logged.
        logger.warning(f"{tag}: pose/face lock not fully kept, delivered anyway")
    del raw, contents
    best, best_score = out, -2
    for attempt in range(MAX_FIXES + 1):
        qc = await _qc(person_b64, out, garments_txt, phone)
        if qc["score"] > best_score:
            best, best_score = out, qc["score"]
        if qc["ok"] or attempt == MAX_FIXES:
            break
        logger.info(f"{tag}: quality check failed (attempt {attempt + 1}): {qc['issues']} — fix pass")
        src = await run_in_threadpool(head_lock.downscale, out, head_lock.PERSON_MAX_SIDE)
        try:
            raw = await _image_call(FIX_SYSTEM, _fix_prompt(qc["issues"], garments_txt, phone),
                                    [ImageContent(base64.b64encode(src).decode()), ImageContent(person_b64)], f"{tag}-fix", aspect)
        except Exception as e:
            logger.warning(f"{tag}: fix pass failed: {e}")
            break
        del src
        fsnap = _snapshot(base)
        fixed = await _heavy(head_lock.finalize, raw, fsnap)
        del raw
        if fsnap.get("pose_fail"):
            # FACE LOCK: a fix output that lost the original head is discarded, never delivered.
            logger.info(f"{tag}: fix pass broke the pose lock, discarded")
            break
        out = fixed
    del base
    return await run_in_threadpool(watermark, best, mark, pads)
