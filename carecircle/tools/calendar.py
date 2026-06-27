"""
calendar.py — Lightweight appointment store (stands in for Google Calendar).
The MCP server exposes this so agents can read upcoming events.
In production, swap the body for the Google Calendar API.
"""

from datetime import datetime, timedelta

# Demo seed data; replaced by real data once a user adds events via the UI.
_EVENTS = [
    {"title": "Dr. Mehta — cardiology check-up", "when": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 10:30")},
    {"title": "Refill: Metformin", "when": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d 09:00")},
]


def list_upcoming(limit: int = 5) -> list[dict]:
    return _EVENTS[:limit]


def add_event(title: str, when: str) -> dict:
    ev = {"title": title, "when": when}
    _EVENTS.append(ev)
    return ev