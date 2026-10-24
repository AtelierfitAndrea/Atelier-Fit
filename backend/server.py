import asyncio
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, Depends, Header, Query, Cookie
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import base64
import requests as http_requests
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
import httpx
from bs4 import BeautifulSoup
import json as pyjson
from cryptography.fernet import Fernet, InvalidToken
from body_measure import brand_sizes, shoe_size
import head_lock
import receipt
import hem as hem_mod
import size_fallback
import re
import stripe

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
stripe.api_key = os.environ['STRIPE_SECRET_KEY']

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "vfit"

storage_key: Optional[str] = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    resp = http_requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = http_requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple:
    key = init_storage()
    resp = http_requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60
    )
    resp.raise_for_status()
    if "/avatar/" in path:
        return FERNET.decrypt(resp.content), "image/jpeg"
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# ===== Models =====
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str = ""
    name: str
    picture: Optional[str] = None
    owner_id: Optional[str] = None
    is_family_profile: bool = False
    display_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def account_id(self) -> str:
        return self.owner_id or self.user_id


class Measurements(BaseModel):
    model_config = ConfigDict(extra="ignore")
    method: Optional[str] = None  # 'auto_photo' | 'height_weight' | 'tape' 
    gender: Optional[str] = None  # 'female' | 'male' | 'unisex'
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    shoulder_cm: Optional[float] = None
    inseam_cm: Optional[float] = None
    foot_cm: Optional[float] = None
    age: Optional[int] = None
    measured_at: Optional[str] = None
    updated_at: Optional[str] = None


class TryOn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    person_path: str
    garment_path: str
    result_path: str
    garment_name: Optional[str] = None
    garment_category: Optional[str] = None  # top, bottom, dress, shoes, outerwear
    recommended_size: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


# ===== Auth helpers =====
async def get_account_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> User:
    token = request.cookies.get("session_token")
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        if await db.revoked_sessions.find_one({"session_token": token}, {"_id": 1}):
            raise HTTPException(status_code=401, detail="session_revoked_other_device")
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = sess["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user_doc = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    if _prelaunch_blocked(user_doc.get("email")):
        raise HTTPException(status_code=403, detail="prelaunch_owner_only")
    return User(**user_doc)


def _prelaunch_blocked(email: Optional[str]) -> bool:
    # Before LAUNCH_AT only OWNER_EMAILS may use the app; afterwards everyone can.
    return datetime.now(timezone.utc) < datetime.fromisoformat(os.environ["LAUNCH_AT"]) and not _is_owner_email(email)


def _is_owner_email(email: Optional[str]) -> bool:
    # Pre-launch gate: only emails listed in OWNER_EMAILS may use the app.
    owners = {e.strip().lower() for e in os.environ["OWNER_EMAILS"].split(",") if e.strip()}
    return (email or "").strip().lower() in owners


async def get_current_user(
    account: User = Depends(get_account_user),
    x_profile_id: Optional[str] = Header(None),
) -> User:
    # Family plan: act as the selected sub-profile; data is scoped to its own user_id.
    if not x_profile_id or x_profile_id == account.user_id:
        return account
    owner_doc = await db.users.find_one({"user_id": account.user_id}, {"_id": 0, "plan": 1})
    if (owner_doc or {}).get("plan") != "FAMILY":
        return account
    prof = await db.users.find_one(
        {"user_id": x_profile_id, "owner_id": account.user_id, "is_family_profile": True}, {"_id": 0}
    )
    return User(**prof) if prof else account


# ===== Size recommendation logic =====
def recommend_size(measurements: dict, category: str) -> str:
    """Size recommendation from the user's real tape measurements only."""
    cat = (category or "").lower()
    if not _measures_complete(measurements):
        return INCOMPLETE_SIZE
    measurements = measurements or {}
    std = next((b for b in measurements.get("brand_sizes") or [] if b.get("brand") == "H&M"), None)
    if std and cat in ("top", "dress", "outerwear", "bottom"):
        return std["bottom"] if cat == "bottom" else std["top"]
    if cat == "shoes":
        return f"{shoe_size(measurements['foot_cm'])} EU"
    # Tops / dresses / outerwear use chest
    if cat in ("top", "dress", "outerwear"):
        chest = measurements.get("chest_cm")
        if chest is None:
            return "M"
        if chest < 84:
            return "XS"
        if chest < 90:
            return "S"
        if chest < 96:
            return "M"
        if chest < 104:
            return "L"
        if chest < 114:
            return "XL"
        return "XXL"
    # Bottoms use waist
    if cat == "bottom":
        waist = measurements.get("waist_cm")
        if waist is None:
            return "M"
        if waist < 68:
            return "XS"
        if waist < 74:
            return "S"
        if waist < 80:
            return "M"
        if waist < 88:
            return "L"
        if waist < 98:
            return "XL"
        return "XXL"
    return "M"


# ===== FastAPI app =====
app = FastAPI()
api_router = APIRouter(prefix="/api")


@app.on_event("startup")
async def startup():
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    await _migrate_plaintext_personal_data()
    try:
        await _backfill_account_fields()
    except Exception as e:
        logger.warning(f"account backfill failed: {e}")


# ----- Auth routes -----
async def _enforce_session_limit(user_id: str) -> None:
    # Personal account: 1 device (FAMILY: up to 4). Newest login wins, older devices are signed out.
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "plan": 1, "email": 1}) or {}
    limit = 4 if user_doc.get("plan") == "FAMILY" or _is_owner_email(user_doc.get("email")) else 1
    sessions = await db.user_sessions.find({"user_id": user_id}, {"_id": 0, "session_token": 1}).sort("created_at", -1).to_list(100)
    old = [x["session_token"] for x in sessions[limit:]]
    if not old:
        return
    now = datetime.now(timezone.utc).isoformat()
    await db.revoked_sessions.insert_many([
        {"session_token": t, "user_id": user_id, "reason": "other_device", "revoked_at": now} for t in old
    ])
    await db.user_sessions.delete_many({"session_token": {"$in": old}})


@api_router.post("/auth/session")
async def auth_session(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    r = http_requests.get(
        "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
        headers={"X-Session-ID": session_id},
        timeout=20,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session_id")
    data = r.json()
    email = data["email"]
    if _prelaunch_blocked(email):
        raise HTTPException(status_code=403, detail="prelaunch_owner_only")
    # Upsert user
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": data.get("name", existing.get("name", "")), "picture": data.get("picture")}},
        )
    else:
        # Email is the unique account key: same email on another device = same account, avatar and plan.
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": data.get("name", ""),
            "picture": data.get("picture"),
            "created_at": now.isoformat(),
            **_free_month_fields(now),
        })
    session_token = data["session_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": (request.headers.get("user-agent") or "")[:300],
    })
    await _enforce_session_limit(user_id)
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"user": user_doc, "session_token": session_token}


def _free_month_fields(created: datetime) -> dict:
    return {"free_month_start": created.isoformat(), "free_month_end": (created + timedelta(days=30)).isoformat()}


async def _backfill_account_fields():
    async for u in db.users.find({"free_month_start": {"$exists": False}}, {"_id": 0, "user_id": 1, "created_at": 1}):
        created = _parse_dt(u.get("created_at")) or datetime.now(timezone.utc)
        await db.users.update_one({"user_id": u["user_id"]}, {"$set": _free_month_fields(created)})
    await db.users.create_index("email", unique=True, partialFilterExpression={"email": {"$type": "string"}})


class ConfirmEmailIn(BaseModel):
    email: str


@api_router.post("/profile/confirm-email")
async def confirm_email(body: ConfirmEmailIn, user: User = Depends(get_account_user)):
    if body.email.strip().lower() != (user.email or "").lower():
        raise HTTPException(status_code=400, detail="Usa la stessa email con cui hai effettuato l'accesso")
    now = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"email_confirmed_at": now}})
    return {"email": user.email, "email_confirmed_at": now}


async def _stripe_customer_for(user: User) -> Optional[str]:
    # One Stripe customer per email: payments follow the account on every device.
    doc = await db.users.find_one({"user_id": user.account_id}, {"_id": 0, "stripe_customer_id": 1, "email": 1, "name": 1}) or {}
    if doc.get("stripe_customer_id"):
        return doc["stripe_customer_id"]
    email = doc.get("email") or user.email
    if not email:
        return None
    try:
        found = await run_in_threadpool(lambda: stripe.Customer.list(email=email, limit=1).data)
        cust = found[0] if found else await run_in_threadpool(lambda: stripe.Customer.create(email=email, name=doc.get("name") or None, metadata={"user_id": user.account_id}))
    except Exception as e:
        logger.warning(f"stripe customer for {email} failed: {e}")
        return None
    await db.users.update_one({"user_id": user.account_id}, {"$set": {"stripe_customer_id": cust.id}})
    return cust.id


TERMS_VERSION = "1.0-2026-06"


@api_router.get("/auth/me")
async def auth_me(user: User = Depends(get_account_user)):
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "terms_version": 1, "terms_accepted_at": 1}) or {}
    return {
        **user.model_dump(),
        "is_owner": _is_owner_email(user.email),
        "terms_version": doc.get("terms_version"),
        "terms_accepted_at": doc.get("terms_accepted_at"),
        "terms_current_version": TERMS_VERSION,
    }


class TermsAcceptIn(BaseModel):
    version: str
    accepted: bool


@api_router.post("/terms/accept")
async def terms_accept(body: TermsAcceptIn, request: Request, user: User = Depends(get_account_user)):
    if not body.accepted or body.version != TERMS_VERSION:
        raise HTTPException(status_code=400, detail="Devi accettare la versione attuale dei Termini")
    now = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"terms_version": TERMS_VERSION, "terms_accepted_at": now}})
    await db.terms_acceptances.insert_one({
        "user_id": user.user_id, "version": TERMS_VERSION, "accepted_at": now,
        "user_agent": (request.headers.get("user-agent") or "")[:300],
    })
    return {"terms_version": TERMS_VERSION, "terms_accepted_at": now}


def _request_token(request: Request, authorization: Optional[str]) -> Optional[str]:
    token = request.cookies.get("session_token")
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    return token


def _device_label(ua: str) -> str:
    ua = ua or ""
    os_name = next((n for k, n in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
                                   ("Mac OS", "Mac"), ("CrOS", "ChromeOS"), ("Linux", "Linux"), ("X11", "Linux")) if k in ua), "Computer")
    browser = next((n for k, n in (("Edg/", "Edge"), ("OPR/", "Opera"), ("Chrome/", "Chrome"), ("Firefox/", "Firefox"),
                                   ("Safari/", "Safari")) if k in ua), "Browser")
    return f"{browser} · {os_name}" if ua else "Dispositivo sconosciuto"


@api_router.get("/auth/devices")
async def auth_devices(request: Request, authorization: Optional[str] = Header(None), user: User = Depends(get_account_user)):
    current = _request_token(request, authorization)
    sessions = await db.user_sessions.find({"user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return [{
        "label": _device_label(x.get("user_agent", "")),
        "signed_in_at": x.get("created_at"),
        "current": x["session_token"] == current,
    } for x in sessions]


@api_router.post("/auth/logout-all")
async def auth_logout_all(response: Response, user: User = Depends(get_account_user)):
    res = await db.user_sessions.delete_many({"user_id": user.user_id})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True, "signed_out": res.deleted_count}


@api_router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True}


# ----- Owner room (visible only to OWNER_EMAILS accounts) -----
async def require_owner(user: User = Depends(get_account_user)) -> User:
    if not _is_owner_email(user.email):
        raise HTTPException(status_code=403, detail="Solo per il proprietario")
    return user


_HOT_CATS = {"top": "Maglie", "dress": "Maglie", "bottom": "Pantaloni", "shoes": "Scarpe", "outerwear": "Giacche"}
_OPTION_LABEL = {"extra": "Una Tantum", "single": "Single", "family": "Family"}


async def _owner_user_ids() -> list:
    # Owner accounts (and their family profiles) never count in the owner-room stats.
    emails = [e.strip().lower() for e in os.environ["OWNER_EMAILS"].split(",") if e.strip()]
    owners = await db.users.distinct("user_id", {"email": {"$in": emails}})
    return owners + await db.users.distinct("user_id", {"owner_id": {"$in": owners}})


def _real_paid_query(excl: list) -> dict:
    # Only live-mode Stripe payments from real customers.
    return {"payment_status": "paid", "livemode": True, "user_id": {"$nin": excl}}


@api_router.get("/admin/stats")
async def admin_stats(_: User = Depends(require_owner)):
    now = datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    excl = await _owner_user_ids()
    paid_q = _real_paid_query(excl)
    subscribers = await db.users.count_documents({"is_family_profile": {"$ne": True}, "user_id": {"$nin": excl}})
    logins_today = len(await db.user_sessions.distinct("user_id", {"created_at": {"$gte": day}, "user_id": {"$nin": excl}}))
    paying = await db.users.count_documents({"plan": {"$in": ["SINGLE", "FAMILY"]}, "plan_expires_at": {"$gt": now.isoformat()}, "user_id": {"$nin": excl}})
    agg = await db.payment_transactions.aggregate([
        {"$match": paid_q},
        {"$group": {"_id": "$option", "count": {"$sum": 1}, "total": {"$sum": "$amount"},
                    "month": {"$sum": {"$cond": [{"$eq": [{"$substrCP": ["$created_at", 0, 7]}, month]}, "$amount", 0]}}}},
    ]).to_list(10)
    by_plan = {o: {"label": lbl, "count": 0, "total": 0.0} for o, lbl in _OPTION_LABEL.items()}
    for a in agg:
        if a["_id"] in by_plan:
            by_plan[a["_id"]].update(count=a["count"], total=round(a["total"], 2))
    last = await db.payment_transactions.find(paid_q, {"_id": 0, "user_id": 1, "option": 1, "amount": 1, "created_at": 1}).sort("created_at", -1).to_list(10)
    emails = {u["user_id"]: u.get("email", "") async for u in db.users.find({"user_id": {"$in": [x["user_id"] for x in last]}}, {"_id": 0, "user_id": 1, "email": 1})}
    hot_rows = await db.product_analyses.aggregate([
        {"$match": {"result.ok": True, "user_id": {"$nin": excl}}},
        {"$group": {"_id": {"brand": "$result.brand", "name": "$result.product_name", "cat": "$result.category"}, "views": {"$sum": 1}}},
        {"$sort": {"views": -1}}, {"$limit": 60},
    ]).to_list(60)
    hot = {c: [] for c in ("Maglie", "Pantaloni", "Scarpe", "Giacche")}
    for r in hot_rows:
        cat = _HOT_CATS.get((r["_id"].get("cat") or "").lower())
        if cat and r["_id"].get("name") and len(hot[cat]) < 5:
            hot[cat].append({"brand": r["_id"].get("brand") or "—", "name": r["_id"].get("name") or "Prodotto", "views": r["views"]})
    return {
        "demo": False,
        "kpi": {"subscribers_total": subscribers, "logins_today": logins_today, "paying_subscribers": paying,
                "revenue_total": round(sum(a["total"] for a in agg), 2), "revenue_month": round(sum(a["month"] for a in agg), 2),
                "currency": "EUR"},
        "by_plan": list(by_plan.values()),
        "last_payments": [{"date": x["created_at"], "plan": _OPTION_LABEL.get(x["option"], x["option"]), "amount": x["amount"],
                           "email": emails.get(x["user_id"], "")} for x in last],
        "hot_products": hot,
        "daily_revenue": await _daily_revenue(now, paid_q),
    }


async def _daily_revenue(now: datetime, paid_q: dict, days: int = 30) -> list:
    since = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    rows = await db.payment_transactions.aggregate([
        {"$match": {**paid_q, "created_at": {"$gte": since}}},
        {"$group": {"_id": {"$substrCP": ["$created_at", 0, 10]}, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]).to_list(days + 1)
    by_day = {r["_id"]: r for r in rows}
    out = []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        r = by_day.get(d, {})
        out.append({"date": d, "total": round(r.get("total", 0), 2), "count": r.get("count", 0)})
    return out


# ----- Encrypted personal data (height, weight, measurements, measure photo) -----
FERNET = Fernet(os.environ["DATA_ENCRYPTION_KEY"].encode())
_MEASURE_FIELDS = set(Measurements.model_fields) - {"updated_at"}


def _enc(value) -> str:
    return FERNET.encrypt(pyjson.dumps(value).encode()).decode()


def _dec(token: str):
    try:
        return pyjson.loads(FERNET.decrypt(token.encode()))
    except (InvalidToken, ValueError):
        logger.error("decrypt failed")
        return None


async def _get_measurements(user_id: str) -> dict:
    doc = await db.measurements.find_one({"user_id": user_id}, {"_id": 0}) or {}
    data = (_dec(doc["enc"]) or {}) if doc.get("enc") else {k: v for k, v in doc.items() if k in _MEASURE_FIELDS}
    if doc.get("updated_at"):
        data["updated_at"] = doc["updated_at"]
    return data


async def _set_measurements(user_id: str, patch: dict, updated_at: Optional[str] = None, remove: tuple = ()) -> dict:
    data = {k: v for k, v in (await _get_measurements(user_id)).items() if k != "updated_at" and k not in remove}
    data.update({k: v for k, v in patch.items() if v is not None and k != "updated_at"})
    now = updated_at or datetime.now(timezone.utc).isoformat()
    await db.measurements.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "enc": _enc(data), "updated_at": now},
         "$unset": {k: "" for k in _MEASURE_FIELDS}},
        upsert=True,
    )
    return {**data, "updated_at": now}


async def _migrate_plaintext_personal_data() -> None:
    async for doc in db.measurements.find({"enc": {"$exists": False}}, {"_id": 0}):
        await _set_measurements(doc["user_id"], {k: v for k, v in doc.items() if k in _MEASURE_FIELDS}, doc.get("updated_at"))
    async for w in db.weight_history.find({"weight_kg": {"$exists": True}}, {"_id": 1, "weight_kg": 1}):
        await db.weight_history.update_one({"_id": w["_id"]}, {"$set": {"weight_enc": _enc(w["weight_kg"])}, "$unset": {"weight_kg": ""}})


REQUIRED_MEASURES = ("height_cm", "chest_cm", "waist_cm", "hips_cm", "shoulder_cm", "inseam_cm", "foot_cm")
INCOMPLETE_SIZE = "Completa le tue misure"


def _measures_complete(m: Optional[dict]) -> bool:
    return bool(m) and m.get("method") == "tape" and all(m.get(k) for k in REQUIRED_MEASURES)


class RealMeasuresIn(BaseModel):
    height_cm: float = Field(ge=120, le=230)
    chest_cm: float = Field(ge=60, le=170)
    waist_cm: float = Field(ge=45, le=170)
    hips_cm: float = Field(ge=60, le=180)
    shoulder_cm: float = Field(ge=30, le=70)
    inseam_cm: float = Field(ge=50, le=110)
    foot_cm: float = Field(ge=18, le=35)
    weight_kg: Optional[float] = Field(None, ge=35, le=200)
    age: Optional[int] = Field(None, ge=14, le=100)
    gender: Optional[str] = Field(None, pattern="^(female|male)$")


@api_router.put("/profile/real-measurements")
async def save_real_measurements(body: RealMeasuresIn, user: User = Depends(get_current_user)):
    current = await _get_measurements(user.user_id)
    now = datetime.now(timezone.utc).isoformat()
    patch = body.model_dump(exclude_none=True)
    gender = patch.get("gender") or current.get("gender")
    patch.update({"method": "tape", "measured_at": now, "brand_sizes": brand_sizes(patch, gender)})
    stale = ("precision", "photo_raw_chest", "photo_raw_waist", "tape_offset_chest", "tape_offset_waist",
             "tape_chest", "tape_waist", "tape_calibrated_at", "photo_measured_at")
    remove = stale + tuple(k for k in ("weight_kg", "age") if k not in patch)
    saved = await _set_measurements(user.user_id, patch, now, remove=remove)
    if body.weight_kg is not None and current.get("weight_kg") != body.weight_kg:
        await db.weight_history.insert_one({
            "id": str(uuid.uuid4()), "user_id": user.user_id, "weight_enc": _enc(body.weight_kg),
            "note": "Misure reali", "recorded_at": now,
        })
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"measures_updated_at": now}, "$unset": {"reminder_snoozed_until": ""}})
    await _compute_accuracy(user.user_id)
    return {**saved, "complete": True}


async def _read_photo(photo: UploadFile) -> bytes:
    raw = await photo.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Foto troppo grande (max 15 MB)")
    try:
        from PIL import Image
        import io
        Image.open(io.BytesIO(raw)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Il file non è una foto valida")
    return await run_in_threadpool(head_lock.downscale, raw, head_lock.PERSON_MAX_SIDE)


def _clean_jpeg(raw: bytes) -> bytes:
    # Upright orientation, no EXIF (GPS/device), always JPEG.
    from PIL import Image, ImageOps
    import io
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


# ----- Il Mio Avatar: one full-body photo for measurements + try-ons -----
@api_router.get("/profile/avatar")
async def get_avatar(user: User = Depends(get_current_user)):
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "avatar_path": 1, "avatar_at": 1, "is_family_profile": 1, "name": 1, "reminder_snoozed_until": 1, "measures_updated_at": 1, "refresh_snoozed_until": 1}) or {}
    return {"path": doc.get("avatar_path"), "created_at": doc.get("avatar_at"),
            "profile_name": doc.get("name") if doc.get("is_family_profile") else None,
            "reminder_due": await _reminder_due(user.user_id, doc), "reminder_young": _is_young(await _get_measurements(user.user_id)),
            "refresh_due": await _refresh_due(user.user_id, doc)}


REFRESH_DAYS = 60


async def _refresh_due(user_id: str, doc: dict) -> bool:
    # Separate 60-day banner: refresh weight and Avatar photo (measures popup keeps its 90/180-day logic).
    now = datetime.now(timezone.utc)
    snoozed = _parse_dt(doc.get("refresh_snoozed_until"))
    if snoozed and snoozed > now:
        return False
    avatar_at = _parse_dt(doc.get("avatar_at"))
    last_w = await db.weight_history.find_one({"user_id": user_id}, {"_id": 0, "recorded_at": 1}, sort=[("recorded_at", -1)])
    w_at = _parse_dt((last_w or {}).get("recorded_at"))
    old = lambda d: d is not None and now - d > timedelta(days=REFRESH_DAYS)  # noqa: E731
    return old(avatar_at) or old(w_at)


@api_router.post("/profile/refresh/snooze")
async def snooze_refresh(user: User = Depends(get_current_user)):
    until = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"refresh_snoozed_until": until}})
    return {"snoozed_until": until}


async def _reminder_due(user_id: str, doc: dict) -> bool:
    # Every 2 months: "have your measurements changed?" (snooze = 7 days).
    m = await _get_measurements(user_id)
    last_w = await db.weight_history.find_one({"user_id": user_id}, {"_id": 0, "recorded_at": 1}, sort=[("recorded_at", -1)])
    stamps = [d for d in (_parse_dt(doc.get("measures_updated_at")), _parse_dt(m.get("measured_at")), _parse_dt(m.get("photo_measured_at")), _parse_dt((last_w or {}).get("recorded_at"))) if d]
    now = datetime.now(timezone.utc)
    snoozed = _parse_dt(doc.get("reminder_snoozed_until"))
    return bool(stamps and now - max(stamps) > timedelta(days=_update_interval_days(m)) and not (snoozed and snoozed > now))


YOUNG_AGE = 22
YOUNG_INTERVAL_DAYS = 90
ADULT_INTERVAL_DAYS = 180


def _is_young(m: dict) -> bool:
    return bool(m.get("age")) and m["age"] < YOUNG_AGE


def _update_interval_days(m: dict) -> int:
    # Smart reminder: under 22 still growing -> 90 days, otherwise (or age unknown) 180 days.
    return YOUNG_INTERVAL_DAYS if _is_young(m) else ADULT_INTERVAL_DAYS
REMINDER_SNOOZE_DAYS = 7


@api_router.post("/profile/reminder/snooze")
async def snooze_reminder(user: User = Depends(get_current_user)):
    until = (datetime.now(timezone.utc) + timedelta(days=REMINDER_SNOOZE_DAYS)).isoformat()
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"reminder_snoozed_until": until}})
    return {"snoozed_until": until}


class DisplayNameIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


@api_router.put("/profile/display-name")
async def set_display_name(body: DisplayNameIn, user: User = Depends(get_account_user)):
    name = " ".join(body.name.split())[:40]
    if not name:
        raise HTTPException(status_code=400, detail="Inserisci il tuo nome")
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"display_name": name}})
    return {"display_name": name}


@api_router.post("/profile/avatar")
async def set_avatar(
    photo: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    # The avatar photo is used ONLY for try-ons: no measurement is ever estimated from it.
    raw = _clean_jpeg(await _read_photo(photo))
    path = f"{APP_NAME}/avatar/{user.user_id}/{uuid.uuid4().hex}.bin"
    put_object(path, FERNET.encrypt(raw), "application/octet-stream")
    now = datetime.now(timezone.utc).isoformat()
    await db.files.insert_one({
        "id": str(uuid.uuid4()), "user_id": user.user_id, "kind": "avatar", "storage_path": path,
        "encrypted": True, "is_deleted": False, "created_at": now,
    })
    old = (await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "avatar_path": 1}) or {}).get("avatar_path")
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"avatar_path": path, "avatar_at": now}})
    if old:
        await _mark_files_deleted([old], user.user_id)
    return {"avatar": {"path": path, "created_at": now}}


@api_router.delete("/profile/avatar")
async def delete_avatar(user: User = Depends(get_current_user)):
    old = (await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "avatar_path": 1}) or {}).get("avatar_path")
    if old:
        await _mark_files_deleted([old], user.user_id)
    await db.users.update_one({"user_id": user.user_id}, {"$unset": {"avatar_path": "", "avatar_at": ""}})
    return {"deleted": bool(old)}


# ----- Profile / Measurements -----
@api_router.get("/profile/measurements")
async def get_measurements(user: User = Depends(get_current_user)):
    m = await _get_measurements(user.user_id)
    return {**m, "complete": _measures_complete(m)}


@api_router.put("/profile/measurements")
async def save_measurements(m: Measurements, user: User = Depends(get_current_user)):
    data = m.model_dump(exclude_none=True)
    return await _set_measurements(user.user_id, data, remove=("brand_sizes", "precision", "method"))


# ----- Weight history (check every 2 months) -----


class WeightEntry(BaseModel):
    weight_kg: float
    note: Optional[str] = None
    recorded_at: Optional[str] = None


def _weight_status(last_iso: Optional[str], days: int = ADULT_INTERVAL_DAYS) -> dict:
    if not last_iso:
        return {"last_check_at": None, "next_check_at": None, "days_overdue": 0, "due": True}
    last = datetime.fromisoformat(last_iso)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    nxt = last + timedelta(days=days)
    now = datetime.now(timezone.utc)
    delta_days = (now - nxt).days
    return {
        "last_check_at": last.isoformat(),
        "next_check_at": nxt.isoformat(),
        "days_overdue": max(0, delta_days),
        "due": now >= nxt,
    }


@api_router.get("/profile/weight-history")
async def get_weight_history(user: User = Depends(get_current_user)):
    items = await db.weight_history.find(
        {"user_id": user.user_id}, {"_id": 0, "user_id": 0}
    ).sort("recorded_at", -1).to_list(200)
    for it in items:
        if "weight_enc" in it:
            it["weight_kg"] = _dec(it.pop("weight_enc"))
    last_iso = items[0]["recorded_at"] if items else None
    return {"entries": items, "status": _weight_status(last_iso, _update_interval_days(await _get_measurements(user.user_id)))}


@api_router.post("/profile/weight-history")
async def add_weight_entry(entry: WeightEntry, user: User = Depends(get_current_user)):
    now_iso = datetime.now(timezone.utc).isoformat()
    recorded_at = now_iso
    if entry.recorded_at:
        try:
            dt = datetime.fromisoformat(entry.recorded_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            recorded_at = dt.isoformat()
        except Exception:
            recorded_at = now_iso
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "weight_enc": _enc(entry.weight_kg),
        "note": entry.note,
        "recorded_at": recorded_at,
    }
    await db.weight_history.insert_one(doc)
    # Keep current measurement in sync for size & avatar
    await _set_measurements(user.user_id, {"weight_kg": entry.weight_kg}, recorded_at)
    doc.pop("_id", None)
    doc.pop("user_id", None)
    doc["weight_kg"] = entry.weight_kg
    doc.pop("weight_enc", None)
    # Refresh accuracy snapshot
    await _compute_accuracy(user.user_id)
    return {"entry": doc, "status": _weight_status(recorded_at, _update_interval_days(await _get_measurements(user.user_id)))}


@api_router.delete("/profile/weight-history/{entry_id}")
async def delete_weight_entry(entry_id: str, user: User = Depends(get_current_user)):
    res = await db.weight_history.delete_one({"id": entry_id, "user_id": user.user_id})
    return {"deleted": res.deleted_count}


# ----- Subscription / Honeymoon logic -----
HONEYMOON_DAYS = 30
FREE_MONTHLY_LIMIT = 5

def _parse_dt(v) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def get_subscription_status(user_id: str) -> dict:
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0}) or {}
    created_at = _parse_dt(user_doc.get("created_at")) or datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    free_end = _parse_dt(user_doc.get("free_month_end")) or created_at + timedelta(days=HONEYMOON_DAYS)
    honeymoon_active = now < free_end
    days_left_honeymoon = int(-(-(free_end - now).total_seconds() // 86400)) if honeymoon_active else 0

    plan = user_doc.get("plan", "FREE")
    exp = _parse_dt(user_doc.get("plan_expires_at"))
    if plan in ("SINGLE", "FAMILY") and exp and exp <= now:
        plan = "FREE"
        await db.users.update_one({"user_id": user_id}, {"$set": {"plan": "FREE"}})
    extra_credits = int(user_doc.get("extra_tryon_credits", 0) or 0)

    # Monthly reset on the 1st of the month
    current_month = now.strftime("%Y-%m")
    monthly = user_doc.get("monthly_tryon_count") or {}
    if monthly.get("month") != current_month:
        monthly = {"month": current_month, "used": 0}
        await db.users.update_one({"user_id": user_id}, {"$set": {"monthly_tryon_count": monthly}})

    used = int(monthly.get("used", 0) or 0)
    if plan in ("SINGLE", "FAMILY") or honeymoon_active:
        limit = None
        remaining = None
        is_blocked = False
    else:
        limit = FREE_MONTHLY_LIMIT
        remaining = max(0, limit - used)
        is_blocked = remaining <= 0 and extra_credits <= 0

    return {
        "plan": plan,
        "honeymoon_active": honeymoon_active,
        "days_left_honeymoon": days_left_honeymoon,
        "tryons_used_this_month": used,
        "tryons_limit": limit,
        "tryons_remaining": remaining,
        "extra_credits": extra_credits,
        "is_blocked": is_blocked,
        "current_month": current_month,
        "member_since": created_at.isoformat(),
        "plan_expires_at": user_doc.get("plan_expires_at") if plan in ("SINGLE", "FAMILY") else None,
    }


async def consume_tryon_quota(user_id: str, status: dict):
    """After a successful try-on. Decrement credits/counter if applicable."""
    if status["plan"] in ("SINGLE", "FAMILY") or status["honeymoon_active"]:
        return
    # FREE plan after honeymoon
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0}) or {}
    extra_credits = int(user_doc.get("extra_tryon_credits", 0) or 0)
    if extra_credits > 0:
        await db.users.update_one({"user_id": user_id}, {"$inc": {"extra_tryon_credits": -1}})
    else:
        await db.users.update_one({"user_id": user_id}, {"$inc": {"monthly_tryon_count.used": 1}})


@api_router.get("/subscription/status")
async def api_subscription_status(user: User = Depends(get_account_user)):
    return await get_subscription_status(user.account_id)


class CheckoutRequest(BaseModel):
    option: str  # "extra" | "single" | "family"
    origin_url: str


STRIPE_LOOKUP = {"extra": "atelier_extra_once", "single": "atelier_single_30d", "family": "atelier_family_30d"}
PLAN_DAYS = 30


@api_router.post("/subscription/checkout")
async def api_subscription_checkout(req: CheckoutRequest, request: Request, user: User = Depends(get_account_user)):
    if req.option not in STRIPE_LOOKUP:
        raise HTTPException(status_code=400, detail="Invalid option")
    origin_hdr = (request.headers.get("origin") or "").rstrip("/")
    if origin_hdr and origin_hdr != req.origin_url.rstrip("/"):
        raise HTTPException(status_code=400, detail="Origin non valida")
    prices = await run_in_threadpool(lambda: stripe.Price.list(lookup_keys=[STRIPE_LOOKUP[req.option]], active=True, limit=1).data)
    if not prices:
        raise HTTPException(status_code=500, detail="Prezzo non configurato")
    price = prices[0]
    if req.option in ("single", "family"):
        st = await get_subscription_status(user.account_id)
        exp = _parse_dt(st.get("plan_expires_at"))
        rank = {"FREE": 0, "SINGLE": 1, "FAMILY": 2}
        if exp and exp - datetime.now(timezone.utc) > timedelta(days=3) and rank.get(st["plan"], 0) >= rank[req.option.upper()]:
            raise HTTPException(status_code=409, detail=f"Hai già un abbonamento {st['plan'].capitalize()} attivo fino al {exp.strftime('%d/%m/%Y')}: non serve pagare di nuovo.")
    customer_id = await _stripe_customer_for(user)
    origin = req.origin_url.rstrip("/")
    kwargs = dict(
        line_items=[{"price": price.id, "quantity": 1}],
        mode="payment",
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/payment/cancel",
        **({"customer": customer_id} if customer_id else {"customer_email": user.email or None}),
        metadata={"user_id": user.account_id, "option": req.option, "email": user.email or ""},
    )
    try:
        session = await run_in_threadpool(lambda: stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True}))
    except stripe.error.InvalidRequestError as e:
        msg = (e.user_message or str(e)).lower()
        if "managed" not in msg and "ineligible" not in msg:
            raise
        session = await run_in_threadpool(lambda: stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required"))
    now = datetime.now(timezone.utc).isoformat()
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user.account_id, "option": req.option,
        "lookup_key": STRIPE_LOOKUP[req.option], "amount": price.unit_amount / 100.0, "currency": price.currency,
        "status": "initiated", "payment_status": "pending", "applied": False, "livemode": bool(session.livemode),
        "created_at": now, "updated_at": now,
    })
    return {"checkout_url": session.url, "session_id": session.id}


async def _apply_paid_session(session_id: str) -> None:
    # Atomic claim so the plan is granted exactly once (poll + webhook may race).
    tx = await db.payment_transactions.find_one_and_update(
        {"session_id": session_id, "payment_status": "paid", "applied": False},
        {"$set": {"applied": True, "applied_at": datetime.now(timezone.utc).isoformat()}},
    )
    if not tx:
        return
    uid, option = tx["user_id"], tx["option"]
    now = datetime.now(timezone.utc)
    if option == "extra":
        await db.users.update_one({"user_id": uid}, {"$inc": {"extra_tryon_credits": 1}})
        asyncio.create_task(_send_receipt(session_id))
        return
    doc = await db.users.find_one({"user_id": uid}, {"_id": 0, "plan": 1, "plan_expires_at": 1}) or {}
    plan = option.upper()
    cur_exp = _parse_dt(doc.get("plan_expires_at"))
    start = cur_exp if doc.get("plan") == plan and cur_exp and cur_exp > now else now
    await db.users.update_one({"user_id": uid}, {"$set": {
        "plan": plan, "plan_started_at": now.isoformat(),
        "plan_expires_at": (start + timedelta(days=PLAN_DAYS)).isoformat(), "stripe_last_session": session_id,
    }})
    asyncio.create_task(_send_receipt(session_id))


async def _send_receipt(session_id: str) -> None:
    # Claimed once per payment; failures are logged on the transaction, never block the plan.
    tx = await db.payment_transactions.find_one_and_update(
        {"session_id": session_id, "receipt_status": {"$exists": False}}, {"$set": {"receipt_status": "sending"}})
    if not tx:
        return
    u = await db.users.find_one({"user_id": tx["user_id"]}, {"_id": 0, "email": 1, "display_name": 1, "name": 1, "plan_expires_at": 1}) or {}
    if not u.get("email"):
        await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"receipt_status": "no_email"}})
        return
    exp = _parse_dt(u.get("plan_expires_at")) if tx["option"] != "extra" else None
    msg = receipt.build(u.get("display_name") or (u.get("name") or "").split(" ")[0], tx["option"], float(tx.get("amount") or 0),
                        tx.get("currency") or "eur", datetime.now(timezone.utc), exp, session_id)
    try:
        await run_in_threadpool(receipt.send, u["email"], msg)
        await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"receipt_status": "sent", "receipt_sent_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logger.error(f"receipt send failed for {session_id}: {e}")
        await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"receipt_status": "failed", "receipt_error": str(e)[:200]}})


async def _mark_paid(session_id: str, s) -> None:
    await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid", "stripe_payment_intent_id": s.get("payment_intent"),
                  **({"amount": s.get("amount_total") / 100.0} if s.get("amount_total") is not None else {}),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await _apply_paid_session(session_id)


@api_router.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.get("payment_status") != "paid":
        try:
            s = await run_in_threadpool(stripe.checkout.Session.retrieve, session_id)
            if s.payment_status == "paid":
                await _mark_paid(session_id, s)
            elif s.status == "expired":
                await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"status": "expired", "payment_status": "expired"}})
            tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except stripe.error.StripeError as e:
            logger.warning(f"stripe status check failed: {e}")
    return {"session_id": session_id, "status": tx["status"], "payment_status": tx["payment_status"], "option": tx.get("option")}


@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), os.environ["STRIPE_WEBHOOK_SECRET"])
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded") and obj.get("payment_status") == "paid":
        await _mark_paid(obj["id"], obj)
    elif t in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        st = "failed" if t.endswith("failed") else "expired"
        await db.payment_transactions.update_one({"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                                                 {"$set": {"status": st, "payment_status": st}})
    elif t == "charge.refunded":
        await db.payment_transactions.update_one({"stripe_payment_intent_id": obj.get("payment_intent")},
                                                 {"$set": {"status": "refunded", "payment_status": "refunded"}})
    return {"status": "ok"}


@api_router.post("/subscription/cancel")
async def api_subscription_cancel(user: User = Depends(get_account_user)):
    """Downgrade back to FREE (demo helper)."""
    await db.users.update_one({"user_id": user.account_id}, {"$set": {"plan": "FREE"}})
    return await get_subscription_status(user.account_id)


# ----- Family profiles -----
FAMILY_MAX_PROFILES = 4


class FamilyProfileIn(BaseModel):
    name: str


async def _family_payload(owner: User) -> dict:
    owner_doc = await db.users.find_one({"user_id": owner.user_id}, {"_id": 0, "plan": 1}) or {}
    subs = await db.users.find(
        {"owner_id": owner.user_id, "is_family_profile": True}, {"_id": 0, "user_id": 1, "name": 1}
    ).sort("created_at", 1).to_list(FAMILY_MAX_PROFILES)
    profiles = [{"profile_id": owner.user_id, "name": owner.name, "is_owner": True}]
    profiles += [{"profile_id": p["user_id"], "name": p["name"], "is_owner": False} for p in subs]
    return {"enabled": owner_doc.get("plan") == "FAMILY", "max_profiles": FAMILY_MAX_PROFILES, "profiles": profiles}


def _clean_profile_name(name: str) -> str:
    name = (name or "").strip()
    if not name or len(name) > 40:
        raise HTTPException(status_code=400, detail="Nome non valido (1-40 caratteri)")
    return name


@api_router.get("/family/profiles")
async def family_list(owner: User = Depends(get_account_user)):
    return await _family_payload(owner)


@api_router.post("/family/profiles")
async def family_create(body: FamilyProfileIn, owner: User = Depends(get_account_user)):
    data = await _family_payload(owner)
    if not data["enabled"]:
        raise HTTPException(status_code=403, detail="Disponibile solo con il piano Family")
    if len(data["profiles"]) >= FAMILY_MAX_PROFILES:
        raise HTTPException(status_code=400, detail="Massimo 4 profili")
    await db.users.insert_one({
        "user_id": f"fam_{uuid.uuid4().hex[:12]}",
        "email": "",
        "name": _clean_profile_name(body.name),
        "owner_id": owner.user_id,
        "is_family_profile": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return await _family_payload(owner)


@api_router.patch("/family/profiles/{profile_id}")
async def family_rename(profile_id: str, body: FamilyProfileIn, owner: User = Depends(get_account_user)):
    data = await _family_payload(owner)
    if not data["enabled"]:
        raise HTTPException(status_code=403, detail="Disponibile solo con il piano Family")
    res = await db.users.update_one(
        {"user_id": profile_id, "owner_id": owner.user_id, "is_family_profile": True},
        {"$set": {"name": _clean_profile_name(body.name)}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Profilo non trovato")
    return await _family_payload(owner)


# ----- Fitting Accuracy -----
# Formula FASE 2:
#   base 100
#   - 15 if altezza (height_cm) missing
#   - 25 per each missing of torace/vita/fianchi (chest, waist, hips)
#   - 30 if weight > 60 days old OR missing entirely
ACCURACY_CORE = ["chest_cm", "waist_cm", "hips_cm"]


async def _compute_accuracy(user_id: str) -> dict:
    m = await _get_measurements(user_id)
    last_weight_doc = await db.weight_history.find_one(
        {"user_id": user_id}, {"_id": 0}, sort=[("recorded_at", -1)]
    )
    last_weight_update = last_weight_doc["recorded_at"] if last_weight_doc else (m.get("updated_at") if m.get("weight_kg") else None)

    complete = _measures_complete(m)
    # Only real tape measures count: photo-era values are treated as missing.
    missing_fields = [f for f in REQUIRED_MEASURES if not (complete or (m.get("method") == "tape" and m.get(f)))]
    accuracy = 100 - 15 * len(missing_fields)

    # Weight is optional: freshness follows the latest real measurement or weight update.
    stamps = [d for d in (_parse_dt(m.get("measured_at")), _parse_dt(last_weight_update)) if d]
    weight_stale = bool(stamps) and (datetime.now(timezone.utc) - max(stamps)).days > _update_interval_days(m)
    if weight_stale:
        accuracy -= 30
    if not complete:
        accuracy = min(accuracy, 40)
    accuracy = max(0, min(100, accuracy))
    result = {
        "accuracy": accuracy,
        "last_weight_update": last_weight_update,
        "reliable": accuracy >= 70,
        "missing_fields": missing_fields,
        "weight_stale": weight_stale,
        "weight": m.get("weight_kg"),
    }
    # Persist snapshot on user profile
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "fitting_accuracy": accuracy,
            "fitting_accuracy_updated_at": datetime.now(timezone.utc).isoformat(),
            "is_reliable": result["reliable"],
            "last_weight_update": last_weight_update,
        }},
    )
    return result


@api_router.get("/fitting-accuracy")
async def consumer_fitting_accuracy(user: User = Depends(get_current_user)):
    """
    Frontend-facing accuracy endpoint.
    Server-side only — the scoring logic is NEVER exposed to the client.
    Returns a presentation-safe payload: value, status band and reliable flag.
    """
    res = await _compute_accuracy(user.user_id)
    value, last_weight_update = res["accuracy"], res["last_weight_update"]
    status = "green" if value >= 70 else ("yellow" if value >= 40 else "red")

    reliable = status == "green"
    # Snapshot so the B2B API & brand dashboards remain consistent.
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "fitting_accuracy": value,
            "fitting_accuracy_status": status,
            "is_reliable": reliable,
            "last_weight_update": last_weight_update,
            "fitting_accuracy_updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {
        "accuracy": value,
        "status": status,
        "reliable": reliable,
        "last_weight_update": last_weight_update,
    }


@api_router.get("/profile/fitting-accuracy")
async def my_fitting_accuracy(user: User = Depends(get_current_user)):
    return await _compute_accuracy(user.user_id)


@api_router.get("/fitting-accuracy/{user_id}")
async def public_fitting_accuracy(user_id: str):
    """Public endpoint used by Shopify brands to decide if free returns apply."""
    exists = await db.users.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1})
    if not exists:
        raise HTTPException(status_code=404, detail="User not found")
    data = await _compute_accuracy(user_id)
    # Public: reliability signal only, never personal data.
    return {k: data[k] for k in ("accuracy", "last_weight_update", "reliable", "weight_stale")}


@api_router.get("/b2b/fitting-accuracy/{user_id}")
async def b2b_fitting_accuracy(user_id: str):
    """B2B endpoint for Shopify brands — reliability signal for free-return decisions."""
    exists = await db.users.find_one({"user_id": user_id}, {"_id": 0, "user_id": 1})
    if not exists:
        raise HTTPException(status_code=404, detail="User not found")
    data = await _compute_accuracy(user_id)
    lw = data.get("last_weight_update")
    last_date = lw.split("T", 1)[0] if lw else None
    return {
        "userId": user_id,
        "accuracy": data["accuracy"],
        "last_weight_update": last_date,
        "is_reliable": data["reliable"],
    }




# ----- File upload / serve -----
@api_router.post("/upload")
async def upload(kind: str = Query(..., regex="^(person|garment)$"), file: UploadFile = File(...), user: User = Depends(get_current_user)):
    if (await get_subscription_status(user.account_id))["is_blocked"]:
        raise HTTPException(status_code=402, detail="Prove gratuite esaurite: scegli un piano per continuare.")
    ext = (file.filename or "img").rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "png"
    path = f"{APP_NAME}/{kind}/{user.user_id}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    content_type = file.content_type or f"image/{'jpeg' if ext == 'jpg' else ext}"
    if kind == "person":
        try:
            data = await run_in_threadpool(head_lock.downscale, data, head_lock.PERSON_MAX_SIDE)
        except Exception:
            raise HTTPException(status_code=400, detail="Il file non è una foto valida")
    result = put_object(path, data, content_type)
    await db.files.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "kind": kind,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", 0),
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"path": result["path"]}


async def _account_owner_ids(account: User) -> set:
    subs = await db.users.find({"owner_id": account.user_id, "is_family_profile": True}, {"_id": 0, "user_id": 1}).to_list(10)
    return {account.user_id, *[x["user_id"] for x in subs]}


def _path_owner(path: str) -> Optional[str]:
    parts = path.split("/")
    return parts[2] if len(parts) >= 4 and parts[0] == APP_NAME else None


@api_router.get("/files/{path:path}")
async def files_get(path: str, request: Request, authorization: Optional[str] = Header(None)):
    # Private by default: only the account (and its family profiles) can view; shared outfits stay public.
    if path.split("/")[1:2] == ["measure"]:
        raise HTTPException(status_code=404, detail="File non trovato")
    if await db.files.find_one({"storage_path": path, "is_deleted": True}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="File non trovato")
    if not await db.outfits.find_one({"result_path": path, "shared": True}, {"_id": 1}):
        account = await get_account_user(request, authorization)
        if _path_owner(path) not in await _account_owner_ids(account):
            raise HTTPException(status_code=403, detail="Accesso negato")
    data, content_type = get_object(path)
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=3600"})


def _erase_object(path: str) -> None:
    # Object storage has no delete: overwrite the content so the image is gone for good.
    try:
        put_object(path, b"", "application/octet-stream")
    except Exception as e:
        logger.warning(f"erase failed for {path}: {e}")


async def _mark_files_deleted(paths: list, user_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for p in paths:
        _erase_object(p)
        await db.files.update_one(
            {"storage_path": p},
            {"$set": {"is_deleted": True, "deleted_at": now}, "$setOnInsert": {"user_id": user_id}},
            upsert=True,
        )


@api_router.post("/photos/delete-all")
async def photos_delete_all(user: User = Depends(get_current_user)):
    uid = user.user_id
    paths = set()
    async for f in db.files.find({"user_id": uid, "kind": {"$in": ["person", "measure", "avatar"]}, "is_deleted": {"$ne": True}}, {"_id": 0, "storage_path": 1}):
        paths.add(f["storage_path"])
    tryons = await db.tryons.find({"user_id": uid}, {"_id": 0, "person_path": 1, "result_path": 1}).to_list(5000)
    outfits = await db.outfits.find({"user_id": uid}, {"_id": 0, "result_path": 1, "person_path": 1}).to_list(5000)
    for d in tryons + outfits:
        for k in ("person_path", "result_path"):
            if d.get(k) and _path_owner(d[k]) == uid:
                paths.add(d[k])
    await _mark_files_deleted(sorted(paths), uid)
    await db.tryons.delete_many({"user_id": uid})
    await db.outfits.delete_many({"user_id": uid})
    await db.users.update_one({"user_id": uid}, {"$unset": {"avatar_path": "", "avatar_at": ""}})
    return {"deleted_photos": len(paths), "deleted_tryons": len(tryons), "deleted_outfits": len(outfits)}


@api_router.delete("/files/{path:path}")
async def files_delete(path: str, user: User = Depends(get_current_user)):
    if _path_owner(path) != user.user_id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    await _mark_files_deleted([path], user.user_id)
    return {"deleted": True}


async def _hand_boxes(person_path: str, person_bytes: bytes) -> list:
    # Hands are detected once per person photo (cached), then pasted back by head_lock when they stay in place.
    cached = await db.hand_boxes.find_one({"path": person_path}, {"_id": 0, "boxes": 1})
    if cached:
        return cached["boxes"]
    small = await run_in_threadpool(head_lock.downscale, person_bytes, head_lock.GARMENT_MAX_SIDE)
    chat = LlmChat(api_key=EMERGENT_KEY, session_id=f"hands-{uuid.uuid4().hex[:8]}", system_message="You are a precise hand detector. Reply with JSON only.")
    chat.with_model("gemini", "gemini-3.8-flash")
    prompt = ("Detect every visible hand of the person in this photo (including a hand holding a phone, and hands in a mirror reflection of that person). "
              "Return ONLY JSON: {\"hands\": [{\"box_2d\": [ymin, xmin, ymax, xmax]}]} normalised 0-1000, each box tightly containing the whole hand "
              "(fingers to wrist). Return {\"hands\": []} if no hand is clearly visible.")
    try:
        reply = await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(base64.b64encode(small).decode())]))
        data = _extract_json(reply)
    except Exception as e:
        logger.warning(f"hand detection failed: {e}")
        return []
    if not isinstance(data, dict):
        return []
    boxes = [h["box_2d"] for h in (data.get("hands") or [])[:4]
             if isinstance(h, dict) and isinstance(h.get("box_2d"), list) and len(h["box_2d"]) == 4]
    await db.hand_boxes.update_one({"path": person_path}, {"$set": {"boxes": boxes, "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return boxes


HANDS_RULE = (
    "IDENTITY — STRICT:\n"
    "• Use IMAGE 1 as the EXACT source for identity. Exactly ONE person with ONE face: no duplicate, twin or second face, no face blending, no face swap.\n"
    "• Preserve the original facial features 100% identical to IMAGE 1: do not modify the face, do not generate a new face, keep the original face geometry.\n"
    "• Body proportions come from IMAGE 1 for sizing, but the person wears EXACTLY the garment(s) provided.\n"
    "• Keep the original background of IMAGE 1 with no distortion. Photorealistic, high resolution, natural skin texture.\n"
    "HANDS — STRICT:\n"
    "• Natural hands with exactly 5 fingers each, relaxed; if the person holds a phone, it is held correctly as in IMAGE 1.\n"
    "• Hands, fingers and wrists must be CLEAN natural skin: absolutely NO tattoos, ink, drawings or markings on the hands.\n"
    "• Do NOT propagate, copy or extend neck/arm/body tattoos onto the hands — tattoos stay ONLY where they are in IMAGE 1, never on hands.\n"
    "• NEGATIVE PROMPT: double face, duplicated face, twin face, blurry face, distorted face, extra hands, extra fingers, 6 fingers, "
    "deformed hands, mutated hands, warped hands, AI artifacts, face swap, tattoos on hands, ink on fingers, tattoos on wrists, hand tattoos, finger tattoos.\n"
)


def _measurements_desc(m_doc: Optional[dict]) -> str:
    parts = []
    for k, label in [
        ("height_cm", "height"), ("weight_kg", "weight"),
        ("chest_cm", "chest"), ("waist_cm", "waist"), ("hips_cm", "hips"),
        ("shoulder_cm", "shoulders"), ("inseam_cm", "inseam"), ("foot_cm", "foot length"),
    ]:
        v = (m_doc or {}).get(k)
        if v:
            parts.append(f"{label} {v}{'kg' if k == 'weight_kg' else 'cm'}")
    return (" Body measurements of the person: " + ", ".join(parts) + ".") if parts else ""


# ----- Try-on generation -----
class TryOnRequest(BaseModel):
    person_path: str
    garment_path: str
    garment_name: Optional[str] = None
    garment_category: Optional[str] = None  # top, bottom, dress, shoes, outerwear
    notes: Optional[str] = None
    chosen_size: Optional[str] = None
    garment_id: Optional[str] = None


async def _render_single(user_id: str, person_path: str, garment_path: str, category_in: Optional[str], name: Optional[str], m_doc: dict, extra: str = "") -> str:
    # Load both images
    person_bytes, person_ct = get_object(person_path)
    garment_bytes, garment_ct = get_object(garment_path)
    canvas_bytes, lock = await run_in_threadpool(head_lock.prepare, person_bytes, head_lock.is_long(category_in, name or ""), await _hand_boxes(person_path, person_bytes))
    garment_bytes = await run_in_threadpool(head_lock.downscale, garment_bytes, head_lock.GARMENT_MAX_SIDE)
    person_b64 = base64.b64encode(canvas_bytes).decode('utf-8')
    garment_b64 = base64.b64encode(garment_bytes).decode('utf-8')
    del person_bytes, garment_bytes, canvas_bytes

    measurements_desc = _measurements_desc(m_doc)

    category = (category_in or "garment").lower()
    prompt = (
        f"Create a photorealistic virtual try-on image. IMAGE 1 is a real photo of a specific person — "
        f"the ONLY person who may appear in the output. IMAGE 2 shows a {category} to be worn.\n\n"
        f"ABSOLUTE REQUIREMENTS — identity preservation is top priority:\n"
        f"• Keep the EXACT face, head, hair, skin tone, body proportions and pose from IMAGE 1 — pixel-level fidelity.\n"
        f"• Keep every visible tattoo (except on hands), mole, scar, piercing, jewellery and personal detail EXACTLY as in IMAGE 1.\n"
        f"• Keep the shape, pose, fingers and nails of the person's hands as in IMAGE 1 — do NOT substitute with other hands (hands always tattoo-free).\n"
        f"• Keep the ORIGINAL BACKGROUND and lighting from IMAGE 1 unchanged (room, wall, floor, props, shadows).\n"
        f"• Framing must match IMAGE 1 — do NOT crop the head, do NOT zoom in or out, keep the same aspect and composition.\n"
        f"• The output must contain exactly ONE person — the same person as IMAGE 1. No stock models, no replacement body, no extra people.\n\n"
        f"WHAT TO CHANGE:\n"
        f"• ONLY swap/overlay the {category} currently worn (if any) with the garment from IMAGE 2.\n"
        f"• Fit the garment realistically onto the person's existing body with natural fabric drape, folds and shadows "
        f"that match the lighting of IMAGE 1.\n"
        f"• Preserve the colour, pattern, cut and material of the garment from IMAGE 2 as faithfully as possible.\n\n"
        f"FORBIDDEN:\n"
        f"• Do NOT alter the face, head, hair or hands.\n"
        f"• Do NOT replace the background with a studio or neutral backdrop.\n"
        f"• Do NOT cut, crop or extend the head/arms/legs beyond the original frame.\n"
        f"• Do NOT invent new tattoos, jewellery or accessories that are not in IMAGE 1.\n\n"
        f"{HANDS_RULE}"
        f"{head_lock.HEAD_LOCK_RULE}"
        f"{measurements_desc}"
        f"{extra}"
    )

    session_id = f"tryon-{user_id}-{uuid.uuid4().hex[:8]}"
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=session_id,
        system_message=(
            "You are a professional fashion virtual try-on image generator. "
            "Your only job is to re-dress the SAME person in the SAME scene, "
            "preserving face, hands, tattoos, hair, pose and the original background. "
            "Never generate stock models, replacement bodies, or neutral studios. "
            "Hands must always be clean, with no tattoos. "
            "The person in IMAGE 1 must remain fully recognisable."
        ),
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    msg = UserMessage(text=prompt, file_contents=[ImageContent(person_b64), ImageContent(garment_b64)])
    try:
        text, images = await chat.send_message_multimodal_response(msg)
    except Exception as e:
        logger.error(f"Try-on generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")
    if not images:
        raise HTTPException(status_code=500, detail="No image was generated")
    img = images[0]
    del msg, person_b64, garment_b64
    out_bytes = await run_in_threadpool(head_lock.finalize, base64.b64decode(img['data']), lock)
    del images, img
    result_path = f"{APP_NAME}/tryon/{user_id}/{uuid.uuid4().hex}.png"
    put_object(result_path, out_bytes, "image/png")
    return result_path


@api_router.post("/tryon/generate")
async def tryon_generate(req: TryOnRequest, user: User = Depends(get_current_user)):
    # Enforce subscription quota before any paid work (Nano Banana call).
    status = await get_subscription_status(user.account_id)
    if status["is_blocked"]:
        raise HTTPException(status_code=402, detail="Quota exhausted — subscribe or buy an extra try-on.")
    m_doc = await _get_measurements(user.user_id)
    result_path = await _render_single(user.user_id, req.person_path, req.garment_path, req.garment_category, req.garment_name, m_doc)

    rec_size = recommend_size(m_doc, req.garment_category or "")
    tryon_id = str(uuid.uuid4())
    accuracy_snapshot = await _compute_accuracy(user.user_id)
    created_at = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": tryon_id,
        "user_id": user.user_id,
        "person_path": req.person_path,
        "garment_path": req.garment_path,
        "result_path": result_path,
        "garment_name": req.garment_name,
        "garment_category": req.garment_category,
        "recommended_size": rec_size,
        "chosen_size": req.chosen_size,
        "notes": req.notes,
        "fitting_accuracy_at_time": accuracy_snapshot["accuracy"],
        "is_reliable_at_time": accuracy_snapshot["reliable"],
        "created_at": created_at,
    }
    await db.tryons.insert_one(doc)
    # Legal evidence log — the proof that our size suggestion was reliable at the moment of purchase
    await db.try_on_log.insert_one({
        "id": str(uuid.uuid4()),
        "userId": user.user_id,
        "tryonId": tryon_id,
        "garmentId": req.garment_id or req.garment_path,
        "garmentName": req.garment_name,
        "garmentCategory": req.garment_category,
        "recommendedSize": rec_size,
        "chosenSize": req.chosen_size,
        "fittingAccuracyAtTime": accuracy_snapshot["accuracy"],
        "isReliableAtTime": accuracy_snapshot["reliable"],
        "timestamp": created_at,
    })
    # Deduct quota after a successful generation.
    await consume_tryon_quota(user.account_id, status)
    doc.pop("_id", None)
    return doc


# ----- Copia Look da Modello -----
COPYLOOK_CATS = ("top", "bottom", "dress", "outerwear", "shoes")


class CopyLookExtractRequest(BaseModel):
    model_path: str


class CopyLookItem(BaseModel):
    name: str
    category: str
    image_path: Optional[str] = None


class CopyLookApplyRequest(BaseModel):
    model_path: str
    items: List[CopyLookItem]


class CopyLookSaveRequest(BaseModel):
    image_path: str
    name: str
    category: str


def _crop_box(img_bytes: bytes, box: list) -> bytes:
    from PIL import Image, ImageOps
    import io
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes))).convert("RGB")
    w, h = im.size
    y0, x0, y1, x1 = [max(0, min(1000, float(v))) for v in box]
    pad = 5
    crop = im.crop((int(max(0, x0 - pad) * w / 1000), int(max(0, y0 - pad) * h / 1000),
                    int(min(1000, x1 + pad) * w / 1000), int(min(1000, y1 + pad) * h / 1000)))
    out = io.BytesIO()
    crop.save(out, "JPEG", quality=90)
    return out.getvalue()


@api_router.post("/copylook/extract")
async def copylook_extract(req: CopyLookExtractRequest, user: User = Depends(get_current_user)):
    if _path_owner(req.model_path) != user.user_id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    img_bytes, _ = get_object(req.model_path)
    img_bytes = await run_in_threadpool(head_lock.downscale, img_bytes, head_lock.PERSON_MAX_SIDE)
    prompt = (
        "This is a photo of a fashion model. Detect EVERY clothing item and shoes worn by the model "
        "(ignore jewellery, bags and accessories). Return ONLY JSON:\n"
        "{\"items\": [{\"name\": \"short Italian name with colour and material, e.g. Blazer beige in lino\", "
        "\"category\": \"top|bottom|dress|outerwear|shoes\", \"box_2d\": [ymin, xmin, ymax, xmax]}]}\n"
        "box_2d is normalised 0-1000 and must tightly contain only that garment. A pair of shoes is ONE item whose box covers both shoes. "
        "No text outside the JSON."
    )
    chat = LlmChat(api_key=EMERGENT_KEY, session_id=f"copylook-{uuid.uuid4().hex[:8]}", system_message="You are a fashion garment detector. Reply with JSON only.")
    chat.with_model("gemini", "gemini-3.8-flash")
    try:
        reply = await chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(base64.b64encode(img_bytes).decode())]))
    except Exception as e:
        logger.error(f"copylook extract error: {e}")
        raise HTTPException(status_code=500, detail="Analisi della foto non riuscita, riprova.")
    raw = (_extract_json(reply) or {}).get("items") or []
    items, seen = [], set()
    for it in raw[:8]:
        cat = str(it.get("category") or "").lower()
        if cat not in COPYLOOK_CATS or (cat == "shoes" and cat in seen):
            continue
        seen.add(cat)
        image_path = None
        box = it.get("box_2d")
        if isinstance(box, list) and len(box) == 4:
            try:
                image_path = f"{APP_NAME}/garment/{user.user_id}/{uuid.uuid4().hex}.jpg"
                put_object(image_path, await run_in_threadpool(_crop_box, img_bytes, box), "image/jpeg")
            except Exception as e:
                logger.warning(f"copylook crop failed: {e}")
                image_path = None
        items.append({"name": str(it.get("name") or cat.capitalize())[:80], "category": cat, "image_path": image_path})
    if not items:
        raise HTTPException(status_code=422, detail="Non abbiamo trovato capi nella foto. Usa una foto a figura intera del modello.")
    m_doc = await _get_measurements(user.user_id)
    for it in items:
        it["recommended_size"] = recommend_size(m_doc, it["category"])
    return {"items": items}


async def _render_copylook(user_id: str, person_path: str, model_path: str, items: list, m_doc: dict, extra: str = "") -> str:
    sizes = [(i, recommend_size(m_doc, i["category"])) for i in items]
    person_bytes, _ = get_object(person_path)
    model_bytes, _ = get_object(model_path)
    model_bytes = await run_in_threadpool(head_lock.downscale, model_bytes, head_lock.GARMENT_MAX_SIDE)
    garments_txt = "\n".join(f"• {i['name']} ({i['category']}) — size {s} for this person" for i, s in sizes)
    prompt = (
        "Create a photorealistic virtual try-on. IMAGE 1 is a real photo of a specific person — the ONLY person who may appear. "
        "IMAGE 2 shows a fashion model wearing a complete look. Copy ONLY these garments from the model onto the person of IMAGE 1:\n"
        f"{garments_txt}\n\n"
        "ABSOLUTE REQUIREMENTS:\n"
        "• Keep the EXACT face, head, hair, skin tone, body shape, proportions and pose of IMAGE 1. NEVER use the model's body or face.\n"
        "• Keep the ORIGINAL BACKGROUND, lighting and framing of IMAGE 1.\n"
        "• Re-cut each garment to the person's REAL body and size: it must fit like the indicated size would fit this body "
        "(natural drape, length and ease relative to the person's measurements), not like it fits the model.\n"
        "• Preserve colour, pattern, cut and material of each garment exactly as in IMAGE 2.\n"
        "• Garments not listed stay as they are in IMAGE 1. Exactly ONE person in the output.\n\n"
        f"{HANDS_RULE}{head_lock.HEAD_LOCK_RULE}{_measurements_desc(m_doc)}{extra}"
    )
    chat = LlmChat(api_key=EMERGENT_KEY, session_id=f"copylook-apply-{user_id}-{uuid.uuid4().hex[:8]}",
                   system_message="You are a professional fashion virtual try-on generator. Re-dress the SAME person of IMAGE 1, never the model.")
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    canvas_bytes, lock = await run_in_threadpool(head_lock.prepare, person_bytes, any(head_lock.is_long(i["category"], i["name"]) for i in items), await _hand_boxes(person_path, person_bytes))
    msg = UserMessage(text=prompt, file_contents=[ImageContent(base64.b64encode(canvas_bytes).decode()), ImageContent(base64.b64encode(model_bytes).decode())])
    del person_bytes, model_bytes, canvas_bytes
    try:
        _text, images = await chat.send_message_multimodal_response(msg)
    except Exception as e:
        logger.error(f"copylook apply error: {e}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")
    if not images:
        raise HTTPException(status_code=500, detail="No image was generated")
    del msg
    result_path = f"{APP_NAME}/tryon/{user_id}/{uuid.uuid4().hex}.png"
    out_bytes = await run_in_threadpool(head_lock.finalize, base64.b64decode(images[0]['data']), lock)
    del images
    put_object(result_path, out_bytes, "image/png")
    return result_path


@api_router.post("/copylook/apply")
async def copylook_apply(req: CopyLookApplyRequest, user: User = Depends(get_current_user)):
    status = await get_subscription_status(user.account_id)
    if status["is_blocked"]:
        raise HTTPException(status_code=402, detail="Quota exhausted — subscribe or buy an extra try-on.")
    if _path_owner(req.model_path) != user.user_id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    items = [i for i in req.items if i.category in COPYLOOK_CATS]
    if not items:
        raise HTTPException(status_code=400, detail="Seleziona almeno un capo")
    acc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "avatar_path": 1})
    person_path = (acc or {}).get("avatar_path")
    if not person_path:
        raise HTTPException(status_code=400, detail="Crea prima il tuo Avatar nella Home")
    m_doc = await _get_measurements(user.user_id)
    sizes = [(i, recommend_size(m_doc, i.category)) for i in items]
    result_path = await _render_copylook(user.user_id, person_path, req.model_path, [{"name": i.name, "category": i.category} for i in items], m_doc)
    accuracy_snapshot = await _compute_accuracy(user.user_id)
    rec = " · ".join(f"{i.category.capitalize()} {s}" for i, s in sizes)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "person_path": person_path,
        "garment_path": req.model_path,
        "result_path": result_path,
        "garment_name": "Look copiato: " + ", ".join(i.name for i in items)[:120],
        "garment_category": "look",
        "recommended_size": rec,
        "copied_items": [{"name": i.name, "category": i.category, "size": s} for i, s in sizes],
        "fitting_accuracy_at_time": accuracy_snapshot["accuracy"],
        "is_reliable_at_time": accuracy_snapshot["reliable"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tryons.insert_one(doc)
    await consume_tryon_quota(user.account_id, status)
    doc.pop("_id", None)
    return doc


@api_router.post("/copylook/save-garment")
async def copylook_save_garment(req: CopyLookSaveRequest, user: User = Depends(get_current_user)):
    if _path_owner(req.image_path) != user.user_id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    meta = {"product_name": req.name, "brand": "Look copiato", "category": req.category}
    return await _save_garment(user.user_id, None, meta, req.image_path)



@api_router.get("/tryons")
async def list_tryons(user: User = Depends(get_current_user)):
    items = await db.tryons.find({"user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@api_router.get("/tryons/{tryon_id}")
async def get_tryon(tryon_id: str, user: User = Depends(get_current_user)):
    doc = await db.tryons.find_one({"id": tryon_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return {**doc, "retry": _retry_state(doc)}


@api_router.delete("/tryons/{tryon_id}")
async def delete_tryon(tryon_id: str, user: User = Depends(get_current_user)):
    res = await db.tryons.delete_one({"id": tryon_id, "user_id": user.user_id})
    return {"deleted": res.deleted_count}


@api_router.get("/b2b/try-on-log/{user_id}")
async def b2b_try_on_log(user_id: str):
    """B2B evidence log — the proof chain for free-return decisions."""
    items = await db.try_on_log.find({"userId": user_id}, {"_id": 0}).sort("timestamp", -1).to_list(1000)
    return {"userId": user_id, "entries": items}


# ----- Size recommendation standalone -----
@api_router.get("/size/recommend")
async def api_size_recommend(category: str = Query(...), user: User = Depends(get_current_user)):
    m_doc = await _get_measurements(user.user_id)
    return {"category": category, "size": recommend_size(m_doc, category)}


@api_router.get("/")
async def root():
    return {"service": "VFit API", "status": "ok"}


# ----- Product Analyzer (Universal size matcher) -----
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_PAGE_CHAR_LIMIT = 18000


_TRACKING_PARAMS = re.compile(
    r"^(utm_.*|gclid|gclsrc|gbraid|wbraid|dclid|gad_source|gad_campaignid|fbclid|msclkid|yclid|ttclid|srsltid|_gl|mc_cid|mc_eid|"
    r"wmc|opc|mpp|otid|campaign.*|ref_?|tag|affiliate.*|cmp.*)$", re.I)


def _clean_url(url: str) -> str:
    """Final destination URL without ads/tracking parameters (Google Ads redirects, gclid Cj0KCQ…, utm_*, Zalando wmc/opc/mpp)."""
    import html as htmllib
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    url = htmllib.unescape((url or "").strip())
    for _ in range(3):  # unwrap googleadservices / google.com/url / doubleclick redirects
        parts = urlsplit(url)
        q = dict(parse_qsl(parts.query, keep_blank_values=True))
        if re.search(r"(googleadservices|doubleclick|google)\.[a-z.]+$", parts.netloc) and (q.get("adurl") or q.get("url") or q.get("q")):
            url = q.get("adurl") or q.get("url") or q.get("q")
            continue
        break
    parts = urlsplit(url)
    keep = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not _TRACKING_PARAMS.match(k) and not v.startswith("Cj0KCQ")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(keep), ""))


async def _fetch_page(url: str) -> Optional[str]:
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15, headers=headers) as c:
            r = await c.get(url)
            if r.status_code < 400:
                return r.text
    except Exception as e:
        logger.warning(f"fetch failed: {e}")
    # Bot walls (Zalando/Akamai, Cloudflare) reject plain clients: retry with a real browser TLS fingerprint.
    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate="chrome", timeout=20) as s:
            r = await s.get(url, headers={"Accept-Language": headers["Accept-Language"]}, allow_redirects=True)
            return r.text if r.status_code < 400 else None
    except Exception as e:
        logger.warning(f"browser fetch failed: {e}")
        return None


def _structured_meta(html: str) -> dict:
    """Brand/name/price from JSON-LD, product meta tags or embedded price JSON (no LLM, exact numbers)."""
    out = {}
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = pyjson.loads(block.strip())
        except Exception:
            continue
        for node in (data if isinstance(data, list) else data.get("@graph", [data])):
            if not isinstance(node, dict) or node.get("@type") not in ("Product", "ProductGroup"):
                continue
            b = node.get("brand")
            out.setdefault("brand", b.get("name") if isinstance(b, dict) else b)
            out.setdefault("product_name", node.get("name"))
            offers = node.get("offers") or (node.get("hasVariant") or [{}])[0].get("offers") or {}
            offers = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offers, dict):
                p = offers.get("price") or offers.get("lowPrice")
                if p is not None:
                    out.setdefault("price", _parse_price(str(p)))
                    out.setdefault("currency", offers.get("priceCurrency"))
    if out.get("price") is None:
        m = (re.search(r'(?:product|og):price:amount"\s+content="([\d.,]+)"', html)
             or re.search(r'"trackingCurrentAmount"\s*:\s*([\d.]+)', html))
        if m:
            out["price"] = _parse_price(m.group(1))
            c = re.search(r'(?:product|og):price:currency"\s+content="([A-Z]{3})"', html) or re.search(r'"currency(?:Code)?"\s*:\s*"([A-Z]{3})"', html)
            out["currency"] = c.group(1) if c else "EUR"
    if not out.get("brand"):
        m = re.search(r'"brand"\s*:\s*\{[^{}]*"name"\s*:\s*"([^"]+)"', html)
        if m:
            out["brand"] = m.group(1)
    return {k: v for k, v in out.items() if v not in (None, "")}


async def _product_meta(html: str, url: str) -> dict:
    exact = _structured_meta(html)
    llm = await _extract_product_meta(_condense_html(html)[0], url) if not (exact.get("price") and exact.get("brand") and exact.get("product_name")) else {}
    return {**llm, **exact}


def _condense_html(html: str) -> tuple:
    """Returns (condensed_text, product_image_url_or_None)."""
    product_image = None
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Extract product image from og/twitter meta
        for sel, attr in (("meta[property='og:image']", "content"),
                          ("meta[name='twitter:image']", "content"),
                          ("meta[property='product:image']", "content")):
            el = soup.select_one(sel)
            if el and el.get(attr):
                product_image = el[attr]
                break
        for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer"]):
            tag.decompose()
        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{2,}", "\n", text)
        condensed = f"TITLE: {title}\n{text}"
        return condensed[:_PAGE_CHAR_LIMIT], product_image
    except Exception:
        return html[:_PAGE_CHAR_LIMIT], None


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    raw = m.group(0)
    try:
        return pyjson.loads(raw)
    except Exception:
        # Try to clean trailing commas
        cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
        try:
            return pyjson.loads(cleaned)
        except Exception:
            return None


async def _call_llm_for_analysis(page_text: Optional[str], image_b64: Optional[str], measurements: dict, hint_url: str = "") -> dict:
    """
    Ask Gemini to extract a size chart and recommend the best size.
    Returns a dict with keys: ok, needs_screenshot, brand, product_name,
    category, size_chart, fit_notes, recommended_size, confidence, explanation.
    """
    user_m = {k: v for k, v in measurements.items() if v and k in ("chest_cm", "waist_cm", "hips_cm", "height_cm", "weight_kg", "foot_cm", "shoulder_cm", "inseam_cm")}
    prompt = (
        "Sei un esperto di taglie e vestibilità per e-commerce. Analizza la pagina prodotto (o lo screenshot "
        "della tabella taglie) e consiglia la taglia perfetta per questo utente.\n\n"
        f"MISURE UTENTE (cm/kg): {pyjson.dumps(user_m)}\n"
        f"URL fornito: {hint_url}\n\n"
        "ISTRUZIONI:\n"
        "1) Identifica brand, nome prodotto, categoria (top/bottom/dress/outerwear/shoes).\n"
        "2) Estrai la TABELLA TAGLIE con le misure corporee a cui corrisponde ogni taglia (NON le misure del capo).\n"
        "3) Rileva NOTE DI VESTIBILITÀ: 'veste piccolo' / 'veste grande' / 'conforme'.\n"
        "4) Confronta con le misure utente e scegli la taglia perfetta. Se c'è una nota 'veste piccolo' consiglia 1 taglia in più, se 'veste grande' 1 in meno.\n"
        "5) Scrivi una spiegazione breve in ITALIANO, concreta, es: 'Su Zara questo capo veste piccolo, prendi L invece di M'.\n\n"
        "SE NON RIESCI A TROVARE LA TABELLA TAGLIE in modo affidabile, imposta needs_screenshot=true e lascia gli altri campi null.\n\n"
        "RISPOSTA — SOLO JSON, nessun testo attorno:\n"
        "{\n"
        '  "needs_screenshot": false,\n'
        '  "brand": "Zara",\n'
        '  "product_name": "Blazer lino",\n'
        '  "category": "top",\n'
        '  "size_chart": {"S": {"chest_cm":88,"waist_cm":72,"hips_cm":94}, "M": {...}, "L": {...}},\n'
        '  "fit_notes": "runs small",\n'
        '  "recommended_size": "L",\n'
        '  "confidence": 0.86,\n'
        '  "explanation": "Spiegazione in italiano."\n'
        "}\n"
    )

    session_id = f"analyze-{uuid.uuid4().hex[:8]}"
    chat = LlmChat(api_key=EMERGENT_KEY, session_id=session_id, system_message="Sei un assistente taglie professionista. Rispondi SOLO con JSON valido.")
    chat.with_model("gemini", "gemini-3.8-flash")

    files = None
    if image_b64:
        files = [ImageContent(image_b64)]
        text = prompt + "\n\n(La tabella taglie è nell'immagine allegata.)"
    else:
        page = page_text or ""
        text = prompt + "\n\nCONTENUTO PAGINA:\n" + page

    msg = UserMessage(text=text, file_contents=files) if files else UserMessage(text=text)
    try:
        reply = await chat.send_message(msg)
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        return {"ok": False, "needs_screenshot": image_b64 is None, "error": str(e)}

    logger.info(f"LLM raw reply (first 500 chars): {str(reply)[:500]}")
    data = _extract_json(reply) or {}
    if data.get("needs_screenshot"):
        return {"ok": False, "needs_screenshot": True}
    required = ["recommended_size", "explanation"]
    if not all(data.get(k) for k in required):
        logger.warning(f"Missing keys in LLM reply. Got keys={list(data.keys())}")
        return {"ok": False, "needs_screenshot": image_b64 is None, "raw": str(reply)[:200]}
    data["ok"] = True
    data["needs_screenshot"] = False
    _apply_true_size(data, user_m)
    return data


_SIZE_DIMS = {"top": ("chest_cm",), "outerwear": ("chest_cm",), "bottom": ("waist_cm", "hips_cm"), "dress": ("chest_cm", "waist_cm", "hips_cm")}
_SIZE_LABEL = {"chest_cm": "torace", "waist_cm": "vita", "hips_cm": "fianchi"}


def _range(v) -> Optional[tuple]:
    if isinstance(v, (int, float)):
        return (float(v), float(v))
    if isinstance(v, dict):
        lo, hi = v.get("min"), v.get("max")
        return (float(lo), float(hi)) if lo is not None and hi is not None else None
    nums = [float(n) for n in re.findall(r"\d+(?:[.,]\d+)?", str(v).replace(",", "."))]
    return (min(nums), max(nums)) if nums else None


def _apply_true_size(data: dict, user_m: dict) -> None:
    # The LLM only reads the chart; the size is picked deterministically from the user's real measurements.
    dims = [d for d in _SIZE_DIMS.get((data.get("category") or "").lower(), ()) if user_m.get(d)]
    chart = data.get("size_chart") if isinstance(data.get("size_chart"), dict) else {}
    rows = []
    for size, vals in chart.items():
        if not isinstance(vals, dict):
            continue
        r = {d: _range(vals.get(d)) for d in dims}
        if all(r.values()):
            rows.append((size, r))
    if not dims or len(rows) < 2:
        return
    rows.sort(key=lambda x: sum(v[1] for v in x[1].values()))
    idx = next((i for i, (_, r) in enumerate(rows) if all(user_m[d] <= r[d][1] + 1 for d in dims)), len(rows) - 1)
    base = idx
    note = (data.get("fit_notes") or "").lower()
    if any(k in note for k in ("small", "piccol", "stretto", "slim")):
        idx = min(idx + 1, len(rows) - 1)
    elif any(k in note for k in ("large", "grand", "oversize", "abbondant")):
        idx = max(idx - 1, 0)
    size, r = rows[idx]
    if size == data.get("recommended_size"):
        return
    who = ", ".join(f"{_SIZE_LABEL[d]} {round(user_m[d])} cm" for d in dims)
    chart_txt = ", ".join(f"{_SIZE_LABEL[d]} fino a {round(rows[base][1][d][1])} cm" for d in dims)
    extra = "" if idx == base else (" Il capo veste piccolo: ti consigliamo una taglia in più." if idx > base else " Il capo veste grande: ti consigliamo una taglia in meno.")
    data["recommended_size"] = size
    data["explanation"] = f"Le tue misure: {who}. In tabella la {rows[base][0]} arriva a {chart_txt}.{extra} La tua taglia è {size}."


class AnalyzeUrlRequest(BaseModel):
    url: str


_MARKETPLACES = {"amazon", "zalando", "asos", "ebay", "aliexpress", "farfetch", "yoox", "shein", "temu", "amzn"}
_CAT_GROUP = {"top": "sopra", "outerwear": "sopra", "dress": "sopra", "bottom": "sotto", "shoes": "scarpe"}


def _brand_key(url: str = "", brand: Optional[str] = None) -> Optional[str]:
    if brand:
        return re.sub(r"[^a-z0-9]", "", brand.lower()) or None
    host = _host(url) if url and re.match(r"^https?://", url) else ""
    labels = host.split(".")
    # Registrable label: zara.com -> zara, m.zalando.it -> zalando, shop.brand.co.uk -> brand
    if len(labels) >= 3 and labels[-2] in ("co", "com", "org", "net") and len(labels[-1]) == 2:
        labels = labels[:-1]
    return labels[-2] if len(labels) >= 2 else None


async def _remember_chart(user: User, url: Optional[str], result: dict) -> None:
    # Size charts read from the user's screenshot/text are kept per account, by brand + garment group.
    if not result.get("ok") or not result.get("size_chart"):
        return
    key = _brand_key(url or "", result.get("brand")) or _brand_key(url or "")
    if not key:
        return
    group = _CAT_GROUP.get((result.get("category") or "top").lower(), "sopra")
    hosts = {k for k in (_brand_key(url or ""),) if k and k not in _MARKETPLACES}
    await db.saved_size_charts.update_one(
        {"account_id": user.account_id, "brand_key": key, "group": group},
        {"$set": {"brand": result.get("brand") or key.capitalize(), "size_chart": result["size_chart"],
                  "fit_notes": result.get("fit_notes"), "saved_at": datetime.now(timezone.utc).isoformat()},
         "$addToSet": {"host_keys": {"$each": list(hosts)}}},
        upsert=True,
    )


_GROUP_WORDS = {
    "scarpe": ("scarp", "shoe", "sneaker", "stivale", "boot", "sandal", "mocassin", "decollet"),
    "sotto": ("pantalon", "trouser", "jean", "gonna", "skirt", "short", "legging", "bermuda", "pant"),
}


def _group_from_url(url: str) -> str:
    u = url.lower()
    return next((g for g, words in _GROUP_WORDS.items() if any(w in u for w in words)), "sopra")


async def _analyze_with_saved_chart(user: User, url: str, m_doc: dict, category: Optional[str] = None) -> Optional[dict]:
    hk = _brand_key(url)
    if not hk or hk in _MARKETPLACES:
        return None
    group = _CAT_GROUP.get((category or "").lower()) or _group_from_url(url)
    # Charts read from screenshots are shared: the user's own first, otherwise any customer's for this brand.
    q = {"$or": [{"brand_key": hk}, {"host_keys": hk}], "group": group}
    saved = await db.saved_size_charts.find_one({**q, "account_id": user.account_id}, {"_id": 0}, sort=[("saved_at", -1)]) \
        or await db.saved_size_charts.find_one(q, {"_id": 0}, sort=[("saved_at", -1)])
    if not saved:
        return None
    text = (f"URL: {url}\nBRAND: {saved['brand']}\nNOTE VESTIBILITÀ: {saved.get('fit_notes') or 'n/d'}\n\n"
            f"TABELLA TAGLIE SALVATA DAL CLIENTE (JSON):\n{pyjson.dumps(saved['size_chart'], ensure_ascii=False)}")
    result = await _call_llm_for_analysis(text, None, m_doc, hint_url=url)
    if result.get("ok"):
        result["confidence"] = 0.98
        result["saved_chart"] = {"brand": saved["brand"], "group": saved["group"], "saved_at": saved["saved_at"],
                                 "shared": saved.get("account_id") != user.account_id}
    return result


@api_router.post("/product/analyze")
async def product_analyze(req: AnalyzeUrlRequest, user: User = Depends(get_current_user)):
    url = _clean_url(req.url)
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="URL non valido")
    m_doc = await _get_measurements(user.user_id)
    if not _measures_complete(m_doc):
        raise HTTPException(status_code=400, detail=INCOMPLETE_SIZE)
    html = await _fetch_page(url)
    condensed, product_image = _condense_html(html) if html else ("", None)
    result = None
    if len(condensed) < 3000:
        # Blocked or bot page: try the chart saved from the user's screenshot first (1 LLM call).
        result = await _analyze_with_saved_chart(user, url, m_doc)
        if not (result and result.get("ok")):
            result = None
            if not html:
                return {"ok": False, "needs_screenshot": True, "reason": "Il sito ha bloccato la lettura automatica. Incolla la tabella taglie o carica uno screenshot."}
    if result is None:
        result = await _call_llm_for_analysis(condensed, None, m_doc, hint_url=url)
        if not result.get("ok"):
            saved = await _analyze_with_saved_chart(user, url, m_doc, result.get("category"))
            if saved and saved.get("ok"):
                result = saved
    if product_image:
        result["product_image_url"] = product_image
    # Log the analysis for audit / brand reporting
    await db.product_analyses.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "url": url,
        "source": "url",
        "result": result,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return result


class SizeFallbackRequest(BaseModel):
    url: Optional[str] = None
    category: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    product_image_url: Optional[str] = None


_KIND_CATEGORY = {"t-shirt": "top", "felpa": "top", "giacca": "outerwear", "abito": "dress", "pantaloni": "bottom", "cargo": "bottom", "sneakers": "shoes"}


@api_router.post("/product/size-fallback")
async def product_size_fallback(req: SizeFallbackRequest, user: User = Depends(get_current_user)):
    # No brand chart: saved tape measures vs the international average (never above 93%).
    m_doc = await _get_measurements(user.user_id)
    if not _measures_complete(m_doc):
        raise HTTPException(status_code=400, detail=INCOMPLETE_SIZE)
    kind = size_fallback.garment_kind(req.category, " ".join(filter(None, [req.product_name, req.url])))
    r = size_fallback.recommend(m_doc, kind)
    result = {
        "ok": True, "source": "international_average", "recommended_size": r["size"], "confidence": r["confidence"] / 100,
        "explanation": r["explanation"], "details": r["details"], "category": _KIND_CATEGORY[kind], "garment_kind": r["kind_label"],
        "brand": req.brand, "product_name": req.product_name, "product_image_url": req.product_image_url,
    }
    await db.product_analyses.insert_one({
        "id": str(uuid.uuid4()), "user_id": user.user_id, "url": req.url, "source": "international_average",
        "result": dict(result), "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return result


class AnalyzeTextRequest(BaseModel):
    chart_text: str
    url: Optional[str] = None


@api_router.post("/product/analyze-text")
async def product_analyze_text(req: AnalyzeTextRequest, user: User = Depends(get_current_user)):
    m_doc = await _get_measurements(user.user_id)
    if not _measures_complete(m_doc):
        raise HTTPException(status_code=400, detail=INCOMPLETE_SIZE)
    pseudo_text = f"URL: {req.url or 'n/a'}\n\nTABELLA TAGLIE INCOLLATA DAL CLIENTE:\n{req.chart_text}"
    result = await _call_llm_for_analysis(pseudo_text, None, m_doc, hint_url=req.url or "")
    await _remember_chart(user, req.url, result)
    await db.product_analyses.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "url": req.url,
        "source": "pasted-text",
        "result": result,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return result


class ImportImageRequest(BaseModel):
    image_url: str
    category: Optional[str] = None
    name: Optional[str] = None


@api_router.post("/product/import-image")
async def product_import_image(req: ImportImageRequest, user: User = Depends(get_current_user)):
    """Downloads a product image from an external URL and stores it as a garment."""
    url = (req.image_url or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="URL immagine non valido")
    headers = {"User-Agent": _UA, "Accept": "image/*,*/*"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=headers) as c:
            r = await c.get(url)
            r.raise_for_status()
            data = r.content
            content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download immagine fallito: {e}")
    ext_map = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map.get(content_type, "jpg")
    path = f"{APP_NAME}/garment/{user.user_id}/{uuid.uuid4().hex}.{ext}"
    result = put_object(path, data, content_type)
    await db.files.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "kind": "garment",
        "storage_path": result["path"],
        "original_filename": url.rsplit("/", 1)[-1][:80],
        "content_type": content_type,
        "size": result.get("size", 0),
        "source_url": url,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"path": result["path"], "category": req.category, "name": req.name}


# ----- Wardrobe garments (saved from URL) -----
def _parse_price(txt: Optional[str]) -> Optional[float]:
    if not txt:
        return None
    m = re.search(r"(\d{1,4}[.,]?\d{0,2})", str(txt))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None


async def _extract_product_meta(page_text: str, url: str) -> dict:
    prompt = (
        "Analizza il testo di una pagina prodotto e restituisci SOLO JSON con questi campi:\n"
        "{ \"brand\": \"Zara\", \"product_name\": \"Blazer lino\", \"price\": 59.95, \"currency\": \"EUR\", \"category\": \"top|bottom|dress|outerwear|shoes\" }\n"
        "Se un campo non è deducibile metti null. Nessun testo attorno.\n\n"
        f"URL: {url}\n\nCONTENUTO:\n{page_text}"
    )
    chat = LlmChat(api_key=EMERGENT_KEY, session_id=f"meta-{uuid.uuid4().hex[:8]}", system_message="Sei un parser prodotto. Rispondi solo JSON.")
    chat.with_model("gemini", "gemini-3.8-flash")
    try:
        reply = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.warning(f"meta extract failed: {e}")
        return {}
    data = _extract_json(reply) or {}
    if isinstance(data.get("price"), str):
        data["price"] = _parse_price(data["price"])
    return data


class SaveGarmentFromUrlRequest(BaseModel):
    url: str


_AMZ_SHORT_HOSTS = {"amzn.eu", "amzn.to", "a.co", "amzn.com"}
_ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d|exec/obidos/ASIN|product)/([A-Z0-9]{10})(?:[/?#]|$)", re.I)


def _host(url: str) -> str:
    return (httpx.URL(url).host or "").lower().removeprefix("www.")


async def _resolve_short_url(url: str) -> str:
    """Follow redirects hop by hop until we leave the short-link domain."""
    current = url
    headers = {"User-Agent": _UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "it-IT,it;q=0.9"}
    async with httpx.AsyncClient(follow_redirects=False, timeout=15, headers=headers) as c:
        for _ in range(10):
            if _host(current) not in _AMZ_SHORT_HOSTS:
                break
            try:
                r = await c.get(current)
            except Exception as e:
                logger.warning(f"short url resolve failed: {e}")
                break
            loc = r.headers.get("location")
            if not (300 <= r.status_code < 400 and loc):
                break
            current = str(httpx.URL(current).join(loc))
    return current


def _amazon_image(html: str) -> Optional[str]:
    for pat in (r'"hiRes":"(https://[^"]+)"', r'data-old-hires="(https://[^"]+)"', r'"large":"(https://[^"]+)"'):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


async def _download_garment_image(image_url: str, user_id: str) -> str:
    headers = {"User-Agent": _UA, "Accept": "image/*,*/*"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=headers) as c:
        r = await c.get(image_url)
        r.raise_for_status()
    content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(content_type, "jpg")
    img_path = f"{APP_NAME}/garment/{user_id}/{uuid.uuid4().hex}.{ext}"
    put_object(img_path, r.content, content_type)
    return img_path


async def _save_garment(user_id: str, url: str, meta: dict, image_path: Optional[str]) -> dict:
    garment = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "image_path": image_path,
        "is_placeholder": image_path is None,
        "name": meta.get("product_name") or "Capo",
        "brand": meta.get("brand") or "Shop",
        "price": meta.get("price"),
        "currency": meta.get("currency") or "EUR",
        "category": (meta.get("category") or "top").lower(),
        "source_url": url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.garments.insert_one(garment)
    garment.pop("_id", None)
    return garment


@api_router.post("/wardrobe/garments/from-url")
async def wardrobe_save_from_url(req: SaveGarmentFromUrlRequest, user: User = Depends(get_current_user)):
    url = _clean_url(req.url)
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="URL non valido")
    was_short = _host(url) in _AMZ_SHORT_HOSTS
    if was_short:
        url = await _resolve_short_url(url)
    is_amazon = was_short or "amazon." in _host(url)
    if "amazon." in _host(url):
        m = _ASIN_RE.search(httpx.URL(url).path + "/")
        if m:
            url = f"https://{httpx.URL(url).host}/dp/{m.group(1).upper()}"

    html = await _fetch_page(url)
    meta, image_url = {}, None
    if html:
        condensed, image_url = _condense_html(html)
        if is_amazon:
            image_url = image_url or _amazon_image(html)
        meta = await _product_meta(html, url)

    image_path = None
    if image_url:
        try:
            image_path = await _download_garment_image(image_url, user.user_id)
        except Exception as e:
            logger.warning(f"garment image download failed: {e}")

    if is_amazon and (not image_path or not meta.get("product_name")):
        # Amazon often blocks bots: save anyway with a placeholder so the user keeps the link.
        meta = {**meta, "brand": meta.get("brand") or "Amazon", "product_name": meta.get("product_name") or "Prodotto Amazon"}
        return await _save_garment(user.user_id, url, meta, image_path)
    if not html:
        raise HTTPException(status_code=400, detail="Impossibile leggere il link. Carica manualmente il capo nello Studio.")
    if not image_path:
        raise HTTPException(status_code=400, detail="Non siamo riusciti a trovare l'immagine del prodotto.")
    return await _save_garment(user.user_id, url, meta, image_path)


@api_router.get("/wardrobe/garments")
async def wardrobe_list_garments(user: User = Depends(get_current_user)):
    items = await db.garments.find({"user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


class GarmentImageRequest(BaseModel):
    image_path: str


@api_router.put("/wardrobe/garments/{garment_id}/image")
async def wardrobe_set_image(garment_id: str, req: GarmentImageRequest, user: User = Depends(get_current_user)):
    if _path_owner(req.image_path) != user.user_id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    res = await db.garments.update_one(
        {"id": garment_id, "user_id": user.user_id},
        {"$set": {"image_path": req.image_path, "is_placeholder": False}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Capo non trovato")
    return await db.garments.find_one({"id": garment_id}, {"_id": 0})


@api_router.delete("/wardrobe/garments/{garment_id}")
async def wardrobe_delete_garment(garment_id: str, user: User = Depends(get_current_user)):
    res = await db.garments.delete_one({"id": garment_id, "user_id": user.user_id})
    return {"deleted": res.deleted_count}


# ----- Outfit generation (single AI call, layered) -----
_LAYER_ORDER = {"bottom": 1, "dress": 2, "shoes": 2, "top": 3, "outerwear": 4}


class OutfitGenerateRequest(BaseModel):
    garment_ids: List[str]
    person_path: Optional[str] = None


_DEFAULT_LAYER_TEXT = "  1) bottoms / dress 2) shoes 3) top / shirt 4) outerwear / jacket on top."


async def _compose_outfit(user: User, person_path: Optional[str], items: list, layer_order_text: str = _DEFAULT_LAYER_TEXT, extra: str = ""):
    """Layer the given garment images on the user's base photo; returns (person_path, result_path)."""
    # Resolve person photo — prefer explicit path, else latest person file for the user
    if not person_path:
        person_path = (await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "avatar_path": 1}) or {}).get("avatar_path")
    if not person_path:
        last_file = await db.files.find_one(
            {"user_id": user.user_id, "kind": "person", "is_deleted": {"$ne": True}},
            {"_id": 0, "storage_path": 1},
            sort=[("created_at", -1)],
        )
        if last_file:
            person_path = last_file["storage_path"]
    if not person_path:
        raise HTTPException(status_code=400, detail="Crea prima il tuo Avatar nella Home")
    # Build the multi-image prompt
    person_bytes, _ = get_object(person_path)
    canvas_bytes, lock = await run_in_threadpool(head_lock.prepare, person_bytes, any(head_lock.is_long(g.get("category"), g.get("name") or "") for g in items), await _hand_boxes(person_path, person_bytes))
    file_contents = [ImageContent(base64.b64encode(canvas_bytes).decode("utf-8"))]
    del person_bytes, canvas_bytes
    layer_lines = []
    for idx, g in enumerate(items, start=2):
        try:
            g_bytes, _ = get_object(g["image_path"])
        except Exception:
            raise HTTPException(status_code=400, detail=f"Immagine del capo {g.get('name')} non disponibile")
        g_bytes = await run_in_threadpool(head_lock.downscale, g_bytes, head_lock.GARMENT_MAX_SIDE)
        file_contents.append(ImageContent(base64.b64encode(g_bytes).decode("utf-8")))
        del g_bytes
        layer_lines.append(f"IMAGE {idx} — {g.get('category','top')} — {g.get('brand') or ''} {g.get('name') or ''}")

    prompt = (
        "You are a virtual try-on image generator. Produce ONE photorealistic image.\n\n"
        "IMAGE 1 is the real photo of a specific person. Images 2..N are garment product shots.\n"
        f"{chr(10).join(layer_lines)}\n\n"
        "ABSOLUTE RULES — identity and scene preservation have top priority:\n"
        "• Keep the EXACT face, head, hair, skin tone, body proportions and pose from IMAGE 1 — pixel-level fidelity.\n"
        "• Keep every visible tattoo (except on hands), mole, scar, piercing and jewellery EXACTLY as in IMAGE 1.\n"
        "• Keep the shape, pose, fingers and nails of the person's hands as in IMAGE 1 — do NOT substitute hands (hands always tattoo-free).\n"
        "• Keep the ORIGINAL BACKGROUND and lighting of IMAGE 1 unchanged (room, wall, floor, props, shadows).\n"
        "• Framing must match IMAGE 1 — do NOT crop the head, do NOT zoom, keep the same composition.\n"
        "• Exactly ONE person in the output — the same as IMAGE 1. No stock models, no extra people.\n\n"
        "WHAT TO DO:\n"
        "• Dress the SAME person with ALL the garments in images 2..N, layered correctly in this order:\n"
        f"{layer_order_text}\n"
        "• Preserve each garment's exact colour, pattern, cut and material from its product shot.\n"
        "• Natural fabric drape, folds and shadows that match IMAGE 1 lighting.\n\n"
        "FORBIDDEN: altering face/hands, replacing the background with a studio, cropping the head, adding items not provided.\n\n"
        + HANDS_RULE + head_lock.HEAD_LOCK_RULE + extra
    )

    session_id = f"outfit-{user.user_id}-{uuid.uuid4().hex[:8]}"
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=session_id,
        system_message=(
            "Virtual try-on for multi-item outfits. Preserve the person's face, hands, tattoos, pose and background exactly. "
            "Compose all provided garments on the SAME person in a SINGLE image. Hands must always be clean, with no tattoos."
        ),
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    try:
        _text, images = await chat.send_message_multimodal_response(
            UserMessage(text=prompt, file_contents=file_contents)
        )
    except Exception as e:
        logger.error(f"Outfit generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Generazione outfit non riuscita: {e}")
    if not images:
        raise HTTPException(status_code=500, detail="Nessuna immagine generata")
    del file_contents
    out_bytes = await run_in_threadpool(head_lock.finalize, base64.b64decode(images[0]["data"]), lock)
    del images
    result_path = f"{APP_NAME}/outfit/{user.user_id}/{uuid.uuid4().hex}.png"
    put_object(result_path, out_bytes, "image/png")
    return person_path, result_path



@api_router.post("/outfit/generate")
async def outfit_generate(req: OutfitGenerateRequest, user: User = Depends(get_current_user)):
    if not (2 <= len(req.garment_ids) <= 4):
        raise HTTPException(status_code=400, detail="Seleziona da 2 a 4 capi")
    # Subscription quota — 1 outfit = 1 credit, enforced like a normal try-on
    status = await get_subscription_status(user.account_id)
    if status["is_blocked"]:
        raise HTTPException(status_code=402, detail="Quota esaurita — sblocca o attiva un piano")
    # Load garments
    items = []
    for gid in req.garment_ids:
        g = await db.garments.find_one({"id": gid, "user_id": user.user_id}, {"_id": 0})
        if not g:
            raise HTTPException(status_code=404, detail=f"Capo {gid} non trovato")
        if not g.get("image_path"):
            raise HTTPException(status_code=400, detail=f"Serve una foto reale del capo \"{g.get('name')}\" per generare l'outfit")
        items.append(g)
    # Order items for layering (bottoms first, outerwear last)
    items.sort(key=lambda g: _LAYER_ORDER.get((g.get("category") or "top").lower(), 2))
    person_path, result_path = await _compose_outfit(user, req.person_path, items)

    total_price = sum((g.get("price") or 0) for g in items)
    outfit_id = str(uuid.uuid4())
    doc = {
        "id": outfit_id,
        "user_id": user.user_id,
        "person_path": person_path,
        "result_path": result_path,
        "items": [{
            "garment_id": g["id"], "image_path": g["image_path"], "name": g["name"],
            "brand": g["brand"], "price": g.get("price"), "currency": g.get("currency", "EUR"),
            "category": g["category"], "source_url": g.get("source_url"),
        } for g in items],
        "total_price": round(total_price, 2) if total_price else None,
        "currency": items[0].get("currency", "EUR"),
        "saved": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.outfits.insert_one(doc)
    # Consume 1 credit (same as single try-on)
    await consume_tryon_quota(user.account_id, status)
    doc.pop("_id", None)
    return doc


_GRID_SLOTS = {
    "shoes": ("shoes", "Scarpe"),
    "bottom": ("bottom", "Pantaloni / Bottom"),
    "top": ("top", "Maglia / Top"),
    "jacket": ("outerwear", "Giacca"),
}
_GRID_ORDER = ["shoes", "bottom", "top", "jacket"]
_GRID_LAYER_TEXT = "  1) shoes 2) trousers / bottoms 3) top / shirt 4) jacket / outerwear on top."


class GridItem(BaseModel):
    slot: str
    image_path: str


class GridOutfitRequest(BaseModel):
    person_path: Optional[str] = None
    items: List[GridItem]


@api_router.post("/outfit/generate-from-uploads")
async def outfit_generate_from_uploads(req: GridOutfitRequest, user: User = Depends(get_current_user)):
    slots = {i.slot: i.image_path for i in req.items}
    if not (1 <= len(slots) <= 4) or any(k not in _GRID_SLOTS for k in slots):
        raise HTTPException(status_code=400, detail="Carica da 1 a 4 capi")
    for path in [*slots.values(), req.person_path]:
        if path and _path_owner(path) != user.user_id:
            raise HTTPException(status_code=403, detail="Accesso negato")
    status = await get_subscription_status(user.account_id)
    if status["is_blocked"]:
        raise HTTPException(status_code=402, detail="Quota esaurita — sblocca o attiva un piano")
    items = [{
        "slot": k, "image_path": slots[k], "category": _GRID_SLOTS[k][0], "name": _GRID_SLOTS[k][1], "brand": None,
    } for k in _GRID_ORDER if k in slots]
    person_path, result_path = await _compose_outfit(user, req.person_path, items, _GRID_LAYER_TEXT)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "person_path": person_path,
        "result_path": result_path,
        "items": [{
            "garment_id": None, "slot": g["slot"], "image_path": g["image_path"], "name": g["name"], "brand": None,
            "price": None, "currency": "EUR", "category": g["category"], "source_url": None,
        } for g in items],
        "total_price": None,
        "currency": "EUR",
        "saved": False,
        "source": "grid",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.outfits.insert_one(doc)
    await consume_tryon_quota(user.account_id, status)
    doc.pop("_id", None)
    return doc


class GarmentFromScreenshotRequest(BaseModel):
    image_path: str
    url: str
    slot: str
    name: Optional[str] = None
    model_path: Optional[str] = None  # Copia Look: groups the saved garments into one "look completo"


async def _add_to_model_look(user_id: str, model_path: str, garment_id: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    await db.model_looks.update_one(
        {"user_id": user_id, "model_path": model_path},
        {"$addToSet": {"garment_ids": garment_id}, "$set": {"updated_at": now},
         "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
        upsert=True,
    )
    return (await db.model_looks.find_one({"user_id": user_id, "model_path": model_path}, {"_id": 0, "id": 1}))["id"]


class LookFromLinkItem(BaseModel):
    image_path: str
    name: Optional[str] = None
    category: Optional[str] = None


class LookFromLinkRequest(BaseModel):
    model_path: str
    url: str
    items: List[LookFromLinkItem]


_LOOK_CAT = {"top": "top", "bottom": "bottom", "dress": "dress", "outerwear": "outerwear", "shoes": "shoes"}


@api_router.post("/wardrobe/looks/from-link")
async def wardrobe_look_from_link(req: LookFromLinkRequest, user: User = Depends(get_current_user)):
    # One link for the whole model look: the look gets brand/price, every isolated garment inherits the same link.
    paths = [req.model_path] + [i.image_path for i in req.items]
    if any(_path_owner(p) != user.user_id for p in paths):
        raise HTTPException(status_code=403, detail="Accesso negato")
    if not req.items:
        raise HTTPException(status_code=400, detail="Nessun capo da salvare")
    url = _clean_url(req.url)
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="URL non valido")
    if _host(url) in _AMZ_SHORT_HOSTS:
        url = await _resolve_short_url(url)
    meta = {}
    html = await _fetch_page(url)
    if html:
        try:
            meta = await _product_meta(html, url)
        except Exception as e:
            logger.warning(f"look meta failed: {e}")
    host = _host(url)
    brand = meta.get("brand") or ("Amazon" if "amazon." in host else re.sub(r"^www\d?\.", "", host) or "Shop")
    garments = [await _save_garment(user.user_id, url, {"product_name": (i.name or "").strip()[:80] or "Capo", "brand": brand,
                                                         "category": _LOOK_CAT.get((i.category or "").lower(), "top")}, i.image_path)
                for i in req.items]
    now = datetime.now(timezone.utc).isoformat()
    look = {"user_id": user.user_id, "model_path": req.model_path, "url": url, "brand": brand,
            "title": meta.get("product_name") or "Totale Look Modello", "price": meta.get("price"),
            "currency": meta.get("currency") or "EUR", "garment_ids": [g["id"] for g in garments], "updated_at": now}
    await db.model_looks.update_one({"user_id": user.user_id, "model_path": req.model_path},
                                    {"$set": look, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}}, upsert=True)
    doc = await db.model_looks.find_one({"user_id": user.user_id, "model_path": req.model_path}, {"_id": 0})
    return {**doc, "garments": garments, "needs_price": doc.get("price") is None}


class LookPriceRequest(BaseModel):
    price: float = Field(gt=0, lt=100000)


@api_router.put("/wardrobe/looks/{look_id}/price")
async def wardrobe_look_price(look_id: str, req: LookPriceRequest, user: User = Depends(get_current_user)):
    res = await db.model_looks.update_one({"id": look_id, "user_id": user.user_id}, {"$set": {"price": round(req.price, 2), "price_manual": True}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Look non trovato")
    return {"id": look_id, "price": round(req.price, 2)}


@api_router.get("/wardrobe/looks")
async def wardrobe_list_looks(user: User = Depends(get_current_user)):
    looks = await db.model_looks.find({"user_id": user.user_id}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    ids = list({g for lk in looks for g in lk.get("garment_ids", [])})
    by_id = {g["id"]: g for g in await db.garments.find({"id": {"$in": ids}, "user_id": user.user_id}, {"_id": 0}).to_list(2000)}
    out = []
    for lk in looks:
        garments = [by_id[g] for g in lk.get("garment_ids", []) if g in by_id]
        if not garments:
            continue
        priced = [g for g in garments if g.get("price") is not None]
        lk_price = lk.get("price")
        out.append({
            "id": lk["id"], "model_path": lk["model_path"], "created_at": lk["created_at"], "updated_at": lk.get("updated_at"),
            "url": lk.get("url"), "brand": lk.get("brand"), "title": lk.get("title") or "Totale Look Modello",
            "garments": garments, "priced_count": len(garments) if lk_price is not None else len(priced),
            "total": lk_price if lk_price is not None else (round(sum(float(g["price"]) for g in priced), 2) if priced else None),
            "currency": lk.get("currency") or (priced[0].get("currency") if priced else None) or "EUR",
        })
    return out


@api_router.delete("/wardrobe/looks/{look_id}")
async def wardrobe_delete_look(look_id: str, user: User = Depends(get_current_user)):
    # Removes only the grouping: the single garments stay in the wardrobe.
    res = await db.model_looks.delete_one({"id": look_id, "user_id": user.user_id})
    return {"deleted": res.deleted_count}


@api_router.post("/wardrobe/garments/from-screenshot")
async def wardrobe_save_from_screenshot(req: GarmentFromScreenshotRequest, user: User = Depends(get_current_user)):
    slots = {**_GRID_SLOTS, "dress": ("dress", "Abito")}  # dress: garments isolated in Copia Look
    if req.slot not in slots:
        raise HTTPException(status_code=400, detail="Tipo di capo non valido")
    if _path_owner(req.image_path) != user.user_id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    url = _clean_url(req.url)
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="URL non valido")
    if _host(url) in _AMZ_SHORT_HOSTS:
        url = await _resolve_short_url(url)
    meta = {}
    try:
        html = await _fetch_page(url)
        if html:
            meta = await _product_meta(html, url)
    except Exception as e:
        logger.warning(f"screenshot garment meta failed: {e}")
    category, label = slots[req.slot]
    meta = {
        **meta,
        "product_name": meta.get("product_name") or (req.name or "").strip()[:80] or label.split(" / ")[0],
        "brand": meta.get("brand") or ("Amazon" if "amazon." in _host(url) else _host(url) or "Shop"),
        "category": category,
    }
    garment = await _save_garment(user.user_id, url, meta, req.image_path)
    if req.model_path and _path_owner(req.model_path) == user.user_id:
        garment["look_id"] = await _add_to_model_look(user.user_id, req.model_path, garment["id"])
    return garment


@api_router.get("/outfits")
async def outfit_list(user: User = Depends(get_current_user)):
    items = await db.outfits.find({"user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


class OutfitSaveRequest(BaseModel):
    name: Optional[str] = None


@api_router.post("/outfits/{outfit_id}/save")
async def outfit_save(outfit_id: str, req: OutfitSaveRequest, user: User = Depends(get_current_user)):
    await db.outfits.update_one(
        {"id": outfit_id, "user_id": user.user_id},
        {"$set": {"saved": True, "name": req.name}},
    )
    doc = await db.outfits.find_one({"id": outfit_id, "user_id": user.user_id}, {"_id": 0})
    return doc


@api_router.post("/outfits/{outfit_id}/share")
async def outfit_mark_shared(outfit_id: str, user: User = Depends(get_current_user)):
    res = await db.outfits.update_one({"id": outfit_id, "user_id": user.user_id}, {"$set": {"shared": True}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Outfit non trovato")
    return {"shared": True}


@api_router.get("/outfits/share/{outfit_id}")
async def outfit_share_public(outfit_id: str):
    """Public read endpoint used by the share link — returns a redacted snapshot."""
    doc = await db.outfits.find_one({"id": outfit_id, "shared": True}, {"_id": 0, "user_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Outfit non trovato")
    return doc


@api_router.post("/product/analyze-screenshot")
async def product_analyze_screenshot(
    file: UploadFile = File(...),
    url: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
):
    m_doc = await _get_measurements(user.user_id)
    if not _measures_complete(m_doc):
        raise HTTPException(status_code=400, detail=INCOMPLETE_SIZE)
    data = await file.read()
    img_b64 = base64.b64encode(data).decode("utf-8")
    result = await _call_llm_for_analysis(None, img_b64, m_doc, hint_url=url or "")
    await _remember_chart(user, url, result)
    await db.product_analyses.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "url": url,
        "source": "screenshot",
        "result": result,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return result


# ----- Lunghezza abito reale + Riprova gratuita -----
RETRY_REASONS = {
    "sfondo": "\n\nRETRY — the previous result changed the background. CRITICAL: keep the background of IMAGE 1 pixel-identical (same wall, floor, light).",
    "viso": "\n\nRETRY — the previous result changed the face or showed a double face. CRITICAL: exactly ONE face, identical to the person of IMAGE 1 (same face, hair and skin), no blending.",
    "capo": "\n\nRETRY — the previous result showed the wrong garment. CRITICAL: reproduce the garment exactly (colour, pattern, cut, length, material).",
    "mani_viso": "\n\nRETRY — the previous result had deformed hands or a strange/double face. CRITICAL: exactly ONE face identical to the person of IMAGE 1, "
                 "no blending; natural hands with exactly 5 fingers each, in the SAME position and grip as IMAGE 1 (phone held as in IMAGE 1).",
    "altro": "\n\nRETRY — the previous result was not satisfying: be maximally faithful to IMAGE 1 and to the garment.",
}
RETRY_WINDOW_H = 24


class RetryIn(BaseModel):
    reason: str = Field(pattern="^(sfondo|viso|capo|altro|mani_viso)$")


def _retry_state(doc: dict) -> dict:
    created = _parse_dt(doc.get("created_at"))
    expired = not created or datetime.now(timezone.utc) - created > timedelta(hours=RETRY_WINDOW_H)
    return {"available": not doc.get("retry_used") and not expired, "used": bool(doc.get("retry_used")), "expired": expired and not doc.get("retry_used")}


async def _hem_for(coll, doc: dict, image_path: Optional[str], source_url: Optional[str], user_id: str) -> dict:
    info = doc.get("hem_info")
    if info is None:
        if not image_path:
            return {"applicable": False}
        img, _ = get_object(image_path)
        try:
            info = await hem_mod.classify(img, EMERGENT_KEY, _extract_json)
        except Exception as e:
            logger.warning(f"hem classify failed: {e}")
            return {"applicable": False}
        page_len = await hem_mod.length_from_page(source_url) if info["long_garment"] else None
        if page_len:
            info.update({"length_cm": page_len, "length_source": "product"})
        await coll.update_one({"id": doc["id"]}, {"$set": {"hem_info": info}})
    m = await _get_measurements(user_id)
    return hem_mod.compute(info, m.get("height_cm"))


@api_router.get("/tryons/{tryon_id}/hem")
async def tryon_hem(tryon_id: str, user: User = Depends(get_current_user)):
    doc = await db.tryons.find_one({"id": tryon_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Prova non trovata")
    cat = (doc.get("garment_category") or "").lower()
    copied = [i.get("category") for i in doc.get("copied_items") or []]
    if cat not in hem_mod.LONG_CATEGORIES and not head_lock.is_long(cat, doc.get("garment_name") or "") and not any(c in hem_mod.LONG_CATEGORIES for c in copied):
        return {"applicable": False}
    g = await db.garments.find_one({"user_id": user.user_id, "image_path": doc.get("garment_path")}, {"_id": 0, "source_url": 1}) or {}
    return await _hem_for(db.tryons, doc, doc.get("garment_path"), g.get("source_url"), user.user_id)


@api_router.get("/outfits/{outfit_id}/hem")
async def outfit_hem(outfit_id: str, user: User = Depends(get_current_user)):
    doc = await db.outfits.find_one({"id": outfit_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Outfit non trovato")
    long_item = next((i for i in doc.get("items", []) if (i.get("category") or "") in hem_mod.LONG_CATEGORIES or head_lock.is_long(i.get("category"), i.get("name") or "")), None)
    if not long_item:
        return {"applicable": False}
    return await _hem_for(db.outfits, doc, long_item.get("image_path"), long_item.get("source_url"), user.user_id)


async def _log_retry(user: User, kind: str, doc: dict, reason: str, new_path: str):
    now = datetime.now(timezone.utc).isoformat()
    await db.free_retries.insert_one({"id": str(uuid.uuid4()), "user_id": user.user_id, "email": user.email, "kind": kind, "item_id": doc["id"],
                                      "name": doc.get("garment_name") or ", ".join(i.get("name") or "" for i in doc.get("items", []))[:120],
                                      "reason": reason, "previous_result_path": doc.get("result_path"), "result_path": new_path, "created_at": now})
    return {"previous_result_path": doc.get("result_path"), "result_path": new_path, "retry_used": True, "retry_reason": reason, "retried_at": now}


@api_router.get("/tryons/{tryon_id}/retry")
async def tryon_retry_state(tryon_id: str, user: User = Depends(get_current_user)):
    doc = await db.tryons.find_one({"id": tryon_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Prova non trovata")
    return _retry_state(doc)


@api_router.post("/tryons/{tryon_id}/retry")
async def tryon_retry(tryon_id: str, body: RetryIn, user: User = Depends(get_current_user)):
    doc = await db.tryons.find_one({"id": tryon_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Prova non trovata")
    st = _retry_state(doc)
    if not st["available"]:
        raise HTTPException(status_code=409, detail="Riprova gratuita già usata" if st["used"] else "Riprova gratuita scaduta (24 ore)")
    # Lock first so a double click can't produce two free generations.
    lock = await db.tryons.update_one({"id": tryon_id, "retry_used": {"$ne": True}}, {"$set": {"retry_used": True}})
    if not lock.modified_count:
        raise HTTPException(status_code=409, detail="Riprova gratuita già usata")
    m_doc = await _get_measurements(user.user_id)
    extra = RETRY_REASONS[body.reason]
    try:
        if doc.get("garment_category") == "look":
            items = [{"name": i["name"], "category": i["category"]} for i in doc.get("copied_items", [])]
            new_path = await _render_copylook(user.user_id, doc["person_path"], doc["garment_path"], items, m_doc, extra)
        else:
            new_path = await _render_single(user.user_id, doc["person_path"], doc["garment_path"], doc.get("garment_category"), doc.get("garment_name"), m_doc, extra)
    except Exception:
        await db.tryons.update_one({"id": tryon_id}, {"$unset": {"retry_used": ""}})
        raise
    upd = await _log_retry(user, "tryon", doc, body.reason, new_path)
    await db.tryons.update_one({"id": tryon_id}, {"$set": upd})
    return {**doc, **upd}


@api_router.post("/outfits/{outfit_id}/retry")
async def outfit_retry(outfit_id: str, body: RetryIn, user: User = Depends(get_current_user)):
    doc = await db.outfits.find_one({"id": outfit_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Outfit non trovato")
    st = _retry_state(doc)
    if not st["available"]:
        raise HTTPException(status_code=409, detail="Riprova gratuita già usata" if st["used"] else "Riprova gratuita scaduta (24 ore)")
    lock = await db.outfits.update_one({"id": outfit_id, "retry_used": {"$ne": True}}, {"$set": {"retry_used": True}})
    if not lock.modified_count:
        raise HTTPException(status_code=409, detail="Riprova gratuita già usata")
    items = sorted(doc["items"], key=lambda g: _LAYER_ORDER.get((g.get("category") or "top").lower(), 2))
    text = _GRID_LAYER_TEXT if doc.get("source") == "grid" else _DEFAULT_LAYER_TEXT
    try:
        _p, new_path = await _compose_outfit(user, doc["person_path"], items, text, RETRY_REASONS[body.reason])
    except Exception:
        await db.outfits.update_one({"id": outfit_id}, {"$unset": {"retry_used": ""}})
        raise
    upd = await _log_retry(user, "outfit", doc, body.reason, new_path)
    await db.outfits.update_one({"id": outfit_id}, {"$set": upd})
    return {**doc, **upd}


@api_router.get("/admin/free-retries")
async def admin_free_retries(_owner: User = Depends(require_owner)):
    rows = await db.free_retries.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    agg = await db.free_retries.aggregate([{"$group": {"_id": "$reason", "n": {"$sum": 1}}}]).to_list(10)
    return {"counts": {r: 0 for r in RETRY_REASONS} | {a["_id"]: a["n"] for a in agg}, "last": rows}


from support import create_support_router
api_router.include_router(create_support_router(db, get_account_user, require_owner, _extract_json, EMERGENT_KEY))
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
