"""WhatsApp Business (Meta Cloud API) transport for the My Atelier support desk."""
import hashlib
import hmac
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("whatsapp")

HANDOFF_TEXT = "Ti passo subito il titolare Andrea, resta qui che ti contatta a breve"


def configured() -> bool:
    return all(os.environ.get(k) for k in ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN"))


def valid_signature(raw: bytes, supplied: Optional[str]) -> bool:
    if not supplied or not supplied.startswith("sha256="):
        return False
    expected = hmac.new(os.environ["WHATSAPP_APP_SECRET"].encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied[7:].lower())


def _url() -> str:
    return f"https://graph.facebook.com/{os.environ['WHATSAPP_API_VERSION']}/{os.environ['WHATSAPP_PHONE_NUMBER_ID']}/messages"


async def _post(payload: dict) -> str:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(_url(), headers={"Authorization": f"Bearer {os.environ['WHATSAPP_ACCESS_TOKEN']}"}, json={"messaging_product": "whatsapp", **payload})
    if r.status_code >= 400:
        raise RuntimeError(f"WhatsApp {r.status_code}: {r.text[:180]}")
    return (r.json().get("messages") or [{}])[0].get("id", "")


async def send_text(to: str, body: str) -> str:
    return await _post({"to": to, "type": "text", "text": {"body": body[:4000], "preview_url": False}})


async def notify_owner(text: str) -> None:
    """Free text to Andrea's personal number; outside the 24h window falls back to the approved template if set."""
    owner = os.environ.get("WHATSAPP_OWNER_NUMBER")
    if not owner or not configured():
        return
    try:
        await send_text(owner, text)
    except Exception as e:
        tpl = os.environ.get("WHATSAPP_NOTIFY_TEMPLATE")
        if not tpl:
            logger.warning(f"whatsapp owner notify failed (no template): {e}")
            return
        try:
            await _post({"to": owner, "type": "template", "template": {
                "name": tpl, "language": {"code": os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE", "it")},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": text[:900]}]}]}})
        except Exception as e2:
            logger.error(f"whatsapp owner template failed: {e2}")


def parse_messages(payload: dict) -> list:
    out = []
    for entry in payload.get("entry", []):
        for ch in entry.get("changes", []):
            val = ch.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in val.get("contacts", [])}
            for m in val.get("messages", []):
                kind = m.get("type")
                text = (m.get("text") or {}).get("body") if kind == "text" else \
                    (m.get("button") or {}).get("text") or ((m.get("interactive") or {}).get("button_reply") or {}).get("title") or \
                    f"[{kind} ricevuto: rispondi con un messaggio di testo]"
                out.append({"wamid": m.get("id"), "from": m.get("from"), "name": names.get(m.get("from"), ""), "text": text or ""})
    return out
