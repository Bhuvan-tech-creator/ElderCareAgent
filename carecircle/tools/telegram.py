"""
telegram.py — Sends the daily Care Summary to the family via Telegram.
If not configured, it prints the message to the console (still works for demos).
"""

import requests
from ..config import config


def send_message(text: str) -> dict:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("\n========== TELEGRAM (console fallback) ==========")
        print(text)
        print("=================================================\n")
        return {"ok": True, "mode": "console"}
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(
            url,
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return {"ok": r.ok, "mode": "telegram", "status": r.status_code}
    except Exception as e:
        print("Telegram send failed:", e)
        return {"ok": False, "error": str(e)}


def format_care_summary(data: dict) -> str:
    """Formats the notification EXACTLY like the uploaded design mockup."""
    cs = data.get("care_score", {})
    return (
        "🏡 <b>CareCircle — Daily Summary</b>\n\n"
        f"<b>Care score:</b> {cs.get('care_score', '—')}/100 ({cs.get('band', '—')})\n\n"
        f"<b>Medication:</b> {data.get('medication', '—')}\n\n"
        f"<b>Activity:</b> {data.get('activity', '—')}\n\n"
        f"<b>Sleep:</b> {data.get('sleep', '—')}\n\n"
        f"<b>Weather today:</b> {data.get('weather', '—')}\n\n"
        f"<b>Upcoming on calendar:</b> {data.get('calendar', '—')}\n\n"
        f"<b>Important notes:</b> {data.get('notes', '—')}"
    )