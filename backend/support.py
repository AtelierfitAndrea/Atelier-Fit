"""My Atelier support desk: in-app requests + studio@ mailbox (IMAP/SMTP) with Claude auto-replies."""
import asyncio
import email
import hmac
import imaplib
import logging
import os
import re
import smtplib
import time
import uuid
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from typing import Optional

import json as pyjson

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from emergentintegrations.llm.chat import LlmChat, UserMessage

import whatsapp

logger = logging.getLogger("support")

FAQ = [
    ('La foto non viene o dà errore', 'Serve una foto a figura intera, dalla testa ai piedi, luce naturale davanti, sfondo neutro, senza altri oggetti o persone, formato JPG, massimo 10 MB. Riprova da Home > Il Mio Avatar con “Scatta ora” o “Carica da galleria”.'),
    ('La foto è scura o sfocata', 'Avvicina la luce al viso, niente controluce, tieni il telefono fermo e dritto (aiutati con la livella della fotocamera), scatta da circa 1,5-2 metri con zoom 1x.'),
    ('Come prendo le misure?', 'Vai in Profilo > Le tue misure e inserisci altezza, torace, vita, fianchi, spalle, lunghezza gamba e lunghezza piede (peso ed età facoltativi). Usa un metro morbido da sarta; il tasto “Guarda come” accanto a ogni campo mostra dove passare il metro. Le misure restano salvate sul tuo account.'),
    ('La taglia consigliata non mi torna', 'Ricontrolla le misure inserite in Profilo. Se sei tra due taglie, per giacche e capispalla scegli la più grande, per pantaloni aderenti la più piccola. Per un capo preciso usa Analisi prodotto incollando il link: confrontiamo la tabella taglie del brand con le tue misure.'),
    ('Posso provare un outfit completo?', 'Sì, puoi provare maglia + giacca + pantaloni + scarpe insieme in Prova taglia > “Componi il tuo outfit” (fino a 4 capi, anche di brand diversi). Con “Copia Look da Modello” puoi anche caricare la foto di un modello e indossare il suo look.'),
    ('Le mie foto e i miei dati sono al sicuro?', 'Foto e misure restano solo nel tuo profilo, sono crittografate, non vengono condivise con nessuno e servono solo a vestirti virtualmente.'),
    ('Posso cancellare la mia foto?', 'Sì, da Impostazioni > Il Mio Avatar > “Elimina foto”. La cancellazione è immediata e definitiva dal server.'),
    ('Il vestito mi sembra lungo o corto', "L'AI adatta la lunghezza del capo alla tua altezza inserita in Profilo; se sei sotto 1,65 m ti consigliamo di valutare un orlo."),
    ('Con le scarpe porto numeri diversi nei vari brand', 'Ogni brand calza in modo diverso (Zara, Nike, Adidas hanno vestibilità diverse). Inserisci la lunghezza del piede in cm in Profilo: calcoliamo il numero esatto per ogni brand.'),
    ('Il risultato non mi piace', 'Puoi riprovare cambiando foto, luce o aggiornando le misure per un risultato più realistico. Il piano Free include 5 prove al mese; con i piani Single o Family le prove sono illimitate.'),
]

KNOWLEDGE_BASE = (
    "KNOWLEDGE BASE UFFICIALE MY ATELIER (fonte primaria, rispondi SEMPRE partendo da qui).\n"
    "Percorsi reali dell'app: Home (Il Mio Avatar), Prova taglia (Camerino virtuale: prova capi, Copia Look da Modello, Componi il tuo outfit), "
    "Analisi prodotto (taglia da link), Il tuo armadio, Profilo (Le tue misure), Impostazioni (gestione foto Avatar e abbonamento), Assistenza (FAQ e domande libere).\n\n"
    + "\n".join(f"{i}. {q} — {a}" for i, (q, a) in enumerate(FAQ, 1))
)

SYSTEM_PROMPT = f"""Sei l'assistenza clienti di My Atelier (studio@myatelierapp.it), atelier digitale di prova virtuale e taglie.
Tono: italiano elegante, cortese, professionale e conciso, come un commesso di fiducia di un atelier. Niente emoji, niente parole come "gioco".
Rispondi sempre partendo dalla knowledge base qui sotto; non inventare funzioni, prezzi o percorsi che non esistono.
Rispondi nella lingua del cliente se non scrive in italiano.

{KNOWLEDGE_BASE}

Devi restituire SOLO un JSON valido:
{{"relevant": true|false, "brand": true|false, "category": "maglie|giacche|pantaloni|scarpe|outfit|foto|misure|privacy|altro", "reply": "testo della mail"}}
- brand = true se chi scrive è un brand, negozio, azienda, agenzia o influencer che propone collaborazione, partnership, vendita, integrazione, sponsorizzazione o pubblicità con My Atelier (in quel caso relevant = false e reply = "").
- relevant = true se la richiesta riguarda l'uso di My Atelier: capi (maglie, giacche, pantaloni, scarpe, vestiti), foto/avatar, misure e taglie, privacy, outfit, prove virtuali.
- relevant = false per fatture, pagamenti/rimborsi, partnership, pubblicità, spam, newsletter, richieste legali o qualsiasi altro tema: in quel caso reply = "".
- La reply è testo semplice: NIENTE Markdown (niente asterischi, cancelletti o grassetti); per i percorsi usa il formato Profilo > Le tue misure.
- La reply: saluto con il nome se noto, soluzione chiara in pochi paragrafi o punti, chiusura "Un caro saluto,\\nIl team My Atelier". Niente oggetto, niente firma extra.
"""

SKIP_SENDERS = re.compile(r"(no-?reply|mailer-daemon|postmaster|notifications?@|bounce)", re.I)
MAX_AUTO_REPLIES_PER_TICKET = 5
BRAND_REPLY = "Ciao! Grazie per averci contattato come brand 🙏 Abbiamo ricevuto la tua proposta. Ti risponderà personalmente Andrea, il fondatore, a brevissimo. Grazie!"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cfg(k: str) -> str:
    return os.environ[k]


def _decode(v: Optional[str]) -> str:
    if not v:
        return ""
    try:
        return str(make_header(decode_header(v)))
    except Exception:
        return v


def _strip_quoted(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.startswith(">") or re.match(r"^(Il giorno|On .+wrote:|-----Original Message|Da: .+@)", line.strip()):
            break
        out.append(line)
    return "\n".join(out).strip() or text.strip()


def _body_text(msg) -> str:
    plain, html = None, None
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_disposition() == "attachment":
            continue
        ct = part.get_content_type()
        try:
            payload = part.get_payload(decode=True)
            txt = payload.decode(part.get_content_charset() or "utf-8", errors="replace") if payload else ""
        except Exception:
            continue
        if ct == "text/plain" and plain is None:
            plain = txt
        elif ct == "text/html" and html is None:
            html = txt
    if plain is None and html:
        plain = re.sub(r"<[^>]+>", " ", re.sub(r"(?i)<br\s*/?>|</p>", "\n", html))
        plain = re.sub(r"[ \t]+", " ", plain)
    return _strip_quoted(plain or "")[:8000]


def _imap() -> imaplib.IMAP4_SSL:
    m = imaplib.IMAP4_SSL(_cfg("SUPPORT_IMAP_HOST"), int(_cfg("SUPPORT_IMAP_PORT")), timeout=30)
    m.login(_cfg("SUPPORT_EMAIL"), _cfg("SUPPORT_EMAIL_PASSWORD"))
    return m


def _fetch_new(last_uid: int) -> list:
    # Read-only + BODY.PEEK: messages stay on the server and stay unread for webmail/Gmail.
    m = _imap()
    try:
        m.select("INBOX", readonly=True)
        _typ, data = m.uid("search", None, f"UID {last_uid + 1}:*")
        uids = [int(u) for u in (data[0] or b"").split() if int(u) > last_uid]
        out = []
        for uid in uids[:50]:
            _t, msg_data = m.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = next((p[1] for p in msg_data if isinstance(p, tuple)), None)
            if raw:
                out.append((uid, email.message_from_bytes(raw)))
        return out
    finally:
        try:
            m.logout()
        except Exception:
            pass


def _send_mail(to_addr: str, subject: str, body: str, in_reply_to: Optional[str], references: Optional[str]) -> str:
    sender = _cfg("SUPPORT_EMAIL")
    msg = EmailMessage()
    msg["From"] = formataddr(("My Atelier", sender))
    msg["To"] = to_addr
    msg["Cc"] = _cfg("SUPPORT_CC_EMAIL")
    msg["Subject"] = subject
    msg["Reply-To"] = sender
    msg["Auto-Submitted"] = "auto-replied"
    mid = make_msgid(domain=sender.split("@")[1])
    msg["Message-ID"] = mid
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = f"{references or ''} {in_reply_to}".strip()
    msg.set_content(body)
    html_body = "".join(f"<p style='margin:0 0 12px'>{line}</p>" for line in body.replace("&", "&amp;").replace("<", "&lt;").split("\n") if line.strip())
    msg.add_alternative(
        f"<div style='font-family:Georgia,serif;color:#0A0A0A;max-width:560px;line-height:1.55'>{html_body}"
        f"<hr style='border:none;border-top:1px solid #8B7355;width:48px;margin:24px 0'/>"
        f"<div style='font-size:11px;letter-spacing:.2em;color:#8B7355'>MY ATELIER · studio@myatelierapp.it</div></div>",
        subtype="html",
    )
    with smtplib.SMTP_SSL(_cfg("SUPPORT_SMTP_HOST"), int(_cfg("SUPPORT_SMTP_PORT")), timeout=30) as s:
        s.login(sender, _cfg("SUPPORT_EMAIL_PASSWORD"))
        s.send_message(msg)
    # Keep a copy in the server "Sent" folder so it is visible in webmail/Gmail too.
    try:
        m = _imap()
        m.append("INBOX.Sent", "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        m.logout()
    except Exception as e:
        logger.warning(f"support: copy to Sent failed: {e}")
    return mid


def create_support_router(db, get_account_user, require_owner, extract_json, emergent_key: str) -> APIRouter:
    r = APIRouter()
    poll_lock = asyncio.Lock()

    async def settings() -> dict:
        doc = await db.support_settings.find_one({"_id": "main"}) or {}
        return {"auto_reply": doc.get("auto_reply", True), "last_uid": doc.get("last_uid"), "last_poll_at": doc.get("last_poll_at"), "last_poll_error": doc.get("last_poll_error")}

    async def add_message(ticket_id: str, author: str, body: str, **extra) -> dict:
        msg = {"id": str(uuid.uuid4()), "ticket_id": ticket_id, "author": author, "body": body, "created_at": _now(), **extra}
        await db.support_messages.insert_one(msg)
        msg.pop("_id", None)
        upd = {"updated_at": msg["created_at"], "last_message_at": msg["created_at"], "last_author": author}
        if author == "user":
            upd["unread_admin"] = True
        await db.support_tickets.update_one({"id": ticket_id}, {"$set": upd})
        return msg

    async def thread_text(ticket_id: str) -> str:
        msgs = await db.support_messages.find({"ticket_id": ticket_id}, {"_id": 0}).sort("created_at", 1).to_list(30)
        who = {"user": "CLIENTE", "ai": "MY ATELIER", "admin": "MY ATELIER"}
        return "\n\n".join(f"[{who.get(m['author'], m['author'])}] {m['body']}" for m in msgs if not m.get("draft"))

    async def notify_owner_brand(ticket: dict):
        contact = f"+{ticket['phone']} (WhatsApp)" if ticket.get("channel") == "whatsapp" else ticket.get("email")
        await whatsapp.notify_owner(f"Un brand ti ha scritto - rispondi tu personalmente\nDa: {ticket.get('name') or ''} {contact}\nOggetto: {ticket.get('subject')}")
        body = (f"Un brand ti ha scritto - rispondi tu personalmente\n\nDa: {ticket.get('name') or ''} <{contact}>\n"
                f"Oggetto: {ticket.get('subject')}\n\n{await thread_text(ticket['id'])}\n\n"
                "Rispondi dalla Stanza del Proprietario > Assistenza > BRAND DA CONTATTARE.")
        msg = EmailMessage()
        msg["From"] = formataddr(("My Atelier", _cfg("SUPPORT_EMAIL")))
        msg["To"] = _cfg("SUPPORT_CC_EMAIL")
        msg["Subject"] = "Un brand ti ha scritto - rispondi tu personalmente"
        if ticket.get("email"):
            msg["Reply-To"] = ticket["email"]
        msg.set_content(body)

        def _send():
            with smtplib.SMTP_SSL(_cfg("SUPPORT_SMTP_HOST"), int(_cfg("SUPPORT_SMTP_PORT")), timeout=30) as smtp:
                smtp.login(_cfg("SUPPORT_EMAIL"), _cfg("SUPPORT_EMAIL_PASSWORD"))
                smtp.send_message(msg)
        try:
            await run_in_threadpool(_send)
            await db.support_tickets.update_one({"id": ticket["id"]}, {"$set": {"brand_notified_at": _now()}})
        except Exception as e:
            logger.error(f"support: brand notify failed for {ticket['id']}: {e}")

    async def handoff_call(ticket: dict):
        # WhatsApp question outside the 10 FAQ: tell the customer Andrea will call and alert him (WhatsApp + email).
        if not ticket.get("handoff_sent"):
            await deliver(ticket, whatsapp.HANDOFF_TEXT, "ai")
        await db.support_tickets.update_one({"id": ticket["id"]}, {"$set": {"status": "needs_human", "handoff_sent": True, "call_requested_at": _now(), "unread_admin": True}})
        last = await db.support_messages.find_one({"ticket_id": ticket["id"], "author": "user"}, {"_id": 0, "body": 1}, sort=[("created_at", -1)])
        q = (last or {}).get("body", "")[:600]
        phone = ticket["phone"]
        text = (f"📞 Richiesta di chiamata My Atelier\nCliente: {ticket.get('name') or 'senza nome'} (+{phone})\nDomanda: {q}\n"
                f"Chiama: tel:+{phone} · WhatsApp: https://wa.me/{phone}")
        await whatsapp.notify_owner(text)
        msg = EmailMessage()
        msg["From"] = formataddr(("My Atelier", _cfg("SUPPORT_EMAIL")))
        msg["To"] = _cfg("SUPPORT_CC_EMAIL")
        msg["Subject"] = f"Richiesta di chiamata WhatsApp: {ticket.get('name') or '+' + phone}"
        msg.set_content(text + "\n\nConversazione nella Stanza del Proprietario > Assistenza.")

        def _send():
            with smtplib.SMTP_SSL(_cfg("SUPPORT_SMTP_HOST"), int(_cfg("SUPPORT_SMTP_PORT")), timeout=30) as smtp:
                smtp.login(_cfg("SUPPORT_EMAIL"), _cfg("SUPPORT_EMAIL_PASSWORD"))
                smtp.send_message(msg)
        try:
            await run_in_threadpool(_send)
        except Exception as e:
            logger.error(f"support: call email failed for {ticket['id']}: {e}")

    async def handle_brand(ticket: dict):
        await db.support_tickets.update_one({"id": ticket["id"]}, {"$set": {"status": "brand", "brand": True, "category": "brand", "unread_admin": True}})
        if not ticket.get("brand_replied") and (await settings())["auto_reply"]:
            await deliver(ticket, BRAND_REPLY, "ai")
            await db.support_tickets.update_one({"id": ticket["id"]}, {"$set": {"brand_replied": True}})
        await notify_owner_brand(ticket)

    async def ai_answer(ticket: dict) -> dict:
        chat = LlmChat(api_key=emergent_key, session_id=f"support-{ticket['id']}-{uuid.uuid4().hex[:6]}", system_message=SYSTEM_PROMPT)
        chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
        channel = ("\nCanale: WhatsApp. Stesse regole e stessa knowledge base, ma reply breve (massimo 700 caratteri), tono cordiale, "
                   "chiudi con \"Il team My Atelier\". Imposta relevant = false SOLO se la domanda esce dai temi delle 10 risposte (foto, misure, taglie, outfit, privacy, cancellazione foto, lunghezza capi, scarpe, risultato della prova): per esempio spedizioni, pagamenti, resi, ordini.\n") if ticket.get("channel") == "whatsapp" else ""
        prompt = f"Nome cliente: {ticket.get('name') or 'non noto'}\nOggetto: {ticket.get('subject')}{channel}\n\nConversazione:\n{await thread_text(ticket['id'])}\n\nRispondi all'ultimo messaggio del CLIENTE."
        data = extract_json(await chat.send_message(UserMessage(text=prompt))) or {}
        reply = re.sub(r"\*\*|__|^#+\s*", "", str(data.get("reply") or ""), flags=re.M).strip()
        return {"relevant": bool(data.get("relevant")), "brand": bool(data.get("brand")), "category": str(data.get("category") or "altro")[:20], "reply": reply}

    async def deliver(ticket: dict, body: str, author: str, **extra) -> dict:
        if ticket.get("channel") == "whatsapp":
            try:
                wid = await whatsapp.send_text(ticket["phone"], body)
                return await add_message(ticket["id"], author, body, wa_message_id=wid, sent=True, **extra)
            except Exception as e:
                logger.error(f"support: whatsapp send failed for {ticket['id']}: {e}")
                return await add_message(ticket["id"], author, body, sent=False, send_error=str(e)[:200], **extra)
        last_in = await db.support_messages.find_one({"ticket_id": ticket["id"], "author": "user", "email_message_id": {"$ne": None}}, {"_id": 0}, sort=[("created_at", -1)])
        subject = ticket.get("subject") or "La tua richiesta"
        subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        try:
            mid = await run_in_threadpool(_send_mail, ticket["email"], subject, body, (last_in or {}).get("email_message_id"), (last_in or {}).get("references"))
            return await add_message(ticket["id"], author, body, email_message_id=mid, sent=True, **extra)
        except Exception as e:
            logger.error(f"support: send failed for {ticket['id']}: {e}")
            return await add_message(ticket["id"], author, body, sent=False, send_error=str(e)[:200], **extra)

    async def process(ticket_id: str):
        ticket = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
        if not ticket:
            return
        if ticket.get("brand"):
            await handle_brand(ticket)
            return
        try:
            ans = await ai_answer(ticket)
        except Exception as e:
            logger.error(f"support: AI failed for {ticket_id}: {e}")
            await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "needs_human", "ai_error": str(e)[:200]}})
            if ticket.get("channel") == "whatsapp":
                await handoff_call(ticket)
            return
        if ans["brand"]:
            await handle_brand(ticket)
            return
        if not ticket.get("category"):
            await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"category": ans["category"]}})
        if not ans["relevant"] or not ans["reply"]:
            await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "needs_human"}})
            if ticket.get("channel") == "whatsapp":
                await handoff_call(ticket)
            return
        auto = (await settings())["auto_reply"] and ticket.get("auto_replies", 0) < MAX_AUTO_REPLIES_PER_TICKET
        if not auto:
            await add_message(ticket_id, "ai", ans["reply"], draft=True)
            await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "needs_human"}})
            return
        await deliver(ticket, ans["reply"], "ai")
        await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "answered"}, "$inc": {"auto_replies": 1}})

    async def new_ticket(email_addr: str, name: str, subject: str, source: str, user_id: Optional[str] = None) -> dict:
        t = {"id": str(uuid.uuid4()), "user_id": user_id, "email": email_addr.lower(), "name": name, "subject": subject[:160] or "Richiesta di assistenza",
             "source": source, "status": "open", "category": None, "auto_replies": 0, "unread_admin": True, "created_at": _now(), "updated_at": _now()}
        await db.support_tickets.insert_one(t)
        t.pop("_id", None)
        return t

    async def poll_mailbox() -> dict:
        async with poll_lock:
            st = await settings()
            try:
                if st["last_uid"] is None:
                    # First connection: start from now, never auto-reply to old mail.
                    def _max_uid():
                        m = _imap()
                        m.select("INBOX", readonly=True)
                        _t, d = m.uid("search", None, "ALL")
                        m.logout()
                        return max([int(u) for u in (d[0] or b"").split()] or [0])
                    uid = await run_in_threadpool(_max_uid)
                    await db.support_settings.update_one({"_id": "main"}, {"$set": {"last_uid": uid, "last_poll_at": _now(), "last_poll_error": None}}, upsert=True)
                    return {"new": 0}
                items = await run_in_threadpool(_fetch_new, st["last_uid"])
            except Exception as e:
                await db.support_settings.update_one({"_id": "main"}, {"$set": {"last_poll_at": _now(), "last_poll_error": str(e)[:200]}}, upsert=True)
                logger.error(f"support: IMAP poll failed: {e}")
                return {"new": 0, "error": str(e)[:200]}
            created, max_uid = 0, st["last_uid"]
            own = _cfg("SUPPORT_EMAIL").lower()
            for uid, msg in items:
                max_uid = max(max_uid, uid)
                name, addr = parseaddr(_decode(msg.get("From")))
                addr = (addr or "").lower()
                auto_hdr = (msg.get("Auto-Submitted") or "no").lower() != "no" or (msg.get("Precedence") or "").lower() in ("bulk", "junk", "list", "auto_reply") or msg.get("X-Autoreply")
                mid = msg.get("Message-ID")
                if not addr or addr == own or (mid and await db.support_messages.find_one({"email_message_id": mid})):
                    continue
                refs = f"{msg.get('References') or ''} {msg.get('In-Reply-To') or ''}".split()
                parent = await db.support_messages.find_one({"email_message_id": {"$in": refs}}, {"_id": 0, "ticket_id": 1}) if refs else None
                ticket = await db.support_tickets.find_one({"id": parent["ticket_id"]}, {"_id": 0}) if parent else None
                if not ticket:
                    ticket = await new_ticket(addr, name, _decode(msg.get("Subject")), "email")
                    created += 1
                await add_message(ticket["id"], "user", _body_text(msg) or "(messaggio vuoto)", email_message_id=mid, references=msg.get("References"), imap_uid=uid)
                await db.support_tickets.update_one({"id": ticket["id"]}, {"$set": {"status": "open"}})
                if auto_hdr or SKIP_SENDERS.search(addr):
                    await db.support_tickets.update_one({"id": ticket["id"]}, {"$set": {"status": "needs_human"}})
                    continue
                await process(ticket["id"])
            await db.support_settings.update_one({"_id": "main"}, {"$set": {"last_uid": max_uid, "last_poll_at": _now(), "last_poll_error": None}}, upsert=True)
            return {"new": created, "fetched": len(items)}

    # ----- Customer side -----
    class TicketIn(BaseModel):
        category: str = Field(pattern="^(maglie|giacche|pantaloni|scarpe|outfit|foto|misure|privacy|altro)$")
        subject: str = Field(min_length=3, max_length=160)
        message: str = Field(min_length=5, max_length=4000)

    class FollowUpIn(BaseModel):
        message: str = Field(min_length=1, max_length=4000)

    async def own_ticket(ticket_id: str, user) -> dict:
        t = await db.support_tickets.find_one({"id": ticket_id, "user_id": user.user_id}, {"_id": 0})
        if not t:
            raise HTTPException(status_code=404, detail="Richiesta non trovata")
        return t

    async def public_messages(ticket_id: str) -> list:
        return await db.support_messages.find({"ticket_id": ticket_id, "draft": {"$ne": True}}, {"_id": 0, "email_message_id": 0, "references": 0}).sort("created_at", 1).to_list(200)

    @r.get("/support/faq")
    async def faq():
        return [{"q": q, "a": a} for q, a in FAQ]

    class VoteIn(BaseModel):
        useful: bool

    @r.get("/support/faq/my-votes")
    async def my_faq_votes(user=Depends(get_account_user)):
        docs = await db.support_faq_votes.find({"user_id": user.user_id}, {"_id": 0, "idx": 1, "useful": 1}).to_list(50)
        return {str(d["idx"]): d["useful"] for d in docs}

    @r.post("/support/faq/{idx}/vote")
    async def vote_faq(idx: int, body: VoteIn, user=Depends(get_account_user)):
        if not 0 <= idx < len(FAQ):
            raise HTTPException(status_code=404, detail="FAQ non trovata")
        await db.support_faq_votes.update_one({"user_id": user.user_id, "idx": idx},
                                              {"$set": {"useful": body.useful, "question": FAQ[idx][0], "voted_at": _now()}}, upsert=True)
        return {"idx": idx, "useful": body.useful}

    @r.post("/support/tickets")
    async def create_ticket(body: TicketIn, bg: BackgroundTasks, user=Depends(get_account_user)):
        t = await new_ticket(user.email, user.name, body.subject, "app", user.user_id)
        await db.support_tickets.update_one({"id": t["id"]}, {"$set": {"category": body.category}})
        await add_message(t["id"], "user", body.message)
        bg.add_task(process, t["id"])
        return {**t, "category": body.category}

    @r.get("/support/tickets")
    async def my_tickets(user=Depends(get_account_user)):
        items = await db.support_tickets.find({"user_id": user.user_id}, {"_id": 0}).sort("updated_at", -1).to_list(100)
        for t in items:
            t["messages"] = await public_messages(t["id"])
        return items

    @r.post("/support/tickets/{ticket_id}/messages")
    async def follow_up(ticket_id: str, body: FollowUpIn, bg: BackgroundTasks, user=Depends(get_account_user)):
        if (await own_ticket(ticket_id, user)).get("status") == "closed":
            raise HTTPException(status_code=400, detail="Questa richiesta è chiusa: aprine una nuova")
        msg = await add_message(ticket_id, "user", body.message)
        await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "open"}})
        bg.add_task(process, ticket_id)
        return msg

    # ----- Owner inbox -----
    class ReplyIn(BaseModel):
        message: str = Field(min_length=1, max_length=8000)

    class StatusIn(BaseModel):
        status: str = Field(pattern="^(open|answered|needs_human|brand|closed)$")

    class SettingsIn(BaseModel):
        auto_reply: bool

    @r.get("/admin/support/tickets")
    async def admin_tickets(status: Optional[str] = None, _owner=Depends(require_owner)):
        q = {"status": status} if status else {}
        items = await db.support_tickets.find(q, {"_id": 0}).sort("updated_at", -1).to_list(500)
        for t in items:
            last = await db.support_messages.find_one({"ticket_id": t["id"]}, {"_id": 0, "body": 1, "author": 1}, sort=[("created_at", -1)])
            t["preview"] = (last or {}).get("body", "")[:140]
        counts = {s: await db.support_tickets.count_documents({"status": s}) for s in ("open", "answered", "needs_human", "brand", "closed")}
        return {"tickets": items, "counts": counts, "settings": await settings()}

    @r.get("/admin/support/tickets/{ticket_id}")
    async def admin_ticket(ticket_id: str, _owner=Depends(require_owner)):
        t = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
        if not t:
            raise HTTPException(status_code=404, detail="Conversazione non trovata")
        await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"unread_admin": False}})
        msgs = await db.support_messages.find({"ticket_id": ticket_id}, {"_id": 0, "references": 0}).sort("created_at", 1).to_list(500)
        return {**t, "messages": msgs}

    @r.post("/admin/support/tickets/{ticket_id}/reply")
    async def admin_reply(ticket_id: str, body: ReplyIn, _owner=Depends(require_owner)):
        t = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
        if not t:
            raise HTTPException(status_code=404, detail="Conversazione non trovata")
        msg = await deliver(t, body.message, "admin")
        if not msg.get("sent"):
            raise HTTPException(status_code=502, detail=f"Invio non riuscito: {msg.get('send_error')}")
        await db.support_messages.delete_many({"ticket_id": ticket_id, "draft": True})
        await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": "answered"}})
        return msg

    @r.post("/admin/support/tickets/{ticket_id}/ai-draft")
    async def admin_ai_draft(ticket_id: str, _owner=Depends(require_owner)):
        t = await db.support_tickets.find_one({"id": ticket_id}, {"_id": 0})
        if not t:
            raise HTTPException(status_code=404, detail="Conversazione non trovata")
        try:
            ans = await ai_answer(t)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI non disponibile: {str(e)[:120]}")
        return {"draft": ans["reply"], "relevant": ans["relevant"], "category": ans["category"]}

    @r.patch("/admin/support/tickets/{ticket_id}")
    async def admin_status(ticket_id: str, body: StatusIn, _owner=Depends(require_owner)):
        res = await db.support_tickets.update_one({"id": ticket_id}, {"$set": {"status": body.status}})
        if not res.matched_count:
            raise HTTPException(status_code=404, detail="Conversazione non trovata")
        return {"status": body.status}

    @r.get("/admin/support/pending-count")
    async def admin_pending(_owner=Depends(require_owner)):
        q = {"status": {"$ne": "closed"}, "$or": [{"status": {"$in": ["needs_human", "brand"]}}, {"unread_admin": True}]}
        return {"pending": await db.support_tickets.count_documents(q)}

    @r.get("/admin/support/faq-stats")
    async def admin_faq_stats(_owner=Depends(require_owner)):
        rows = await db.support_faq_votes.aggregate([{"$group": {"_id": "$idx", "yes": {"$sum": {"$cond": ["$useful", 1, 0]}}, "no": {"$sum": {"$cond": ["$useful", 0, 1]}}}}]).to_list(50)
        by = {r["_id"]: r for r in rows}
        return [{"idx": i, "q": q, "yes": by.get(i, {}).get("yes", 0), "no": by.get(i, {}).get("no", 0)} for i, (q, _a) in enumerate(FAQ)]

    @r.put("/admin/support/settings")
    async def admin_settings(body: SettingsIn, _owner=Depends(require_owner)):
        await db.support_settings.update_one({"_id": "main"}, {"$set": {"auto_reply": body.auto_reply}}, upsert=True)
        return await settings()

    @r.post("/admin/support/sync")
    async def admin_sync(bg: BackgroundTasks, _owner=Depends(require_owner)):
        bg.add_task(poll_mailbox)
        return {"status": "started"}

    @r.get("/whatsapp/webhook")
    async def wa_verify(request: Request):
        q = request.query_params
        token = os.environ.get("WHATSAPP_VERIFY_TOKEN") or ""
        if q.get("hub.mode") != "subscribe" or not token or not hmac.compare_digest(q.get("hub.verify_token") or "", token):
            raise HTTPException(status_code=403, detail="verification failed")
        return Response(content=q.get("hub.challenge") or "", media_type="text/plain")

    async def wa_handle(items: list):
        for it in items:
            if not it["wamid"] or not it["from"] or await db.support_messages.find_one({"wa_message_id": it["wamid"]}):
                continue
            ticket = await db.support_tickets.find_one({"channel": "whatsapp", "phone": it["from"], "status": {"$ne": "closed"}}, {"_id": 0}, sort=[("updated_at", -1)])
            if not ticket:
                ticket = await new_ticket("", it["name"], f"WhatsApp · {it['text'][:60]}", "whatsapp")
                await db.support_tickets.update_one({"id": ticket["id"]}, {"$set": {"channel": "whatsapp", "phone": it["from"]}})
                ticket.update({"channel": "whatsapp", "phone": it["from"]})
            await add_message(ticket["id"], "user", it["text"], wa_message_id=it["wamid"])
            if not ticket.get("brand"):
                await db.support_tickets.update_one({"id": ticket["id"]}, {"$set": {"status": "open"}})
            await process(ticket["id"])

    @r.post("/whatsapp/webhook")
    async def wa_inbound(request: Request, bg: BackgroundTasks):
        if not whatsapp.configured():
            raise HTTPException(status_code=503, detail="WhatsApp non configurato")
        raw = await request.body()
        if not whatsapp.valid_signature(raw, request.headers.get("x-hub-signature-256")):
            raise HTTPException(status_code=401, detail="invalid signature")
        try:
            payload = pyjson.loads(raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid JSON")
        bg.add_task(wa_handle, whatsapp.parse_messages(payload))
        return {"ok": True}

    @r.get("/admin/support/whatsapp-status")
    async def wa_status(_owner=Depends(require_owner)):
        return {"configured": whatsapp.configured(), "owner_number": os.environ.get("WHATSAPP_OWNER_NUMBER"), "webhook_path": "/api/whatsapp/webhook"}

    @r.post("/cron/support-poll")
    async def cron_poll(request: Request, bg: BackgroundTasks):
        # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
        auth = request.headers.get("authorization") or ""
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not token or not hmac.compare_digest(token, _cfg("WEBHOOK_CRON_SECRET")):
            raise HTTPException(status_code=401, detail="Unauthorized")
        try:
            env = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid body")
        if not isinstance(env, dict):
            raise HTTPException(status_code=400, detail="Invalid body")
        run_id = request.headers.get("x-webhook-id") or env.get("run_id") or str(uuid.uuid4())
        if await db.cron_runs.find_one({"run_id": run_id}):
            return {"status": "duplicate"}
        await db.cron_runs.insert_one({"run_id": run_id, "name": "support-poll", "at": _now()})
        bg.add_task(poll_mailbox)
        return {"status": "accepted"}

    return r
