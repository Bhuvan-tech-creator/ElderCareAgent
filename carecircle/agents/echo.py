"""
echo.py — ECHO: Communication & Translation Agent.

Drafts natural family updates and bridges language gaps between the
elder and caregivers. Adapts tone (formal <-> familiar) per family preference.
"""

from .base import BaseAgent, AgentResult


class EchoAgent(BaseAgent):
    name = "ECHO"
    domain = "communication"
    persona = (
        "You are ECHO, the warm voice of CareCircle. You turn raw care data into "
        "short, reassuring, human messages for family members. You adapt tone "
        "(formal or familiar) and cultural norms. Reply with ONLY the message text — "
        "no preamble, no quotes, no JSON. Keep it under 90 words. Never be alarmist "
        "unless GUARDIAN flags an emergency."
    )

    def _fallback_message(self, facts: dict) -> str:
        """Build a real, fact-based message if the LLM returns nothing."""
        cs = facts.get("care_score", "—")
        band = facts.get("band", "—")
        parts = [f"Today's CareScore is {cs}/100 ({band})."]
        missed = facts.get("missed_doses") or []
        if missed:
            parts.append(f"Still pending: {', '.join(missed)}.")
        else:
            parts.append("All medications are on track.")
        extra = facts.get("extra_meds") or []
        if extra:
            names = ", ".join(m.get("name", "?") for m in extra)
            parts.append(f"An extra/OTC medication was reported: {names} — please keep an eye on this.")
        symptoms = facts.get("symptoms") or []
        if symptoms:
            parts.append(f"Noted symptoms: {', '.join(symptoms)}.")
        if facts.get("note_summary"):
            parts.append(facts["note_summary"])
        return " ".join(parts)

    def run(self, payload: dict) -> AgentResult:
        facts = payload.get("facts", {})
        tone = payload.get("tone", "warm and familiar")
        language = payload.get("language", "English")

        # Screen any free-text note the caregiver dictated (untrusted input).
        note = payload.get("elder_note", "")
        if note:
            safe, reason = self.screened(note)
            if not safe:
                note = "[note withheld by safety guard]"

        user = (
            f"Care facts: {facts}\n"
            f"Caregiver's note: {note}\n"
            f"Write a family update in {language}, tone: {tone}. "
            "Reflect the specific facts above (medications taken/missed, any extra meds, "
            "symptoms, and the score). Keep it under 90 words. Plain text only."
        )
        message = self.think(user, temperature=0.6)

        # Guard against empty / placeholder output -> build from facts instead.
        if (not message
                or "connect groq_api_key" in message.lower()
                or "demo mode" in message.lower()):
            message = self._fallback_message(facts)

        return AgentResult(agent=self.name, output={"message": message})