"""
cli.py — AGENT SKILLS / AGENTS CLI (Kaggle key concept).

A command-line interface to operate the CareCircle agent system directly:

  python -m carecircle.cli status         # show CareScore + agent snapshot
  python -m carecircle.cli summary         # run cycle + send Telegram summary
  python -m carecircle.cli night-watch     # run the Night Watch check
  python -m carecircle.cli weather [city]  # query the weather tool
  python -m carecircle.cli guard "<text>"  # test the prompt-injection guard
"""

import sys
import json
from .orchestrator import orchestrator
from .tools import weather as weather_tool
from .security import guard_input
from . import store


def _print(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_status():
    result = orchestrator.run_care_cycle()
    _print({
        "care_score": result["sage"]["care_score"],
        "band": result["sage"]["band"],
        "medication_adherence": result["vita"]["adherence_pct"],
        "escalate": result["guardian"]["escalate"],
        "message": result["echo"]["message"],
    })


def cmd_summary():
    result = orchestrator.send_summary()
    print(result["telegram_text"])
    print("\nTelegram:", result["telegram_send"])


def cmd_night_watch():
    data = store.load()
    nw = data.get("night_watch", {})
    wx = weather_tool.get_weather()
    print("🌙 Night Watch Summary")
    print(f"  Bathroom visits: {nw.get('bathroom_visits')}")
    print(f"  Returned to bed: {nw.get('returned_to_bed')}")
    print(f"  Weather: {wx['temp_c']}°C, {wx['condition']}")
    print(f"  Environmental risk: {wx['risk']}")


def cmd_weather(args):
    city = args[0] if args else None
    _print(weather_tool.get_weather(city))


def cmd_guard(args):
    if not args:
        print("Usage: python -m carecircle.cli guard \"text to screen\"")
        return
    _print(guard_input(" ".join(args)))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, rest = sys.argv[1], sys.argv[2:]
    {
        "status": cmd_status,
        "summary": cmd_summary,
        "night-watch": cmd_night_watch,
        "weather": lambda: cmd_weather(rest),
        "guard": lambda: cmd_guard(rest),
    }.get(cmd, lambda: print(__doc__))()


if __name__ == "__main__":
    main()