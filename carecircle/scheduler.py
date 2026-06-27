"""
scheduler.py
------------
Background scheduler that AUTOMATICALLY sends the daily family summary to the
Telegram group chat every morning at a configured time (default 08:00 local).

This is what turns CareCircle from a manual app into an *ambient* one: families
wake up to a calm summary without anyone pressing a button. The manual
"Send to family" button still works for on-demand sends.

Implemented with a lightweight daemon thread (no external scheduler dependency)
so deployment stays simple.
"""

import threading
import time
from datetime import datetime, timedelta
from .config import config


class DailySummaryScheduler:
    def __init__(self, send_callable) -> None:
        """send_callable: a zero-arg function that runs + sends the summary."""
        self._send = send_callable
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_sent_date = None

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
            # Sleep in short chunks so we can stop promptly on shutdown.
            slept = 0.0
            while slept < wait and not self._stop.is_set():
                chunk = min(30.0, wait - slept)
                time.sleep(chunk)
                slept += chunk
            if self._stop.is_set():
                break
            today = datetime.now().date()
            if self._last_sent_date != today:
                try:
                    print(f"[CareCircle] Sending automatic daily summary at {datetime.now():%H:%M}")
                    self._send()
                    self._last_sent_date = today
                except Exception as e:
                    print(f"[CareCircle] Daily summary failed: {e}")

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