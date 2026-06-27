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
        "short, reassuring, human messages for family members. You can translate "
        "between the elder's language and the caregiver's language. You adapt tone "
        "based on the family's preference (formal or familiar) and cultural norms. "
        "Be concise, warm, and never alarmist unless GUARDIAN flags an emergency."
    )

    def run(self, payload: dict) -> AgentResult:
        facts = payload.get("facts", {})
        tone = payload.get("tone", "warm and familiar")
        language = payload.get("language", "English")

        # Screen any free-text note the elder dictated (untrusted input).
        note = payload.get("elder_note", "")
        if note:
            safe, reason = self.screened(note)
            if not safe:
                note = "[note withheld by safety guard]"

        user = (
            f"Care facts: {facts}\n"
            f"Elder's dictated note: {note}\n"
            f"Write a family update in {language}, tone: {tone}. "
            "Keep it under 90 words. Return plain text only."
        )
        message = self.think(user, temperature=0.6)

        return AgentResult(agent=self.name, output={"message": message})