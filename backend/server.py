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
from body_measure import estimate as estimate_body, estimate_from_height_weight, brand_sizes
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
    if not _is_owner_email(user_doc.get("email")):
        raise HTTPException(status_code=403, detail="prelaunch_owner_only")
    return User(**user_doc)


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
    """Simple size recommendation based on body measurements."""
    if not measurements:
        return "M"
    cat = (category or "").lower()
    if cat == "shoes":
        foot = measurements.get("foot_cm")
        if not foot:
            return "40 EU"
        # Rough EU shoe size from foot length
        eu = round(foot * 1.5 + 2)
        return f"{eu} EU"
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
    if not _is_owner_email(email):
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
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": data.get("name", ""),
            "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
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


class QuickEstimateIn(BaseModel):
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=40, le=150)
    gender: str = Field(pattern="^(female|male)$")


@api_router.post("/profile/quick-estimate")
async def quick_estimate(body: QuickEstimateIn, user: User = Depends(get_current_user)):
    current = await _get_measurements(user.user_id)
    patch = {"height_cm": body.height_cm, "weight_kg": body.weight_kg, "gender": body.gender}
    # Photo or tape measurements are more precise: keep them unless height/sex changed.
    keep = (current.get("method") in ("auto_photo", "tape")
            and abs((current.get("height_cm") or 0) - body.height_cm) < 1
            and abs((current.get("weight_kg") or body.weight_kg) - body.weight_kg) <= 5
            and current.get("gender") == body.gender)
    if not keep:
        est = estimate_from_height_weight(body.height_cm, body.weight_kg, body.gender)
        patch.update({**est, "method": "height_weight", "brand_sizes": brand_sizes(est, body.gender)})
    saved = await _set_measurements(user.user_id, patch, remove=() if keep else ("precision",))
    await _compute_accuracy(user.user_id)
    return {"measurements": saved, "kept_precise": keep}


class FeatureRatios(BaseModel):
    shoulder_r: float = Field(gt=0.05, lt=0.5)
    chest_r: float = Field(gt=0.05, lt=0.5)
    waist_r: float = Field(gt=0.05, lt=0.5)
    hips_r: float = Field(gt=0.05, lt=0.5)
    inseam_r: float = Field(gt=0.3, lt=0.6)


@api_router.post("/profile/auto-measure")
async def auto_measure(
    photo: UploadFile = File(...),
    features: str = Query(...),
    height_cm: Optional[float] = Query(None, ge=120, le=230),
    gender: Optional[str] = Query(None, regex="^(female|male)$"),
    weight_kg: Optional[float] = Query(None, ge=40, le=150),
    forget_weight: bool = Query(False),
    user: User = Depends(get_current_user),
):
    try:
        ratios = FeatureRatios(**pyjson.loads(features)).model_dump()
    except Exception:
        raise HTTPException(status_code=400, detail="Non riusciamo a leggere la tua figura: riprova con una foto intera, frontale, ben illuminata")
    raw = await _read_photo(photo)
    return await _measure_and_save(user, raw, ratios, height_cm, weight_kg, gender, forget_weight, store_photo=True)


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
    return raw


def _clean_jpeg(raw: bytes) -> bytes:
    # Upright orientation, no EXIF (GPS/device), always JPEG.
    from PIL import Image, ImageOps
    import io
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue()


async def _resolve_body_inputs(user: User, height_cm, weight_kg, gender, forget_weight):
    saved_m = await _get_measurements(user.user_id)
    # Missing values fall back to the ones already saved in the profile.
    height_cm = height_cm or saved_m.get("height_cm")
    if not height_cm:
        raise HTTPException(status_code=400, detail="need_height")
    if weight_kg is None and not forget_weight:
        weight_kg = saved_m.get("weight_kg")
    gender = gender or (saved_m.get("gender") if saved_m.get("gender") in ("female", "male") else None)
    return saved_m, height_cm, weight_kg, gender


async def _measure_and_save(user: User, raw: bytes, ratios: dict, height_cm, weight_kg, gender, forget_weight, store_photo: bool):
    saved_m, height_cm, weight_kg, gender = await _resolve_body_inputs(user, height_cm, weight_kg, gender, forget_weight)
    est = estimate_body(ratios, height_cm, weight_kg, gender)
    sizes = brand_sizes(est, gender)
    now = datetime.now(timezone.utc).isoformat()
    if store_photo:
        # The calculation photo is stored encrypted and never served back.
        path = f"{APP_NAME}/measure/{user.user_id}/{uuid.uuid4().hex}.bin"
        put_object(path, FERNET.encrypt(raw), "application/octet-stream")
        await db.files.insert_one({
            "id": str(uuid.uuid4()), "user_id": user.user_id, "kind": "measure", "storage_path": path,
            "encrypted": True, "is_deleted": False, "created_at": now,
        })
    precision = (98 if weight_kg else 85) - (0 if gender else 10)
    new_weight = weight_kg is not None and weight_kg != saved_m.get("weight_kg")
    saved = await _set_measurements(user.user_id, {
        **est, "height_cm": height_cm, "weight_kg": weight_kg, "gender": gender,
        "brand_sizes": sizes, "precision": precision, "method": "auto_photo", "photo_measured_at": now,
    }, now, remove=("weight_kg",) if forget_weight else ())
    if new_weight:
        await db.weight_history.insert_one({
            "id": str(uuid.uuid4()), "user_id": user.user_id, "weight_enc": _enc(weight_kg),
            "note": "Calcolo automatico", "recorded_at": now,
        })
    await _compute_accuracy(user.user_id)
    return {"measurements": saved, "brand_sizes": sizes, "precision": precision}


# ----- Il Mio Avatar: one full-body photo for measurements + try-ons -----
@api_router.get("/profile/avatar")
async def get_avatar(user: User = Depends(get_current_user)):
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0, "avatar_path": 1, "avatar_at": 1, "is_family_profile": 1, "name": 1}) or {}
    return {"path": doc.get("avatar_path"), "created_at": doc.get("avatar_at"),
            "profile_name": doc.get("name") if doc.get("is_family_profile") else None}


@api_router.post("/profile/avatar")
async def set_avatar(
    photo: UploadFile = File(...),
    features: Optional[str] = Query(None),
    height_cm: Optional[float] = Query(None, ge=120, le=230),
    gender: Optional[str] = Query(None, regex="^(female|male)$"),
    weight_kg: Optional[float] = Query(None, ge=40, le=150),
    user: User = Depends(get_current_user),
):
    ratios = None
    if features:
        try:
            ratios = FeatureRatios(**pyjson.loads(features)).model_dump()
        except Exception:
            raise HTTPException(status_code=400, detail="Non riusciamo a leggere la tua figura: riprova con una foto intera, frontale, ben illuminata")
        await _resolve_body_inputs(user, height_cm, weight_kg, gender, False)
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
    out = {"avatar": {"path": path, "created_at": now}}
    if ratios:
        out.update(await _measure_and_save(user, raw, ratios, height_cm, weight_kg, gender, False, store_photo=False))
    return out


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
    return await _get_measurements(user.user_id)


@api_router.put("/profile/measurements")
async def save_measurements(m: Measurements, user: User = Depends(get_current_user)):
    data = m.model_dump(exclude_none=True)
    return await _set_measurements(user.user_id, data, remove=("brand_sizes", "precision", "method"))


# ----- Weight history (check every 2 months) -----
WEIGHT_CHECK_DAYS = 60


class WeightEntry(BaseModel):
    weight_kg: float
    note: Optional[str] = None
    recorded_at: Optional[str] = None


def _weight_status(last_iso: Optional[str]) -> dict:
    if not last_iso:
        return {"last_check_at": None, "next_check_at": None, "days_overdue": 0, "due": True}
    last = datetime.fromisoformat(last_iso)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    nxt = last + timedelta(days=WEIGHT_CHECK_DAYS)
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
    return {"entries": items, "status": _weight_status(last_iso)}


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
    return {"entry": doc, "status": _weight_status(recorded_at)}


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
    days_since_signup = (now - created_at).days
    honeymoon_active = days_since_signup < HONEYMOON_DAYS
    days_left_honeymoon = max(0, HONEYMOON_DAYS - days_since_signup)

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
    origin = req.origin_url.rstrip("/")
    kwargs = dict(
        line_items=[{"price": price.id, "quantity": 1}],
        mode="payment",
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/payment/cancel",
        customer_email=user.email or None,
        metadata={"user_id": user.account_id, "option": req.option},
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
        return
    doc = await db.users.find_one({"user_id": uid}, {"_id": 0, "plan": 1, "plan_expires_at": 1}) or {}
    plan = option.upper()
    cur_exp = _parse_dt(doc.get("plan_expires_at"))
    start = cur_exp if doc.get("plan") == plan and cur_exp and cur_exp > now else now
    await db.users.update_one({"user_id": uid}, {"$set": {
        "plan": plan, "plan_started_at": now.isoformat(),
        "plan_expires_at": (start + timedelta(days=PLAN_DAYS)).isoformat(), "stripe_last_session": session_id,
    }})


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

    missing_core = [f for f in ACCURACY_CORE if not m.get(f)]
    height_missing = not m.get("height_cm")

    accuracy = 100
    accuracy -= 25 * len(missing_core)
    if height_missing:
        accuracy -= 15

    weight_stale = False
    if not m.get("weight_kg"):
        weight_stale = True
        accuracy -= 30
    elif last_weight_update:
        last_dt = datetime.fromisoformat(last_weight_update)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - last_dt).days > WEIGHT_CHECK_DAYS:
            weight_stale = True
            accuracy -= 30

    accuracy = max(0, min(100, accuracy))
    missing_fields = list(missing_core) + (["height_cm"] if height_missing else [])
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
    # Resolve freshness entirely server-side.
    last_weight_doc = await db.weight_history.find_one(
        {"user_id": user.user_id}, {"_id": 0}, sort=[("recorded_at", -1)]
    )
    fresh = False
    last_weight_update = None
    if last_weight_doc:
        last_weight_update = last_weight_doc["recorded_at"]
        last_dt = datetime.fromisoformat(last_weight_update)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        fresh = (datetime.now(timezone.utc) - last_dt).days <= WEIGHT_CHECK_DAYS

    # Proprietary scoring resolution — kept server-side.
    if fresh:
        value, status = 85, "green"
    else:
        value, status = 10, "red"

    reliable = status in ("green", "yellow")
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


HANDS_RULE = (
    "HANDS — STRICT:\n"
    "• Hands, fingers and wrists must be CLEAN natural skin: absolutely NO tattoos, ink, drawings or markings on the hands.\n"
    "• Do NOT propagate, copy or extend neck/arm/body tattoos onto the hands — tattoos stay ONLY where they are in IMAGE 1, never on hands.\n"
    "• NEGATIVE PROMPT: tattoos on hands, ink on fingers, tattoos on wrists, hand tattoos, finger tattoos.\n"
)


# ----- Try-on generation -----
class TryOnRequest(BaseModel):
    person_path: str
    garment_path: str
    garment_name: Optional[str] = None
    garment_category: Optional[str] = None  # top, bottom, dress, shoes, outerwear
    notes: Optional[str] = None
    chosen_size: Optional[str] = None
    garment_id: Optional[str] = None


@api_router.post("/tryon/generate")
async def tryon_generate(req: TryOnRequest, user: User = Depends(get_current_user)):
    # Enforce subscription quota before any paid work (Nano Banana call).
    status = await get_subscription_status(user.account_id)
    if status["is_blocked"]:
        raise HTTPException(status_code=402, detail="Quota exhausted — subscribe or buy an extra try-on.")
    # Load measurements for prompt context
    m_doc = await _get_measurements(user.user_id)
    # Load both images
    person_bytes, person_ct = get_object(req.person_path)
    garment_bytes, garment_ct = get_object(req.garment_path)
    person_b64 = base64.b64encode(person_bytes).decode('utf-8')
    garment_b64 = base64.b64encode(garment_bytes).decode('utf-8')

    measurements_desc = ""
    if m_doc:
        parts = []
        for k, label in [
            ("height_cm", "height"), ("weight_kg", "weight"),
            ("chest_cm", "chest"), ("waist_cm", "waist"), ("hips_cm", "hips"),
            ("shoulder_cm", "shoulders"), ("inseam_cm", "inseam"), ("foot_cm", "foot length"),
        ]:
            v = m_doc.get(k)
            if v:
                unit = "kg" if k == "weight_kg" else "cm"
                parts.append(f"{label} {v}{unit}")
        if parts:
            measurements_desc = " Body measurements of the person: " + ", ".join(parts) + "."

    category = (req.garment_category or "garment").lower()
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
        f"{measurements_desc}"
    )

    session_id = f"tryon-{user.user_id}-{uuid.uuid4().hex[:8]}"
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
    out_bytes = base64.b64decode(img['data'])
    result_path = f"{APP_NAME}/tryon/{user.user_id}/{uuid.uuid4().hex}.png"
    put_object(result_path, out_bytes, "image/png")

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


@api_router.get("/tryons")
async def list_tryons(user: User = Depends(get_current_user)):
    items = await db.tryons.find({"user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@api_router.get("/tryons/{tryon_id}")
async def get_tryon(tryon_id: str, user: User = Depends(get_current_user)):
    doc = await db.tryons.find_one({"id": tryon_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


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


async def _fetch_page(url: str) -> Optional[str]:
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15, headers=headers) as c:
            r = await c.get(url)
            if r.status_code >= 400:
                return None
            return r.text
    except Exception as e:
        logger.warning(f"fetch failed: {e}")
        return None


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
    return data


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
    q = {"account_id": user.account_id, "$or": [{"brand_key": hk}, {"host_keys": hk}], "group": group}
    saved = await db.saved_size_charts.find_one(q, {"_id": 0}, sort=[("saved_at", -1)])
    if not saved:
        return None
    text = (f"URL: {url}\nBRAND: {saved['brand']}\nNOTE VESTIBILITÀ: {saved.get('fit_notes') or 'n/d'}\n\n"
            f"TABELLA TAGLIE SALVATA DAL CLIENTE (JSON):\n{pyjson.dumps(saved['size_chart'], ensure_ascii=False)}")
    result = await _call_llm_for_analysis(text, None, m_doc, hint_url=url)
    if result.get("ok"):
        result["saved_chart"] = {"brand": saved["brand"], "group": saved["group"], "saved_at": saved["saved_at"]}
    return result


@api_router.post("/product/analyze")
async def product_analyze(req: AnalyzeUrlRequest, user: User = Depends(get_current_user)):
    url = (req.url or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="URL non valido")
    m_doc = await _get_measurements(user.user_id)
    if not any(m_doc.get(k) for k in ("chest_cm", "waist_cm", "hips_cm", "height_cm")):
        raise HTTPException(status_code=400, detail="Aggiungi prima almeno torace, vita, fianchi o altezza nel profilo.")
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


class AnalyzeTextRequest(BaseModel):
    chart_text: str
    url: Optional[str] = None


@api_router.post("/product/analyze-text")
async def product_analyze_text(req: AnalyzeTextRequest, user: User = Depends(get_current_user)):
    m_doc = await _get_measurements(user.user_id)
    if not any(m_doc.get(k) for k in ("chest_cm", "waist_cm", "hips_cm", "height_cm")):
        raise HTTPException(status_code=400, detail="Aggiungi prima almeno torace, vita, fianchi o altezza nel profilo.")
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
    url = (req.url or "").strip()
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
        meta = await _extract_product_meta(condensed, url)

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


async def _compose_outfit(user: User, person_path: Optional[str], items: list, layer_order_text: str = _DEFAULT_LAYER_TEXT):
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
    person_b64 = base64.b64encode(person_bytes).decode("utf-8")
    file_contents = [ImageContent(person_b64)]
    layer_lines = []
    for idx, g in enumerate(items, start=2):
        try:
            g_bytes, _ = get_object(g["image_path"])
        except Exception:
            raise HTTPException(status_code=400, detail=f"Immagine del capo {g.get('name')} non disponibile")
        file_contents.append(ImageContent(base64.b64encode(g_bytes).decode("utf-8")))
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
        + HANDS_RULE
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
    out_bytes = base64.b64decode(images[0]["data"])
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


@api_router.post("/wardrobe/garments/from-screenshot")
async def wardrobe_save_from_screenshot(req: GarmentFromScreenshotRequest, user: User = Depends(get_current_user)):
    if req.slot not in _GRID_SLOTS:
        raise HTTPException(status_code=400, detail="Tipo di capo non valido")
    if _path_owner(req.image_path) != user.user_id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    url = (req.url or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="URL non valido")
    if _host(url) in _AMZ_SHORT_HOSTS:
        url = await _resolve_short_url(url)
    meta = {}
    try:
        html = await _fetch_page(url)
        if html:
            meta = await _extract_product_meta(_condense_html(html)[0], url)
    except Exception as e:
        logger.warning(f"screenshot garment meta failed: {e}")
    category, label = _GRID_SLOTS[req.slot]
    meta = {
        **meta,
        "product_name": meta.get("product_name") or label.split(" / ")[0],
        "brand": meta.get("brand") or ("Amazon" if "amazon." in _host(url) else _host(url) or "Shop"),
        "category": category,
    }
    return await _save_garment(user.user_id, url, meta, req.image_path)


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
    if not any(m_doc.get(k) for k in ("chest_cm", "waist_cm", "hips_cm", "height_cm")):
        raise HTTPException(status_code=400, detail="Aggiungi prima almeno torace, vita, fianchi o altezza nel profilo.")
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
