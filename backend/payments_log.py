"""Payments ledger for the Admin Room, owner payment alerts (WhatsApp + email fallback) and PRO renewal reminders."""
import logging
import os
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape

from starlette.concurrency import run_in_threadpool

import receipt
import whatsapp

logger = logging.getLogger("payments")


async def record(db, pid: str, email: str, amount, status: str, ptype: str, reason: str = "") -> bool:
    """Upsert one payment row; returns True only the first time this id/status is stored (used to alert once)."""
    now = datetime.now(timezone.utc).isoformat()
    res = await db.payments.update_one(
        {"id": pid, "status": status},
        {"$setOnInsert": {"id": pid, "email": email or "", "amount": float(amount or 0), "status": status,
                          "type": ptype, "reason": reason or "", "createdAt": now}},
        upsert=True)
    logger.info(f"payment {status}: {pid} {email} {amount} {ptype} {reason}")
    return res.upserted_id is not None


def _owner_email() -> str:
    return next((e.strip() for e in os.environ["OWNER_EMAILS"].split(",") if e.strip()), "")


def _plain(subject: str, body: str) -> EmailMessage:
    sender = os.environ["SUPPORT_EMAIL"]
    msg = EmailMessage()
    msg["From"] = formataddr(("My Atelier", sender))
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[1])
    msg.set_content(body)
    return msg


async def alert_owner(text: str) -> None:
    # Meta reports out-of-window (24h) WhatsApp failures only asynchronously, so the email copy is always sent too.
    number = os.environ.get("WHATSAPP_OWNER_NUMBER")
    if number and whatsapp.configured():
        try:
            await whatsapp.send_text(number, text)
            logger.info(f"owner alert sent on WhatsApp: {text}")
        except Exception as e:
            logger.warning(f"owner WhatsApp alert failed: {e}")
    to = _owner_email()
    if not to:
        return
    try:
        await run_in_threadpool(receipt.send, to, _plain(text[:120], text + "\n\n— My Atelier · avviso pagamenti"))
        logger.info(f"owner alert sent by email to {to}")
    except Exception as e:
        logger.error(f"owner alert email failed: {e}")


def fmt_eur(amount) -> str:
    return receipt._fmt_eur(float(amount or 0), "eur")


def renewal_email(name: str, expires_at: datetime, link: str) -> EmailMessage:
    greeting = f"Ciao {name}," if name else "Ciao,"
    date = expires_at.strftime("%d/%m/%Y")
    msg = _plain("Il tuo PRO My Atelier scade tra 3 giorni",
                 f"{greeting}\n\nil tuo abbonamento PRO scade il {date}.\nRinnovalo con un clic per continuare con prove illimitate:\n{link}\n\n"
                 "Un caro saluto,\nIl team My Atelier\nstudio@myatelierapp.it")
    msg.add_alternative(f"""<div style="background:#FAF8F5;padding:32px 12px">
<div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E8E2D9">
  <div style="background:#0A0A0A;padding:28px 32px;text-align:center">
    <div style="font-family:Georgia,serif;color:#ffffff;font-size:22px;letter-spacing:.35em">MY ATELIER</div>
    <div style="height:1px;width:48px;background:#D4AF37;margin:14px auto 0"></div>
  </div>
  <div style="padding:32px">
    <div style="font-size:11px;letter-spacing:.3em;color:#8B7355">PROMEMORIA RINNOVO</div>
    <p style="font-family:Georgia,serif;font-size:20px;color:#0A0A0A;margin:14px 0 6px">{escape(greeting)}</p>
    <p style="font-size:14px;color:#404040;line-height:1.6;margin:0 0 24px">il tuo abbonamento <b>PRO</b> scade il <b>{date}</b>.
    Rinnovalo ora per continuare con prove illimitate.</p>
    <a href="{escape(link)}" style="display:inline-block;background:#0A0A0A;color:#ffffff;text-decoration:none;padding:14px 28px;font-size:12px;letter-spacing:.3em">RINNOVA PRO · 2,99 €</a>
    <p style="font-family:Georgia,serif;font-size:15px;color:#0A0A0A;margin:28px 0 0">Un caro saluto,<br/>Il team My Atelier</p>
  </div>
</div></div>""", subtype="html")
    return msg
