"""FASHN v1.6 dedicated virtual try-on via fal.ai (Emergent Universal Key). One generation per call, no retries."""
import base64
import logging
import os
import time
from urllib.parse import urlparse

import requests

logger = logging.getLogger("fashn")

ENDPOINT = "fal-ai/fashn/tryon/v1.6"

# Fal Universal Key supports queue inference through the Emergent proxy only, not Fal Platform APIs.
CONTROL_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "https://integrations.emergentagent.com").rstrip("/") + "/api/v1/fal"
QUEUE_BASE = f"{CONTROL_BASE}/queue"
CATEGORY = {"top": "tops", "outerwear": "tops", "bottom": "bottoms", "dress": "one-pieces", "suit": "one-pieces"}


class TryOnError(Exception):
    pass


class InsufficientCredits(TryOnError):
    pass


def _headers(extra=None):
    h = {"Authorization": f"Bearer {os.environ['EMERGENT_LLM_KEY']}", "Content-Type": "application/json"}
    if os.environ.get("job_id"):
        h["X-App-ID"] = h["X-Job-ID"] = os.environ["job_id"]
    if os.environ.get("run_id"):
        h["X-Environment-ID"] = os.environ["run_id"]
    if extra:
        h.update(extra)
    return h


def _trusted(url: str) -> str:
    c, q = urlparse(url), urlparse(QUEUE_BASE)
    if c.scheme != q.scheme or c.netloc != q.netloc or c.username or c.password or c.fragment or not c.path.startswith(q.path.rstrip("/") + "/"):
        raise TryOnError("untrusted queue URL")
    return url


def _get(url: str, deadline: float, timeout: int = 30) -> requests.Response:
    delay = 1
    for attempt in range(5):
        left = deadline - time.monotonic()
        if left <= 0:
            raise TryOnError("timeout")
        try:
            return requests.get(url, headers=_headers(), timeout=min(timeout, left))
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as e:
            if attempt == 4:
                raise TryOnError("polling failed") from e
            time.sleep(min(delay, max(0.1, deadline - time.monotonic())))
            delay *= 2
    raise AssertionError("unreachable")


def _data_uri(img: bytes) -> str:
    mime = "image/png" if img[:8] == b"\x89PNG\r\n\x1a\n" else "image/webp" if img[8:12] == b"WEBP" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(img).decode()


def tryon(person_jpeg: bytes, garment_jpeg: bytes, category: str, timeout_s: int = 300) -> bytes:
    """Blocking: run in a worker thread. Exactly one submit (never retried); returns the result image bytes."""
    try:
        return _tryon(person_jpeg, garment_jpeg, category, timeout_s)
    except requests.RequestException as e:
        raise TryOnError(f"network/http error: {e}") from e


def _tryon(person_jpeg: bytes, garment_jpeg: bytes, category: str, timeout_s: int) -> bytes:
    payload = {
        "model_image": _data_uri(person_jpeg),
        "garment_image": _data_uri(garment_jpeg),
        "category": CATEGORY.get((category or "").lower(), "auto"),
        "mode": "quality",
        "garment_photo_type": "auto",
        "segmentation_free": False,  # stay inside the clothing segmentation: face, hands, skin and background untouched
        "num_samples": 1,
        "output_format": "png",
        "moderation_level": "permissive",
    }
    r = requests.post(f"{CONTROL_BASE}/proxy", headers=_headers({"X-Fal-Target-Url": f"https://queue.fal.run/{ENDPOINT}"}), json=payload, timeout=60)
    if r.status_code == 402:
        raise InsufficientCredits("insufficient Universal Key balance")
    if r.status_code >= 400:
        raise TryOnError(f"submit failed {r.status_code}: {r.text[:200]}")
    sub = r.json()
    status_url, response_url = _trusted(sub["status_url"]), _trusted(sub["response_url"])
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        s = _get(status_url, deadline)
        s.raise_for_status()
        st = (s.json().get("status") or "").upper()
        if st in ("COMPLETED", "OK"):
            res = _get(response_url, deadline, 60)
            if res.status_code >= 400:
                raise TryOnError(f"result failed {res.status_code}: {res.text[:200]}")
            imgs = res.json().get("images") or []
            if not imgs or not imgs[0].get("url"):
                raise TryOnError("empty result")
            img = requests.get(imgs[0]["url"], timeout=60)
            img.raise_for_status()
            logger.info(f"fashn try-on done ({len(img.content)} bytes)")
            return img.content
        if st in ("FAILED", "CANCELLED", "CANCELED", "ERROR"):
            raise TryOnError(f"generation {st}")
        time.sleep(2)
    raise TryOnError("timeout")
