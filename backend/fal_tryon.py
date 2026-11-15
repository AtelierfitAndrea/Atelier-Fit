"""External try-on for TRANSPARENT garments (owner test switch). Direct fal.ai with the owner's own FAL_KEY (billed on the fal account)."""
import base64
import os

import fal_client
import requests

ENDPOINT = "fal-ai/image-apps-v2/virtual-try-on"


class FalError(Exception):
    pass


CREDIT_WORDS = ("balance", "exhausted", "locked", "insufficient", "credit", "403")


def credit_ok() -> bool:
    """Blocking: tiny fal call (1 token). False ONLY when fal answers that the account has no credit; other errors do not block."""
    key = os.environ.get("FAL_KEY")
    if not key:
        return False
    try:
        fal_client.SyncClient(key=key, default_timeout=20).subscribe(
            "fal-ai/any-llm", arguments={"prompt": "ok", "model": VISION_MODEL, "max_tokens": 1}, interval=0.5)
    except Exception as e:
        return not any(w in str(e).lower() for w in CREDIT_WORDS)
    return True


def _data_url(data: bytes, ct: str) -> str:
    return f"data:{ct};base64,{base64.b64encode(data).decode()}"


def tryon(person: bytes, garment: bytes, ratio: str = "9:16", timeout_s: int = 300) -> bytes:
    """Blocking (run in a threadpool): one submit (never retried), wait for the result, download the image bytes."""
    key = os.environ.get("FAL_KEY")
    if not key:
        raise FalError("FAL_KEY mancante")
    client = fal_client.SyncClient(key=key, default_timeout=timeout_s)
    payload = {"person_image_url": _data_url(person, "image/jpeg"), "clothing_image_url": _data_url(garment, "image/jpeg"),
               "preserve_pose": True, "aspect_ratio": {"ratio": ratio}}
    try:
        result = client.subscribe(ENDPOINT, arguments=payload, interval=1.0)
    except Exception as e:
        raise FalError(str(e)[:300]) from e
    images = (result or {}).get("images") or []
    if not images:
        raise FalError("no image")
    img = requests.get(images[0]["url"], timeout=60)
    img.raise_for_status()
    return img.content


VISION = "openrouter/router/vision"
VISION_MODEL = "google/gemini-2.5-flash"
TRANSP_PROMPT = ("Product photo of a garment. How transparent is it (or a large part of it)? Reply with ONE word: "
                 "NONE (opaque), LIGHT (light / semi-transparent lace, skin only slightly visible), "
                 "HIGH (highly transparent: sheer tulle, mesh, organza, voile, open lace, body clearly visible).")


def level(reply: str) -> str:
    r = str(reply).upper()
    return "high" if "HIGH" in r else ("light" if "LIGHT" in r else "none")


def transparency(garment: bytes) -> str:
    """Blocking: fal vision with the owner's FAL_KEY -> none|light|high. Raises FalError when fal does not answer (caller falls back)."""
    key = os.environ.get("FAL_KEY")
    if not key:
        raise FalError("FAL_KEY mancante")
    client = fal_client.SyncClient(key=key, default_timeout=60)
    try:
        r = client.subscribe(VISION, arguments={"prompt": TRANSP_PROMPT, "model": VISION_MODEL, "temperature": 0, "max_tokens": 5,
                                                "image_urls": [_data_url(garment, "image/jpeg")]}, interval=0.5)
    except Exception as e:
        raise FalError(str(e)[:300]) from e
    return level((r or {}).get("output", ""))
