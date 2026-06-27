"""
orchestrator.py
---------------
MULTI-AGENT ORCHESTRATOR (ADK root-agent pattern).

The orchestrator owns the four specialized agents and coordinates a full
"care cycle": it gathers signals, runs each agent in the right order
(VITA -> SAGE -> GUARDIAN -> ECHO), composes the final family summary,
and dispatches the Telegram notification.

This is the heart of CareCircle's multi-agent system.
"""

from .agents import VitaAgent, EchoAgent, SageAgent, GuardianAgent
from .tools import weather as weather_tool
from .tools import calendar as calendar_tool
from .tools import telegram as telegram_tool
from . import store


class Orchestrator:
    def __init__(self) -> None:
        self.vita = VitaAgent()
        self.sage = SageAgent()
        self.guardian = GuardianAgent()
        self.echo = EchoAgent()

    def run_care_cycle(self, elder_note: str = "") -> dict:
        data = store.load()
        culture = data["elder"].get("culture", {})

        # 1) VITA: medication intelligence.
        vita = self.vita.run({
            "medications": data["medications"],
            "taken_today": data["taken_today"],
            "culture": culture,
        })

        # 2) SAGE: feed VITA's adherence into the CareScore.
        signals = dict(data["signals"])
        signals["adherence_pct"] = vita.output["adherence_pct"]
        sage = self.sage.run({"signals": signals})

        # 3) Environmental context via MCP weather tool.
        wx = weather_tool.get_weather()

        # 4) GUARDIAN: escalation decision.
        guardian = self.guardian.run({
            "care_score": sage.output["care_score"],
            "band": sage.output["band"],
            "night_watch": data.get("night_watch", {}),
            "contacts": data["contacts"],
            "weather_risk": wx["risk"],
        })

        # 5) Upcoming calendar (MCP calendar tool).
        upcoming = calendar_tool.list_upcoming(3)
        cal_str = "; ".join(f"{e['title']} ({e['when']})" for e in upcoming) or "Nothing scheduled."

        # 6) ECHO: compose the warm family message.
        echo = self.echo.run({
            "facts": {
                "care_score": sage.output["care_score"],
                "band": sage.output["band"],
                "missed_doses": vita.output["missed_doses"],
                "risk_window": sage.output["risk_window_72h"],
                "weather": wx,
            },
            "tone": culture.get("tone", "warm and familiar"),
            "language": data["elder"].get("language", "English"),
            "elder_note": elder_note,
        })

        # 7) Build the structured Telegram summary (matches the design mockup).
        summary_payload = {
            "care_score": {"care_score": sage.output["care_score"], "band": sage.output["band"]},
            "medication": f"{vita.output['adherence_pct']}% adherence. "
                          + (f"Missed: {', '.join(vita.output['missed_doses'])}." if vita.output["missed_doses"] else "All doses on track."),
            "activity": f"Activity score {signals.get('activity_score')}/100.",
            "sleep": f"Sleep score {signals.get('sleep_score')}/100.",
            "weather": f"{wx['temp_c']}°C, {wx['condition']}. {wx['risk']}",
            "calendar": cal_str,
            "notes": data.get("notes", "—"),
        }
        telegram_text = telegram_tool.format_care_summary(summary_payload)

        return {
            "vita": vita.output,
            "sage": sage.output,
            "guardian": guardian.output,
            "echo": echo.output,
            "weather": wx,
            "calendar": upcoming,
            "telegram_text": telegram_text,
            "summary_payload": summary_payload,
        }

    def send_summary(self, elder_note: str = "") -> dict:
        result = self.run_care_cycle(elder_note)
        send = telegram_tool.send_message(result["telegram_text"])
        result["telegram_send"] = send
        return result


orchestrator = Orchestrator()