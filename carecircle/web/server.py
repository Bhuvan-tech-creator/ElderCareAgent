"""
web/server.py — FastAPI backend serving the mobile-first UI + JSON API.

Now with USER ACCOUNTS:
  GET  /login              -> login + registration page
  POST /api/register       -> create a personalized account (stores profile)
  POST /api/login          -> authenticate, set signed session cookie
  POST /api/logout         -> clear session
  GET  /                   -> the app (requires login, else redirects to /login)

Authenticated, per-user endpoints:
  POST /api/analyze        -> run care cycle from camera/mic input (Capture)
  GET  /api/dashboard      -> suggestions + weekly calendar (Today)
  POST /api/send-summary   -> dispatch the Telegram notification (Summary)
  GET  /api/profile        -> elder medical profile (History)
  POST /api/profile        -> update the medical profile
  POST /api/guard          -> test the security guard
  GET  /api/health         -> status + rate-limit headroom

Sessions are signed with itsdangerous (SESSION_SECRET).
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer, BadSignature

from ..orchestrator import orchestrator
from ..tools import calendar as calendar_tool
from ..security import guard_input
from ..config import config
from ..ratelimit import api_limiter
from ..scheduler import DailySummaryScheduler
from .. import db, store

BASE = os.path.dirname(__file__)
COOKIE_NAME = "carecircle_session"
_serializer = URLSafeSerializer(config.SESSION_SECRET, salt="carecircle-auth")

# Scheduler auto-sends each user's morning summary to the family group chat.
scheduler = DailySummaryScheduler(send_for_user=lambda u: orchestrator.send_summary(u))


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()           # ensure the users table exists
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="CareCircle", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))


# --- Session helpers --------------------------------------------------------

def _set_session(response: Response, username: str) -> None:
    token = _serializer.dumps({"u": username})
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, samesite="lax", max_age=60 * 60 * 24 * 14,  # 14 days
    )


def _current_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = _serializer.loads(token)
        return data.get("u")
    except BadSignature:
        return None


def _require_user(request: Request) -> str:
    user = _current_user(request)
    if not user or not db.user_exists(user):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# --- Pages ------------------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not _current_user(request):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request})


# --- Auth API ---------------------------------------------------------------

@app.post("/api/register")
async def register(request: Request):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    profile = body.get("profile", {}) or {}

    # Build a fresh record seeded with the user's submitted profile.
    record = db.default_record(elder_name=profile.get("name") or "Your loved one")
    # Overlay submitted profile fields onto the default record.
    record["profile"].update({
        "age": profile.get("age", record["profile"]["age"]),
        "gender": profile.get("gender", record["profile"]["gender"]),
        "weight_kg": profile.get("weight_kg", record["profile"]["weight_kg"]),
        "height_cm": profile.get("height_cm", record["profile"]["height_cm"]),
        "blood_type": profile.get("blood_type", record["profile"]["blood_type"]),
        "allergies": profile.get("allergies", record["profile"]["allergies"]),
        "injuries": profile.get("injuries", record["profile"]["injuries"]),
        "conditions": profile.get("conditions", record["profile"]["conditions"]),
        "history_notes": profile.get("history_notes", record["profile"]["history_notes"]),
        "primary_doctor": profile.get("primary_doctor", record["profile"]["primary_doctor"]),
        "emergency_note": profile.get("emergency_note", record["profile"]["emergency_note"]),
    })
    if profile.get("name"):
        record["elder"]["name"] = profile["name"]
    if profile.get("language"):
        record["elder"]["language"] = profile["language"]

    ok, msg = db.create_user(username, password, record)
    if not ok:
        return JSONResponse({"ok": False, "error": msg}, status_code=400)

    resp = JSONResponse({"ok": True, "message": msg})
    _set_session(resp, username.strip().lower())
    return resp


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    if not db.verify_user(username, password):
        return JSONResponse({"ok": False, "error": "Invalid username or password."}, status_code=401)
    resp = JSONResponse({"ok": True})
    _set_session(resp, username.strip().lower())
    return resp


@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME)
    return resp


# --- App API (per-user) -----------------------------------------------------

@app.post("/api/analyze")
async def analyze(request: Request):
    user = _require_user(request)
    body = await request.json()
    note = body.get("transcript", "")

    # SECURITY: screen the untrusted transcript before agents act on it.
    verdict = guard_input(note)
    safe_note = note if verdict["safe"] else ""

    result = orchestrator.run_care_cycle(user, elder_note=safe_note)
    return JSONResponse({
        "guard": verdict,
        "care_score": result["sage"]["care_score"],
        "band": result["sage"]["band"],
        "explanation": result["sage"]["explanation"],
        "risk_window": result["sage"]["risk_window_72h"],
        "suggestions": result["sage"]["suggestions"],
        "vita": result["vita"],
        "guardian": result["guardian"],
        "message": result["echo"]["message"],
        "weather": result["weather"],
        "telegram_text": result["telegram_text"],
    })


@app.get("/api/dashboard")
async def dashboard(request: Request):
    user = _require_user(request)
    result = orchestrator.run_care_cycle(user)
    return JSONResponse({
        "care_score": result["sage"]["care_score"],
        "band": result["sage"]["band"],
        "suggestions": result["sage"]["suggestions"],
        "calendar": calendar_tool.list_upcoming(7),
    })


@app.post("/api/send-summary")
async def send_summary(request: Request):
    user = _require_user(request)
    body = await request.json()
    result = orchestrator.send_summary(user, elder_note=body.get("transcript", ""))
    return JSONResponse({
        "telegram_text": result["telegram_text"],
        "send": result["telegram_send"],
    })


@app.get("/api/profile")
async def get_profile(request: Request):
    user = _require_user(request)
    data = store.load(user)
    return JSONResponse({
        "elder": data.get("elder", {}),
        "profile": data.get("profile", {}),
        "medications": data.get("medications", []),
        "contacts": data.get("contacts", []),
    })


@app.post("/api/profile")
async def set_profile(request: Request):
    user = _require_user(request)
    body = await request.json()
    updated = store.update_profile(user, body.get("profile", {}))
    return JSONResponse({"ok": True, "profile": updated})


@app.post("/api/guard")
async def guard(request: Request):
    body = await request.json()
    return JSONResponse(guard_input(body.get("text", "")))


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "warnings": config.validate(),
        "rate_limit_remaining": api_limiter.remaining(),
        "daily_summary_enabled": config.ENABLE_DAILY_SUMMARY,
        "daily_summary_time": f"{config.DAILY_SUMMARY_HOUR:02d}:{config.DAILY_SUMMARY_MINUTE:02d}",
    }