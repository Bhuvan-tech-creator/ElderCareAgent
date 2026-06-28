"""
orchestrator.py
---------------
MULTI-AGENT ORCHESTRATOR (ADK root-agent pattern).

The orchestrator owns the four specialized agents and coordinates a full
"care cycle" for a SPECIFIC user: it loads that user's encrypted record,
INTERPRETS the caregiver's free-text note into structured care events,
runs each agent in order (VITA -> SAGE -> GUARDIAN -> ECHO), composes the
final family summary, and dispatches the Telegram notification.

This is the heart of CareCircle's multi-agent system.
"""

from .agents import VitaAgent, EchoAgent, SageAgent, GuardianAgent
from .tools import weather as weather_tool
from .tools import calendar as calendar_tool
from .tools import telegram as telegram_tool
from .llm import chat_json
from . import store


class Orchestrator:
    def __init__(self) -> None:
        self.vita = VitaAgent()
        self.sage = SageAgent()
        self.guardian = GuardianAgent()
        self.echo = EchoAgent()

    # ------------------------------------------------------------------
    # NOTE INTERPRETER
    # Turns the caregiver's free-text note into structured care events so
    # the agents actually RESPOND to what was said. This is why the output
    # now changes with every different note.
    # ------------------------------------------------------------------
    def interpret_note(self, note: str, data: dict) -> dict:
        """
        Returns:
          {
            "meds_taken":   [<medication names from data['medications']>],
            "extra_meds":   [{"name":..., "note":...}],   # off-list / OTC like Advil
            "symptoms":     [str, ...],
            "mood":         "positive|neutral|negative",
            "activity_hint":"more|same|less",
            "sleep_hint":   "better|same|worse",
            "summary":      str
          }
        Falls back to a safe empty interpretation if no note or LLM error.
        """
        empty = {
            "meds_taken": [], "extra_meds": [], "symptoms": [],
            "mood": "neutral", "activity_hint": "same", "sleep_hint": "same",
            "summary": "",
        }
        if not note or not note.strip():
            return empty

        med_names = [m.get("name", "") for m in data.get("medications", [])]
        system = (
            "You are a careful clinical intake parser for an elder-care app. "
            "Read the caregiver's note and extract structured facts. "
            "Only list a medication under 'meds_taken' if its name matches one of the "
            "KNOWN medications provided. Any other medication or OTC drug the caregiver "
            "mentions taking (e.g. Advil, ibuprofen, aspirin, a painkiller) goes under "
            "'extra_meds'. Be literal and do not invent facts."
        )
        user = (
            f"KNOWN medications: {med_names}\n"
            f"Caregiver note: \"{note}\"\n\n"
            "Return ONLY a JSON object with keys: "
            "meds_taken (list of known medication names mentioned as taken), "
            "extra_meds (list of objects {name, note} for any non-listed/OTC meds taken), "
            "symptoms (list of strings), "
            "mood (one of: positive, neutral, negative), "
            "activity_hint (one of: more, same, less), "
            "sleep_hint (one of: better, same, worse), "
            "summary (one short sentence paraphrasing the note)."
        )
        try:
            parsed = chat_json(system, user, temperature=0.1)
        except Exception:
            return empty

        # Normalize / validate against the empty template.
        result = dict(empty)
        if isinstance(parsed, dict) and "_raw" not in parsed:
            # Keep only known meds in meds_taken.
            taken = parsed.get("meds_taken") or []
            result["meds_taken"] = [m for m in taken if m in med_names]
            result["extra_meds"] = parsed.get("extra_meds") or []
            result["symptoms"] = parsed.get("symptoms") or []
            result["mood"] = parsed.get("mood") or "neutral"
            result["activity_hint"] = parsed.get("activity_hint") or "same"
            result["sleep_hint"] = parsed.get("sleep_hint") or "same"
            result["summary"] = parsed.get("summary") or ""
        return result

    @staticmethod
    def _adjust(value: int, hint: str, up: str, down: str, step: int = 12) -> int:
        """Nudge a 0-100 signal up/down based on a qualitative hint."""
        if hint == up:
            value = min(100, value + step)
        elif hint == down:
            value = max(0, value - step)
        return value

    def run_care_cycle(self, username: str, elder_note: str = "") -> dict:
        data = store.load(username)
        culture = data["elder"].get("culture", {})

        # 0) INTERPRET the caregiver note into structured events.
        interp = self.interpret_note(elder_note, data)

        # Merge any newly reported "taken" meds with what's already recorded.
        taken_today = list(dict.fromkeys(
            list(data.get("taken_today", [])) + interp["meds_taken"]
        ))

        # 1) VITA: medication intelligence (now aware of the note's events).
        vita = self.vita.run({
            "medications": data["medications"],
            "taken_today": taken_today,
            "extra_meds": interp["extra_meds"],
            "symptoms": interp["symptoms"],
            "culture": culture,
        })

        # 2) SAGE: feed VITA's adherence + note-derived hints into the CareScore.
        signals = dict(data["signals"])
        signals["adherence_pct"] = vita.output["adherence_pct"]
        signals["activity_score"] = self._adjust(
            signals.get("activity_score", 70), interp["activity_hint"], "more", "less"
        )
        signals["sleep_score"] = self._adjust(
            signals.get("sleep_score", 70), interp["sleep_hint"], "better", "worse"
        )
        # Negative mood / symptoms reduce behavioral consistency confidence.
        if interp["mood"] == "negative" or interp["symptoms"]:
            signals["consistency_score"] = max(0, signals.get("consistency_score", 75) - 10)
        elif interp["mood"] == "positive":
            signals["consistency_score"] = min(100, signals.get("consistency_score", 75) + 6)

        sage = self.sage.run({"signals": signals, "symptoms": interp["symptoms"]})

        # 3) Environmental context via MCP weather tool.
        wx = weather_tool.get_weather()

        # 4) GUARDIAN: escalation decision (symptoms now factored in).
        guardian = self.guardian.run({
            "care_score": sage.output["care_score"],
            "band": sage.output["band"],
            "night_watch": data.get("night_watch", {}),
            "contacts": data["contacts"],
            "weather_risk": wx["risk"],
            "symptoms": interp["symptoms"],
            "extra_meds": interp["extra_meds"],
        })

        # 5) Upcoming calendar (MCP calendar tool).
        upcoming = calendar_tool.list_upcoming(3)
        cal_str = "; ".join(f"{e['title']} ({e['when']})" for e in upcoming) or "Nothing scheduled."

        # 6) ECHO: compose the warm family message (uses the parsed note).
        echo = self.echo.run({
            "facts": {
                "care_score": sage.output["care_score"],
                "band": sage.output["band"],
                "missed_doses": vita.output["missed_doses"],
                "extra_meds": interp["extra_meds"],
                "symptoms": interp["symptoms"],
                "risk_window": sage.output["risk_window_72h"],
                "weather": wx,
                "note_summary": interp["summary"],
            },
            "tone": culture.get("tone", "warm and familiar"),
            "language": data["elder"].get("language", "English"),
            "elder_note": elder_note,
        })

        # 7) Build the structured Telegram summary (matches the design mockup).
        elder_name = data["elder"].get("name", "your loved one")
        extra_note = ""
        if interp["extra_meds"]:
            names = ", ".join(m.get("name", "?") for m in interp["extra_meds"])
            extra_note = f" Extra/OTC reported: {names}."
        summary_payload = {
            "care_score": {"care_score": sage.output["care_score"], "band": sage.output["band"]},
            "medication": f"{vita.output['adherence_pct']}% adherence. "
                          + (f"Missed: {', '.join(vita.output['missed_doses'])}." if vita.output["missed_doses"] else "All doses on track.")
                          + extra_note,
            "activity": f"Activity score {signals.get('activity_score')}/100.",
            "sleep": f"Sleep score {signals.get('sleep_score')}/100.",
            "weather": f"{wx['temp_c']}°C, {wx['condition']}. {wx['risk']}",
            "calendar": cal_str,
            "notes": interp["summary"] or data.get("notes", "—"),
        }
        telegram_text = telegram_tool.format_care_summary(summary_payload, elder_name=elder_name)

        return {
            "interpretation": interp,
            "vita": vita.output,
            "sage": sage.output,
            "guardian": guardian.output,
            "echo": echo.output,
            "weather": wx,
            "calendar": upcoming,
            "telegram_text": telegram_text,
            "summary_payload": summary_payload,
        }

    def send_summary(self, username: str, elder_note: str = "") -> dict:
        result = self.run_care_cycle(username, elder_note)
        send = telegram_tool.send_message(result["telegram_text"])
        result["telegram_send"] = send
        return result


orchestrator = Orchestrator()