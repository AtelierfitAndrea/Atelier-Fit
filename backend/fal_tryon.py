"""External try-on for TRANSPARENT garments (owner test switch). Direct fal.ai with the owner's own FAL_KEY (billed on the fal account)."""
import base64
import os

import fal_client
import requests

ENDPOINT = "fal-ai/image-apps-v2/virtual-try-on"


class FalError(Exception):
    pass


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
TRANSP_PROMPT = ("Product photo of a garment. Is the garment (or a large part of it) transparent or semi-transparent: sheer, lace with skin "
                 "showing through, tulle, organza, voile, mesh, chiffon? Reply with ONE word: YES or NO.")


def is_transparent(garment: bytes) -> bool:
    """Blocking: fal vision with the owner's FAL_KEY. Raises FalError when fal does not answer (caller falls back)."""
    key = os.environ.get("FAL_KEY")
    if not key:
        raise FalError("FAL_KEY mancante")
    client = fal_client.SyncClient(key=key, default_timeout=60)
    try:
        r = client.subscribe(VISION, arguments={"prompt": TRANSP_PROMPT, "model": VISION_MODEL, "temperature": 0, "max_tokens": 5,
                                                "image_urls": [_data_url(garment, "image/jpeg")]}, interval=0.5)
    except Exception as e:
        raise FalError(str(e)[:300]) from e
    return "YES" in str((r or {}).get("output", "")).upper()
