"""Real dress length: where the hem falls on the user's real height."""
import base64
import re
from typing import Optional

import httpx

from emergentintegrations.llm.chat import ImageContent, LlmChat, UserMessage

# Hem height from the floor as a fraction of body height, for a garment worn by a 175 cm reference model.
STYLES = {"mini": 0.40, "sopra_ginocchio": 0.32, "ginocchio": 0.27, "midi": 0.18, "maxi": 0.06, "fino_a_terra": 0.0}
STYLE_LABEL = {"mini": "Mini", "sopra_ginocchio": "Sopra il ginocchio", "ginocchio": "Al ginocchio", "midi": "Midi", "maxi": "Maxi", "fino_a_terra": "Fino a terra"}
REF_HEIGHT = 175.0
SHOULDER = 0.818
SHORT_HEIGHT = 165
LONG_CATEGORIES = ("dress", "outerwear")
_POSITIONS = [(0.40, "a metà coscia"), (0.31, "sopra il ginocchio"), (0.255, "al ginocchio"), (0.21, "sotto il ginocchio"),
              (0.14, "a metà polpaccio"), (0.07, "sopra la caviglia"), (0.025, "alla caviglia"), (0.0001, "sfiora terra")]
_LEN_RE = re.compile(r"(?:lunghezza|length|longueur|länge)[^0-9]{0,40}(\d{2,3}(?:[.,]\d)?)\s*cm", re.I)


async def classify(image_bytes: bytes, api_key: str, extract_json) -> dict:
    chat = LlmChat(api_key=api_key, session_id=f"hem-{base64.b16encode(image_bytes[:6]).decode()}", system_message="You are a fashion garment analyst. Reply with JSON only.")
    chat.with_model("gemini", "gemini-3.8-flash")
    prompt = (
        "Look at the dress, gown or coat shown (on a model or as a product shot). Return ONLY JSON:\n"
        '{"long_garment": true|false, "style": "mini|sopra_ginocchio|ginocchio|midi|maxi|fino_a_terra", "length_cm": number|null}\n'
        "long_garment = true only for dresses, gowns, jumpsuits, long skirts on a dress or coats/trench that reach at least mid-thigh. "
        "style = where the hem falls on an average 175 cm model. length_cm only if a length in cm is written in the image, else null."
    )
    data = extract_json(await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(base64.b64encode(image_bytes).decode())]))) or {}
    style = data.get("style") if data.get("style") in STYLES else None
    length = data.get("length_cm")
    return {"long_garment": bool(data.get("long_garment")) and bool(style), "style": style,
            "length_cm": float(length) if isinstance(length, (int, float)) and 50 <= length <= 200 else None}


async def length_from_page(url: Optional[str]) -> Optional[float]:
    # Optional bonus: never blocks the result if the shop page is unreachable.
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as c:
            text = (await c.get(url)).text
        m = _LEN_RE.search(re.sub(r"<[^>]+>", " ", text))
        v = float(m.group(1).replace(",", ".")) if m else None
        return v if v and 50 <= v <= 200 else None
    except Exception:
        return None


def compute(info: dict, height_cm: Optional[float]) -> dict:
    if not info.get("long_garment"):
        return {"applicable": False}
    style = info["style"]
    out = {"applicable": True, "style": style, "style_label": STYLE_LABEL[style], "length_source": info.get("length_source", "photo")}
    if not height_cm:
        return {**out, "needs_height": True}
    length = info.get("length_cm") or (SHOULDER - STYLES[style]) * REF_HEIGHT
    hem = SHOULDER * height_cm - length
    ratio = hem / height_cm
    position = next((label for limit, label in _POSITIONS if ratio >= limit), "tocca terra")
    designed = STYLES[style] * height_cm
    advice = round(designed - hem) if (hem <= 1 or height_cm < SHORT_HEIGHT) else 0
    return {**out, "length_cm": round(length), "height_cm": height_cm, "hem_from_floor_cm": round(max(0.0, hem), 1),
            "touches_floor": hem <= 1, "ratio": round(max(0.0, min(1.0, ratio)), 3), "position_label": position,
            "hem_advice_cm": advice if advice >= 2 else None}
