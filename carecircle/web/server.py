"""
web/server.py — FastAPI backend serving the mobile-first UI + JSON API.

Endpoints:
  GET  /                  -> the app (4 swipeable screens)
  POST /api/analyze       -> run care cycle from camera/mic input (Capture)
  GET  /api/dashboard     -> suggestions + weekly calendar (Today)
  POST /api/send-summary  -> dispatch the Telegram notification (Summary)
  GET  /api/profile       -> elder medical profile (History)
  POST /api/profile       -> update the medical profile
  POST /api/guard         -> test the security guard
  GET  /api/health        -> status + rate-limit headroom

Also starts the daily-summary scheduler on startup.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..orchestrator import orchestrator
from ..tools import calendar as calendar_tool
from ..security import guard_input
from ..config import config
from ..ratelimit import api_limiter
from ..scheduler import DailySummaryScheduler
from .. import store

BASE = os.path.dirname(__file__)

# Scheduler that auto-sends the morning summary to the family group chat.
scheduler = DailySummaryScheduler(send_callable=lambda: orchestrator.send_summary())


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="CareCircle", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/analyze")
async def analyze(request: Request):
    """Capture screen: details captured from camera/mic are sent to the agents."""
    body = await request.json()
    note = body.get("transcript", "")

    # SECURITY: screen the untrusted transcript before agents act on it.
    verdict = guard_input(note)
    safe_note = note if verdict["safe"] else ""

    result = orchestrator.run_care_cycle(elder_note=safe_note)
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
async def dashboard():
    """Today screen: daily suggestions + weekly calendar grid."""
    result = orchestrator.run_care_cycle()
    return JSONResponse({
        "care_score": result["sage"]["care_score"],
        "band": result["sage"]["band"],
        "suggestions": result["sage"]["suggestions"],
        "calendar": calendar_tool.list_upcoming(7),
    })


@app.post("/api/send-summary")
async def send_summary(request: Request):
    body = await request.json()
    result = orchestrator.send_summary(elder_note=body.get("transcript", ""))
    return JSONResponse({
        "telegram_text": result["telegram_text"],
        "send": result["telegram_send"],
    })


@app.get("/api/profile")
async def get_profile():
    """History screen: full elder medical profile."""
    data = store.load()
    return JSONResponse({
        "elder": data.get("elder", {}),
        "profile": data.get("profile", {}),
        "medications": data.get("medications", []),
        "contacts": data.get("contacts", []),
    })


@app.post("/api/profile")
async def set_profile(request: Request):
    body = await request.json()
    updated = store.update_profile(body.get("profile", {}))
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