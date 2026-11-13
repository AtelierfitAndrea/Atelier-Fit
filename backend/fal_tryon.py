"""External try-on for TRANSPARENT garments (owner test switch). fal.ai fal-ai/image-apps-v2/virtual-try-on via Emergent Universal Key."""
import base64
import os
import time
from urllib.parse import urlparse

import requests

ENDPOINT = "fal-ai/image-apps-v2/virtual-try-on"
# Fal Universal Key supports queue inference through the Emergent proxy only, not Fal Platform APIs.
CONTROL_BASE = os.environ.get("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com").rstrip("/") + "/api/v1/fal"
QUEUE_BASE = f"{CONTROL_BASE}/queue"


class FalError(Exception):
    pass


def _headers(extra: dict = None) -> dict:
    h = {"Authorization": f"Bearer {os.environ['EMERGENT_LLM_KEY']}", "Content-Type": "application/json"}
    if os.environ.get("job_id"):
        h["X-App-ID"] = h["X-Job-ID"] = os.environ["job_id"]
    if os.environ.get("run_id"):
        h["X-Environment-ID"] = os.environ["run_id"]
    return {**h, **(extra or {})}


def _trusted(url: str) -> str:
    c, q = urlparse(url), urlparse(QUEUE_BASE)
    if c.scheme != q.scheme or c.netloc != q.netloc or c.username or c.password or c.fragment or not c.path.startswith(q.path.rstrip("/") + "/"):
        raise FalError("untrusted queue url")
    return url


def _get(url: str, deadline: float, timeout: int) -> requests.Response:
    delay = 1
    for attempt in range(5):
        left = deadline - time.monotonic()
        if left <= 0:
            raise FalError("timeout")
        try:
            return requests.get(url, headers=_headers(), timeout=min(timeout, left))
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as e:
            if attempt == 4:
                raise FalError("polling failed") from e
            time.sleep(min(delay, max(0.1, deadline - time.monotonic())))
            delay *= 2
    raise FalError("unreachable")


def _data_url(data: bytes, ct: str) -> str:
    return f"data:{ct};base64,{base64.b64encode(data).decode()}"


def tryon(person: bytes, garment: bytes, ratio: str = "9:16", timeout_s: int = 300) -> bytes:
    """Blocking: one submit (never retried), poll, download the result image bytes."""
    payload = {"person_image_url": _data_url(person, "image/jpeg"), "clothing_image_url": _data_url(garment, "image/jpeg"),
               "preserve_pose": True, "aspect_ratio": {"ratio": ratio}}
    r = requests.post(f"{CONTROL_BASE}/proxy", headers=_headers({"X-Fal-Target-Url": f"https://queue.fal.run/{ENDPOINT}"}), json=payload, timeout=60)
    if r.status_code == 402:
        raise FalError("credito Universal Key insufficiente")
    r.raise_for_status()
    sub = r.json()
    status_url, response_url = _trusted(sub["status_url"]), _trusted(sub["response_url"])
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        s = _get(status_url, deadline, 30)
        s.raise_for_status()
        body = s.json()
        st = (body.get("status") or "").upper()
        if st in ("COMPLETED", "OK"):
            if body.get("error"):
                raise FalError(str(body["error"]))
            res = _get(response_url, deadline, 60)
            res.raise_for_status()
            images = res.json().get("images") or []
            if not images:
                raise FalError("no image")
            img = requests.get(images[0]["url"], timeout=60)
            img.raise_for_status()
            return img.content
        if st in ("FAILED", "CANCELLED", "CANCELED", "ERROR"):
            raise FalError(st)
        time.sleep(2)
    raise FalError("timeout")
