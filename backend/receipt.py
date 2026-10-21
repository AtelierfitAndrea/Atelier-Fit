"""Elegant My Atelier payment receipt, sent from studio@ after every purchase."""
import imaplib
import logging
import os
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from html import escape
from typing import Optional

logger = logging.getLogger("receipt")

LABELS = {"extra": "1 prova extra", "single": "Abbonamento Single · 30 giorni", "family": "Abbonamento Family · 30 giorni"}


def _fmt_date(dt: Optional[datetime]) -> str:
    return dt.strftime("%d/%m/%Y") if dt else "—"


def _fmt_eur(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {(currency or 'eur').upper()}".replace(",", "X").replace(".", ",").replace("X", ".")


def build(name: str, option: str, amount: float, currency: str, paid_at: datetime, expires_at: Optional[datetime], ref: str) -> EmailMessage:
    sender = os.environ["SUPPORT_EMAIL"]
    label = LABELS.get(option, option)
    greeting = f"Gentile {name}," if name else "Gentile cliente,"
    validity = (f"Il tuo abbonamento è attivo fino al {_fmt_date(expires_at)}." if expires_at
                else "La prova extra è già disponibile nel tuo account e non scade.")
    rows = [("Acquisto", label), ("Importo", _fmt_eur(amount, currency)), ("Data", _fmt_date(paid_at)),
            ("Scadenza", _fmt_date(expires_at) if expires_at else "Nessuna"), ("Riferimento", ref[-14:])]
    text = "\n".join([greeting, "", "grazie per il tuo acquisto su My Atelier. Ecco la tua ricevuta.", ""]
                     + [f"{k}: {v}" for k, v in rows]
                     + ["", validity, "L'abbonamento è legato alla tua email: resta attivo anche se cambi telefono.", "",
                        "Un caro saluto,", "Il team My Atelier", "studio@myatelierapp.it"])
    trs = "".join(
        f"<tr><td style='padding:10px 0;border-bottom:1px solid #E8E2D9;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#8B7355'>{escape(k)}</td>"
        f"<td style='padding:10px 0;border-bottom:1px solid #E8E2D9;text-align:right;font-family:Georgia,serif;font-size:16px;color:#0A0A0A'>{escape(v)}</td></tr>"
        for k, v in rows)
    html = f"""<div style="background:#FAF8F5;padding:32px 12px">
<div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E8E2D9">
  <div style="background:#0A0A0A;padding:28px 32px;text-align:center">
    <div style="font-family:Georgia,serif;color:#ffffff;font-size:22px;letter-spacing:.35em">MY ATELIER</div>
    <div style="height:1px;width:48px;background:#D4AF37;margin:14px auto 0"></div>
  </div>
  <div style="padding:32px">
    <div style="font-size:11px;letter-spacing:.3em;color:#8B7355">RICEVUTA DI PAGAMENTO</div>
    <p style="font-family:Georgia,serif;font-size:20px;color:#0A0A0A;margin:14px 0 6px">{escape(greeting)}</p>
    <p style="font-size:14px;color:#404040;line-height:1.6;margin:0 0 20px">grazie per il tuo acquisto su My Atelier. Ecco la tua ricevuta.</p>
    <table style="width:100%;border-collapse:collapse">{trs}</table>
    <p style="font-size:14px;color:#0A0A0A;line-height:1.6;margin:24px 0 6px"><b>{escape(validity)}</b></p>
    <p style="font-size:13px;color:#525252;line-height:1.6;margin:0">L'abbonamento è legato alla tua email: resta attivo anche se cambi telefono.</p>
    <p style="font-family:Georgia,serif;font-size:15px;color:#0A0A0A;margin:28px 0 0">Un caro saluto,<br/>Il team My Atelier</p>
  </div>
  <div style="border-top:1px solid #E8E2D9;padding:16px 32px;font-size:11px;color:#8B7355;letter-spacing:.15em;text-align:center">
    STUDIO@MYATELIERAPP.IT · Pagamento gestito in sicurezza da Stripe
  </div>
</div></div>"""
    msg = EmailMessage()
    msg["From"] = formataddr(("My Atelier", sender))
    msg["Subject"] = f"La tua ricevuta My Atelier · {label}"
    msg["Reply-To"] = sender
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[1])
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def send(to_addr: str, msg: EmailMessage) -> None:
    sender, pwd = os.environ["SUPPORT_EMAIL"], os.environ["SUPPORT_EMAIL_PASSWORD"]
    msg["To"] = to_addr
    with smtplib.SMTP_SSL(os.environ["SUPPORT_SMTP_HOST"], int(os.environ["SUPPORT_SMTP_PORT"]), timeout=30) as s:
        s.login(sender, pwd)
        s.send_message(msg)
    try:
        m = imaplib.IMAP4_SSL(os.environ["SUPPORT_IMAP_HOST"], int(os.environ["SUPPORT_IMAP_PORT"]), timeout=30)
        m.login(sender, pwd)
        m.append("INBOX.Sent", "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        m.logout()
    except Exception as e:
        logger.warning(f"receipt: copy to Sent failed: {e}")
