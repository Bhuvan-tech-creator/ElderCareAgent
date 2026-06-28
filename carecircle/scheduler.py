"""
scheduler.py
------------
Background scheduler that AUTOMATICALLY sends the daily family summary every
morning at a configured time (default 08:00 local) for EVERY registered user.

This is what turns CareCircle from a manual app into an *ambient* one: families
wake up to a calm summary without anyone pressing a button.
"""

import threading
import time
import sqlite3
from datetime import datetime, timedelta
from .config import config
from . import db


class DailySummaryScheduler:
    def __init__(self, send_for_user) -> None:
        """send_for_user: a function taking a username that sends their summary."""
        self._send_for_user = send_for_user
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_sent_date = None

    def _all_usernames(self) -> list[str]:
        try:
            with db._connect() as conn:
                rows = conn.execute("SELECT username FROM users").fetchall()
            return [r["username"] for r in rows]
        except sqlite3.Error:
            return []

    def _seconds_until_next_run(self) -> float:
        now = datetime.now()
        target = now.replace(
            hour=config.DAILY_SUMMARY_HOUR,
            minute=config.DAILY_SUMMARY_MINUTE,
            second=0, microsecond=0,
        )
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    def _loop(self) -> None:
        while not self._stop.is_set():
            wait = self._seconds_until_next_run()
            slept = 0.0
            while slept < wait and not self._stop.is_set():
                chunk = min(30.0, wait - slept)
                time.sleep(chunk)
                slept += chunk
            if self._stop.is_set():
                break
            today = datetime.now().date()
            if self._last_sent_date != today:
                for username in self._all_usernames():
                    try:
                        print(f"[CareCircle] Sending daily summary for '{username}' at {datetime.now():%H:%M}")
                        self._send_for_user(username)
                    except Exception as e:
                        print(f"[CareCircle] Daily summary failed for '{username}': {e}")
                self._last_sent_date = today

    def start(self) -> None:
        if not config.ENABLE_DAILY_SUMMARY:
            print("[CareCircle] Daily summary scheduler is disabled (ENABLE_DAILY_SUMMARY=false).")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="DailySummary")
        self._thread.start()
        print(f"[CareCircle] Daily summary scheduled for "
              f"{config.DAILY_SUMMARY_HOUR:02d}:{config.DAILY_SUMMARY_MINUTE:02d} local time.")

    def stop(self) -> None:
        self._stop.set()