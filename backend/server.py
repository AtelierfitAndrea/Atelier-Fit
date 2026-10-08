from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, Depends, Header, Query, Cookie
from fastapi.responses import JSONResponse
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
import re

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# ===== Models =====
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Measurements(BaseModel):
    model_config = ConfigDict(extra="ignore")
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
async def get_current_user(
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
    return User(**user_doc)


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


# ----- Auth routes -----
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
    })
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


@api_router.get("/auth/me")
async def auth_me(user: User = Depends(get_current_user)):
    return user.model_dump()


@api_router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True}


# ----- Profile / Measurements -----
@api_router.get("/profile/measurements")
async def get_measurements(user: User = Depends(get_current_user)):
    doc = await db.measurements.find_one({"user_id": user.user_id}, {"_id": 0, "user_id": 0})
    return doc or {}


@api_router.put("/profile/measurements")
async def save_measurements(m: Measurements, user: User = Depends(get_current_user)):
    data = m.model_dump(exclude_none=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.measurements.update_one(
        {"user_id": user.user_id},
        {"$set": {**data, "user_id": user.user_id}},
        upsert=True,
    )
    return data


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
        "weight_kg": entry.weight_kg,
        "note": entry.note,
        "recorded_at": recorded_at,
    }
    await db.weight_history.insert_one(doc)
    # Keep current measurement in sync for size & avatar
    await db.measurements.update_one(
        {"user_id": user.user_id},
        {"$set": {"user_id": user.user_id, "weight_kg": entry.weight_kg, "updated_at": recorded_at}},
        upsert=True,
    )
    doc.pop("_id", None)
    doc.pop("user_id", None)
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
PLAN_PRICES = {
    "extra": {"amount_cents": 99, "label": "+1 try-on"},
    "single": {"amount_cents": 299, "label": "Single Unlimited"},
    "family": {"amount_cents": 499, "label": "Family Unlimited"},
}


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
async def api_subscription_status(user: User = Depends(get_current_user)):
    return await get_subscription_status(user.user_id)


class CheckoutRequest(BaseModel):
    option: str  # "extra" | "single" | "family"


@api_router.post("/subscription/checkout")
async def api_subscription_checkout(req: CheckoutRequest, user: User = Depends(get_current_user)):
    """Mock Stripe checkout — returns a fake session ID for the frontend to confirm."""
    if req.option not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Invalid option")
    session_id = f"mock_cs_{uuid.uuid4().hex[:16]}"
    await db.stripe_sessions.insert_one({
        "id": session_id,
        "user_id": user.user_id,
        "option": req.option,
        "amount_cents": PLAN_PRICES[req.option]["amount_cents"],
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "session_id": session_id,
        "option": req.option,
        "amount_cents": PLAN_PRICES[req.option]["amount_cents"],
        "mock": True,
    }


class ConfirmRequest(BaseModel):
    session_id: str


@api_router.post("/subscription/confirm")
async def api_subscription_confirm(req: ConfirmRequest, user: User = Depends(get_current_user)):
    """Mock payment success — flips the stored session to paid and applies the plan."""
    sess = await db.stripe_sessions.find_one({"id": req.session_id, "user_id": user.user_id}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if sess["status"] == "paid":
        return await get_subscription_status(user.user_id)
    option = sess["option"]
    now_iso = datetime.now(timezone.utc).isoformat()
    update = {"stripe_last_session": req.session_id, "stripe_last_paid_at": now_iso}
    if option == "extra":
        await db.users.update_one({"user_id": user.user_id}, {"$inc": {"extra_tryon_credits": 1}, "$set": update})
    elif option == "single":
        update["plan"] = "SINGLE"
        update["plan_started_at"] = now_iso
        await db.users.update_one({"user_id": user.user_id}, {"$set": update})
    elif option == "family":
        update["plan"] = "FAMILY"
        update["plan_started_at"] = now_iso
        await db.users.update_one({"user_id": user.user_id}, {"$set": update})
    await db.stripe_sessions.update_one({"id": req.session_id}, {"$set": {"status": "paid", "paid_at": now_iso}})
    return await get_subscription_status(user.user_id)


@api_router.post("/subscription/cancel")
async def api_subscription_cancel(user: User = Depends(get_current_user)):
    """Downgrade back to FREE (demo helper)."""
    await db.users.update_one({"user_id": user.user_id}, {"$set": {"plan": "FREE"}})
    return await get_subscription_status(user.user_id)


# ----- Fitting Accuracy -----
# Formula FASE 2:
#   base 100
#   - 15 if altezza (height_cm) missing
#   - 25 per each missing of torace/vita/fianchi (chest, waist, hips)
#   - 30 if weight > 60 days old OR missing entirely
ACCURACY_CORE = ["chest_cm", "waist_cm", "hips_cm"]


async def _compute_accuracy(user_id: str) -> dict:
    m = await db.measurements.find_one({"user_id": user_id}, {"_id": 0}) or {}
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
    return await _compute_accuracy(user_id)


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
        "weight": data.get("weight"),
    }




# ----- File upload / serve -----
@api_router.post("/upload")
async def upload(kind: str = Query(..., regex="^(person|garment)$"), file: UploadFile = File(...), user: User = Depends(get_current_user)):
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


@api_router.get("/files/{path:path}")
async def files_get(path: str, request: Request):
    # Lightweight: allow any logged-in user to view files they reference.
    # Attempt auth but don't fail hard for images.
    data, content_type = get_object(path)
    return Response(content=data, media_type=content_type)


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
    status = await get_subscription_status(user.user_id)
    if status["is_blocked"]:
        raise HTTPException(status_code=402, detail="Quota exhausted — subscribe or buy an extra try-on.")
    # Load measurements for prompt context
    m_doc = await db.measurements.find_one({"user_id": user.user_id}, {"_id": 0, "user_id": 0}) or {}
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
        f"• Keep every visible tattoo, mole, scar, piercing, jewellery and personal detail EXACTLY as in IMAGE 1.\n"
        f"• Keep the person's hands, fingers and nails IDENTICAL to IMAGE 1 — do NOT substitute with other hands.\n"
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
        f"• Do NOT invent new tattoos, jewellery or accessories that are not in IMAGE 1.\n"
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
    await consume_tryon_quota(user.user_id, status)
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
    m_doc = await db.measurements.find_one({"user_id": user.user_id}, {"_id": 0, "user_id": 0}) or {}
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


@api_router.post("/product/analyze")
async def product_analyze(req: AnalyzeUrlRequest, user: User = Depends(get_current_user)):
    url = (req.url or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(status_code=400, detail="URL non valido")
    m_doc = await db.measurements.find_one({"user_id": user.user_id}, {"_id": 0, "user_id": 0}) or {}
    if not any(m_doc.get(k) for k in ("chest_cm", "waist_cm", "hips_cm", "height_cm")):
        raise HTTPException(status_code=400, detail="Aggiungi prima almeno torace, vita, fianchi o altezza nel profilo.")
    html = await _fetch_page(url)
    if not html:
        return {"ok": False, "needs_screenshot": True, "reason": "Il sito ha bloccato la lettura automatica. Incolla la tabella taglie o carica uno screenshot."}
    condensed, product_image = _condense_html(html)
    result = await _call_llm_for_analysis(condensed, None, m_doc, hint_url=url)
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
    m_doc = await db.measurements.find_one({"user_id": user.user_id}, {"_id": 0, "user_id": 0}) or {}
    if not any(m_doc.get(k) for k in ("chest_cm", "waist_cm", "hips_cm", "height_cm")):
        raise HTTPException(status_code=400, detail="Aggiungi prima almeno torace, vita, fianchi o altezza nel profilo.")
    pseudo_text = f"URL: {req.url or 'n/a'}\n\nTABELLA TAGLIE INCOLLATA DAL CLIENTE:\n{req.chart_text}"
    result = await _call_llm_for_analysis(pseudo_text, None, m_doc, hint_url=req.url or "")
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


@api_router.post("/product/analyze-screenshot")
async def product_analyze_screenshot(
    file: UploadFile = File(...),
    url: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
):
    m_doc = await db.measurements.find_one({"user_id": user.user_id}, {"_id": 0, "user_id": 0}) or {}
    if not any(m_doc.get(k) for k in ("chest_cm", "waist_cm", "hips_cm", "height_cm")):
        raise HTTPException(status_code=400, detail="Aggiungi prima almeno torace, vita, fianchi o altezza nel profilo.")
    data = await file.read()
    img_b64 = base64.b64encode(data).decode("utf-8")
    result = await _call_llm_for_analysis(None, img_b64, m_doc, hint_url=url or "")
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
